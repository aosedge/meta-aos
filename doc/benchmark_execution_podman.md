# Benchmark Execution (Podman)

## Goal

This document records the execution procedure for the Podman benchmark - the same benchmark plan as
[Benchmark Execution (AosCore)](benchmark_execution_aos.md), run against plain Podman containers instead of
through AosCore's deployment pipeline, so the two container runtimes can be compared on the same metrics.

* For each benchmark chapter, it specifies the test environment and any deviation from the plan required for that
  test, so runs are reproducible and comparable across releases and against the AosCore results.
* The resulting measurements themselves are recorded in [Benchmark Results](benchmark_results.md), alongside the
  AosCore figures for direct comparison.
* Tests are deployed directly with `podman`/`podman-compose` (see each benchmark's `podman/` folder in
  [demo-services](https://github.com/aosedge/demo-services/tree/main/benchmark)), not through AosCore's
  aos-signer/cloud/subject pipeline; where a chapter has no meaningful Podman equivalent (e.g. it measures an
  AosCore-internal component), that is noted instead of forced into a fit.
* Metrics are collected via the same VictoriaMetrics/Grafana stack the AosCore benchmark uses - `cgroup-exporter`
  and the dashboard are both runtime-agnostic (see [meta-aos benchmark instrumentation](benchmark.md)), so the
  same panels show either runtime's data.
* Test results are collected and analyzed via Grafana dashboards. The dashboard definition is
  [benchmark.json](../docker/grafana/dashboards/benchmark.json); importing it reproduces every panel
  referenced below.
* Every chapter records its full execution steps, regardless of whether they match the benchmark plan. Where
  execution deviates from the plan (e.g. a different tool, parameter, or execution order), the deviation and its
  rationale are recorded alongside that chapter's results.

## Disclaimer

The following are not covered in this document, as they are generic information and procedures:

* generic explanation of Podman/OCI container concepts and terminology.

**podman-compose version**: the unit runs podman-compose 1.6.0 (`meta-aos/recipes-containers/podman-compose`), which
pulls every service's image concurrently (`asyncio.gather` over one pull task per distinct image). Every chapter here
deploys via `podman-compose up`, so this shapes every measurement that involves pulling more than one image, not
just Operational Speed.

podman-compose 1.6.0 only honors `deploy.replicas` when `deploy.mode: replicated` is set alongside it - every
compose template here sets both.

## Prerequisites

### Environment variables

The following environment variables should be set before running any benchmarks in console sessions on the build/push
host:

```bash
export REGISTRY_HOST=<registry-host>:5000
export UNIT_HOST=<unit-host>
```

On the unit under test:

```bash
export REGISTRY_HOST=<registry-host>:5000
```

### Item and instance counts

The `create_services.py` steps of every chapter take the number of items and the number of instances per item as
variables: `NUM_SERVICES` is passed as `--num-services` and `NUM_INSTANCES` as `--num-instances`. Set them in the
console session on the build/push host before the render step, and change them for each tier as the chapter's last
step says (each chapter uses the ones it needs):

```bash
export NUM_SERVICES=1
export NUM_INSTANCES=1
```

The bandwidth and latency chapters scale their clients with `NUM_SERVICES` (see their "scaling clients" deviation), and
the `-n` of the native `iperf3-servers.sh` and `sockperf-servers.sh` takes that same client count, so set
`NUM_SERVICES` in the session on the unit or the external host that runs them as well.

### Unit provisioning

The unit under test is provisioned the same way [Benchmark Execution (AosCore)](benchmark_execution_aos.md)
requires (`aos-prov provision -u <NODE_IP>`), even though this document never deploys anything through
AosCore's own pipeline:
provisioning is what actually creates the LUKS-encrypted `aos` volume group on disk, not anything AosCore-specific
that runs afterward. `benchmark-diskio`'s compose file bind-mounts two paths straight from that provisioned
layout - `/var/aos/storages` (encrypted) and `/var/aos/common-data` (unencrypted) - so without provisioning first,
those paths don't exist yet and diskio's "Container disk I/O" chapter has nothing to bind-mount.

### AosCore

AosCore is stopped for the whole benchmark run, after the unit is provisioned. Its services (`aos-cm`, `aos-sm`,
`aos-iam`, ...) would otherwise compete with the runtime under test for CPU and RAM and add their own components to
the "orchestrator components" measurements. On the unit:

```bash
systemctl stop aos.target
```

This stops only the Aos services: the Aos firewall (`aos-nftables.service`), the metric exporters and VictoriaMetrics
keep running. Once all tests are done, start it again:

```bash
systemctl start aos.target
```

### Container network

The unit's Podman uses the Netavark backend (aardvark-dns built in). Every compose file in this document attaches
to one shared network named `benchmark`, which has to be created once on the unit with DNS enabled - the
built-in `podman` network never has DNS, so containers on it can't resolve each other's service names:

```bash
podman network create --disable-dns=false benchmark
```

Podman's bridges (`podman*`) are allowed through the Aos firewall's default-drop forward chain by the image itself
when built with the `benchmark` `DISTRO_FEATURES` - without that, containers couldn't reach each other even by IP.

### Container registry

A local container registry is up and running, reachable from the unit under test. Every benchmark image is
pulled from it, so a scenario's "Download"-type metric always measures a real network transfer rather than a
`podman load` from a local tarball (a `podman load` is a disk copy, not a network transfer, and can't stand in
for one):

```bash
docker compose -f docker/registry/docker-compose.yml up -d
```

It's plain HTTP, so Podman/Docker otherwise refuse the connection instead of falling back from HTTPS
(`pinging container registry <host>:5000: ... http: server gave HTTP response to HTTPS client`). Two different hosts
talk to it, and each needs a different fix:

* **The build/push host** (see "Container images" below) runs standalone `podman build`/`push` commands, so
  `--tls-verify=false` on each one is enough - no host-wide trust needed there.
* **The unit** deploys every scenario with `podman-compose up`/`start`, which does its own pulling internally and
  has no equivalent flag to pass that pull - every chapter in this document uses compose files, so this isn't a
  one-off. The unit needs the registry trusted host-wide instead. Its rootfs is read-only by default, so remount
  it read-write first:

  ```bash
  mount -o remount,rw /
  ```

  Then add the registry to the `registries` list under `[registries.insecure]` in
  `/etc/containers/registries.conf`:

  ```toml
  [registries.insecure]
  registries = ["<registry-host>"]
  ```

### Grafana

Grafana is up and running on a Linux host, pointed at the main node under test (see
[Running Grafana](benchmark.md#running-grafana)) - the same host used for the local registry above can host it.
Before the first run, set the unit's actual IP address as `url` in
[docker/grafana/provisioning/datasources/victoriametrics.yml](../docker/grafana/provisioning/datasources/victoriametrics.yml)
(it ships with a placeholder address); changing it later needs a Grafana restart to take effect, since a
provisioned data source is only re-read on startup:

```bash
docker compose -f docker/grafana/docker-compose.yml up -d
```

### Container images

Every benchmark image is built and pushed to the registry above before a run - `podman pull` needs a real remote
tag to fetch, and a scenario's own execution steps only ever `podman-compose up`/`start` an already-pushed image,
never build one on the fly. Every `cd benchmark/...` path below is relative to a checkout of
[demo-services](https://github.com/aosedge/demo-services/tree/main/benchmark) on the build/push host - rendering
and deploying the resulting `compose.yaml` on the unit itself is each chapter's own concern (see its own
execution steps: `podman-compose` needs to run where the containers do, but the `compose.yaml` it reads is the
only thing that has to physically be on the unit, not this whole checkout). Podman must be installed on whichever
host runs the commands below - unlike the unit under test, that host isn't necessarily built with the `benchmark`
`DISTRO_FEATURES`, so Podman isn't there by default.

#### Operational Speed

16 `benchmark-timing-1` .. `benchmark-timing-16` images, each with its own independently-random 16 MiB payload.

`--build-arg SERVICE_ID=<N>` must differ across the 16 builds even though nothing in `compose.yaml` reads it:
Podman/Docker's layer cache otherwise reuses the first build's `dd` layer verbatim for every later one with the
same `SIZE_MB`, silently giving every image byte-identical "unique" payload data instead of independently-random
ones:

```bash
cd benchmark/timing
for i in $(seq 1 16); do
  podman build -f podman/Containerfile --build-arg SIZE_MB=16 --build-arg SERVICE_ID=${i} \
      -t ${REGISTRY_HOST}/benchmark-timing-${i}:latest .
  podman push --tls-verify=false ${REGISTRY_HOST}/benchmark-timing-${i}:latest
done
```

#### Container disk I/O

A single `benchmark-diskio` image - no per-build uniqueness concern, since its payload is generated at runtime by
`fio`, not baked into the image:

```bash
cd benchmark/diskio
podman build -f podman/Containerfile -t ${REGISTRY_HOST}/benchmark-diskio:latest .
podman push --tls-verify=false ${REGISTRY_HOST}/benchmark-diskio:latest
```

#### Network

Six images, a server/peer and a client per scenario - each pair has its own `podman/Containerfile.server`/
`Containerfile.client` (`Containerfile.peer` for DNS) in its benchmark's folder, since a single Containerfile
can't produce two different images:

The two latency images compile `sockperf` from source (a pinned commit cloned from GitHub, see the Latency
chapter), so building them needs internet access on the build/push host and takes noticeably longer than the rest.

```bash
cd benchmark/network/bandwidth
podman build -f podman/Containerfile.server -t ${REGISTRY_HOST}/benchmark-network-bandwidth-server:latest .
podman build -f podman/Containerfile.client -t ${REGISTRY_HOST}/benchmark-network-bandwidth-client:latest .
podman push --tls-verify=false ${REGISTRY_HOST}/benchmark-network-bandwidth-server:latest
podman push --tls-verify=false ${REGISTRY_HOST}/benchmark-network-bandwidth-client:latest

cd ../latency
podman build -f podman/Containerfile.server -t ${REGISTRY_HOST}/benchmark-network-latency-server:latest .
podman build -f podman/Containerfile.client -t ${REGISTRY_HOST}/benchmark-network-latency-client:latest .
podman push --tls-verify=false ${REGISTRY_HOST}/benchmark-network-latency-server:latest
podman push --tls-verify=false ${REGISTRY_HOST}/benchmark-network-latency-client:latest

cd ../dns
podman build -f podman/Containerfile.peer -t ${REGISTRY_HOST}/benchmark-network-dns-peer:latest .
podman build -f podman/Containerfile.client -t ${REGISTRY_HOST}/benchmark-network-dns-client:latest .
podman push --tls-verify=false ${REGISTRY_HOST}/benchmark-network-dns-peer:latest
podman push --tls-verify=false ${REGISTRY_HOST}/benchmark-network-dns-client:latest
```

No deviation from the AosCore version in the "service to service" path (server/peer reached by its compose service
name over Podman's own network DNS): `iperf3`'s `-c`, `dns_client.py`'s own resolver and the latency images'
`sockperf` (built from the same commit AosCore uses) all handle a DNS name the same as a real hostname.

## Cleanup

Once a session's images are pushed, remove them from the host they were built on - they're only needed locally
long enough to `podman push`, and 16 timing images plus diskio/network ones add up. The registry host must be
part of the filter, not just `benchmark-*`: a `*` in `--filter reference=` doesn't cross the `/` between it and
the image name (`*benchmark-*` alone only ever matches a bare, no-prefix local tag, never the
registry-qualified ones this doc's build commands actually produce):

```bash
podman rmi -f $(podman images -q --filter reference="${REGISTRY_HOST}/benchmark-*")
```

## Troubleshooting

See [Benchmark Execution (AosCore)](benchmark_execution_aos.md#troubleshooting) - nothing here is Podman-specific,
since VictoriaMetrics/Grafana are the same instance/stack either way.

## Result aggregation

See [Benchmark Execution (AosCore)](benchmark_execution_aos.md#result-aggregation) - the mean-across-instances
convention applies unchanged, since both versions push the exact same `checkpoint_event`/`benchmark_result`
shape to the same VictoriaMetrics.

## Repetition

See [Benchmark Execution (AosCore)](benchmark_execution_aos.md#repetition) - the one-run-per-configuration policy
applies unchanged.

## Operational Speed

### Install new deployable items

Goal: measure the different operational time intervals during deploying new deployable items to the unit - same
goal as the AosCore version, adapted to what Podman actually exposes as separately observable phases.

Deployable item: `benchmark-timing-1` .. `benchmark-timing-16`, 16 separate images each with its own
independently-random 16 MiB payload (see "Container images" above) - the same N-separate-items shape the AosCore
version uses (not instance-count scaling of one item), so a batch's total deployment size scales with item count
the same way (16/128/256 MiB at 1/8/16 items). See the Disclaimer's podman-compose version note - "Total" below
is dominated by the pull step for a cold N-item batch, so it's especially sensitive to it.

Metrics:

* **Total** - time from issuing the deploy command until every item's own instance has started. This is the only
  metric measured: AosCore's Download/Install/Prepare/Network breakdown has no Podman equivalent -
  `podman-compose up` has no internal phase boundaries to checkpoint the way `aos-sm.service` does, so pulling,
  unpacking, preparing, networking, and starting an item all happen inside one opaque call.

Checkpoint/timing used to measure it:

| Metric | Measured as |
| --- | --- |
| Total | `time_event.py` wrapping `podman-compose up -d` (which pulls every item's image itself, same as AosCore's own deploy step would), cross-checked against the max (latest) per-item `checkpoint_event(event="Start")` timestamp (`source="Instance: timing-<container-id>"`) - the same per-instance checkpoint the AosCore version's own "Total"/"Start" rows use |

Execution steps:

1. With no containers running, capture the idle CPU/RAM used by the orchestrator components (see "CPU/RAM used
   by orchestrator components" below) - Podman has no daemon of its own, so at idle the `podman` component shows
   near zero.
2. Set up working directories, once for this whole test - not repeated per tier, since steps 3-9 below all stay
   inside them. On the build/push host:

   ```bash
   cd benchmark/timing/podman
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/timing
   cd ~/benchmark/timing
   ```

3. Render `compose.yaml` for `NUM_SERVICES` items on the build/push host (1, then 8, then 16 per step 10 - each tier is
   a fresh, independent batch of `NUM_SERVICES` items, not additive on top of the previous tier's, matching the AosCore
   version's own per-tier `--version` bump):

   ```bash
   ../../scripts/create_services.py --num-services ${NUM_SERVICES}
   ```

4. Deploy the rendered file to the unit - only `compose.yaml` itself needs to be there, not the rest of this
   checkout:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/timing/compose.yaml
   ```

5. On the unit, time the deploy, letting `podman-compose` pull and start every item itself:

   ```bash
   time_event.py --name "timing deploy ${NUM_SERVICES} items" --source podman -- podman-compose -p timing -f compose.yaml up -d
   ```

6. Wait for every item's own `checkpoint_event` to appear in the Grafana Events view.
7. Calculate Total from the max per-item `Start` checkpoint minus when step 5's `podman-compose up` was issued
   (`time_event.py` already reports step 5's own wall-clock time as a lower bound; the checkpoint-based figure is
   the more AosCore-comparable one - see "Install new deployable items" in the AosCore version for why).
8. Capture the CPU/RAM used by the orchestrator components (see below).
9. Tear down and remove the images, so the next tier redownloads them from scratch rather than reusing what's
   already cached locally - otherwise only the first tier run would measure a real download:

   ```bash
   podman-compose -p timing -f compose.yaml down -t 0
   podman rmi -f $(podman images -q --filter reference="${REGISTRY_HOST}/benchmark-*")
   ```

10. Repeat from step 3 with `NUM_SERVICES` set to 8, then 16.

### Install cached deployable items

Goal: measure the different operational time intervals during deploying cached deployable items to the unit -
same goal as the AosCore version, adapted the same way "Install new deployable items" above is.

Deployable item: same `benchmark-timing-1` .. `benchmark-timing-16` images used in "Install new deployable items"
above.

Cached deployable item: an image already present in the unit's local `podman images` store from a prior pull, but
with no currently-running container for it - unlike "Install new deployable items", which removes every timing
image after each tier specifically to force a cold pull, this chapter deliberately leaves them cached so
`podman-compose up`'s own default pull policy (`missing`) skips the pull entirely and only creates/starts the
container. See the Disclaimer's podman-compose version note - with no pull step to parallelize, this chapter's
"Total" doesn't depend on concurrent pulling the way "Install new deployable items" does.

Metrics and checkpoint/timing are the same as in "Install new deployable items" above.

Prerequisites:

1. Each of the `NUM_SERVICES` items under test for a given tier has previously been pulled onto the unit at least once,
   with no container currently running for it - step 5 below does this explicitly before the measured run, so this isn't
   a separate manual setup step.

Execution steps:

1. With no containers running, capture the idle CPU/RAM used by the orchestrator components (see "CPU/RAM used
   by orchestrator components" below).
2. Set up working directories, once for this whole test - not repeated per tier, same as "Install new deployable
   items" step 2. On the build/push host:

   ```bash
   cd benchmark/timing/podman
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/timing
   cd ~/benchmark/timing
   ```

3. Render `compose.yaml` for `NUM_SERVICES` items on the build/push host:

   ```bash
   ../../scripts/create_services.py --num-services ${NUM_SERVICES}
   ```

4. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/timing/compose.yaml
   ```

5. On the unit, warm the cache: pull and start every item once, untimed, then tear the containers back down
   without removing the images - this is what makes the next step's images "cached" rather than "new":

   ```bash
   podman-compose -p timing -f compose.yaml up -d
   podman-compose -p timing -f compose.yaml down -t 0
   ```

6. Time the actual measured deploy - with every image already cached, `podman-compose` only creates and starts
   each container, no pull involved:

   ```bash
   time_event.py --name "timing deploy ${NUM_SERVICES} cached items" --source podman -- podman-compose -p timing -f compose.yaml up -d
   ```

7. Wait for every item's own `checkpoint_event` to appear in the Grafana Events view.
8. Calculate Total from the max per-item `Start` checkpoint minus when step 6's `podman-compose up` was issued.
9. Capture the CPU/RAM used by the orchestrator components (see below).
10. Tear down, but leave the images cached this time (no `podman rmi`) - a subsequent tier only adds the items
    it needs beyond what a smaller tier already cached:

    ```bash
    podman-compose -p timing -f compose.yaml down -t 0
    ```

11. Repeat from step 3 with `NUM_SERVICES` set to 8, then 16.

### Start/stop already installed instances

Goal: measure Podman start/stop time for a fixed set of already-installed instances - same goal as the AosCore
version, adapted to what `podman-compose start`/`stop` actually operate on (already-created containers, not
creating new ones the way `up` does).

Deployable item: same `benchmark-timing` image(s) as "Install new deployable items" above, scaled via
`deploy.replicas` instead of one instance per separate item. `deploy.replicas` itself has no per-item instance
limit, but this document mirrors AosCore's own 64-instances-per-item cap so item/instance counts stay directly
comparable between the two versions:

| Instances | Items | Instances/item  |
|:---------:|:-----:|:---------------:|
|     1     |   1   |        1        |
|     8     |   1   |        8        |
|    16     |   1   |       16        |
|    64     |   1   |       64        |
|    128    |   2   |       64        |
|    256    |   4   |       64        |

Metrics:

* **Start instances** - time from issuing `podman-compose start` until every instance has started;
* **Stop instances** - time to issue and complete `podman-compose stop` for all instances.

Checkpoint/timing used to measure each:

| Metric | Measured as |
| --- | --- |
| Start instances | `time_event.py` wrapping `podman-compose start`, cross-checked against the max (latest) per-instance `checkpoint_event(event="Start")` timestamp - the same per-instance checkpoint "Install new deployable items"' Total uses |
| Stop instances | `time_event.py` wrapping `podman-compose stop`'s own reported wall-clock elapsed time. `benchmark-timing` pushes no `Stop` checkpoint on shutdown (only `Start`, on launch), so unlike every other timing metric in this document there is no checkpoint-based cross-check available here |

`benchmark-timing` installs no `SIGTERM` handler, and as PID 1 of its container the kernel then ignores `SIGTERM`
entirely - so a plain `podman stop` would wait out its whole 10 s grace period before `SIGKILL`, and "Stop
instances" would measure that grace period instead of stopping. `timing`'s `compose.yaml.in` therefore sets
`init: true`: an init as PID 1 forwards the signal to `benchmark-timing`, which then terminates at once. The
default `stop` timeout is left as is - no `-t 0` override.

Prerequisites:

1. No containers are currently running for the `timing` project on the unit (clean slate) - matching the AosCore
   version's own "test subject contains no deployable items" prerequisite.

Execution steps:

1. With no containers running, capture the idle CPU/RAM used by the orchestrator components (see "CPU/RAM used
   by orchestrator components" below).
2. Set up working directories, once for this whole test - not repeated per tier, same as "Install new deployable
   items" step 2. On the build/push host:

   ```bash
   cd benchmark/timing/podman
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/timing
   cd ~/benchmark/timing
   ```

3. Render `compose.yaml` for the current tier on the build/push host, with `NUM_INSTANCES` set to the table's
   Instances/item column and `NUM_SERVICES` set to its Items column (`NUM_SERVICES` is 1 below the 128 tier):

   ```bash
   ../../scripts/create_services.py --num-services ${NUM_SERVICES} --num-instances ${NUM_INSTANCES}
   ```

4. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/timing/compose.yaml
   ```

5. On the unit, deploy the instances, untimed - this chapter measures stopping/starting an already-running set,
   not the initial deploy (see "Install new deployable items" for that):

   ```bash
   podman-compose -p timing -f compose.yaml up -d
   ```

6. Wait for every instance to be successfully started.
7. Time stopping every instance:

   ```bash
   time_event.py --name "timing stop $((NUM_SERVICES * NUM_INSTANCES)) instances" --source podman -- podman-compose -p timing -f compose.yaml stop
   ```

8. Wait for every instance to be confirmed stopped (`podman ps` shows none running for this project).
9. Time starting every instance back up:

   ```bash
   time_event.py --name "timing start $((NUM_SERVICES * NUM_INSTANCES)) instances" --source podman -- podman-compose -p timing -f compose.yaml start
   ```

10. Wait for every instance's own `checkpoint_event` to appear in the Grafana Events view.
11. Calculate Start instances from the max per-instance `Start` checkpoint minus when step 9's `podman-compose
    start` was issued; Stop instances is step 7's own reported wall-clock elapsed time (see above for why no
    checkpoint-based figure exists for it).
12. Capture the CPU/RAM used by the orchestrator components (see below).
13. Tear down and remove the images, same as "Install new deployable items" step 9, so the next tier starts
    clean:

    ```bash
    podman-compose -p timing -f compose.yaml down -t 0
    podman rmi -f $(podman images -q --filter reference="${REGISTRY_HOST}/benchmark-*")
    ```

14. Repeat from step 3 for 8, 16, 64, 128, 256 instances, setting `NUM_SERVICES` and `NUM_INSTANCES` to the
    table's Items and Instances/item columns for each tier.

## Container disk I/O

Same [diskio](https://github.com/aosedge/demo-services/tree/main/benchmark/diskio) benchmark service and the
exact same `diskio_benchmark.py` script the AosCore version deploys (`podman/Containerfile` builds it from the
same `../src/diskio_benchmark.py`) - see the AosCore chapter for the four-`fio`-job sequence, metrics, and
`checkpoint_event`/`benchmark_result` shape, all unchanged since the script itself doesn't know which runtime
started it.

`TEST_DIR` still selects the storage backend, but instead of AosCore's own storage resource abstraction,
`benchmark/diskio/podman/compose.yaml.in` bind-mounts the real host paths directly - `/var/aos/storages:/storage`
(encrypted) and `/var/aos/common-data:/common` (unencrypted) are both always mounted, so switching backends is
just changing `TEST_DIR`, matching the AosCore version's own `--test-dir`-driven behavior. Both paths must
already exist on the unit - see "Unit provisioning" in Prerequisites for why.

Prerequisites:

1. No containers are currently running for the `diskio` project on the unit (clean slate) - matching the AosCore
   version's own "test subject contains no deployable items" prerequisite.

### Encrypted storage

Execution steps:

1. Set up working directories, once for this whole test - not repeated per tier. On the build/push host:

   ```bash
   cd benchmark/diskio/podman
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/diskio
   cd ~/benchmark/diskio
   ```

2. Render `compose.yaml` for one instance on the encrypted backend on the build/push host:

   ```bash
   ../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-dir /storage
   ```

3. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/diskio/compose.yaml
   ```

4. On the unit, deploy the instance(s):

   ```bash
   podman-compose -p diskio -f compose.yaml up -d
   ```

5. Wait for the instance(s) to finish all four jobs (`All jobs finished` in each instance log, `Stop` checkpoint
   event in the Grafana Events view for each instance).
6. Read the sequential throughput/latency and random IOPS/latency (avg/p99) `benchmark_result` samples from
   Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down, but leave the image cached - unlike timing's N distinct images, there's only ever this one
   `benchmark-diskio` image regardless of tier or backend, so there's nothing to force a fresh pull of; it's only
   removed once, after every diskio tier in both this chapter and "Unencrypted storage" below is done (see that
   chapter's own last step). Every instance also leaves its 16 MiB data file behind on the volume, named after its
   instance ID, so remove them too or they accumulate across tiers (64 instances leave 1 GiB):

   ```bash
   podman-compose -p diskio -f compose.yaml down -t 0
   rm -f /var/aos/storages/diskio-*.dat
   ```

9. Repeat from step 2 for 8, 16, 64 instances, updating `NUM_INSTANCES`.
10. Once every tier of this chapter is done, remove the image:

    ```bash
    podman rmi -f $(podman images -q --filter reference="${REGISTRY_HOST}/benchmark-*")
    ```

### Unencrypted storage

Execution steps:

1. Set up working directories, once for this whole test - not repeated per tier. On the build/push host:

   ```bash
   cd benchmark/diskio/podman
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/diskio
   cd ~/benchmark/diskio
   ```

2. Render `compose.yaml` for one instance on the unencrypted backend on the build/push host:

   ```bash
   ../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-dir /common
   ```

3. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/diskio/compose.yaml
   ```

4. On the unit, deploy the instance(s):

   ```bash
   podman-compose -p diskio -f compose.yaml up -d
   ```

5. Wait for the instance(s) to finish all four jobs (`All jobs finished` in each instance log, `Stop` checkpoint
   event in the Grafana Events view for each instance).
6. Read the sequential throughput/latency and random IOPS/latency (avg/p99) `benchmark_result` samples from
   Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down, but leave the image cached - same reasoning as "Encrypted storage" step 8 above - and remove the
   instances' data files as there:

   ```bash
   podman-compose -p diskio -f compose.yaml down -t 0
   rm -f /var/aos/common-data/diskio-*.dat
   ```

9. Repeat from step 2 for 8, 16, 64 instances, updating `NUM_INSTANCES`.
10. Once every tier of this chapter is done, remove the image:

    ```bash
    podman rmi -f $(podman images -q --filter reference="${REGISTRY_HOST}/benchmark-*")
    ```

## Network

Same deployable items as [Benchmark Execution (AosCore)](benchmark_execution_aos.md#network) (`benchmark-network-*`
server/peer and client pairs), run via `podman-compose` instead of AosCore's deployment pipeline. Each scenario's
`compose.yaml.in` bundles both the server/peer and the client service(s). For "service to unit"/"service to
external host" the bundled server/peer is started too but goes unused (the AosCore version doesn't deploy it,
since the server side there is a native process) - it only sits idle. `create_services.py` renders `compose.yaml` on
the build/push host; only that rendered file needs to reach the unit, into a folder mirroring this checkout's own path
(e.g. `~/benchmark/network/bandwidth/compose.yaml`) so different scenarios' files never collide - `podman-compose`
itself then runs on the unit, where the containers do.

### Bandwidth

Goal: measure the throughput available to a container through the Podman network, for TCP and UDP in both
directions, together with UDP jitter and packet loss, across the same three paths as the AosCore version - service
to service, service to unit, and service to an external host - and how that throughput scales with the number of
concurrent client instances.

Deployable items: [bandwidth](https://github.com/aosedge/demo-services/tree/main/benchmark/network/bandwidth)
server and client images, `benchmark-network-bandwidth-server` and `benchmark-network-bandwidth-client` (see
"Container images" above), the same `bandwidth_server.py`/`bandwidth_client.py` the AosCore version deploys.

On start, each client instance runs four `iperf3` tests in a row against `TARGET`, each for `DURATION` seconds:
`tcp_up`, `tcp_down` (`-R`), `udp_up` (`-u`), `udp_down` (`-u -R`). Every test's full result is logged; the
throughput, and for the UDP tests loss and jitter, are pushed as `benchmark_result` samples to VictoriaMetrics,
bracketed by a `checkpoint_event` Start/Stop pair for the whole run - unchanged from the AosCore version, see its
chapter for the details. `TARGET` selects the path and `UDP_BANDWIDTH` (`--udp-bandwidth`, `80M` by default) the UDP
rate, exactly as there.

`iperf3 -c` resolves a Podman network DNS name the same as a real hostname (on the DNS-enabled `benchmark` network,
see Prerequisites), so the "service to service" path needs no adaptation.

**Deviation - scaling clients**: AosCore gives each instance of a scaled service a sequential `AOS_INSTANCE_INDEX`,
so `N` concurrent clients each dial their own `bandwidth_server.py`-run `iperf3` port. Podman's `deploy.replicas`
has no per-replica ordinal (all replicas of a service are identical, and the hostname is a random container ID),
so the client isn't scaled with replicas: `create_services.py` clones one `bandwidth-client-<N>` service per
instance instead, and `NUM_SERVICES` (`--num-services`) sets the client count (the server's `NUM_INSTANCES` is
filled in to match). `podman/entrypoint-client.sh` derives the 0-based `AOS_INSTANCE_INDEX` from the 1-based service
ID. Scale clients with `NUM_SERVICES`, not with `NUM_INSTANCES` (`--num-instances`).

Metrics:

* `tcp_up`/`tcp_down`: throughput (Mbps);
* `udp_up`/`udp_down`: throughput (Mbps), loss (%), jitter (ms);
* System CPU - whole-host max CPU usage (%) for the duration of the run.

For more than one instance, every metric above is aggregated as described in "Result aggregation" above.

Prerequisites:

1. No containers are currently running for the `bandwidth` project on the unit (clean slate).

The three paths below share the same working directories, on both hosts - set them up once, they're not repeated
per path or per instance count. On the build/push host:

```bash
cd benchmark/network/bandwidth/podman
```

On the unit, open one session for the rest of this chapter and `cd` there once:

```bash
mkdir -p ~/benchmark/network/bandwidth
cd ~/benchmark/network/bandwidth
```

#### Service to service

Execution steps:

1. Render `compose.yaml` for the service-to-service path for one client instance on the build/push host:

   ```bash
   ../../../scripts/create_services.py --num-services ${NUM_SERVICES} --test-host bandwidth-server
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/network/bandwidth/compose.yaml
   ```

3. On the unit, deploy the server and client instance(s):

   ```bash
   podman-compose -p bandwidth -f compose.yaml up -d
   ```

4. Wait for the client instance(s) to finish all four tests (`All tests finished` in each client container log,
   `Stop` checkpoint event in the Grafana Events view for each client instance).
5. Read the `tcp_up`/`tcp_down` throughput and `udp_up`/`udp_down` throughput/loss/jitter `benchmark_result`
   samples from Grafana. For more than one instance, average each metric across all instances' samples.
6. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
7. Tear down, leaving the images cached (they're only removed once, at the end of the DNS chapter):

   ```bash
   podman-compose -p bandwidth -f compose.yaml down -t 0
   ```

8. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_SERVICES`.

#### Service to unit

With `USE_DHCP=yes` the unit's uplink interface carries two addresses: the static `10.0.0.100/24`, used for the
unit's own services, and the DHCP-assigned address, which holds the default route. `NODE_IP=10.0.0.100` is
therefore correct for every "service to unit" scenario on both the DHCP and the static deployment.

Execution steps:

1. Render `compose.yaml` for the service-to-unit path for one client instance on the build/push host, using the
   unit's own network address as `--test-host` (`NODE_IP` is `10.0.0.100` by default on the main node):

   ```bash
   ../../../scripts/create_services.py --num-services ${NUM_SERVICES} --test-host ${NODE_IP}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/network/bandwidth/compose.yaml
   ```

3. On the unit, start one native `iperf3` server per instance, bound to the unit's address, using
   `iperf3-servers.sh` ([meta-aos](https://github.com/aosedge/meta-aos) `recipes-support/benchmark-network`),
   installed at `/opt/aos/benchmark/iperf3-servers.sh` on the `benchmark` `DISTRO_FEATURES`. First confirm the
   port(s) are free - a leftover `iperf3` process from an earlier run:

   ```bash
   /opt/aos/benchmark/iperf3-servers.sh -b ${NODE_IP} -n ${NUM_SERVICES}
   ```

4. On the unit, deploy the client instance(s). The bundled server container is started too but isn't used for
   this path, since the server side here is the native one from step 3:

   ```bash
   podman-compose -p bandwidth -f compose.yaml up -d
   ```

5. Wait for the client instance(s) to finish all four tests (`All tests finished` in each client container log,
   `Stop` checkpoint event in the Grafana Events view for each client instance).
6. Read the `tcp_up`/`tcp_down` throughput and `udp_up`/`udp_down` throughput/loss/jitter `benchmark_result`
   samples from Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down the containers:

   ```bash
   podman-compose -p bandwidth -f compose.yaml down -t 0
   ```

9. Stop the native `iperf3` server(s) started on the unit in step 3.
10. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_SERVICES` and the `-n` passed to
    `iperf3-servers.sh` in step 3.

#### Service to external host

Execution steps:

1. Render `compose.yaml` for the service-to-external path for one client instance on the build/push host, using an
   external host's address on the unit's local network as `--test-host` (`HOST_IP` is the IP behind the unit,
   accessible from the unit; on an AosCore VM it is `10.0.0.1` by default):

   ```bash
   ../../../scripts/create_services.py --num-services ${NUM_SERVICES} --test-host ${HOST_IP}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/network/bandwidth/compose.yaml
   ```

3. On the external host, start one native `iperf3` server per instance, bound to that host's address, using
   `iperf3-servers.sh`. The external host is not an AosCore unit, so get the script from
   [meta-aos](https://github.com/aosedge/meta-aos) `recipes-support/benchmark-network/files/iperf3-servers.sh`
   and copy it over. First confirm the port(s) are free - a leftover `iperf3` process, or (on Debian/Ubuntu) a
   pre-installed `iperf3.service` enabled on `*:5201`, can already be listening:

   ```bash
   ./iperf3-servers.sh -b ${HOST_IP} -n ${NUM_SERVICES}
   ```

4. On the unit, deploy the client instance(s) (the bundled server container is started too but unused, as above):

   ```bash
   podman-compose -p bandwidth -f compose.yaml up -d
   ```

5. Wait for the client instance(s) to finish all four tests (`All tests finished` in each client container log,
   `Stop` checkpoint event in the Grafana Events view for each client instance).
6. Read the `tcp_up`/`tcp_down` throughput and `udp_up`/`udp_down` throughput/loss/jitter `benchmark_result`
   samples from Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down the containers:

   ```bash
   podman-compose -p bandwidth -f compose.yaml down -t 0
   ```

9. Stop the native `iperf3` server(s) started on the external host in step 3.
10. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_SERVICES` and the `-n` passed to
    `iperf3-servers.sh` in step 3.

### Latency

Goal: measure the round-trip time through the Podman network, reported as percentiles (p50/p99/p999) rather than
an average, so the tail that real-time/RPC traffic feels stays visible, across the same three paths as the AosCore
version - service to service, service to unit, and service to an external host - and how that tail scales with the
number of concurrent client instances.

Deployable items: [latency](https://github.com/aosedge/demo-services/tree/main/benchmark/network/latency) server
and client images, `benchmark-network-latency-server` and `benchmark-network-latency-client` (see "Container
images" above), the same `latency_server.py`/`latency_client.py` the AosCore version deploys.

On start, each client instance runs a `sockperf` ping-pong test in each direction against `TARGET`, each for
`DURATION` seconds: `udp_rtt`, then `tcp_rtt` (`--tcp`), both with `--full-rtt` so every figure is a full round
trip. The p50/p99/p999 figures are pushed as `benchmark_result` samples to VictoriaMetrics, bracketed by a
`checkpoint_event` Start/Stop pair for the whole run - unchanged from the AosCore version, see its chapter for the
details. `TARGET` selects the path exactly as there.

**Same `sockperf` as AosCore**: the images build `sockperf` from the exact commit `meta-aos`'
`recipes-support/sockperf` pins (3.10+git) instead of installing Debian's 3.7-1, whose `-i` rejects a hostname
(`sockperf: '-i' Invalid address: localhost`). That commit resolves `-i` with `getaddrinfo()`, so
`TARGET=latency-server` (the server's compose service name) works directly, exactly as in the AosCore version, with
no workaround in the entrypoint.

**Deviation - scaling clients**: same as Bandwidth - Podman's `deploy.replicas` has no per-replica ordinal, so
`create_services.py` clones one `latency-client-<N>` service per instance instead, `NUM_SERVICES`
(`--num-services`) sets the client count (the server's `NUM_INSTANCES` is filled in to match), and
`podman/entrypoint-client.sh` derives the 0-based `AOS_INSTANCE_INDEX` (which of the server's `NUM_INSTANCES` port
pairs the client dials) from the 1-based service ID. Scale clients with `NUM_SERVICES`, not with `NUM_INSTANCES`
(`--num-instances`).

Metrics:

* `udp_rtt`/`tcp_rtt`: p50, p99, p999 (µs).

For more than one instance, every metric above is aggregated as described in "Result aggregation" above.

Prerequisites:

1. No containers are currently running for the `latency` project on the unit (clean slate).

The three paths below share the same working directories, on both hosts - set them up once, they're not repeated
per path or per instance count. On the build/push host:

```bash
cd benchmark/network/latency/podman
```

On the unit, open one session for the rest of this chapter and `cd` there once:

```bash
mkdir -p ~/benchmark/network/latency
cd ~/benchmark/network/latency
```

#### Service to service

Execution steps:

1. Render `compose.yaml` for the service-to-service path for one client instance on the build/push host:

   ```bash
   ../../../scripts/create_services.py --num-services ${NUM_SERVICES} --test-host latency-server
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/network/latency/compose.yaml
   ```

3. On the unit, deploy the server and client instance(s):

   ```bash
   podman-compose -p latency -f compose.yaml up -d
   ```

4. Wait for the client instance(s) to finish both tests (`All tests finished` in each client container log, `Stop`
   checkpoint event in the Grafana Events view for each client instance).
5. Read the `udp_rtt`/`tcp_rtt` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance,
   average each metric across all instances' samples.
6. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
7. Tear down, leaving the images cached (they're only removed once, at the end of the DNS chapter):

   ```bash
   podman-compose -p latency -f compose.yaml down -t 0
   ```

8. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_SERVICES`.

#### Service to unit

Execution steps:

1. Render `compose.yaml` for the service-to-unit path for one client instance on the build/push host, using the
   unit's own network address as `--test-host` (`NODE_IP` is `10.0.0.100` by default on the main node):

   ```bash
   ../../../scripts/create_services.py --num-services ${NUM_SERVICES} --test-host ${NODE_IP}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/network/latency/compose.yaml
   ```

3. On the unit, start one native `sockperf` UDP server and one TCP server per instance, both bound to the unit's
   address, using `sockperf-servers.sh` ([meta-aos](https://github.com/aosedge/meta-aos)
   `recipes-support/benchmark-network`), installed at `/opt/aos/benchmark/sockperf-servers.sh` on the `benchmark`
   `DISTRO_FEATURES`. First confirm the port(s) are free - a leftover `sockperf server` process from an earlier
   manual run is the only thing that can conflict, since the server container's own `sockperf` listens inside its
   own container network namespace:

   ```bash
   /opt/aos/benchmark/sockperf-servers.sh -b ${NODE_IP} -n ${NUM_SERVICES}
   ```

4. On the unit, deploy the client instance(s). The bundled server container is started too but isn't used for
   this path, since the server side here is the native one from step 3:

   ```bash
   podman-compose -p latency -f compose.yaml up -d
   ```

5. Wait for the client instance(s) to finish both tests (`All tests finished` in each client container log, `Stop`
   checkpoint event in the Grafana Events view for each client instance).
6. Read the `udp_rtt`/`tcp_rtt` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance,
   average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down the containers:

   ```bash
   podman-compose -p latency -f compose.yaml down -t 0
   ```

9. Stop the native `sockperf` server(s) started on the unit in step 3.
10. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_SERVICES` and the `-n` passed to
    `sockperf-servers.sh` in step 3.

#### Service to external host

Execution steps:

1. Render `compose.yaml` for the service-to-external path for one client instance on the build/push host, using an
   external host's address on the unit's local network as `--test-host` (`HOST_IP` is the IP behind the unit,
   accessible from the unit; on an AosCore VM it is `10.0.0.1` by default):

   ```bash
   ../../../scripts/create_services.py --num-services ${NUM_SERVICES} --test-host ${HOST_IP}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/network/latency/compose.yaml
   ```

3. On the external host, install `sockperf` if not already present (Debian/Ubuntu ships it), then start one
   native UDP server and one TCP server per instance, both bound to that host's address, using
   `sockperf-servers.sh`. The external host is not an AosCore unit, so get the script from
   [meta-aos](https://github.com/aosedge/meta-aos) `recipes-support/benchmark-network/files/sockperf-servers.sh`
   and copy it over. First confirm the port(s) are free - a leftover `sockperf server` process from an earlier
   manual run is the only thing that can conflict:

   ```bash
   ./sockperf-servers.sh -b ${HOST_IP} -n ${NUM_SERVICES}
   ```

4. On the unit, deploy the client instance(s) (the bundled server container is started too but unused, as above):

   ```bash
   podman-compose -p latency -f compose.yaml up -d
   ```

5. Wait for the client instance(s) to finish both tests (`All tests finished` in each client container log, `Stop`
   checkpoint event in the Grafana Events view for each client instance).
6. Read the `udp_rtt`/`tcp_rtt` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance,
   average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down the containers:

   ```bash
   podman-compose -p latency -f compose.yaml down -t 0
   ```

9. Stop the native `sockperf` server(s) started on the external host in step 3.
10. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_SERVICES` and the `-n` passed to
    `sockperf-servers.sh` in step 3.

### DNS

Goal: measure how long a container takes to resolve a name, reported as percentiles (p50/p99/p999) rather than an
average, across the same three paths as the AosCore version - service to service, service to unit, and service to
an external host - and how that time scales with the number of concurrent client instances.

Deployable items: [dns](https://github.com/aosedge/demo-services/tree/main/benchmark/network/dns) peer and client
images, `benchmark-network-dns-peer` and `benchmark-network-dns-client` (see "Container images" above), the same
`dns_client.py` the AosCore version deploys.

On start, each client instance sends `QUERIES` DNS queries for `NAME` one at a time over its own UDP socket, timing
each with `time.perf_counter()`. The full sample set and a breakdown of any failures are logged; the p50/p99/p999
figures are pushed as `benchmark_result` samples to VictoriaMetrics, bracketed by a `checkpoint_event` Start/Stop
pair for the whole run - unchanged from the AosCore version, see its chapter for the details.

`NAME` and `RESOLVER` decide which path the run measures:

* **service to service** - `NAME=dns-peer`, resolved by the network's aardvark-dns, which registers the peer's
  compose service name. `RESOLVER` is left empty, so the client asks the nameserver in its own `/etc/resolv.conf`
  (aardvark-dns);
* **service to unit** - `NAME` is a hostname the unit's `dnsmasq` already answers for out of `/etc/aos/addnhosts`
  (`main` by default, mapped to the node's own address). `RESOLVER` is the unit's address, so the client asks the
  unit's `dnsmasq` directly;
* **service to external host** - `NAME` is a wildcard domain an external host's `dnsmasq` answers for, with
  `RANDOM_LABEL=1` so every query gets a fresh, uncached label and the unit's own `dnsmasq` cache never masks the
  round trip. `RESOLVER` is again the unit's address, and its `dnsmasq` forwards the domain to the external host.

**Deviation - resolver**: AosCore points an instance's `/etc/resolv.conf` at the unit's `dnsmasq`, so the client
needs no `RESOLVER` there. A Podman container's only nameserver is the network's aardvark-dns, which answers
NXDOMAIN for names only the unit's `dnsmasq` knows (`main`, the wildcard domain), so the unit and external paths
set `RESOLVER` (`create_services.py --resolver`) to the unit's address instead.

Metrics:

* `resolve`: p50, p99, p999 (µs).

System CPU is not collected for this chapter - a run finishes in a few seconds, too fast for a meaningful
whole-host max reading.

For more than one instance, every metric above is aggregated as described in "Result aggregation" above.

Prerequisites:

1. No containers are currently running for the `dns` project on the unit (clean slate).

The three paths below share the same working directories, on both hosts - set them up once, they're not repeated
per path or per instance count. On the build/push host:

```bash
cd benchmark/network/dns/podman
```

On the unit, open one session for the rest of this chapter and `cd` there once:

```bash
mkdir -p ~/benchmark/network/dns
cd ~/benchmark/network/dns
```

Unlike Bandwidth and Latency, nothing here is addressed per instance, so clients are scaled with plain
`deploy.replicas` (`--num-instances`), not cloned services.

#### Service to service

Execution steps:

1. Render `compose.yaml` for the service-to-service path for one client instance on the build/push host:

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host dns-peer
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/network/dns/compose.yaml
   ```

3. On the unit, deploy the peer and client instance(s):

   ```bash
   podman-compose -p dns -f compose.yaml up -d
   ```

4. Wait for the client instance(s) to finish (`All tests finished` in each client container log, `Stop` checkpoint
   event in the Grafana Events view for each client instance).
5. Read the `resolve` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance, average
   each metric across all instances' samples.
6. Tear down, leaving the images cached (they're only removed once, at the end of the "Service to external host"
   path below):

   ```bash
   podman-compose -p dns -f compose.yaml down -t 0
   ```

7. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES`.

#### Service to unit

Execution steps:

1. Render `compose.yaml` for the service-to-unit path for one client instance on the build/push host, using a
   hostname the unit's `dnsmasq` already answers for as `--test-host` (`main`, mapped to `NODE_IP` in
   `/etc/aos/addnhosts`, works on a stock unit with no further setup; see dns's README "Setting up each scenario"
   to measure a different name) and the unit's own address as `--resolver` (`NODE_IP` is `10.0.0.100` by default on
   the main node):

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host main --resolver ${NODE_IP}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/network/dns/compose.yaml
   ```

3. On the unit, deploy only the client instance(s) - the peer isn't needed for this path:

   ```bash
   podman-compose -p dns -f compose.yaml up -d dns-client
   ```

4. Wait for the client instance(s) to finish (`All tests finished` in each client container log, `Stop` checkpoint
   event in the Grafana Events view for each client instance).
5. Read the `resolve` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance, average
   each metric across all instances' samples.
6. Tear down:

   ```bash
   podman-compose -p dns -f compose.yaml down -t 0
   ```

7. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES`.

#### Service to external host

Execution steps:

The external host and the unit must be prepared to resolve the wildcard test domain before these steps start,
following the dns benchmark's
[README](https://github.com/aosedge/demo-services/blob/main/benchmark/network/dns/README.md), "Setting up each
scenario" section - it covers both the case where the unit sits behind a bridge gateway that already forwards
to the external host, and the case where the unit and the external host are two separate machines that need
forwarding configured between them explicitly.

1. Verify the wildcard resolves from the unit before deploying:

   ```bash
   nslookup probe123.dns-probe.test ${NODE_IP}
   ```

2. Render `compose.yaml` for the service-to-external path for one client instance on the build/push host, using
   the wildcard domain as `--test-host`, `RANDOM_LABEL` on so every query bypasses the unit's `dnsmasq` cache, and
   the unit's address as `--resolver`:

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host dns-probe.test --random-label 1 \
       --resolver ${NODE_IP}
   ```

3. Deploy the rendered file to the unit:

   ```bash
   scp compose.yaml root@${UNIT_HOST}:~/benchmark/network/dns/compose.yaml
   ```

4. On the unit, deploy only the client instance(s) - the peer isn't needed for this path:

   ```bash
   podman-compose -p dns -f compose.yaml up -d dns-client
   ```

5. Wait for the client instance(s) to finish (`All tests finished` in each client container log, `Stop` checkpoint
   event in the Grafana Events view for each client instance).
6. Read the `resolve` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance, average
   each metric across all instances' samples.
7. Tear down the containers:

   ```bash
   podman-compose -p dns -f compose.yaml down -t 0
   ```

8. Repeat from step 2 for 8, 16, 64 instances, updating `NUM_INSTANCES`.
9. Once every path in Bandwidth, Latency, and DNS is done, remove all six network images - none of them change
   across paths or tiers, so there's nothing to force a fresh pull of in between (run on the unit):

   ```bash
   podman rmi -f $(podman images -q --filter reference="${REGISTRY_HOST}/benchmark-network-*")
   ```

## CPU/RAM used by orchestrator components

CPU and RAM (proportional set size - the process-level memory metric `process-exporter` reports, accounting for
shared pages) consumption of the Podman orchestrator is sampled continuously by `process-exporter`, scraped into
VictoriaMetrics and visualized in Grafana, the same way as for the AosCore version. No dedicated execution steps are
required beyond running the scenario under test in its own chapter; the same run provides this chapter's CPU/RAM
figures for that scenario.

Podman is daemonless, so there is no long-lived orchestrator service like AosCore's CM/SM/IAM. The measured
components are:

* `podman` (the `component:podman` group in `process-exporter.yml`) - the CLI and every call `podman-compose` makes.
* `netavark` (the `component:netavark` group) - the helper that sets up a container's network each time one starts
  or stops.
* `aardvark-dns` (the `component:aardvark-dns` group) - the DNS daemon of the container network, one per unit. It is
  the resolver the DNS benchmark loads, the counterpart of CoreDNS in the k3s version (which appears among the
  container instances there, since it runs as a pod).

`podman` and `netavark` are not long-lived: they only exist while a command runs, so they show up as a spike around
the operation that ran them (a deploy, a start, a stop). The other helper processes Podman starts - `conmon` (one per
running container, about 0.5 MB PSS each) and `crun` - are small and aren't monitored separately.

The AosCore components (`cm`, `sm`, `iam`) run on the same unit unless it is stopped (see "AosCore" above) and appear
on the same panels - for this document read only the Podman ones. Per-container CPU and memory come from the separate
container-instances panels (`cgroup-exporter`), the same ones the AosCore version uses.

This is a per-component metric, distinct from the whole-host "System CPU" metric captured in the disk I/O and
network chapters above.

Execution steps:

1. Run the scenario under test (idle observation window, or a full test case from another chapter).
2. Read the `podman`, `netavark` and `aardvark-dns` components' CPU and RAM from the "CPU % - orchestrator
   components" and "Memory (PSS) - orchestrator components" Grafana panels for the duration of that scenario.

### Test scenarios

CPU/RAM is recorded for the following scenarios:

* Idle, no containers deployed;
* Operational Speed / Install new deployable items;
* Operational Speed / Install cached deployable items;
* Operational Speed / Start/stop already installed instances.
