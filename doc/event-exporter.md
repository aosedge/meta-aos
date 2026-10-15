# event-exporter

`event-exporter` is one of the services in the [AosCore benchmarking](benchmark.md) stack. It tails journald for a
fixed list of systemd units and, for each line matching a configured regex, pushes a `checkpoint_event` sample to
VictoriaMetrics - so Grafana can overlay operation events (instance/component start/stop) on the same graphs as the
CPU/RAM series the rest of the benchmarking stack collects.

`event-exporter` only ever forwards checkpoints - it doesn't aggregate them into anything. For elapsed-time metrics
computed *from* those checkpoints (e.g. "how long did starting instances take"), see
[benchmark-results-publisher](benchmark-results-publisher.md), a separate service that watches VictoriaMetrics from
the outside rather than tailing journald itself.

Source: `recipes-support/event-exporter/files/event_exporter.py`.

## Command-line usage

```console
event_exporter.py --victoria-url http://localhost:8428 --config event-exporter.yml \
    --node main --unit aos-cm --unit aos-sm --unit aos-iam
```

| Option | Required | Meaning |
| --- | --- | --- |
| `--victoria-url` | yes | The main node's VictoriaMetrics base URL (e.g. `http://localhost:8428` on the main node itself, or the main node's address from a secondary node). |
| `--config` | yes | Path to the [config file](#config-file-format) listing the checkpoint regexes to match. |
| `--unit` | yes, repeatable | A systemd unit to tail (e.g. `--unit aos-cm --unit aos-sm --unit aos-iam`). Repeat for each unit. |
| `--node` | yes | This instance's node label (e.g. `main`, `secondary-1`) - stamped on every `checkpoint_event` sample it pushes, so events from different nodes can be told apart. |
| `--since` | no (default `now`) | `journalctl --since` value the journald tail starts from. |

## Deployment

`recipes-support/event-exporter/event-exporter.bb` installs one systemd service per node, with per-node arguments
picked via the `:aos-main-node`/`:aos-secondary-node` OVERRIDES layer.conf sets from `AOS_MAIN_NODE` (the same
mechanism `aos-image.inc` uses elsewhere):

* `UNIT_ARGS` - which units to tail. Every node tails `aos-sm`/`aos-iam` (they run on every node); the main node
  additionally tails `aos-cm` (which only runs there).

`VICTORIA_URL`/`NODE` come from `AOS_MAIN_NODE_HOSTNAME`/`AOS_NODE_HOSTNAME`, the same variables
`aos-communicationmanager`/`aos-servicemanager`/`aos-iamanager` already use to resolve the main node and their own
node identity.

The config file (`event-exporter.yml` in the recipe's own `files/`) is installed as `/etc/event-exporter/patterns.yml`
and marked `CONFFILES`, so a customized copy on a real device survives a package upgrade instead of being silently
overwritten by a fresh default.

## Config file format

```yaml
patterns:
  - '\[profiling\]\s*(.*)'
  - '^((?:Starting|Started|Stopping|Stopped) AosCore.*)'
```

A list of regexes. Each journald line is tried against them in order; the first capture group of the first pattern
that matches becomes the `event` label of the `checkpoint_event` sample pushed to VictoriaMetrics. A line matching
no pattern is ignored. The defaults match AosCore's own `[profiling] <text>` checkpoint lines (e.g. `[profiling]
Start instance begin`) and the generic systemd unit start/stop status lines PID1 logs for
`Starting`/`Started`/`Stopping`/`Stopped AosCore ...` units - but nothing about this is AosCore-specific; point it at
a different service's own log conventions without a code change.
