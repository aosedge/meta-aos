# benchmark-results-publisher

`benchmark-results-publisher` is one of the services in the [AosCore benchmarking](benchmark.md) stack. It watches
VictoriaMetrics from the outside (unlike [event-exporter](event-exporter.md), which tails journald directly) for
repeating "windows" of `checkpoint_event` samples - e.g. one AosCore deployment cycle - and publishes each window's
aggregated elapsed-time metrics back to VictoriaMetrics as `benchmark_result` samples, so they show up in Grafana's
"Benchmark Results" table without anyone having to separately run `report_timing.py` by hand.

Entirely config-driven (see [Config file format](#config-file-format)): nothing in the script itself names a
specific service, checkpoint text, or event. The shipped default config happens to describe AosCore's own
Operational Speed checkpoints (see [Benchmark Execution's Operational Speed
chapter](benchmark_execution_aos.md#operational-speed) for what each metric means and how a test run is actually driven
end to end), but this service has no idea what AosCore is.

Runs once, on the main node only (see `aos-image.inc`'s `IMAGE_INSTALL:append:aos-main-node`) - VictoriaMetrics is a
single shared store, so watching it from more than one place at once would double-detect and double-publish every
window.

Source: `recipes-support/benchmark-results-publisher/files/benchmark_results_publisher.py`. The script's own module
docstring and comments go into considerably more depth than this document on *why* each piece of the
window-resolution logic works the way it does (checkpoint pairing edge cases, window-boundary staleness, etc.) -
read it directly if you're changing that code, not just using it.

## Command-line usage

```console
benchmark_results_publisher.py --victoria-url http://localhost:8428 \
    --config benchmark-results-publisher.yml --node main \
    --state-file /var/lib/benchmark-results-publisher/last-boundary
```

| Option | Required | Meaning |
| --- | --- | --- |
| `--victoria-url` | yes | VictoriaMetrics base URL - always `http://localhost:8428`, since this service only ever runs colocated with VictoriaMetrics on the main node. |
| `--config` | yes | Path to the [config file](#config-file-format). |
| `--node` | yes | This script's own node identity - used only by a `suite_boundary` or metric explicitly pinned to it (`node: self`), not by anything scoped to a window's own node - see [Config file format](#config-file-format). |
| `--state-file` | no | File the last published window's boundary is persisted to. On start, the script resumes from it, so a window that was detected but not yet published when the script stopped is still published; without it (or before it's first written), the script starts from the latest boundary already in VictoriaMetrics and skips anything before that. |

## Deployment

`recipes-support/benchmark-results-publisher/benchmark-results-publisher.bb` installs a single systemd service,
included on the main node only, next to `victoria-metrics` itself (see `aos-image.inc`). The service is ordered after
`victoria-metrics` and `event-exporter` (the latter pulled in with `Wants=`, and the package depends on it), since
`event-exporter` pushes the AosCore checkpoints every metric is built from. Unlike `event-exporter`,
there's no per-node argument variation to pick between nodes - `--victoria-url` is a fixed `http://localhost:8428`
literal, since this recipe never runs anywhere but the main node. `--node` still comes from
`AOS_NODE_HOSTNAME` (substituted into the service file at build time, the same variable `event-exporter.bb` uses
for its own `--node`), not a literal `"main"`: `AOS_NODE_HOSTNAME` defaults to `"main"` on the main node but is
overrideable (`conf/layer.conf`), and a `node: self` metric needs to keep matching whatever a product actually
configures it to.

The service runs with `--state-file /var/lib/benchmark-results-publisher/last-boundary` (systemd's
`StateDirectory=` creates the directory), so a restart resumes where the previous run left off.

The config file is installed as `/etc/benchmark-results-publisher/benchmark-results-publisher.yml` and marked
`CONFFILES`, so a customized copy on a real device survives a package upgrade instead of being silently overwritten
by a fresh default.

## Config file format

Two sections - see the shipped default,
`recipes-support/benchmark-results-publisher/files/benchmark-results-publisher.yml`, for the actual checkpoints
AosCore logs today.

### `suite_boundary`

What marks the start of a new window. Every `checkpoint_event` whose `source` matches `source_pattern` (a regex) and
`event` equals `event` defines one occurrence (across every node, by default). Occurrences newer than the previous
window's own boundary and at most `settle_seconds` apart form one batch, and the last occurrence of the oldest such
batch is the next window's boundary - so if several windows finish while one is still being resolved, each is
published in turn rather than only the latest.

A window therefore spans everything between two consecutive boundaries - including a teardown that precedes its own
instances starting. In the Operational Speed procedure (`systemctl stop aos.target`, then `systemctl start
aos.target`), the stop phase's checkpoints (`Stop network`, `Stop instances`, `Release SM`) land before the restarted
instances' own `Start` checkpoints, so they're resolved as part of that restart's window, together with `Init SM`,
`Start network` and `Start instances`. A stop that's never followed by a start produces no boundary, so its teardown
isn't published.

```yaml
suite_boundary:
  source_pattern: '^Instance: .*'
  event: "Start"
  settle_seconds: 2
```

| Key | Required | Meaning |
| --- | --- | --- |
| `source_pattern` | yes | A regex matched against the `source` label. |
| `event` | yes | The exact `event` label (tolerating an optional `": key=value, ..."` detail suffix, the same as every other checkpoint lookup here). |
| `node` | no | Pins boundary detection to one specific node instead of searching every node - see [Node scoping](#node-scoping). |
| `settle_seconds` | no (default 2) | How long to keep watching for an even-newer occurrence before locking the current one in, in case more of the same batch (e.g. several instances starting near-simultaneously) is still trickling in. |

The default config's `source_pattern` matches each benchmark-timing instance's own `"Instance: <id>"` / `"Start"`
checkpoint - the last one across a whole deployment batch marks that batch's own end.

### `metrics`

A list of entries, one per elapsed-time metric published as a `benchmark_result` sample - each metric is the
elapsed time between a `start` and an `end` checkpoint.

| Key | Required | Meaning |
| --- | --- | --- |
| `label` | yes | Display name and the `benchmark_result` sample's `name` (lowercased, spaces to underscores, `_s` suffix - e.g. `"Start network"` → `start_network_s`). |
| `start_source` / `start_event` | yes | The `source`/`event` of the checkpoint that starts this metric's interval. |
| `end_event` | yes | The `event` of the checkpoint that ends this metric's interval. |
| `end_source` / `end_source_pattern` | exactly one | The end checkpoint's `source`: either one fixed source, or a regex matching a batch of sources (e.g. `'^Instance: .*'`), in which case the metric ends at the *last* match - see [How start and end are paired](#how-start-and-end-are-paired). |
| `per_instance` | no (default `false`) | Also publish one sample per `end_source_pattern` match, each the elapsed time from this metric's own start to that match. Needs `end_source_pattern`. |
| `node` | no | `"self"` to pin this metric to the node this script itself runs on (e.g. a component that only runs on one specific node), instead of the window's own node - see [Node scoping](#node-scoping). |

```yaml
metrics:
  - label: Start network
    start_source: aos-sm.service
    start_event: "Start networks begin"
    end_source: aos-sm.service
    end_event: "Start networks end"
  - label: Init SM
    start_source: init.scope
    start_event: "Starting AosCore Service Manager..."
    end_source: aos-sm.service
    end_event: "Update instances begin"
  - label: Stop network
    start_source: aos-sm.service
    start_event: "Stop all networks begin"
    end_source: aos-sm.service
    end_event: "Stop all networks end"
  - label: Start instances
    start_source: aos-sm.service
    start_event: "Start instances begin"
    end_source_pattern: '^Instance: .*'
    end_event: "Start"
    per_instance: true
  - label: Total
    start_source: aos-cm.service
    start_event: "Process desired status"
    end_source_pattern: '^Instance: .*'
    end_event: "Start"
    node: self
```

Every lookup already tolerates a `": key=value, ..."` detail suffix on a checkpoint line (e.g. `"Start networks
begin: count=13"` still matches `start_event: "Start networks begin"`), so `start_event`/`end_event` only need the
fixed prefix, not the full logged text.

#### How start and end are paired

A metric's start is the *latest* `start_event` in the window, and its end is the *earliest* `end_event` at or after
that start - not simply the latest `end_event`. Pairing "latest" with "latest" breaks in two ways: while the latest
start's own end isn't visible yet, it pairs that start with an earlier end (a negative or too-short duration); and
when `end_event` recurs more often than `start_event` - `Init SM`'s `"Starting AosCore Service Manager..."` only
fires when SM itself restarts, but `"Update instances begin"` fires on *every* deployment afterward - it pairs a
start with an unrelated, much later end.

With `end_source_pattern`, the end is instead the *latest* match at or after the start: the pattern names a batch
of sources (e.g. every benchmark-timing instance's own `"Instance: <id>"` / `"Start"`), and the batch is done only
once its last member is. That's how `Start instances` and `Total` end when the last instance has started, not at
Service Manager's own `"Start instances end"`.

AosCore logs network/instance teardown two ways - `"Stop all networks/instances begin/end"` when the whole SM
process is shutting down, or the same text without `"all "` for a routine per-update teardown of only what's
actually being replaced. These are separate metrics in the default config (`Stop network`/`Stop instances` and
`Update stop network`/`Update stop instances`), each published whenever its own pair appears in a window.

### Node scoping

By default, every metric is looked up (and published) on whichever node the *current window's own* boundary
occurrence came from, since a window's own activity can happen on any node (SM/IAM run on every node in the unit -
see [event-exporter](event-exporter.md)'s own multi-node note). A metric whose own checkpoint is only ever logged by
one specific node regardless of where a window's activity happens - `Total`'s `"Process desired status"`, which
only ever comes from `aos-cm.service` on the main node - sets `node: self` to pin it to this script's own `--node`
instead. An `end_source_pattern` end is always looked up on the window's own node, even for a `node: self` metric -
it names the window's own activity (e.g. its instances), wherever that metric's start was logged. `suite_boundary`
itself can similarly be pinned with its own `node` key, though the default config leaves
it unpinned (searches every node), since benchmark-timing instances can land anywhere.

A window whose own activity is split across more than one node isn't supported - only the node of the boundary
occurrence itself is used for everything else in that window.

## Published metrics

Every resolved metric is pushed as a `benchmark_result` sample only if it actually resolved; a metric that doesn't
apply to a given window (e.g. `Download` when nothing needed downloading) is never pushed at all, not pushed as
zero. The default config's own metrics:

| `name` | Meaning |
| --- | --- |
| `download_s`, `install_s`, `prepare_s` | Time to download, install, and prepare deployable items - only for a genuine "install new items" deployment. |
| `init_sm_s` | Time from Service Manager restarting to it beginning to process instance updates. |
| `start_network_s`, `start_instances_s` | Time to set up instance networking and start instances. |
| `stop_network_s`, `stop_instances_s` | Time to tear down instance networking and stop instances when Service Manager shuts down (`"Stop all ..."`). |
| `update_stop_network_s`, `update_stop_instances_s` | Time to tear down the networking and instances replaced by a deployment (`"Stop networks/instances ..."`, no `"all"`). |
| `release_sm_s` | Time from network teardown finishing to Service Manager itself stopping. |
| `total_s` | Time from AosCore receiving a new desired status to every instance having started. |

`start_instances_s` is additionally published once per instance (`source="Instance: <id>"`), alongside the single
aggregate value above (`source` matching that metric's own `start_source`, e.g. `aos-sm.service`).
