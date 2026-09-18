# benchmark-results-publisher

`benchmark-results-publisher` is one of the services in the [AosCore benchmarking](benchmark.md) stack. It watches
VictoriaMetrics from the outside (unlike [event-exporter](event-exporter.md), which tails journald directly) for
repeating "windows" of `checkpoint_event` samples - e.g. one AosCore deployment cycle - and publishes each window's
aggregated elapsed-time metrics back to VictoriaMetrics as `benchmark_result` samples, so they show up in Grafana's
"Benchmark Results" table without anyone having to separately run `report_timing.py` by hand.

Entirely config-driven (see [Config file format](#config-file-format)): nothing in the script itself names a
specific service, checkpoint text, or event. The shipped default config happens to describe AosCore's own
Operational Speed checkpoints (see [Benchmark Execution's Operational Speed
chapter](benchmark_execution.md#operational-speed) for what each metric means and how a test run is actually driven
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
    --config benchmark-results-publisher.yml --node main
```

| Option | Required | Meaning |
| --- | --- | --- |
| `--victoria-url` | yes | VictoriaMetrics base URL - always `http://localhost:8428`, since this service only ever runs colocated with VictoriaMetrics on the main node. |
| `--config` | yes | Path to the [config file](#config-file-format). |
| `--node` | yes | This script's own node identity - used only by a `suite_boundary` or metric explicitly pinned to it (`node: self`), not by anything scoped to a window's own node - see [Config file format](#config-file-format). |

## Deployment

`recipes-support/benchmark-results-publisher/benchmark-results-publisher.bb` installs a single systemd service,
included on the main node only, next to `victoria-metrics` itself (see `aos-image.inc`). Unlike `event-exporter`,
there's no per-node argument variation to pick between nodes - `--victoria-url` is a fixed `http://localhost:8428`
literal, since this recipe never runs anywhere but the main node. `--node` still comes from
`AOS_NODE_HOSTNAME` (substituted into the service file at build time, the same variable `event-exporter.bb` uses
for its own `--node`), not a literal `"main"`: `AOS_NODE_HOSTNAME` defaults to `"main"` on the main node but is
overrideable (`conf/layer.conf`), and a `node: self` metric needs to keep matching whatever a product actually
configures it to.

The config file is installed as `/etc/benchmark-results-publisher/benchmark-results-publisher.yml` and marked
`CONFFILES`, so a customized copy on a real device survives a package upgrade instead of being silently overwritten
by a fresh default.

## Config file format

Two sections - see the shipped default,
`recipes-support/benchmark-results-publisher/files/benchmark-results-publisher.yml`, for the actual checkpoints
AosCore logs today.

### `suite_boundary`

What marks the start of a new window. Every `checkpoint_event` whose `source` matches `source_pattern` (a regex) and
`event` equals `event` defines one occurrence; the *latest* such occurrence (across every node, by default) that's
newer than the previous window's own boundary starts a new window.

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
| `end_source` / `end_event` | yes, unless `end_is_suite_boundary` | Same, for the checkpoint that ends it. |
| `end_is_suite_boundary` | no (default `false`) | This metric's elapsed time ends exactly at the window's own boundary, not a separate checkpoint - for a "how long did the whole window take" metric. Mutually exclusive with `end_source`/`end_event`. |
| `nearest_end` | no (default `false`) | Resolve the end as the *earliest* occurrence at or after the start, not the latest overall - see [`nearest_end`](#nearest_end) below. |
| `fallback` | no | `{start_source, start_event, end_source, end_event}` (any subset - unset keys fall back to this metric's own primary ones), tried only if the primary pair is never found - see [`fallback`](#fallback) below. Mutually exclusive with `nearest_end`. |
| `per_instance` | no (default `false`) | Also publish one sample per `suite_boundary` occurrence in this window, each the elapsed time from this metric's own start to that occurrence's own timestamp. |
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
    nearest_end: true
  - label: Stop network
    start_source: aos-sm.service
    start_event: "Stop all networks begin"
    end_source: aos-sm.service
    end_event: "Stop all networks end"
    fallback:
      start_event: "Stop networks begin"
      end_event: "Stop networks end"
  - label: Start instances
    start_source: aos-sm.service
    start_event: "Start instances begin"
    end_source: aos-sm.service
    end_event: "Start instances end"
    per_instance: true
  - label: Total
    start_source: aos-cm.service
    start_event: "Process desired status"
    end_is_suite_boundary: true
    node: self
```

Every lookup already tolerates a `": key=value, ..."` detail suffix on a checkpoint line (e.g. `"Start networks
begin: count=13"` still matches `start_event: "Start networks begin"`), so `start_event`/`end_event` only need the
fixed prefix, not the full logged text.

#### `nearest_end`

Without it, a metric is resolved as the *latest* occurrence of `start_event` paired with the *latest* occurrence of
`end_event` - fine when both sides recur at the same rate. `Init SM` is different: `"Starting AosCore Service
Manager..."` only fires when SM itself restarts (rare), but `"Update instances begin"` fires on *every* deployment
afterward (frequent). Pairing "latest" with "latest" would pair a long-ago SM restart with an unrelated, much-later
deployment. `nearest_end: true` instead resolves the end as the *earliest* occurrence at or after the (rare) start.

#### `fallback`

AosCore logs network/instance teardown two ways - `"Stop all networks/instances begin/end"` when the whole SM
process is shutting down, or the same text without `"all "` for a routine per-update teardown of only what's
actually being replaced. Both can appear in the same window; the primary pair is tried first and preferred whenever
found, falling back to the `fallback` pair only if the primary is never found at all, rather than picking whichever
is merely more recent.

#### `end_is_suite_boundary`

A metric like `Total` isn't the elapsed time between two checkpoints *within* a window - it's "how long did the
whole window take", measured from its own start checkpoint to the window's own boundary. Setting
`end_is_suite_boundary: true` (instead of `end_source`/`end_event`) tells this script that.

### Node scoping

By default, every metric is looked up (and published) on whichever node the *current window's own* boundary
occurrence came from, since a window's own activity can happen on any node (SM/IAM run on every node in the unit -
see [event-exporter](event-exporter.md)'s own multi-node note). A metric whose own checkpoint is only ever logged by
one specific node regardless of where a window's activity happens - `Total`'s `"Process desired status"`, which
only ever comes from `aos-cm.service` on the main node - sets `node: self` to pin it to this script's own `--node`
instead. `suite_boundary` itself can similarly be pinned with its own `node` key, though the default config leaves
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
| `stop_network_s`, `stop_instances_s` | Time to tear down instance networking and stop instances. |
| `release_sm_s` | Time from network teardown finishing to Service Manager itself stopping. |
| `total_s` | Time from AosCore receiving a new desired status to every instance having started. |

`start_instances_s` is additionally published once per instance (`source="Instance: <id>"`), alongside the single
aggregate value above (`source` matching that metric's own `start_source`, e.g. `aos-sm.service`).
