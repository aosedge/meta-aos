# Benchmark Execution (k3s)

## Goal

This document records the execution procedure for the k3s benchmark - the same benchmark plan as
[Benchmark Execution (AosCore)](benchmark_execution_aos.md) and
[Benchmark Execution (Podman)](benchmark_execution_podman.md), run against Kubernetes workloads on a single-node k3s
cluster, so the three container runtimes can be compared on the same metrics.

* For each benchmark chapter, it specifies the test environment and any deviation from the plan required for that
  test, so runs are reproducible and comparable across releases and against the AosCore and Podman results.
* The resulting measurements themselves are recorded in [Benchmark Results](benchmark_results.md), alongside the
  AosCore and Podman figures for direct comparison.
* Tests are deployed directly with `kubectl` (see each benchmark's `k3s/` folder in
  [demo-services](https://github.com/aosedge/demo-services/tree/main/benchmark)), not through AosCore's
  aos-signer/cloud/subject pipeline; where a chapter has no meaningful k3s equivalent (e.g. it measures an
  AosCore-internal component), that is noted instead of forced into a fit.
* Metrics are collected via the same VictoriaMetrics/Grafana stack the AosCore and Podman benchmarks use -
  `cgroup-exporter` and the dashboard are both runtime-agnostic (see
  [meta-aos benchmark instrumentation](benchmark.md)), so the same panels show every runtime's data.
* Test results are collected and analyzed via Grafana dashboards. The dashboard definition is
  [benchmark.json](../docker/grafana/dashboards/benchmark.json); importing it reproduces every panel
  referenced below.
* Every chapter records its full execution steps, regardless of whether they match the benchmark plan. Where
  execution deviates from the plan (e.g. a different tool, parameter, or execution order), the deviation and its
  rationale are recorded alongside that chapter's results.

## Disclaimer

The following are not covered in this document, as they are generic information and procedures:

* generic explanation of Kubernetes/k3s concepts and terminology (pods, deployments, services, CNI, etc.).

**k3s version and topology**: the unit runs k3s v1.28.7+k3s1 (`meta-virtualization` recipe `k3s`) as a single node that
acts as both server and agent. Its containers are run by k3s's own embedded containerd, not by Podman - the two
runtimes are installed side by side on the unit but never run a test at the same time. The k3s service is installed
but not enabled at boot, so a k3s run starts it explicitly (see "k3s server" below) and Podman/AosCore runs are not
affected by an idle Kubernetes control plane.

**Unit of deployment**: an item is a Deployment and an instance is one of its replicas, i.e. a pod of its own. This
differs from the other two runtimes and is described in "Deployment model" below.

**Cluster components**: `traefik`, `servicelb`, `metrics-server`, `local-storage` and the network policy controller
are disabled - no benchmark uses them, and each would otherwise add idle CPU/RAM load to the unit. CoreDNS stays
enabled, since every "service name" resolution in the network chapters goes through it.

**Image pulls**: k3s starts its kubelet with `serialize-image-pulls=false`, so the images of every pod created at
the same time are pulled concurrently (like podman-compose 1.6.0 in the Podman benchmark, unlike AosCore). Every
chapter deploys through `kubectl apply`, so this shapes every measurement that involves pulling more than one
image, not just Operational Speed.

**SELinux**: the Aos image runs SELinux in enforcing mode, and the refpolicy has no rules for k3s. The `k3s` binary
is built with text relocations, which need executable memory (`execmem`) that the policy denies, so it can't even
load, and k3s's containerd is also denied reading its `config.toml` under `/var/lib/rancher` (labeled `var_lib_t`).
Every k3s run therefore executes with SELinux in permissive mode (see "k3s server" below), unlike the AosCore and
Podman runs, which are enforcing. Permissive mode enforces nothing but still logs denials, so
it adds a little audit-logging load; that difference is part of what the k3s results include.

**Container networking**: pods use k3s's default flannel CNI, and `kube-proxy` programs `iptables` (the legacy
backend the image is built with) for Services. All benchmark pods run on the same node, so pod-to-pod traffic stays
on the node's local bridge. The pods' interfaces (`cni0`, `flannel.1`) are allowed through the Aos firewall's
default-drop forward chain by the image itself when built with the `benchmark` `DISTRO_FEATURES` - without that, pods
couldn't reach each other or anything routed through the unit.

### Deployment model

Every chapter deploys one **item** as one Deployment, and each **instance** of it is one **replica**, which
Kubernetes always runs as a separate **pod**: instances are scaled with `replicas`, and there is one pod per instance.

| | AosCore | Podman | k3s |
| --- | --- | --- | --- |
| Item | deployable item, up to 64 instances | a service of the compose file | Deployment |
| Instance | a container run by `crun`, no sandbox | a container with its own `conmon` (about 0.5 MB PSS), all containers of a compose project in one pod without an infra container | a pod: a `pause` container plus the benchmark container, with its own `containerd-shim` process |
| Network | own network per instance | own network per container | own pod IP per instance |

Why one pod per instance and not all the instances of an item as containers of one pod: Kubernetes has no way to
scale a container inside a pod, only pods, so replicas are pods. Packing an item's instances into one pod would also
change what the tests measure: the containers of a pod share one network namespace (traffic between them would go over
loopback instead of the network being measured), start one after another and can only be stopped together with the
pod.

What this means for the results: a k3s instance carries more per-instance overhead than an AosCore or a Podman one -
the `pause` container (about 0.5 MB resident) and the shim (about 11 MB resident, measured on the unit), in addition to
the benchmark container (about 7 MB). That cost is part of the k3s result, and it is visible in the panels: the
`pause` containers show up among the container instances, and the shims are in the `k3s.service` instance (see "CPU/RAM
used by orchestrator components"). It is a difference between the runtimes, not a measurement error.

Limits of the deployment model:

* Pod count. The kubelet allows 110 pods per node and the controller manager gives a node a `/24` pod subnet (about
  254 addresses), which is less than the 128 and 256 instance tiers need. The image's `config.yaml` sets `max-pods=300`
  and a `/23` node subnet (about 510 addresses); the subnet size is only applied to a node that has none yet, i.e. a
  new cluster.
* Memory. A pod takes about 19 MB of resident memory (the shim, the `pause` container and the benchmark container; an
  upper bound, since shared pages are counted in each process) and `k3s` itself about 0.5 GB. The 128 and 256 instance
  tiers therefore need about 2.9 GB and 5.4 GB of RAM, so the unit under test must have clearly more memory than that;
  a unit with 2 GB of RAM and no swap runs out of memory and stops responding at 256 pods.

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

The network chapters scale their clients with `NUM_INSTANCES`, and the `-n` of the native `iperf3-servers.sh` and
`sockperf-servers.sh` takes that same client count, so set `NUM_INSTANCES` in the session on the unit or the external
host that runs them as well.

### Unit provisioning

The unit under test is provisioned the same way [Benchmark Execution (AosCore)](benchmark_execution_aos.md)
requires (`aos-prov provision -u <NODE_IP>`), even though this document never deploys anything through
AosCore's own pipeline: provisioning is what creates the LUKS-encrypted `aos` volume group on disk. The
"Container disk I/O" chapter mounts two paths straight from that provisioned layout - `/var/aos/storages`
(encrypted) and `/var/aos/common-data` (unencrypted) - into its pods as `hostPath` volumes, so without provisioning
first those paths don't exist.

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

### k3s server

The image ships `/etc/rancher/k3s/config.yaml` (from `meta-aos/recipes-containers/k3s`), which disables the
components no benchmark uses (see Disclaimer), so no server configuration is needed. `k3s` and its `kubectl` and
`crictl` links are installed in `/usr/bin`.

Start the server on the unit with SELinux in permissive mode (see Disclaimer) and wait until the node is `Ready`:

```bash
setenforce 0
systemctl start k3s
kubectl get nodes
```

`kubectl` reads `/etc/rancher/k3s/k3s.yaml` (the image links it to `/var/lib/rancher/k3s/k3s.yaml`, since the rootfs
is read-only), so no further setup is needed to run it as `root`.

To return the unit to its no-Kubernetes state (for a Podman or AosCore run), stop the service and every process k3s
left behind, and put SELinux back into enforcing mode:

```bash
systemctl stop k3s
k3s-killall.sh
setenforce 1
```

#### System images

k3s runs every pod inside a `pause` sandbox container, and DNS inside the cluster through CoreDNS, so it needs the
`rancher/mirrored-pause` and `rancher/mirrored-coredns-coredns` images. They are pulled from Docker Hub the first
time k3s starts, so the unit needs internet access for that first start, and stay cached in k3s's containerd after
it. Run the first start, and wait for the `coredns` pod to be `Running` (`kubectl get pods -A`), before any
measurement, so a pull never falls inside one:

```bash
kubectl -n kube-system get pods
```

### Container registry

The local container registry from the Podman document is reused unchanged: every benchmark image is pulled from it,
so a scenario's "Download"-type metric measures a real network transfer, and the same images the AosCore and Podman
runs use are the ones k3s deploys (see [Container registry](benchmark_execution_podman.md#container-registry) for
how to start it).

It's plain HTTP, and k3s's containerd refuses the connection unless the registry is declared as an HTTP endpoint
(`failed to do request: ... http: server gave HTTP response to HTTPS client`, shown as `ErrImagePull`/
`ImagePullBackOff` on the pod). The registry address is specific to the setup, so unlike `config.yaml` this file
isn't part of the image: on the unit, the rootfs is read-only by default, so remount it read-write first, then create
`/etc/rancher/k3s/registries.yaml` before starting k3s (or restart it afterwards - k3s only reads this file on
startup):

```bash
mount -o remount,rw /
```

```yaml
mirrors:
  "<registry-host>:5000":
    endpoint:
      - "http://<registry-host>:5000"
```

### Grafana

Grafana is set up exactly as in [Benchmark Execution (Podman)](benchmark_execution_podman.md#grafana) - it is
runtime-agnostic and points at the main node under test.

### Container images

The benchmark images are the ones built and pushed for the Podman benchmark (see
[Container images](benchmark_execution_podman.md#container-images)) - k3s pulls the same tags from the same
registry, so nothing is rebuilt for it. Per-instance differences the Podman compose files carry (e.g. the
`SERVICE_ID`-based client indexing) are expressed in each benchmark's `k3s/` manifests instead of in the images.

## Troubleshooting

For anything not listed below, see [Benchmark Execution (AosCore)](benchmark_execution_aos.md#troubleshooting) -
VictoriaMetrics/Grafana are the same instance/stack whichever runtime is under test.

* **The node never becomes `Ready`, or `kubectl` can't connect**: k3s writes everything to the journal:

  ```bash
  journalctl -u k3s --no-pager | tail -50
  ```

* **A pod stays in `ErrImagePull`/`ImagePullBackOff`**: the reason is in the pod's events:

  ```bash
  kubectl describe pod <pod>
  ```

  `http: server gave HTTP response to HTTPS client` means `registries.yaml` is missing or was created after k3s
  started - see "Container registry" above.

* **A pod stays `Pending`**: `describe pod` also shows why (typically an unsatisfiable resource request or a
  node that isn't `Ready` yet).

* **Leftovers from a previous run**: delete the workload and wait for its pods to actually terminate before starting
  the next measurement, otherwise the old pods' load overlaps it:

  ```bash
  kubectl delete -f <manifest> --wait --cascade=foreground
  kubectl get pods -A
  ```

  A plain `--wait` returns while the pods are still terminating; `--cascade=foreground` waits for them.

* **k3s doesn't start, or `k3s.service` keeps restarting**: with SELinux in enforcing mode the policy denies k3s (the
  journal shows `cannot make segment writable for relocation: Permission denied`, or containerd exits right after
  starting). Check the mode and the denials, then switch to permissive as the "k3s server" step says:

  ```bash
  getenforce
  grep denied /var/log/audit/audit.log | tail
  setenforce 0
  ```

* **Service names don't resolve, or the network clients log `Server ... not ready`, right after k3s started**: CoreDNS
  is not ready yet. Wait until it is `1/1 Running`; the clients retry on their own, so this only delays a run:

  ```bash
  kubectl -n kube-system get pods
  ```

* **A diskio pod stays in `ContainerCreating`**: `kubectl describe pod` shows a `FailedMount` event for
  `/var/aos/storages` or `/var/aos/common-data`. The `hostPath` volumes require both directories to exist, so the unit
  isn't provisioned (see "Unit provisioning").
* **`kubectl logs -l ...` for many pods fails with a concurrency limit**: it follows at most 5 pods at a time unless
  `--max-log-requests` is raised, as the chapters' commands do.
* **The unit stops responding while many pods start**: it ran out of memory, since every pod costs about 19 MB (see
  "Deployment model"). Use a unit with enough RAM for the tier, or a smaller tier.
* **The volume fills up between diskio tiers**: every instance leaves a `diskio-*.dat` file of 16 MiB behind, on
  `/var/aos/storages` or `/var/aos/common-data`, so remove them after each tier (the chapter's teardown step does):

  ```bash
  df -h /var/aos/storages /var/aos/common-data
  rm -f /var/aos/storages/diskio-*.dat /var/aos/common-data/diskio-*.dat
  ```

* **A native `iperf3`/`sockperf` server is still running after a network test**: the servers are started in the
  foreground by `iperf3-servers.sh`/`sockperf-servers.sh`, so stop them with Ctrl+C in that session. If they were
  started in the background, the unit's BusyBox has no `pkill`: find and stop them by PID.

  ```bash
  ps -eo pid,comm | awk '$2=="iperf3" || $2=="sockperf" {print $1}'
  kill <pid>...
  ```

* **Everything k3s started needs to go** (before an AosCore or Podman run, or after a failed one):
  `systemctl stop k3s && k3s-killall.sh`.

## Result aggregation

See [Benchmark Execution (AosCore)](benchmark_execution_aos.md#result-aggregation) - the mean-across-instances
convention applies unchanged, since all versions push the exact same `checkpoint_event`/`benchmark_result` shape to
the same VictoriaMetrics.

## Repetition

See [Benchmark Execution (AosCore)](benchmark_execution_aos.md#repetition) - the one-run-per-configuration policy
applies unchanged.

## Operational Speed

### Install new deployable items

Goal: measure the different operational time intervals during deploying new deployable items to the unit - same
goal as the AosCore version, adapted to what k3s actually exposes as separately observable phases.

Deployable item: `benchmark-timing-1` .. `benchmark-timing-16`, 16 separate images each with its own
independently-random 16 MiB payload (the images built for the Podman benchmark, see
[Container images](benchmark_execution_podman.md#container-images)) - the same N-separate-items shape the AosCore
version uses (not instance-count scaling of one item), so a batch's total deployment size scales with item count
the same way (16/128/256 MiB at 1/8/16 items). Each item is one Deployment with one replica. See the Disclaimer's
image pull note - "Total" below is dominated by the pull step for a cold N-item batch, so it's especially sensitive
to it.

Metrics:

* **Total** - time from issuing the deploy command until every item's own instance has started. This is the only
  metric measured: AosCore's Download/Install/Prepare/Network breakdown has no k3s equivalent - `kubectl apply`
  hands the objects to the API server, and pulling, unpacking, preparing, networking and starting a pod all happen
  inside the kubelet and containerd without phase boundaries to checkpoint the way `aos-sm.service` does.

Checkpoint/timing used to measure it:

| Metric | Measured as |
| --- | --- |
| Total | `time_event.py` wrapping `kubectl apply` followed by `kubectl wait --for=condition=Available` (the pods pull every item's image themselves, same as AosCore's own deploy step would), cross-checked against the max (latest) per-item `checkpoint_event(event="Start")` timestamp (`source="Instance: timing-<pod-name>"`) - the same per-instance checkpoint the AosCore version's own "Total"/"Start" rows use |

Execution steps:

1. With no pods running, capture the idle CPU/RAM used by the orchestrator components (see "CPU/RAM used by
   orchestrator components" below) - unlike Podman, k3s has its own always-running control plane, so at idle it
   already shows a real baseline.
2. Set up working directories, once for this whole test - not repeated per tier, since steps 3-9 below all stay
   inside them. On the build/push host:

   ```bash
   cd benchmark/timing/k3s
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/timing
   cd ~/benchmark/timing
   ```

3. Render `manifest.yaml` for `NUM_SERVICES` items on the build/push host (1, then 8, then 16 per step 10 - each tier is
   a fresh, independent batch of `NUM_SERVICES` items, not additive on top of the previous tier's, matching the AosCore
   version's own per-tier `--version` bump). The registry host has to be rendered into the image references, since
   Kubernetes doesn't expand environment variables in a manifest:

   ```bash
   ../../scripts/create_services.py --num-services ${NUM_SERVICES} --registry-host ${REGISTRY_HOST}
   ```

4. Deploy the rendered file to the unit - only `manifest.yaml` itself needs to be there, not the rest of this
   checkout:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/timing/manifest.yaml
   ```

5. On the unit, time the deploy, letting the pods pull and start every item themselves. `kubectl apply` returns as
   soon as the API server accepts the objects, so the timed command also waits until every Deployment is available:

   ```bash
   time_event.py --name "timing deploy ${NUM_SERVICES} items" --source k3s -- sh -c \
       "kubectl apply -f manifest.yaml && kubectl wait --for=condition=Available deployment --all --timeout=600s"
   ```

6. Wait for every item's own `checkpoint_event` to appear in the Grafana Events view.
7. Calculate Total from the max per-item `Start` checkpoint minus when step 5's `kubectl apply` was issued
   (`time_event.py` already reports step 5's own wall-clock time as a lower bound; the checkpoint-based figure is
   the more AosCore-comparable one - see "Install new deployable items" in the AosCore version for why).
8. Capture the CPU/RAM used by the orchestrator components (see below).
9. Tear down and remove the images, so the next tier redownloads them from scratch rather than reusing what's
   already cached locally - otherwise only the first tier run would measure a real download. The delete waits for
   the pods to be gone (`--cascade=foreground`), so the next tier doesn't start on top of terminating pods:

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   crictl rmi $(crictl images | awk '/benchmark-/ {print $1":"$2}')
   ```

   `crictl` prints a warning about its default endpoints on every call; it finds k3s's containerd socket anyway.

10. Repeat from step 3 with `NUM_SERVICES` set to 8, then 16.

### Install cached deployable items

Goal: measure the different operational time intervals during deploying cached deployable items to the unit - same
goal as the AosCore version, adapted the same way "Install new deployable items" above is.

Deployable item: same `benchmark-timing-1` .. `benchmark-timing-16` images used in "Install new deployable items"
above, one Deployment with one replica each.

Cached deployable item: an image already present in k3s's containerd image store from a prior pull, but with no
running pod for it - unlike "Install new deployable items", which removes every timing image after each tier
specifically to force a cold pull, this chapter deliberately leaves them cached, so the manifest's
`imagePullPolicy: IfNotPresent` makes the kubelet skip the pull entirely and only create and start the pod. With no
pull step, this chapter's "Total" doesn't depend on the concurrent image pulls the Disclaimer describes.

Metrics and checkpoint/timing are the same as in "Install new deployable items" above.

Prerequisites:

1. Each of the `NUM_SERVICES` items under test for a given tier has previously been pulled onto the unit at least once,
   with no pod currently running for it - step 5 below does this explicitly before the measured run, so this isn't a
   separate manual setup step.

Execution steps:

1. With no pods running, capture the idle CPU/RAM used by the orchestrator components (see "CPU/RAM used by
   orchestrator components" below).
2. Set up working directories, once for this whole test - not repeated per tier, same as "Install new deployable
   items" step 2. On the build/push host:

   ```bash
   cd benchmark/timing/k3s
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/timing
   cd ~/benchmark/timing
   ```

3. Render `manifest.yaml` for `NUM_SERVICES` items on the build/push host:

   ```bash
   ../../scripts/create_services.py --num-services ${NUM_SERVICES} --registry-host ${REGISTRY_HOST}
   ```

4. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/timing/manifest.yaml
   ```

5. On the unit, warm the cache: create every item once, untimed, wait until it is available, then delete the pods
   again without removing the images - this is what makes the next step's images "cached" rather than "new":

   ```bash
   kubectl apply -f manifest.yaml
   kubectl wait --for=condition=Available deployment --all --timeout=600s
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

6. Time the actual measured deploy - with every image already cached, the kubelet only creates and starts each pod,
   no pull involved:

   ```bash
   time_event.py --name "timing deploy ${NUM_SERVICES} cached items" --source k3s -- sh -c \
       "kubectl apply -f manifest.yaml && kubectl wait --for=condition=Available deployment --all --timeout=600s"
   ```

7. Wait for every item's own `checkpoint_event` to appear in the Grafana Events view.
8. Calculate Total from the max per-item `Start` checkpoint minus when step 6's `kubectl apply` was issued.
9. Capture the CPU/RAM used by the orchestrator components (see below).
10. Tear down, but leave the images cached this time (no `crictl rmi`) - a subsequent tier only adds the items it
    needs beyond what a smaller tier already cached. The delete waits for the pods to be gone
    (`--cascade=foreground`), so the next tier doesn't start on top of terminating pods:

    ```bash
    kubectl delete -f manifest.yaml --wait --cascade=foreground
    ```

11. Repeat from step 3 with `NUM_SERVICES` set to 8, then 16.

### Start/stop already installed instances

Goal: measure k3s start/stop time for a fixed set of already-installed instances - same goal as the AosCore version,
adapted to what Kubernetes actually offers: it has no operation that stops or starts an already-created container,
because pods are only ever created and deleted. The equivalent is scaling the Deployment to zero and back: the
Deployment object and the images already on the unit are "installed", and the instances (pods) are what stops and
starts. This is a deviation from the other two runtimes, and it makes the k3s numbers include more work: stopping
deletes each pod, its `pause` sandbox and its network, and starting creates them again, where `podman-compose stop`
and `start` and AosCore only stop and start containers that already exist.

Deployable item: same `benchmark-timing` image(s) as "Install new deployable items" above, scaled via the
Deployment's `replicas`, with each replica being a pod (see "Deployment model"). This document mirrors AosCore's own
64-instances-per-item cap so item/instance counts stay directly comparable between the versions:

| Instances | Items | Instances/item  |
|:---------:|:-----:|:---------------:|
|     1     |   1   |        1        |
|     8     |   1   |        8        |
|    16     |   1   |       16        |
|    64     |   1   |       64        |
|    128    |   2   |       64        |
|    256    |   4   |       64        |

The 128 and 256 instance tiers need more memory than a small unit has (see "Deployment model").

Metrics:

* **Start instances** - time from issuing the scale-up until every instance has started;
* **Stop instances** - time to issue the scale-down and for every pod to be gone.

Checkpoint/timing used to measure each:

| Metric | Measured as |
| --- | --- |
| Start instances | `time_event.py` wrapping `kubectl scale` to the item's instance count followed by a wait until every Deployment reports that many available replicas, cross-checked against the max (latest) per-instance `checkpoint_event(event="Start")` timestamp (`source="Instance: timing-<pod-name>"`) - the same per-instance checkpoint "Install new deployable items"' Total uses |
| Stop instances | `time_event.py` wrapping `kubectl scale` to zero followed by a wait until every pod is deleted, taking its own reported wall-clock elapsed time. `benchmark-timing` pushes no `Stop` checkpoint on shutdown (only `Start`, on launch), so there is no checkpoint-based cross-check for it |

The start wait is for an exact replica count (`.status.availableReplicas` equal to the instance count) and not for the
Deployment's `Available` condition: Kubernetes defines `Available` as minimum availability, which a rolling-update
Deployment can satisfy with some replicas still missing, and this measurement has to end when every instance is up.

`benchmark-timing` installs no `SIGTERM` handler, and as PID 1 of its container the kernel then ignores `SIGTERM`
entirely - so stopping a pod would wait out its whole termination grace period before `SIGKILL`, and "Stop
instances" would measure that grace period instead of stopping. The manifest therefore sets
`shareProcessNamespace: true`: the pod's `pause` container is then PID 1 and the benchmark container is not, so the
signal terminates it at once. The termination grace period is left as is.

Prerequisites:

1. No pods are currently running for the `timing` items on the unit (clean slate) - matching the AosCore version's own
   "test subject contains no deployable items" prerequisite.

Execution steps:

1. With no pods running, capture the idle CPU/RAM used by the orchestrator components (see "CPU/RAM used by
   orchestrator components" below).
2. Set up working directories, once for this whole test - not repeated per tier, same as "Install new deployable
   items" step 2. On the build/push host:

   ```bash
   cd benchmark/timing/k3s
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/timing
   cd ~/benchmark/timing
   ```

3. Render `manifest.yaml` for the current tier on the build/push host, with `NUM_INSTANCES` set to the table's
   Instances/item column and `NUM_SERVICES` set to its Items column (`NUM_SERVICES` is 1 below the 128 tier):

   ```bash
   ../../scripts/create_services.py --num-services ${NUM_SERVICES} --num-instances ${NUM_INSTANCES} \
       --registry-host ${REGISTRY_HOST}
   ```

4. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/timing/manifest.yaml
   ```

5. On the unit, deploy the instances, untimed - this chapter measures stopping/starting an already-running set, not
   the initial deploy (see "Install new deployable items" for that):

   ```bash
   kubectl apply -f manifest.yaml
   kubectl wait --for=jsonpath='{.status.availableReplicas}'=${NUM_INSTANCES} deployment --all --timeout=600s
   ```

6. Wait for every instance to be successfully started.
7. Time stopping every instance:

   ```bash
   time_event.py --name "timing stop $((NUM_SERVICES * NUM_INSTANCES)) instances" --source k3s -- sh -c \
       "kubectl scale deployment --all --replicas=0 && kubectl wait --for=delete pod --all --timeout=600s"
   ```

8. Wait for every instance to be confirmed stopped (`kubectl get pods` shows none).
9. Time starting every instance back up:

   ```bash
   time_event.py --name "timing start $((NUM_SERVICES * NUM_INSTANCES)) instances" --source k3s -- sh -c \
       "kubectl scale deployment --all --replicas=${NUM_INSTANCES} && \
        kubectl wait --for=jsonpath='{.status.availableReplicas}'=${NUM_INSTANCES} deployment --all --timeout=600s"
   ```

10. Wait for every instance's own `checkpoint_event` to appear in the Grafana Events view.
11. Calculate Start instances from the max per-instance `Start` checkpoint minus when step 9's `kubectl scale` was
    issued; Stop instances is step 7's own reported wall-clock elapsed time (see above for why no checkpoint-based
    figure exists for it).
12. Capture the CPU/RAM used by the orchestrator components (see below).
13. Tear down and remove the images, same as "Install new deployable items" step 9, so the next tier starts clean:

    ```bash
    kubectl delete -f manifest.yaml --wait --cascade=foreground
    crictl rmi $(crictl images | awk '/benchmark-/ {print $1":"$2}')
    ```

14. Repeat from step 3 for 8, 16, 64, 128, 256 instances, setting `NUM_SERVICES` and `NUM_INSTANCES` to the
    table's Items and Instances/item columns for each tier.

## Container disk I/O

Same [diskio](https://github.com/aosedge/demo-services/tree/main/benchmark/diskio) benchmark service and the
exact same `diskio_benchmark.py` script the AosCore version deploys (the image is the one the Podman benchmark
builds from the same `../src/diskio_benchmark.py`, see
[Container images](benchmark_execution_podman.md#container-images)) - see the AosCore chapter for the
four-`fio`-job sequence, metrics, and `checkpoint_event`/`benchmark_result` shape, all unchanged since the script
itself doesn't know which runtime started it.

`TEST_DIR` still selects the storage backend, but instead of AosCore's own storage resource abstraction,
`benchmark/diskio/k3s/manifest.yaml.in` mounts the real host paths directly as `hostPath` volumes -
`/var/aos/storages` as `/storage` (encrypted) and `/var/aos/common-data` as `/common` (unencrypted) are both always
mounted, so switching backends is just changing `TEST_DIR`, matching the AosCore version's own `--test-dir`-driven
behavior. Both paths must already exist on the unit - see "Unit provisioning" in Prerequisites for why. The volumes
are declared with `type: Directory`, so on a unit that is not provisioned the pod fails to start with a clear event
instead of containerd silently creating the directory on the root filesystem.

How the manifest differs from the compose file of the Podman chapter:

* It is a Deployment whose replicas are the instances, one pod per instance (see "Deployment model"). It is not a Job:
  `diskio_benchmark.py` runs its jobs once and then keeps running, so that its logs stay available and it isn't
  restarted in a loop, which means a pod never completes and a Job would never finish. A run is over when an
  instance's log shows `All jobs finished`.
* `fio`'s `libaio` engine needs a syscall that a runtime-default seccomp profile blocks, which the compose file
  handles with `seccomp=unconfined`. k3s doesn't apply a seccomp profile to a pod that doesn't ask for one, but the
  manifest states `Unconfined` explicitly so that doesn't depend on the cluster's default.
* `diskio_benchmark.py` installs no `SIGTERM` handler, and as PID 1 of its container the kernel then ignores
  `SIGTERM`, so deleting a pod would wait out its 30 s termination grace period. The manifest sets
  `shareProcessNamespace: true`, which makes the pod's `pause` container PID 1 instead, and deleting takes about a
  second.
* The `label=disable` setting of the compose file isn't needed: k3s runs with SELinux in permissive mode (see the
  Disclaimer).

Prerequisites:

1. No pods are currently running for the `diskio` Deployment on the unit (clean slate) - matching the AosCore
   version's own "test subject contains no deployable items" prerequisite.

### Encrypted storage

Execution steps:

1. Set up working directories, once for this whole test - not repeated per tier. On the build/push host:

   ```bash
   cd benchmark/diskio/k3s
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/diskio
   cd ~/benchmark/diskio
   ```

2. Render `manifest.yaml` for one instance on the encrypted backend on the build/push host:

   ```bash
   ../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-dir /storage --registry-host ${REGISTRY_HOST}
   ```

3. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/diskio/manifest.yaml
   ```

4. On the unit, deploy the instance(s):

   ```bash
   kubectl apply -f manifest.yaml
   ```

5. Wait for the instance(s) to finish all four jobs (`All jobs finished` in each instance log, `Stop` checkpoint
   event in the Grafana Events view for each instance). The number of instances that have finished is:

   ```bash
   kubectl logs -l app=diskio --prefix --max-log-requests=64 | grep -c "All jobs finished"
   ```

6. Read the sequential throughput/latency and random IOPS/latency (avg/p99) `benchmark_result` samples from
   Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down, but leave the image cached - unlike timing's N distinct images, there's only ever this one
   `benchmark-diskio` image regardless of tier or backend, so there's nothing to force a fresh pull of; it's only
   removed once, after every diskio tier in both this chapter and the other backend's is done (see the last step).
   Every instance also leaves its 16 MiB data file behind on the volume, named after its pod, so remove them too or
   they accumulate across tiers (64 instances leave 1 GiB):

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   rm -f /var/aos/storages/diskio-*.dat
   ```

9. Repeat from step 2 for 8, 16, 64 instances, updating `NUM_INSTANCES`.
10. Once every tier of this chapter is done, remove the image:

    ```bash
    crictl rmi $(crictl images | awk '/benchmark-/ {print $1":"$2}')
    ```

### Unencrypted storage

Execution steps:

1. Set up working directories, once for this whole test - not repeated per tier. On the build/push host:

   ```bash
   cd benchmark/diskio/k3s
   ```

   On the unit, open one session for the rest of this test and `cd` there once:

   ```bash
   mkdir -p ~/benchmark/diskio
   cd ~/benchmark/diskio
   ```

2. Render `manifest.yaml` for one instance on the unencrypted backend on the build/push host:

   ```bash
   ../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-dir /common --registry-host ${REGISTRY_HOST}
   ```

3. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/diskio/manifest.yaml
   ```

4. On the unit, deploy the instance(s):

   ```bash
   kubectl apply -f manifest.yaml
   ```

5. Wait for the instance(s) to finish all four jobs (`All jobs finished` in each instance log, `Stop` checkpoint
   event in the Grafana Events view for each instance). The number of instances that have finished is:

   ```bash
   kubectl logs -l app=diskio --prefix --max-log-requests=64 | grep -c "All jobs finished"
   ```

6. Read the sequential throughput/latency and random IOPS/latency (avg/p99) `benchmark_result` samples from
   Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down, but leave the image cached - unlike timing's N distinct images, there's only ever this one
   `benchmark-diskio` image regardless of tier or backend, so there's nothing to force a fresh pull of; it's only
   removed once, after every diskio tier in both this chapter and the other backend's is done (see the last step).
   Every instance also leaves its 16 MiB data file behind on the volume, named after its pod, so remove them too or
   they accumulate across tiers (64 instances leave 1 GiB):

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   rm -f /var/aos/common-data/diskio-*.dat
   ```

9. Repeat from step 2 for 8, 16, 64 instances, updating `NUM_INSTANCES`.
10. Once every tier of this chapter is done, remove the image:

    ```bash
    crictl rmi $(crictl images | awk '/benchmark-/ {print $1":"$2}')
    ```

## Network

Same deployable items as [Benchmark Execution (AosCore)](benchmark_execution_aos.md#network) (`benchmark-network-*`
server/peer and client pairs, the images the Podman benchmark builds and pushes), run with `kubectl` instead of
AosCore's deployment pipeline. Each scenario's `manifest.yaml.in` bundles both the server/peer and the client pods.
For "service to unit"/"service to external host" the bundled server/peer is started too but goes unused (the AosCore
version doesn't deploy it, since the server side there is a native process) - it only sits idle. `create_services.py`
renders `manifest.yaml` on the build/push host; only that rendered file needs to reach the unit, into a folder
mirroring this checkout's own path (e.g. `~/benchmark/network/bandwidth/manifest.yaml`) so different scenarios' files
never collide - `kubectl` itself then runs on the unit.

### Bandwidth

Goal: measure the throughput available to a pod through the k3s network, for TCP and UDP in both directions, together
with UDP jitter and packet loss, across the same three paths as the AosCore version - service to service, service to
unit, and service to an external host - and how that throughput scales with the number of concurrent client
instances.

Deployable items: [bandwidth](https://github.com/aosedge/demo-services/tree/main/benchmark/network/bandwidth)
server and client images, `benchmark-network-bandwidth-server` and `benchmark-network-bandwidth-client` (see
[Container images](benchmark_execution_podman.md#container-images)), the same
`bandwidth_server.py`/`bandwidth_client.py` the AosCore version deploys.

On start, each client instance runs four `iperf3` tests in a row against `TARGET`, each for `DURATION` seconds:
`tcp_up`, `tcp_down` (`-R`), `udp_up` (`-u`), `udp_down` (`-u -R`). Every test's full result is logged; the
throughput, and for the UDP tests loss and jitter, are pushed as `benchmark_result` samples to VictoriaMetrics,
bracketed by a `checkpoint_event` Start/Stop pair for the whole run - unchanged from the AosCore version, see its
chapter for the details. `TARGET` selects the path (`--test-host`) and `UDP_BANDWIDTH` (`--udp-bandwidth`, `80M` by
default) the UDP rate, exactly as there.

`iperf3 -c` resolves a Kubernetes service name the same as a real hostname, so the "service to service" path needs
no adaptation: `TARGET=bandwidth-server` is the server's own service name, resolved by CoreDNS.

**Scaling clients**: AosCore gives each instance of a scaled service a sequential `AOS_INSTANCE_INDEX`, so `N`
concurrent clients each dial their own `bandwidth_server.py`-run `iperf3` port (5201 + index). The replicas of a
Deployment have random names and no such number, so the clients are the replicas of a StatefulSet instead, whose pod
names end in an ordinal (`bandwidth-client-0`, `bandwidth-client-1`, ...) that is exactly the 0-based index. The
client's command derives the `SERVICE_ID` the image's entrypoint expects from that ordinal, so the image is the same
one the Podman benchmark uses. The clients are started all at once (`podManagementPolicy: Parallel`) and are scaled
with `NUM_INSTANCES` (`--num-instances`), which also sets the server's `NUM_INSTANCES` to match, so it opens exactly
that many ports.

**Headless services**: both services are headless (`clusterIP: None`), so a name resolves straight to the pod's IP and
the traffic goes pod to pod, like container to container in the other runtimes. A normal (ClusterIP) service would
add kube-proxy's address translation to every packet, which is not part of what is being compared.

Metrics:

* `tcp_up`/`tcp_down`: throughput (Mbps);
* `udp_up`/`udp_down`: throughput (Mbps), loss (%), jitter (ms);
* System CPU - whole-host max CPU usage (%) for the duration of the run.

For more than one instance, every metric above is aggregated as described in "Result aggregation" above.

Prerequisites:

1. No pods are currently running for the `bandwidth` server and clients on the unit (clean slate).

The three paths below share the same working directories, on both hosts - set them up once, they're not repeated per
path or per instance count. On the build/push host:

```bash
cd benchmark/network/bandwidth/k3s
```

On the unit, open one session for the rest of this chapter and `cd` there once:

```bash
mkdir -p ~/benchmark/network/bandwidth
cd ~/benchmark/network/bandwidth
```

#### Service to service

Execution steps:

1. Render `manifest.yaml` for the service-to-service path for one client instance on the build/push host:

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host bandwidth-server --registry-host ${REGISTRY_HOST}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/network/bandwidth/manifest.yaml
   ```

3. On the unit, deploy the server and client instance(s):

   ```bash
   kubectl apply -f manifest.yaml
   ```

4. Wait for the client instance(s) to finish all four tests (`All tests finished` in each client pod log, `Stop`
   checkpoint event in the Grafana Events view for each client instance). The number of clients that have finished is:

   ```bash
   kubectl logs -l app=bandwidth-client --prefix --max-log-requests=64 | grep -c "All tests finished"
   ```

5. Read the `tcp_up`/`tcp_down` throughput and `udp_up`/`udp_down` throughput/loss/jitter `benchmark_result`
   samples from Grafana. For more than one instance, average each metric across all instances' samples.
6. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
7. Tear down, leaving the images cached (they're only removed once, at the end of the DNS chapter):

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

8. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES`.

#### Service to unit

With `USE_DHCP=yes` the unit's uplink interface carries two addresses: the static `10.0.0.100/24`, used for the
unit's own services, and the DHCP-assigned address, which holds the default route. `NODE_IP=10.0.0.100` is
therefore correct for every "service to unit" scenario on both the DHCP and the static deployment. The traffic
between a pod and its own node never leaves the unit, so it never reaches a physical network.

Execution steps:

1. Render `manifest.yaml` for the service-to-unit path for one client instance on the build/push host, using the
   unit's own network address as `--test-host` (`NODE_IP` is `10.0.0.100` by default on the main node):

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host ${NODE_IP} --registry-host ${REGISTRY_HOST}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/network/bandwidth/manifest.yaml
   ```

3. On the unit, start one native `iperf3` server per instance, bound to the unit's address, using
   `iperf3-servers.sh` ([meta-aos](https://github.com/aosedge/meta-aos) `recipes-support/benchmark-network`),
   installed at `/opt/aos/benchmark/iperf3-servers.sh` on the `benchmark` `DISTRO_FEATURES`. First confirm the
   port(s) are free - a leftover `iperf3` process from an earlier run. It runs in the foreground, so start it in a
   second session on the unit (or in the background):

   ```bash
   /opt/aos/benchmark/iperf3-servers.sh -b ${NODE_IP} -n ${NUM_INSTANCES}
   ```

4. On the unit, deploy the client instance(s). The bundled server pod is started too but isn't used for this path,
   since the server side here is the native one from step 3:

   ```bash
   kubectl apply -f manifest.yaml
   ```

5. Wait for the client instance(s) to finish all four tests (`All tests finished` in each client pod log, `Stop`
   checkpoint event in the Grafana Events view for each client instance):

   ```bash
   kubectl logs -l app=bandwidth-client --prefix --max-log-requests=64 | grep -c "All tests finished"
   ```

6. Read the `tcp_up`/`tcp_down` throughput and `udp_up`/`udp_down` throughput/loss/jitter `benchmark_result`
   samples from Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down the pods:

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

9. Stop the native `iperf3` server(s) started on the unit in step 3.
10. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES` and the `-n` passed to
    `iperf3-servers.sh` in step 3.

#### Service to external host

Execution steps:

1. Render `manifest.yaml` for the service-to-external path for one client instance on the build/push host, using an
   external host's address on the unit's local network as `--test-host` (`HOST_IP` is the IP behind the unit,
   accessible from the unit; on an AosCore VM it is `10.0.0.1` by default):

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host ${HOST_IP} --registry-host ${REGISTRY_HOST}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/network/bandwidth/manifest.yaml
   ```

3. On the external host, start one native `iperf3` server per instance, bound to that host's address, using
   `iperf3-servers.sh`. The external host is not an AosCore unit, so get the script from
   [meta-aos](https://github.com/aosedge/meta-aos) `recipes-support/benchmark-network/files/iperf3-servers.sh`
   and copy it over. First confirm the port(s) are free - a leftover `iperf3` process, or (on Debian/Ubuntu) a
   pre-installed `iperf3.service` enabled on `*:5201`, can already be listening. It runs in the foreground:

   ```bash
   ./iperf3-servers.sh -b ${HOST_IP} -n ${NUM_INSTANCES}
   ```

4. On the unit, deploy the client instance(s). The bundled server pod is started too but isn't used for this path,
   since the server side here is the native one from step 3:

   ```bash
   kubectl apply -f manifest.yaml
   ```

5. Wait for the client instance(s) to finish all four tests (`All tests finished` in each client pod log, `Stop`
   checkpoint event in the Grafana Events view for each client instance):

   ```bash
   kubectl logs -l app=bandwidth-client --prefix --max-log-requests=64 | grep -c "All tests finished"
   ```

6. Read the `tcp_up`/`tcp_down` throughput and `udp_up`/`udp_down` throughput/loss/jitter `benchmark_result`
   samples from Grafana. For more than one instance, average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down the pods:

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

9. Stop the native `iperf3` server(s) started on the external host in step 3.
10. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES` and the `-n` passed to
    `iperf3-servers.sh` in step 3.

### Latency

Goal: measure the round-trip time through the k3s network, reported as percentiles (p50/p99/p999) rather than an
average, so the tail that real-time/RPC traffic feels stays visible, across the same three paths as the AosCore
version - service to service, service to unit, and service to an external host - and how that tail scales with the
number of concurrent client instances.

Deployable items: [latency](https://github.com/aosedge/demo-services/tree/main/benchmark/network/latency) server and
client images, `benchmark-network-latency-server` and `benchmark-network-latency-client` (see
[Container images](benchmark_execution_podman.md#container-images)), the same `latency_server.py`/`latency_client.py`
the AosCore version deploys.

On start, each client instance runs a `sockperf` ping-pong test in each direction against `TARGET`, each for
`DURATION` seconds: `udp_rtt`, then `tcp_rtt` (`--tcp`), both with `--full-rtt` so every figure is a full round trip.
The p50/p99/p999 figures are pushed as `benchmark_result` samples to VictoriaMetrics, bracketed by a
`checkpoint_event` Start/Stop pair for the whole run - unchanged from the AosCore version, see its chapter for the
details. `TARGET` selects the path (`--test-host`) exactly as there.

**Same `sockperf` as AosCore**: the images are the ones the Podman benchmark builds, with `sockperf` built from the
exact commit `meta-aos`' `recipes-support/sockperf` pins (3.10+git), whose `-i` resolves a hostname with
`getaddrinfo()`, so `TARGET=latency-server` (the server's service name) works directly, exactly as in the AosCore
version.

**Scaling clients**, and the **headless services**: exactly as in Bandwidth. The clients are the replicas of a
StatefulSet, whose pod-name ordinal is the 0-based `AOS_INSTANCE_INDEX` (which of the server's `NUM_INSTANCES` port
pairs the client dials, 11111 + index); they are scaled with `NUM_INSTANCES` (`--num-instances`), which also sets the
server's `NUM_INSTANCES` to match. Both services are headless, so the traffic goes pod to pod without kube-proxy's
address translation.

Metrics:

* `udp_rtt`/`tcp_rtt`: p50, p99, p999 (µs).

For more than one instance, every metric above is aggregated as described in "Result aggregation" above.

Prerequisites:

1. No pods are currently running for the `latency` server and clients on the unit (clean slate).

The three paths below share the same working directories, on both hosts - set them up once, they're not repeated per
path or per instance count. On the build/push host:

```bash
cd benchmark/network/latency/k3s
```

On the unit, open one session for the rest of this chapter and `cd` there once:

```bash
mkdir -p ~/benchmark/network/latency
cd ~/benchmark/network/latency
```

#### Service to service

Execution steps:

1. Render `manifest.yaml` for the service-to-service path for one client instance on the build/push host:

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host latency-server \
       --registry-host ${REGISTRY_HOST}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/network/latency/manifest.yaml
   ```

3. On the unit, deploy the server and client instance(s):

   ```bash
   kubectl apply -f manifest.yaml
   ```

4. Wait for the client instance(s) to finish both tests (`All tests finished` in each client pod log, `Stop`
   checkpoint event in the Grafana Events view for each client instance). The number of clients that have finished is:

   ```bash
   kubectl logs -l app=latency-client --prefix --max-log-requests=64 | grep -c "All tests finished"
   ```

   The clients retry until the server name resolves and its port answers (`Server ... not ready` in their log), so
   starting them right after `k3s` itself was started, while CoreDNS is not ready yet, only delays a run.

5. Read the `udp_rtt`/`tcp_rtt` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance,
   average each metric across all instances' samples.
6. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
7. Tear down, leaving the images cached (they're only removed once, at the end of the DNS chapter):

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

8. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES`.

#### Service to unit

Execution steps:

1. Render `manifest.yaml` for the service-to-unit path for one client instance on the build/push host, using the
   unit's own network address as `--test-host` (`NODE_IP` is `10.0.0.100` by default on the main node):

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host ${NODE_IP} \
       --registry-host ${REGISTRY_HOST}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/network/latency/manifest.yaml
   ```

3. On the unit, start one native `sockperf` UDP server and one TCP server per instance, both bound to the unit's
   address, using `sockperf-servers.sh` ([meta-aos](https://github.com/aosedge/meta-aos)
   `recipes-support/benchmark-network`), installed at `/opt/aos/benchmark/sockperf-servers.sh` on the `benchmark`
   `DISTRO_FEATURES`. First confirm the port(s) are free - a leftover `sockperf server` process from an earlier
   manual run is the only thing that can conflict, since the server pod's own `sockperf` listens inside its own
   network namespace. The script runs in the foreground, so start it in a second session on the unit (or in the
   background):

   ```bash
   /opt/aos/benchmark/sockperf-servers.sh -b ${NODE_IP} -n ${NUM_INSTANCES}
   ```

4. On the unit, deploy the client instance(s). The bundled server pod is started too but isn't used for this path,
   since the server side here is the native one from step 3:

   ```bash
   kubectl apply -f manifest.yaml
   ```

5. Wait for the client instance(s) to finish both tests (`All tests finished` in each client pod log, `Stop`
   checkpoint event in the Grafana Events view for each client instance):

   ```bash
   kubectl logs -l app=latency-client --prefix --max-log-requests=64 | grep -c "All tests finished"
   ```

6. Read the `udp_rtt`/`tcp_rtt` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance,
   average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down the pods:

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

9. Stop the native `sockperf` server(s) started on the unit in step 3.
10. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES` and the `-n` passed to
    `sockperf-servers.sh` in step 3.

#### Service to external host

Execution steps:

1. Render `manifest.yaml` for the service-to-external path for one client instance on the build/push host, using an
   external host's address on the unit's local network as `--test-host` (`HOST_IP` is the IP behind the unit,
   accessible from the unit; on an AosCore VM it is `10.0.0.1` by default):

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host ${HOST_IP} \
       --registry-host ${REGISTRY_HOST}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/network/latency/manifest.yaml
   ```

3. On the external host, install `sockperf` if not already present (Debian/Ubuntu ships it), then start one
   native UDP server and one TCP server per instance, both bound to that host's address, using
   `sockperf-servers.sh`. The external host is not an AosCore unit, so get the script from
   [meta-aos](https://github.com/aosedge/meta-aos) `recipes-support/benchmark-network/files/sockperf-servers.sh`
   and copy it over. First confirm the port(s) are free - a leftover `sockperf server` process from an earlier
   manual run is the only thing that can conflict. The script runs in the foreground:

   ```bash
   ./sockperf-servers.sh -b ${HOST_IP} -n ${NUM_INSTANCES}
   ```

4. On the unit, deploy the client instance(s). The bundled server pod is started too but isn't used for this path,
   since the server side here is the native one from step 3:

   ```bash
   kubectl apply -f manifest.yaml
   ```

5. Wait for the client instance(s) to finish both tests (`All tests finished` in each client pod log, `Stop`
   checkpoint event in the Grafana Events view for each client instance):

   ```bash
   kubectl logs -l app=latency-client --prefix --max-log-requests=64 | grep -c "All tests finished"
   ```

6. Read the `udp_rtt`/`tcp_rtt` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance,
   average each metric across all instances' samples.
7. Capture System CPU from the "Node CPU % (whole host)" Grafana panel for the duration of the run.
8. Tear down the pods:

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

9. Stop the native `sockperf` server(s) started on the external host in step 3.
10. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES` and the `-n` passed to
    `sockperf-servers.sh` in step 3.

### DNS

Goal: measure how long a pod takes to resolve a name, reported as percentiles (p50/p99/p999) rather than an average,
across the same three paths as the AosCore version - service to service, service to unit, and service to an external
host - and how that time scales with the number of concurrent client instances.

Deployable items: [dns](https://github.com/aosedge/demo-services/tree/main/benchmark/network/dns) peer and client
images, `benchmark-network-dns-peer` and `benchmark-network-dns-client` (see
[Container images](benchmark_execution_podman.md#container-images)), the same `dns_client.py` the AosCore version
deploys.

On start, each client instance sends `QUERIES` DNS queries for `NAME` one at a time over its own UDP socket, timing
each with `time.perf_counter()`. The full sample set and a breakdown of any failures are logged; the p50/p99/p999
figures are pushed as `benchmark_result` samples to VictoriaMetrics, bracketed by a `checkpoint_event` Start/Stop pair
for the whole run - unchanged from the AosCore version, see its chapter for the details.

`NAME` (`--test-host`) and `RESOLVER` (`--resolver`) decide which path the run measures:

* **service to service** - `NAME=dns-peer.default.svc.cluster.local`, resolved by CoreDNS, which registers the peer's
  service. `RESOLVER` is left empty, so the client asks the nameserver in its own `/etc/resolv.conf`, which in a pod is
  the cluster's DNS service (`kube-dns`, `10.43.0.10`), and its packets are handed to CoreDNS by kube-proxy, which is
  how every pod resolves names and so is part of what is measured. The name is the full one because
  `dns_client.py` sends `NAME` as it is and doesn't apply the search domains of the pod's `resolv.conf`, which a
  short `dns-peer` would need. CoreDNS answers repeated queries for the same name from its cache (`cache 30` in the
  k3s Corefile) after the first one;
* **service to unit** - `NAME` is a hostname the unit's `dnsmasq` already answers for out of `/etc/aos/addnhosts`
  (`main` by default, mapped to the node's own address). `RESOLVER` is the unit's address, so the client asks the
  unit's `dnsmasq` directly;
* **service to external host** - `NAME` is a wildcard domain an external host's `dnsmasq` answers for, with
  `RANDOM_LABEL=1` so every query gets a fresh, uncached label and the unit's own `dnsmasq` cache never masks the
  round trip. `RESOLVER` is again the unit's address, and its `dnsmasq` forwards the domain to the external host.

**Deviation - resolver**: AosCore points an instance's `/etc/resolv.conf` at the unit's `dnsmasq`, so the client needs
no `RESOLVER` there. A pod's nameserver is CoreDNS, so, as in the Podman version, the unit and external paths set
`RESOLVER` to the unit's address, which makes them measure the unit's `dnsmasq` in the same way in all three versions,
independently of the runtime's own DNS.

Metrics:

* `resolve`: p50, p99, p999 (µs).

System CPU is not collected for this chapter - a run finishes in a few seconds, too fast for a meaningful whole-host max
reading.

For more than one instance, every metric above is aggregated as described in "Result aggregation" above.

Prerequisites:

1. No pods are currently running for the `dns` peer and clients on the unit (clean slate).

The three paths below share the same working directories, on both hosts - set them up once, they're not repeated per
path or per instance count. On the build/push host:

```bash
cd benchmark/network/dns/k3s
```

On the unit, open one session for the rest of this chapter and `cd` there once:

```bash
mkdir -p ~/benchmark/network/dns
cd ~/benchmark/network/dns
```

Unlike Bandwidth and Latency, nothing here is addressed per instance, so the clients are scaled with plain Deployment
replicas (`NUM_INSTANCES`, `--num-instances`), not a StatefulSet.

#### Service to service

Execution steps:

1. Render `manifest.yaml` for the service-to-service path for one client instance on the build/push host:

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} \
       --test-host dns-peer.default.svc.cluster.local --registry-host ${REGISTRY_HOST}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/network/dns/manifest.yaml
   ```

3. On the unit, deploy the peer and client instance(s):

   ```bash
   kubectl apply -f manifest.yaml
   ```

4. Wait for the client instance(s) to finish (`All tests finished` in each client pod log, `Stop` checkpoint event in
   the Grafana Events view for each client instance). The number of clients that have finished is:

   ```bash
   kubectl logs -l app=dns-client --prefix --max-log-requests=64 | grep -c "All tests finished"
   ```

5. Read the `resolve` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance, average each
   metric across all instances' samples.
6. Tear down, leaving the images cached (they're only removed once, at the end of the "Service to external host" path
   below):

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

7. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES`.

#### Service to unit

Execution steps:

1. Render `manifest.yaml` for the service-to-unit path for one client instance on the build/push host, using a hostname
   the unit's `dnsmasq` already answers for as `--test-host` (`main`, mapped to `NODE_IP` in `/etc/aos/addnhosts`,
   works on a stock unit with no further setup; see dns's README "Setting up each scenario" to measure a different
   name) and the unit's own address as `--resolver` (`NODE_IP` is `10.0.0.100` by default on the main node):

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host main --resolver ${NODE_IP} \
       --registry-host ${REGISTRY_HOST}
   ```

2. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/network/dns/manifest.yaml
   ```

3. On the unit, deploy only the client instance(s) - the peer isn't needed for this path (`-l` applies only the objects
   with that label):

   ```bash
   kubectl apply -f manifest.yaml -l app=dns-client
   ```

4. Wait for the client instance(s) to finish (`All tests finished` in each client pod log, `Stop` checkpoint event in
   the Grafana Events view for each client instance):

   ```bash
   kubectl logs -l app=dns-client --prefix --max-log-requests=64 | grep -c "All tests finished"
   ```

5. Read the `resolve` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance, average each
   metric across all instances' samples.
6. Tear down:

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

7. Repeat from step 1 for 8, 16, 64 instances, updating `NUM_INSTANCES`.

#### Service to external host

Execution steps:

The external host and the unit must be prepared to resolve the wildcard test domain before these steps start,
following the dns benchmark's
[README](https://github.com/aosedge/demo-services/blob/main/benchmark/network/dns/README.md), "Setting up each
scenario" section - it covers both the case where the unit sits behind a bridge gateway that already forwards to the
external host, and the case where the unit and the external host are two separate machines that need forwarding
configured between them explicitly.

1. Verify the wildcard resolves from the unit before deploying:

   ```bash
   nslookup probe123.dns-probe.test ${NODE_IP}
   ```

2. Render `manifest.yaml` for the service-to-external path for one client instance on the build/push host, using the
   wildcard domain as `--test-host`, `RANDOM_LABEL` on so every query bypasses the unit's `dnsmasq` cache, and the
   unit's address as `--resolver`:

   ```bash
   ../../../scripts/create_services.py --num-instances ${NUM_INSTANCES} --test-host dns-probe.test --random-label 1 \
       --resolver ${NODE_IP} --registry-host ${REGISTRY_HOST}
   ```

3. Deploy the rendered file to the unit:

   ```bash
   scp manifest.yaml root@${UNIT_HOST}:~/benchmark/network/dns/manifest.yaml
   ```

4. On the unit, deploy only the client instance(s) - the peer isn't needed for this path:

   ```bash
   kubectl apply -f manifest.yaml -l app=dns-client
   ```

5. Wait for the client instance(s) to finish (`All tests finished` in each client pod log, `Stop` checkpoint event in
   the Grafana Events view for each client instance):

   ```bash
   kubectl logs -l app=dns-client --prefix --max-log-requests=64 | grep -c "All tests finished"
   ```

6. Read the `resolve` p50/p99/p999 `benchmark_result` samples from Grafana. For more than one instance, average each
   metric across all instances' samples.
7. Tear down the pods:

   ```bash
   kubectl delete -f manifest.yaml --wait --cascade=foreground
   ```

8. Repeat from step 2 for 8, 16, 64 instances, updating `NUM_INSTANCES`.
9. Once every path in Bandwidth, Latency, and DNS is done, remove all six network images - none of them change across
   paths or tiers, so there's nothing to force a fresh pull of in between (run on the unit):

   ```bash
   crictl rmi $(crictl images | awk '/benchmark-network-/ {print $1":"$2}')
   ```

## CPU/RAM used by orchestrator components

CPU and RAM of the k3s runtime is sampled continuously by `process-exporter` and `cgroup-exporter`, scraped into
VictoriaMetrics and visualized in Grafana, the same way as for the AosCore and Podman versions. No dedicated execution
steps are required beyond running the scenario under test in its own chapter; the same run provides this chapter's
CPU/RAM figures for that scenario.

Unlike Podman, k3s has always-running components, so it has a real idle baseline: `k3s`, `containerd`, and CoreDNS with
its `pause` container and shim. k3s runs with SELinux in permissive mode (see the Disclaimer), so its CPU includes the
audit logging of the denials that mode records. What the runtime keeps on the node besides the workload is measured as
follows:

* `k3s` - the `k3s server` process, which runs the whole control plane (API server, scheduler, controllers,
  datastore) and the kubelet, kube-proxy and flannel (the `component:k3s` group in `process-exporter.yml`).
* `containerd` - the daemon k3s launches for itself (the `component:containerd` group).
* `containerd-shim` - one process per pod. It has no `process-exporter` group, because `process-exporter` counts a
  matched process's children with it and a shim's children are the pod's own processes. The shims share the
  `k3s.service` cgroup with `k3s` and `containerd`, which `cgroup-exporter` exports as one instance named
  `k3s.service` in the container-instances panels ("CPU % - container instances" and "Memory - container
  instances"); it covers `k3s`, `containerd` and every shim together.
* The `pause` containers and CoreDNS run as pods, so they appear in the container-instances panels too, like the
  benchmark's own pods.
* `kubectl` and `crictl` calls are short-lived and aren't monitored.

Every instance is a pod of its own (see "Deployment model"), so a `pause` container and a shim are added for each one:
the runtime's overhead grows with the instance count, and part of it (the shims) is in `k3s.service`, not in the
component panels.

Memory of the `k3s.service` instance is the cgroup's `memory.current`, which counts the memory charged to that cgroup
(anonymous memory and page cache; a page shared between cgroups is charged to the one that used it first), so it
differs from the PSS of the component panels, which splits shared pages between the processes using them. Don't add
`k3s.service` to `component:k3s` or `component:containerd`: it already contains them.

The AosCore components (`cm`, `sm`, `iam`) run on the same unit unless it is stopped (see "AosCore" above) and appear
on the same panels - for this document read only the k3s ones.

Execution steps:

1. Run the scenario under test (idle observation window, or a full test case from another chapter).
2. Read the `k3s` and `containerd` components' CPU and RAM from the "CPU % - orchestrator components" and "Memory
   (PSS) - orchestrator components" Grafana panels, and the `k3s.service` instance (the shims included) from the
   container-instances panels, for the duration of that scenario.

### Test scenarios

CPU/RAM is recorded for the following scenarios:

* Idle, k3s running with no benchmark pods deployed (only CoreDNS);
* Operational Speed / Install new deployable items;
* Operational Speed / Install cached deployable items;
* Operational Speed / Start/stop already installed instances.
