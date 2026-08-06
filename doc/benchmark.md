# AosCore benchmarking

meta-aos can build a monitoring stack that measures AosCore's own CPU/RAM footprint (per component and per app
instance) and correlates it against operation events (instance start/stop, component start/stop, custom benchmark
runs). Everything described here is opt-in: it's only installed when `DISTRO_FEATURES` contains `benchmark`, so a
normal build is unaffected.

## Architecture

![AosCore benchmarking architecture](img/benchmark-architecture.png)

VictoriaMetrics only runs on the main node - it scrapes its own node/process/cgroup-exporter over `localhost`, and
every secondary node's exporters over the unit's own network, discovered via `file_sd_configs` pointing at
`targets/secondary-{node,process,cgroup}-exporter.json` (`recipes-support/victoria-metrics/files/`). VictoriaMetrics
re-reads those files on its own, so adding/removing a secondary node doesn't need a restart or a `scrape.yml` edit.
Every series is tagged with a `node` label so Grafana can offer a dropdown to switch between nodes.

Grafana itself is not part of the image - it runs off-target (`docker/grafana/docker-compose.yml`), since running
the dashboard/query UI on the unit under test would itself skew the measurement. The `aos-provfirewall` benchmark
variant (see below) is what lets it reach VictoriaMetrics through the unit's normal lockdown.

## Services and their purpose

| Recipe | Runs on | Purpose |
| --- | --- | --- |
| `node-exporter` | every node | Whole-host CPU/memory. Only the `cpu`/`meminfo` collectors are enabled (`--collector.disable-defaults`) and the exporter's own Go/HTTP self-instrumentation is disabled (`--web.disable-exporter-metrics`) - this is a benchmarking sidecar, so it should cost the host as little overhead as possible. |
| `process-exporter` | every node | Per-AosCore-component CPU% and PSS memory, grouped by binary name (`component:cm`/`component:sm`/`component:iam`). App instances are **not** covered here: they run as crun containers whose workload process cmdline carries no instance ID. `-threads=false` skips the most expensive part of each scrape (per-thread `/proc` iteration), since only group-level metrics are used. |
| `cgroup-exporter` | every node | Per-app-instance CPU/memory. A custom script (`cgroup_exporter.py`), not the third-party `treydock/cgroup_exporter`: that tool's cgroup-path handling truncates to a fixed depth that collapses every AosCore instance to the same label (confirmed against a real target). Reads the same cgroup v2 accounting files (`cpu.stat`, `memory.current`) AosCore's own `launcher::Monitoring` class already reads. |
| `event-exporter` | every node | Tails journald for the given systemd units and pushes lines matching a config-driven regex list (`event-exporter.yml`, by default AosCore's own `[profiling] <text>` checkpoints) to VictoriaMetrics as `checkpoint_event` samples, so Grafana can overlay operation events (instance/component start/stop) on the same graphs as the CPU/RAM series above. |
| `victoria-metrics` | main node only | The time series database: scrapes every node's exporters and accepts pushed samples (`event-exporter`'s checkpoints, and benchmark deployable items' own start/stop events and results) via its `/api/v1/import/prometheus` endpoint. |

Benchmark deployable items themselves (disk I/O, network, or any other custom benchmark container - see
`aos_core_cpp/scripts/monitoring/benchmark_template.py` for a copy-and-adapt starting point) aren't a meta-aos
recipe: they're ordinary AosCore app instances that push their own start/stop events and result values straight to
VictoriaMetrics over the network, the same way `event-exporter` does, so their results land on the same
dashboard/timeline as everything else.

## Port map

| Port | Bound to | Service | Reachable from |
| --- | --- | --- | --- |
| 9100 | `0.0.0.0` | `node-exporter` | VictoriaMetrics (localhost on the main node, over the network from secondary nodes) |
| 9256 | `0.0.0.0` | `process-exporter` | VictoriaMetrics (same as above) |
| 9400 | `0.0.0.0` | `cgroup-exporter` | VictoriaMetrics (same as above) |
| 8428 | `0.0.0.0` | `victoria-metrics` (main node only) | Every node's exporters (scrape), every node's `event-exporter`/benchmark items (push), and Grafana on the bench host (query - opened through the gateway by the `aos-provfirewall` benchmark variant) |
| 3000 | bench host only, not part of the image | Grafana | Whoever's viewing the dashboard |

`event-exporter` has no listening port: it only ever initiates outbound pushes to VictoriaMetrics.

## Enabling

```bash
DISTRO_FEATURES:append = " benchmark"
```

This pulls `node-exporter`/`process-exporter`/`cgroup-exporter`/`event-exporter` into every node's image and
`victoria-metrics` into the main node's, and switches `aos-provfirewall` to its benchmark-variant firewall script
(see `recipes-core/images/aos-image.inc`).

## Running Grafana

Grafana runs on the bench host, not on the unit under test - start it once, point it at the main node, and leave it
running for the length of a benchmark session.

Start it:

```bash
docker compose -f docker/grafana/docker-compose.yml up -d
```

Point it at the real main node before the first run: edit `url` in
`docker/grafana/docker-compose.yml`'s sibling file, `docker/grafana/provisioning/datasources/victoriametrics.yml`
(it ships with a `<main-node-address>` placeholder). Changing it later needs a restart to take effect, since
Grafana only re-reads a provisioned data source on startup:

```bash
docker compose -f docker/grafana/docker-compose.yml restart
```

Open `http://localhost:3000` (default login `admin`/`admin`) and pick the pre-provisioned "AosCore Benchmark"
dashboard - the VictoriaMetrics data source and every panel are already wired up.

Stop it once the session is done:

```bash
docker compose -f docker/grafana/docker-compose.yml down
```

`down` removes the container but keeps the provisioned files (they're bind-mounted from the repo, not stored in a
volume), so nothing needs re-importing on the next `up`. Dashboard edits made through the Grafana UI, though, don't
persist across `down`/`up` - that's expected, since the dashboard is meant to be edited as the checked-in JSON file
(`docker/grafana/dashboards/aos-benchmark.json`), not through the UI.
