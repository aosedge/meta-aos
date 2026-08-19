# Benchmark Execution

## Goal

This document records the execution procedure for the AosCore benchmark. The resulting measurements themselves are
recorded in [Benchmark Results](benchmark_results.md).

All tests are executed against an instrumented AosCore build. Instrumentation details are specified in
[meta-aos benchmark instrumentation](benchmark.md).

Test results are collected and analyzed via Grafana dashboards.

## Prerequisites

The following prerequisites apply to every test in this document:

* the unit under test is provisioned and online;
* the unit is included in the dedicated validation unit set on the cloud;
* the OEM has a dedicated subject used for these tests;
* the unit's board/SoC and the AosCore version or Git SHA under test are recorded alongside the results in
  [Benchmark Results](benchmark_results.md), so runs stay comparable across releases.

## Troubleshooting

### VictoriaMetrics stops accepting samples after boot

The unit's VictoriaMetrics instance can start rejecting every incoming sample right after boot, with a
timestamp-out-of-range warning in its journal (`journalctl -u victoria-metrics`), even though AosCore and the
`node-exporter`/`process-exporter`/`cgroup-exporter` scrape targets are otherwise healthy. When this happens, no
metrics or `checkpoint_event` samples reach Grafana, so a benchmark run performed in this state silently produces
no data at all.

Root cause: the board has no RTC. VictoriaMetrics seeds its insertion-time validation ceiling from the system
clock at the moment it starts. If it starts before the kernel clock has been synced to NTP, that ceiling is seeded
from a bogus (typically far-past) clock value; once NTP later steps the clock forward past that ceiling, every new
sample looks like it is "from the future" and gets dropped. Only a restart re-seeds the ceiling from the
now-correct clock.

Manual fix, on the unit:

```console
systemctl restart victoria-metrics.service
```

Verify recovery by checking that the scrape targets report fresh `up` samples:

```console
wget -qO- 'http://localhost:8428/api/v1/query?query=up'
```

Check for this (and restart if needed) before starting any benchmark run.

## Result aggregation

Where a chapter says a metric is "averaged" or "aggregated" across instances, that means the arithmetic mean of
each instance's own value for that metric. For percentile metrics (p50/p99/p999), this is the mean of each
instance's own percentile - not a percentile recomputed over the pooled raw samples of every instance, since only
the percentiles themselves, not the underlying samples, are pushed to VictoriaMetrics. A reported p99 for N
instances is therefore the mean of N per-instance p99s, and can differ from the p99 of the combined workload;
treat it as a per-instance figure, not a system-wide tail latency.

For throughput and IOPS, this document reports only the per-instance mean, not the summed aggregate across all
instances; readers wanting total system throughput at a given instance count should multiply the reported
per-instance mean by the instance count.

## Repetition

Each configuration (a given instance count, path, or storage backend) is executed once; the reported figure is
that single run's result, not a mean, median, or other statistic across repeated runs. No warm-up run is
discarded; the single run performed is the one reported. Run-to-run variability is therefore not characterized by
this document.

## Operational Speed

### Install new deployable items

Goal: measure the different operational time intervals during deploying new deployable items to the unit.

