# AosCore benchmarking

meta-aos can build a monitoring stack that measures AosCore's own CPU/RAM footprint (per component and per app
instance) and correlates it against operation events (instance start/stop, component start/stop, custom benchmark
runs). The same stack also measures two other container runtimes on the same unit, Podman and k3s, so the three can be
compared on the same metrics - see [Benchmark Execution (AosCore)](benchmark_execution_aos.md),
[Benchmark Execution (Podman)](benchmark_execution_podman.md) and
[Benchmark Execution (k3s)](benchmark_execution_k3s.md), and the recorded results in
[Benchmark Results](benchmark_results.md). Everything described here is opt-in: it's only installed when
`DISTRO_FEATURES` contains `benchmark`, so a normal build is unaffected.

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
| `process-exporter` | every node | Per-component CPU% and PSS memory, grouped by binary name: AosCore's `component:cm`/`component:sm`/`component:iam`, Podman's `component:podman`/`component:netavark`/`component:aardvark-dns`, and k3s's `component:k3s`/`component:containerd`. App instances are **not** covered here: they run as containers whose workload process cmdline carries no instance ID. `-threads=false` skips the most expensive part of each scrape (per-thread `/proc` iteration), since only group-level metrics are used. |
| `cgroup-exporter` | every node | Per-app-instance CPU/memory. A custom script (`cgroup_exporter.py`), not the third-party `treydock/cgroup_exporter`: that tool's cgroup-path handling truncates to a fixed depth that collapses every AosCore instance to the same label (confirmed against a real target). Reads the same cgroup v2 accounting files (`cpu.stat`, `memory.current`) AosCore's own `launcher::Monitoring` class already reads. Which cgroups it covers is config-driven (`cgroup-exporter.yml`): AosCore's instances, Podman's containers (`libpod-*.scope`), k3s's pod containers (`kubepods.slice`) and the `k3s.service` cgroup, which holds k3s, its containerd and the per-pod shims. |
| `event-exporter` | every node | Tails journald for the given systemd units and pushes lines matching a config-driven regex list (`event-exporter.yml`, by default AosCore's own `[profiling] <text>` checkpoints) to VictoriaMetrics as `checkpoint_event` samples, so Grafana can overlay operation events (instance/component start/stop) on the same graphs as the CPU/RAM series above. |
| `victoria-metrics` | main node only | The time series database: scrapes every node's exporters and accepts pushed samples (`event-exporter`'s checkpoints, and benchmark deployable items' own start/stop events and results) via its `/api/v1/import/prometheus` endpoint. |

Benchmark deployable items themselves (disk I/O, network, or any other custom benchmark container - see
`aos_core_cpp/scripts/monitoring/benchmark_template.py` for a copy-and-adapt starting point) aren't a meta-aos
recipe: they're ordinary AosCore app instances that push their own start/stop events and result values straight to
VictoriaMetrics over the network, the same way `event-exporter` does, so their results land on the same
dashboard/timeline as everything else.

## Container runtimes and benchmark tools

The `benchmark` feature also installs what the Podman and k3s benchmarks and the network and disk I/O tests need, none
of which is started at boot:

| Recipe | Installed on | Purpose |
| --- | --- | --- |
| `podman`, `podman-compose` | main node | The Podman runtime and its compose front end (podman-compose 1.6.0, `recipes-containers/podman-compose`). Podman uses the Netavark network backend (with `aardvark-dns` for DNS on user networks), selected in `recipes-containers/podman`. |
| `k3s`, `k3s-server` | main node | The k3s runtime (`recipes-containers/k3s`), installed as a single node acting as server and agent. Its service is not enabled at boot: a k3s run starts it explicitly, so an idle Kubernetes control plane doesn't skew the AosCore and Podman measurements. Its containerd binary is meta-virtualization's, with the standalone service disabled (`recipes-containers/containerd`): k3s launches the binary itself. |
| `time-event` | main node | `time_event.py`: runs a command and pushes `checkpoint_event` samples bracketing it, used to time the Podman and k3s operations. |
| `iperf3`, `sockperf`, `fio` | every node | The tools the network and disk I/O benchmarks run. `sockperf` is built from the same commit the benchmark's container images use. |
| `benchmark-network` | every node | `iperf3-servers.sh`/`sockperf-servers.sh`, which start the native servers for the "service to unit" network scenarios. |
| `benchmark-target` | every node | `benchmark.target`, which groups the exporters under one systemd target. |

The Aos firewall's default-drop forward chain also has benchmark-only accept rules for the interfaces Podman
(`podman*`) and k3s (`cni0`, `flannel.1`) create, without which containers and pods can't reach each other
(`recipes-aos/aos-nftables`).

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

This pulls `node-exporter`/`process-exporter`/`cgroup-exporter`/`event-exporter` and the benchmark tools into every
node's image and `victoria-metrics`, Podman and k3s into the main node's, and switches `aos-provfirewall` to its
benchmark-variant firewall script (see `recipes-core/images/aos-image.inc`).

The k3s benchmark also needs kernel options the base kernel doesn't have. The `k3s` distro feature makes
meta-virtualization add its kernel configuration fragment for k3s (`kubernetes.scc`), which requires the
`virtualization` feature (not otherwise needed by AosCore, see [AosCore integration](integration.md)). The
`meta-aos-vm` reference build therefore enables `benchmark virtualization k3s` with its `WITH_BENCHMARK` option
(`aos-vm.yaml`), plus a small `benchmark.cfg` for Netavark. This changes the kernel and part of the userland of the
whole image, including for the AosCore runs on it - for example the k3s fragment sets `CONFIG_RT_GROUP_SCHED=y` - so
compare the resulting kernel configuration if the AosCore results have to stay comparable with an image built without
`WITH_BENCHMARK`.

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

Open `http://localhost:3000` (default login `admin`/`admin`) and pick the pre-provisioned "Container Runtime Benchmark"
dashboard - the VictoriaMetrics data source and every panel are already wired up.

Stop it once the session is done:

```bash
docker compose -f docker/grafana/docker-compose.yml down
```

`down` removes the container but keeps the provisioned files (they're bind-mounted from the repo, not stored in a
volume), so nothing needs re-importing on the next `up`. Dashboard edits made through the Grafana UI, though, don't
persist across `down`/`up` - that's expected, since the dashboard is meant to be edited as the checked-in JSON file
(`docker/grafana/dashboards/benchmark.json`), not through the UI.