Deployable item: [timing](https://github.com/aosedge/demo-services/tree/main/benchmark/timing) benchmark service.

Each generated service runs `benchmark-timing`, a C++ binary that pushes a `checkpoint_event` (`event="Start"`)
sample to VictoriaMetrics on start, surfacing in the same Grafana Events table/annotations as AosCore's own
instance start/stop checkpoints, and also ships a configurable-size `test.dat` payload so the same batch doubles as
a deployment-size benchmark. The payload is fixed at 16 MiB per service, so at 1/8/16 services item count and total
deployment size scale together (16/128/256 MiB); this test does not separate the two, so an observed change cannot
be attributed to item count or total payload size alone.

Metrics:

* **Total** - time from receiving new desired status until all instances are started;
* **Download** - time to download, decrypt, and verify deployable item images;
* **Install** - time to unpack and install deployable items layers;
* **Prepare** - time to prepare newly installed instances;
* **Network** - time to set up instances network;
* **Start** - time to start instances.

Checkpoints used to measure each metric, from the `checkpoint_event` samples pushed to VictoriaMetrics:

| Metric   | Start source   | Start event                  | End source               | End event                   |
|----------|----------------|------------------------------|--------------------------|-----------------------------|
| Total    | aos-cm.service | Process desired status       | Last Instance: `${UUID}` | Start                       |
| Download | aos-cm.service | Download update items start  | aos-cm.service           | Download update items end   |
| Install  | aos-sm.service | Install items begin          | aos-sm.service           | Install items end           |
| Prepare  | aos-sm.service | Prepare instances begin      | aos-sm.service           | Prepare instances end       |
| Network  | aos-sm.service | Start networks begin         | aos-sm.service           | Start networks end          |
| Start    | aos-sm.service | Start instances begin        | aos-sm.service           | Start instances end         |

"Source" is the value of the `source` label on the `checkpoint_event` sample, and "event" is the value of its
`event` label - usually the AosCore component that pushed it (`aos-cm.service`, `aos-sm.service`), except for
AosCore's own per-instance start/stop checkpoints, whose `source` is the instance instead (`Last Instance:
${UUID}`). This applies to every checkpoint table in this document. Each metric is the End timestamp minus the
Start timestamp of the samples matching its row, e.g.:

```text
Total = timestamp(source="Last Instance: ${UUID}", event="Start")
      - timestamp(source="aos-cm.service", event="Process desired status")
```

Prerequisites:

1. Build the `benchmark-timing` binary with the SDK toolchain, using the shared `build.sh` at the repo root, for
   both `amd64` and `arm64` (`config.yaml.in` declares both an `amd64` and an `arm64` image for every generated
   service, so both builds are required regardless of which architecture the test unit runs):

   ```sh
   ../../build.sh . --toolchain=<amd64-toolchain-path> --arch=amd64
   ../../build.sh . --toolchain=<arm64-toolchain-path> --arch=arm64
   ```

Execution steps:

1. With no deployable items installed on the unit, capture the idle CPU/RAM used by each AosCore component (CM,
   SM, IAM) from the Grafana dashboard (see "CPU/RAM used by AosCore" below).
2. Copy each built architecture's output into a numbered service folder carrying a 16 MiB `test.dat` payload, then
   render `config.yaml` from `config.yaml.in`, using the service's shared `benchmark/scripts` generators:

   ```sh
   ../scripts/copy_images.py --num-services 1 --data-size 16
   ../scripts/create_services.py --num-services 1 --version 1.0.0-beta.1
   ```

3. Deploy the generated services to the cloud with `aos-signer`.
4. Attach the uploaded benchmark timing services to a subject, and attach that subject to the unit.
5. Wait for the deployable item to be successfully installed on the unit and its instance running.
6. Wait for the corresponding checkpoint events to appear in the Grafana Events view.
7. Calculate the required timing metrics from the checkpoints (see "Checkpoints" above).
8. Capture the CPU/RAM used by each AosCore component (see "CPU/RAM used by AosCore" below).
9. Detach the test subject from the unit on the cloud.
10. Repeat from step 2 for 8 and 16 services, incrementing the `--version` parameter passed to
    `create_services.py` each time.

### Install cached deployable items

Goal: measure the different operational time intervals during deploying cached deployable items to the unit.

Deployable item: same [timing](https://github.com/aosedge/demo-services/tree/main/benchmark/timing) benchmark
service used in "Install new deployable items" above.

Cached deployable item: an item whose image layers are already present in AosCore's local cache on this unit from
a prior install, but which currently has no installed/running instance - installing it again should skip or
shorten download/decrypt/verify since the layers are already on disk.

Metrics and checkpoints are the same as in "Install new deployable items" above.

Prerequisites:

1. Each of the 16 deployable items under test has previously been installed on this unit at least once, then
   detached (its instance removed via desired status) while leaving the unit's local cache populated, and the test
   subject is currently detached from the unit.

Execution steps:

1. With no deployable items installed on the unit, capture the idle CPU/RAM used by each AosCore component (CM,
   SM, IAM) from the Grafana dashboard (see "CPU/RAM used by AosCore" below).
2. Add one deployable item to the test subject and attach the subject to the unit.
3. Wait for the deployable items to be successfully installed on the unit and their instances running.
4. Wait for the corresponding checkpoint events to appear in the Grafana Events view.
5. Calculate the required timing metrics from the checkpoints (see "Checkpoints" above).
6. Capture the CPU/RAM used by each AosCore component (see "CPU/RAM used by AosCore" below).
7. Detach the test subject from the unit on the cloud.
8. Repeat from step 2 for 8 and 16 items.

### Start/stop already installed instances

Goal: measure the operational time intervals for AosCore startup and shutdown with a fixed set of already-installed
deployable item instances.

Deployable item: same [timing](https://github.com/aosedge/demo-services/tree/main/benchmark/timing) benchmark
service as in "Install new deployable items" above.

Each deployable item is capped at 64 instances, so reaching 128 and 256 total instances requires more than one
item; number of items is therefore not fixed across all data points:

| Instances | Deployable items | Instances/item |
|:---------:|:----------------:|:--------------:|
|     1     |        1         |        1       |
|     8     |        1         |        8       |
|    16     |        1         |       16       |
|    64     |        1         |       64       |
|    128    |        2         |       64       |
|    256    |        4         |       64       |

Metrics:

* **Init SM** - time from starting AosCore Service Manager until it begins updating instances;
* **Start network** - time to set up instances network;
* **Start instances** - time to start instances;
* **Release SM** - time from finishing network teardown until AosCore Service Manager successfully stopped;
* **Stop network** - time to release instances network;
* **Stop instances** - time to stop instances.

Checkpoints used to measure each metric, from the `checkpoint_event` samples pushed to VictoriaMetrics:

| Metric | Start source | Start event | End source | End event |
| --- | --- | --- | --- | --- |
| Init SM | init.scope | Starting AosCore Service Manager... | aos-sm.service | Update instances begin |
| Start network | aos-sm.service | Start networks begin | aos-sm.service | Start networks end |
| Start instances | aos-sm.service | Start instances begin | aos-sm.service | Start instances end |
| Stop network | aos-sm.service | Stop all networks begin | aos-sm.service | Stop all networks end |
| Stop instances | aos-sm.service | Stop all instances begin | aos-sm.service | Stop all instances end |
| Release SM | aos-sm.service | Stop all networks end | init.scope | Stopped AosCore Service Manager. |

Prerequisites:

1. The test subject contains no deployable items and is detached from the unit.

Execution steps:

1. With no deployable items installed on the unit, capture the idle CPU/RAM used by each AosCore component (CM,
   SM, IAM) from the Grafana dashboard (see "CPU/RAM used by AosCore" below).
2. Copy each built architecture's output into a numbered service folder without a `test.dat` payload, then render
   `config.yaml` from `config.yaml.in` for one instance, using the service's shared `benchmark/scripts` generators:

   ```sh
   ../scripts/copy_images.py --num-services 1
   ../scripts/create_services.py --num-services 1 --num-instances 1 --version 1.0.0-beta.1
   ```

   Increment `--version` for each generated configuration.
3. Deploy the generated services to the cloud with `aos-signer`.
4. Attach the uploaded benchmark timing services to a subject, and attach that subject to the unit.
5. Wait for the deployable item to be successfully installed on the unit and its instance running.
6. Stop AosCore using the dedicated `aos.target`:

   ```sh
   sudo systemctl stop aos.target
   ```

7. Wait for AosCore components and installed instances to be successfully stopped.
8. Start AosCore using the dedicated `aos.target`:

   ```sh
   sudo systemctl start aos.target
   ```

9. Wait for the corresponding checkpoint events to appear in the Grafana Events view.
10. Calculate the required timing metrics from the checkpoints (see "Checkpoints" above).
11. Capture the CPU/RAM used by each AosCore component (see "CPU/RAM used by AosCore" below).
12. Detach the test subject from the unit on the cloud.
13. Repeat from step 2 for 8, 16, 64, 128, 256 instances, using the deployable item count from the table above for
    each instance count.

## Container disk I/O

Deployable item: [diskio](https://github.com/aosedge/demo-services/tree/main/benchmark/diskio) benchmark service
(`benchmark-diskio-service`).

On instance start, the item runs four `fio` jobs in a row against a file under `TEST_DIR`
(`TEST_DIR/${AOS_INSTANCE_ID}.dat`, so concurrent instances never collide on one file): sequential write, sequential
read (1M blocks), then random write, random read (4K blocks). Every job's full result, `fio`'s own JSON document
included, is logged; the throughput/IOPS and latency (avg/p99) worth charting are pushed as `benchmark_result`
samples to VictoriaMetrics, bracketed by a single `checkpoint_event` Start/Stop pair for the whole run, the same
shape as the timing service above.

`TEST_DIR` decides which storage backend the run measures - comparing encrypted against unencrypted storage is
covered by running the same item twice, once per backend (see diskio's README "Storage backends" for how `/common`
is provided):

* **encrypted** - `TEST_DIR=/storage`, on AosCore's own storage volume, part of the LUKS-encrypted `aos` volume
  group;
* **unencrypted** - `TEST_DIR=/common`, on the unit's `common-data` resource, a plain unencrypted host partition.

Metrics:

* sequential read/write: throughput (MB/s) and latency (avg/p99, ms), per job;
* random read/write: IOPS and latency (avg/p99, ms), per job;
* System CPU - whole-host max CPU usage (%) for the duration of the run.

Prerequisites:

1. The test subject contains no deployable items and is detached from the unit.

### Encrypted storage

Execution steps:

1. Render `config.yaml` for the encrypted backend for one instance:

   ```sh
   ../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-dir /storage
   ```

2. Deploy the generated service to the cloud with `aos-signer`.
3. Attach the uploaded benchmark diskio service to a subject, and attach that subject to the unit.
4. Wait for the instance(s) to finish all four jobs (`All jobs finished` in each instance log, `Stop` checkpoint
   event in the Grafana Events view for each instance).
5. Read the sequential throughput/latency and random IOPS/latency (avg/p99) `benchmark_result` samples from
   Grafana. For more than one instance, average each metric across all instances' samples.
6. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
7. Detach the test subject from the unit on the cloud.
8. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
   `create_services.py` each time.

### Unencrypted storage

Execution steps:

1. Render `config.yaml` for the unencrypted backend:

   ```sh
   ../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-dir /common
   ```

2. Deploy the generated service to the cloud with `aos-signer`.
3. Attach the uploaded benchmark diskio service to a subject, and attach that subject to the unit.
4. Wait for the instance(s) to finish all four jobs (`All jobs finished` in each instance log, `Stop` checkpoint
   event in the Grafana Events view for each instance).
5. Read the sequential throughput/latency and random IOPS/latency (avg/p99) `benchmark_result` samples from
   Grafana. For more than one instance, average each metric across all instances' samples.
6. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
7. Detach the test subject from the unit on the cloud.
8. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
   `create_services.py` each time.

## Network

### Bandwidth

Goal: measure the throughput available to a deployable item instance through the container network AosCore sets
up, for TCP and UDP in both directions, together with UDP jitter and packet loss, across the paths that network
supports - service to service, service to unit, and service to an external host - and how that throughput scales
with the number of concurrent instances.

Deployable items: [bandwidth](https://github.com/aosedge/demo-services/tree/main/benchmark/network/bandwidth)
benchmark service pair, `benchmark-network-bandwidth-server-service` and `benchmark-network-bandwidth-client-service`.

On instance start, each client instance runs four `iperf3` tests in a row against `TARGET`, each for `DURATION`
seconds, spaced 3 seconds apart: `tcp_up`, `tcp_down` (`-R`), `udp_up` (`-u`), `udp_down` (`-u -R`). Every test's
full result, `iperf3`'s own JSON document included, is logged; the throughput, and for the UDP tests loss and
jitter, worth charting are pushed as `benchmark_result` samples to VictoriaMetrics, bracketed by a single
`checkpoint_event` Start/Stop pair for the whole run, the same shape as the diskio service above. Each test
additionally pushes its own `checkpoint_event` (`event=<test name>`) the moment it begins.

`TARGET` decides which path the run measures - covered by rendering the client item three times, once per path
(see bandwidth's README "Setting up each scenario" for how the unit/external `iperf3` servers are started):

* **service to service** - `TARGET=bandwidth-server`, both client and server are AosCore service instances on the
  same unit;
* **service to unit** - `TARGET` is the unit's own network address, with an `iperf3` server started natively on
  the unit host, bound to that address;
* **service to external host** - `TARGET` is an external host's address on the unit's local network, with an
  `iperf3` server started natively on that host.

The UDP tests target `UDP_BANDWIDTH` (`create_services.py`'s `--udp-bandwidth`, `80M` by default) rather than an
unbounded rate, so loss and jitter measure the path's behavior at a sustainable rate instead of `iperf3`'s own
datagram-processing ceiling (see bandwidth's README "Reading the numbers" for why). The default is used throughout
the steps below; `--udp-bandwidth` only needs to change to measure UDP at a different target rate.

Metrics:

* `tcp_up`/`tcp_down`: throughput (Mbps);
* `udp_up`/`udp_down`: throughput (Mbps), loss (%), jitter (ms);
* System CPU - whole-host max CPU usage (%) for the duration of the run.

For more than one instance, every metric above is aggregated as described in "Result aggregation" above.

Prerequisites:

1. The test subject contains no deployable items and is detached from the unit.

#### Service to service

Execution steps:

1. Render `config.yaml` for the service-to-service path for one instance:

   ```sh
   ../../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-host bandwidth-server
   ```

2. Deploy the generated server and client services to the cloud with `aos-signer`.
3. Attach both the uploaded benchmark bandwidth server and client services to a subject, and attach that subject
   to the unit.
4. Wait for the client instance(s) to finish all four tests (`All tests finished` in each client instance log,
   `Stop` checkpoint event in the Grafana Events view for each client instance).
5. Read the `tcp_up`/`tcp_down` throughput and `udp_up`/`udp_down` throughput/loss/jitter `benchmark_result`
   samples from Grafana. For more than one instance, average each metric across all instances' samples.
6. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
7. Detach the test subject from the unit on the cloud.
8. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
   `create_services.py` each time.

#### Service to unit

Execution steps:

1. Render `config.yaml` for the service-to-unit path for one instance, using the unit's own network address as
   `--test-host` (`NODE_IP` is `10.0.0.100` by default on the main node, and can be confirmed with `ifconfig` on
   the unit):

   ```sh
   ../../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-host ${NODE_IP}
   ```

2. On the unit, start one native `iperf3` server per instance, bound to that same address, using
   `iperf3-servers.sh` ([meta-aos](https://github.com/aosedge/meta-aos)
   `recipes-support/benchmark-network`), installed at `/opt/aos/benchmark/iperf3-servers.sh` on the `benchmark`
   `DISTRO_FEATURES`. First confirm the port(s) are free - a leftover `iperf3` process from an earlier run:

   ```sh
   /opt/aos/benchmark/iperf3-servers.sh -b ${NODE_IP} -n 1
   ```

3. Deploy the generated services to the cloud with `aos-signer`.
4. Attach the uploaded benchmark bandwidth client service to a subject (the bundled server service is not needed
   for this path), and attach that subject to the unit.
5. Wait for the client instance(s) to finish all four tests (`All tests finished` in each client instance log,
   `Stop` checkpoint event in the Grafana Events view for each client instance).
6. Read the `tcp_up`/`tcp_down` throughput and `udp_up`/`udp_down` throughput/loss/jitter `benchmark_result`
   samples from Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Detach the test subject from the unit on the cloud.
9. Stop the native `iperf3` server(s) started on the unit in step 2.
10. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
    `create_services.py`, and `-n` passed to `iperf3-servers.sh` in step 2, each time.

#### Service to external host

Execution steps:

1. Render `config.yaml` for the service-to-external path for one instance, using an external host's address on
   the unit's local network as `--test-host` (`HOST_IP` is the IP behind the unit, accessible from the unit; on
   an AosCore VM it is `10.0.0.1` by default):

   ```sh
   ../../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-host ${HOST_IP}
   ```

2. On the external host, start one native `iperf3` server per instance, bound to that same address, using
   `iperf3-servers.sh`. The external host is not an AosCore unit, so it is not built with this script already on
   it - get it from [meta-aos](https://github.com/aosedge/meta-aos)
   `recipes-support/benchmark-network/files/iperf3-servers.sh` and copy it over. First confirm the port(s) are
   free - a leftover `iperf3` process from an earlier run, or (on Debian/Ubuntu) a pre-installed `iperf3.service`
   enabled on `*:5201`, can already be listening (see network bandwidth's README "Before deploying" for how to
   disable the pre-installed service):

   ```sh
   ./iperf3-servers.sh -b ${HOST_IP} -n 1
   ```

3. Deploy the generated services to the cloud with `aos-signer`.
4. Attach the uploaded benchmark bandwidth client service to a subject (the bundled server service is not needed
   for this path), and attach that subject to the unit.
5. Wait for the client instance(s) to finish all four tests (`All tests finished` in each client instance log,
   `Stop` checkpoint event in the Grafana Events view for each client instance).
6. Read the `tcp_up`/`tcp_down` throughput and `udp_up`/`udp_down` throughput/loss/jitter `benchmark_result`
   samples from Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Detach the test subject from the unit on the cloud.
9. Stop the native `iperf3` server(s) started on the external host in step 2.
10. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
    `create_services.py`, and `-n` passed to `iperf3-servers.sh` in step 2, each time.

### Latency

Goal: measure the round-trip time through the container network AosCore sets up, reported as percentiles
(p50/p99/p999) rather than an average, so the tail that real-time/RPC traffic feels stays visible, across the
paths that network supports - service to service, service to unit, and service to an external host - and how
that tail scales with the number of concurrent instances.

Deployable items: [latency](https://github.com/aosedge/demo-services/tree/main/benchmark/network/latency)
benchmark service pair, `benchmark-network-latency-server-service` and `benchmark-network-latency-client-service`.

On instance start, each client instance runs a `sockperf` ping-pong test in each direction against `TARGET`, each
for `DURATION` seconds, spaced 3 seconds apart: `udp_rtt`, `tcp_rtt` (`--tcp`), both with `--full-rtt` so every
figure is a full round trip. `sockperf`'s own report, all five percentiles included, is logged; the three
percentiles the benchmark plan names are pushed as `benchmark_result` samples to VictoriaMetrics, bracketed by a
single `checkpoint_event` Start/Stop pair for the whole run, the same shape as the bandwidth service above. Each
test additionally pushes its own `checkpoint_event` (`event=<test name>`) the moment it begins.

`TARGET` decides which path the run measures - covered by rendering the client item three times, once per path
(see latency's README "Setting up each scenario" for how the unit/external `sockperf` servers are started):

* **service to service** - `TARGET=latency-server`, both client and server are AosCore service instances on the
  same unit;
* **service to unit** - `TARGET` is the unit's own network address, with `sockperf` UDP and TCP servers started
  natively on the unit host, bound to that address;
* **service to external host** - `TARGET` is an external host's address on the unit's local network, with
  `sockperf` UDP and TCP servers started natively on that host.

Metrics:

* `udp_rtt`/`tcp_rtt`: p50, p99, p999 (µs).

For more than one instance, every metric above is aggregated as described in "Result aggregation" above.

Prerequisites:

1. The test subject contains no deployable items and is detached from the unit.

#### Service to service

Execution steps:

1. Render `config.yaml` for the service-to-service path for one instance:

   ```sh
   ../../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-host latency-server
   ```

2. Deploy the generated server and client services to the cloud with `aos-signer`.
3. Attach both the uploaded benchmark latency server and client services to a subject, and attach that subject
   to the unit.
4. Wait for the client instance(s) to finish both tests (`All tests finished` in each client instance log, `Stop`
   checkpoint event in the Grafana Events view for each client instance).
5. Read the `udp_rtt`/`tcp_rtt` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance,
   average each metric across all instances' samples.
6. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
7. Detach the test subject from the unit on the cloud.
8. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
   `create_services.py` each time.

#### Service to unit

Execution steps:

1. Render `config.yaml` for the service-to-unit path for one instance, using the unit's own network address as
   `--test-host` (`NODE_IP` is `10.0.0.100` by default on the main node, and can be confirmed with `ifconfig` on
   the unit):

   ```sh
   ../../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-host ${NODE_IP}
   ```

2. On the unit, start one native `sockperf` UDP server and one TCP server per instance, both bound to that same
   address, using `sockperf-servers.sh` ([meta-aos](https://github.com/aosedge/meta-aos)
   `recipes-support/benchmark-network`), installed at `/opt/aos/benchmark/sockperf-servers.sh` on the `benchmark`
   `DISTRO_FEATURES`. First confirm the port(s) are free - a leftover `sockperf server` process from an earlier
   manual run is the only thing that can conflict, since the server item's own `sockperf` listens inside its own
   container network namespace:

   ```sh
   /opt/aos/benchmark/sockperf-servers.sh -b ${NODE_IP} -n 1
   ```

3. Deploy the generated services to the cloud with `aos-signer`.
4. Attach the uploaded benchmark latency client service to a subject (the bundled server service is not needed
   for this path), and attach that subject to the unit.
5. Wait for the client instance(s) to finish both tests (`All tests finished` in each client instance log, `Stop`
   checkpoint event in the Grafana Events view for each client instance).
6. Read the `udp_rtt`/`tcp_rtt` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance,
   average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Detach the test subject from the unit on the cloud.
9. Stop the native `sockperf` server(s) started on the unit in step 2.
10. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
    `create_services.py`, and `-n` passed to `sockperf-servers.sh` in step 2, each time.

#### Service to external host

Execution steps:

1. Render `config.yaml` for the service-to-external path for one instance, using an external host's address on
   the unit's local network as `--test-host` (`HOST_IP` is the IP behind the unit, accessible from the unit; on
   an AosCore VM it is `10.0.0.1` by default):

   ```sh
   ../../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-host ${HOST_IP}
   ```

2. On the external host, install `sockperf` if not already present (Debian/Ubuntu ships it), then start one
   native UDP server and one TCP server per instance, both bound to that same address, using
   `sockperf-servers.sh`. The external host is not an AosCore unit, so it is not built with this script already
   on it - get it from [meta-aos](https://github.com/aosedge/meta-aos)
   `recipes-support/benchmark-network/files/sockperf-servers.sh` and copy it over. First confirm the port(s) are
   free - a leftover `sockperf server` process from an earlier manual run is the only thing that can conflict:

   ```sh
   ./sockperf-servers.sh -b ${HOST_IP} -n 1
   ```

3. Deploy the generated services to the cloud with `aos-signer`.
4. Attach the uploaded benchmark latency client service to a subject (the bundled server service is not needed
   for this path), and attach that subject to the unit.
5. Wait for the client instance(s) to finish both tests (`All tests finished` in each client instance log, `Stop`
   checkpoint event in the Grafana Events view for each client instance).
6. Read the `udp_rtt`/`tcp_rtt` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance,
   average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Detach the test subject from the unit on the cloud.
9. Stop the native `sockperf` server(s) started on the external host in step 2.
10. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
    `create_services.py`, and `-n` passed to `sockperf-servers.sh` in step 2, each time.

### DNS

Goal: measure how long a service instance takes to resolve a name through the `dnsmasq` the unit runs for its
instances, reported as percentiles (p50/p99/p999) rather than an average, across the paths that DNS resolution
uses - service to service, service to unit, and service to an external host - and how that time scales with the
number of concurrent instances.

Deployable items: [dns](https://github.com/aosedge/demo-services/tree/main/benchmark/network/dns) benchmark
service pair, `benchmark-network-dns-peer-service` and `benchmark-network-dns-client-service`.

On instance start, each client instance sends `QUERIES` DNS queries for `NAME` one at a time over its own UDP
socket, timing each with `time.perf_counter()` rather than shelling out to `dig` (`dig` only reports whole
milliseconds, and starting the process would cost more than the query itself). The full sample set, and a
breakdown of any failures by reason, is logged; the three percentiles the benchmark plan names are pushed as
`benchmark_result` samples to VictoriaMetrics, bracketed by a `checkpoint_event` Start/Stop pair for the whole
run, the same shape as the bandwidth/latency services above.

`NAME` decides which path the run measures - covered by rendering the client item three times, once per path
(see dns's README "Setting up each scenario" for how the unit/external resolvers are configured):

* **service to service** - `NAME=dns-peer`, resolved out of a file `dnsmasq` reads for the idle peer item
  installed alongside the client;
* **service to unit** - `NAME` is a hostname the unit's `dnsmasq` already answers for out of
  `/etc/aos/addnhosts` (`main` by default, mapped to the node's own address);
* **service to external host** - `NAME` is a wildcard domain an external host's `dnsmasq` answers for, with
  `RANDOM_LABEL=1` so every query gets a fresh, uncached label and the unit's own `dnsmasq` cache never masks the
  round trip.

Metrics:

* `resolve`: p50, p99, p999 (µs).

System CPU is not collected for this chapter - a run finishes in a few seconds, too fast for a meaningful
whole-host max reading.

For more than one instance, every metric above is aggregated as described in "Result aggregation" above.

Prerequisites:

1. The test subject contains no deployable items and is detached from the unit.

#### Service to service

Execution steps:

1. Render `config.yaml` for the service-to-service path for one instance:

   ```sh
   ../../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-host dns-peer
   ```

2. Deploy the generated peer and client services to the cloud with `aos-signer`.
3. Attach both the uploaded benchmark DNS peer and client services to a subject, and attach that subject to the
   unit.
4. Wait for the client instance(s) to finish (`All tests finished` in each client instance log, `Stop` checkpoint
   event in the Grafana Events view for each client instance).
5. Read the `resolve` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance, average
   each metric across all instances' samples.
6. Detach the test subject from the unit on the cloud.
7. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
   `create_services.py` each time.

#### Service to unit

Execution steps:

1. Render `config.yaml` for the service-to-unit path for one instance, using a hostname the unit's `dnsmasq`
   already answers for as `--test-host` (`main`, mapped to `NODE_IP` in `/etc/aos/addnhosts`, works on a stock
   unit with no further setup; see dns's README "Setting up each scenario" to measure a different name):

   ```sh
   ../../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-host main
   ```

2. Deploy the generated services to the cloud with `aos-signer`.
3. Attach the uploaded benchmark DNS client service to a subject (the bundled peer service is not needed for
   this path), and attach that subject to the unit.
4. Wait for the client instance(s) to finish (`All tests finished` in each client instance log, `Stop` checkpoint
   event in the Grafana Events view for each client instance).
5. Read the `resolve` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance, average
   each metric across all instances' samples.
6. Detach the test subject from the unit on the cloud.
7. Repeat from step 1 for 8, 16, 64 instances, updating `--num-instances` passed to `create_services.py` each
   time.

#### Service to external host

Execution steps:

The external host and the unit must be prepared to resolve the wildcard test domain before these steps start,
following the dns benchmark's
[README](https://github.com/aosedge/demo-services/blob/main/benchmark/network/dns/README.md), "Setting up each
scenario" section - it covers both the case where the unit sits behind a bridge gateway that already forwards
to the external host, and the case where the unit and the external host are two separate machines that need
forwarding configured between them explicitly.

1. Verify the wildcard resolves from the unit before deploying:

   ```console
   nslookup probe123.dns-probe.test 10.0.0.100
   ```

2. Render `config.yaml` for the service-to-external path for one instance, using the wildcard domain as
   `--test-host` and `RANDOM_LABEL` on, so every query bypasses the unit's `dnsmasq` cache:

   ```sh
   ../../scripts/create_services.py --num-instances 1 --version 1.0.0-beta.1 --test-host dns-probe.test \
                                  --random-label 1
   ```

3. Deploy the generated services to the cloud with `aos-signer`.
4. Attach the uploaded benchmark DNS client service to a subject (the bundled peer service is not needed for
   this path), and attach that subject to the unit.
5. Wait for the client instance(s) to finish (`All tests finished` in each client instance log, `Stop` checkpoint
   event in the Grafana Events view for each client instance).
6. Read the `resolve` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance, average
   each metric across all instances' samples.
7. Detach the test subject from the unit on the cloud.
8. Repeat from step 2 for 8, 16, 64 instances, updating `--num-instances` and incrementing `--version` passed to
   `create_services.py` each time.

## CPU/RAM used by AosCore

CPU and RAM (proportional set size - the process-level memory metric `process-exporter` reports, accounting for
shared pages) consumption of each AosCore component (CM, SM, IAM) is sampled continuously by the instrumented
AosCore build's `process-exporter`/`node_exporter` metrics, scraped into VictoriaMetrics and visualized in Grafana.
No dedicated execution steps are required beyond running the scenario under test in its own chapter; the same run
provides this chapter's CPU/RAM figures for that scenario.

This is a per-component metric, distinct from the whole-host "System CPU" metric captured in the disk I/O and
network chapters above.

Execution steps:

1. Run the scenario under test (idle observation window, or a full test case from another chapter).
2. Read the corresponding component's CPU and RAM from the Grafana dashboard for the duration of that scenario.

### Test scenarios

CPU/RAM is recorded for the following scenarios:

* idle, no instances installed;
* Operational Speed / Install new deployable items;
* Operational Speed / Install cached deployable items.
* Operational Speed / Start/stop already installed instances.
