#!/usr/bin/env python3
"""Tail a journald log and forward "[profiling]" checkpoint lines to VictoriaMetrics as events.

This lets checkpoint log lines already written by a service (e.g. "[profiling] Start instance
begin") show up as timestamped markers on the same Grafana graphs that plot CPU/MEM usage
collected by process-exporter, so operations can be visually matched against resource usage. Not
AosCore-specific: any systemd unit that logs "[profiling] <text>" lines works, journald is just
the log source this reads from today.

Each checkpoint is pushed as a single point of a "checkpoint_event" metric (value 1, labeled with
node/source/event) via VictoriaMetrics' /api/v1/import/prometheus endpoint - the same push path
already used for benchmark-container results - rather than Grafana's annotation API, so events and
metrics both live in the one store. The dashboard's annotation query needs to be a Prometheus-type
query against checkpoint_event (Title/Tags mapped from its labels), not Grafana's native tag-based
annotations.

VictoriaMetrics' own sample timestamps are millisecond-precision only (confirmed empirically: two
points pushed 500us apart both landed on the same millisecond) - too coarse to tell apart events
that land in the same millisecond. So the precise time also gets carried as a "time_us" label
(a plain string, not subject to that storage limit), which the dashboard's events table displays
instead of relying on the sample's own timestamp.

The unit is multiple nodes (main + secondary), and SM/IAM run on all of them, so an instance
start/stop can be logged on any node. Run one instance of this script locally on each node (each
with its own --unit list and --node label matching that node's process-exporter/node_exporter
"node" label - see promscrape.yml). Since VictoriaMetrics only runs on the main node, a secondary
node's instance needs a path to it (localhost if run on the main node itself, or the main node's
address otherwise) - the same reachability this tooling already relies on for exporter scraping
and benchmark-container result pushes.

Which log lines count as checkpoints is defined by a YAML config file (see --config), not a
hardcoded pattern, so this can be pointed at other services' log conventions without a code
change - see event-exporter.yml for the format.

Usage (run locally on each node, pushing to the main node's VictoriaMetrics):
    event_exporter.py --victoria-url http://localhost:8428 --config event-exporter.yml \
        --node main --unit aos-cm --unit aos-sm --unit aos-iam

    event_exporter.py --victoria-url http://main-node:8428 --config event-exporter.yml \
        --node secondary-1 --unit aos-sm --unit aos-iam
"""

import argparse
import datetime
import json
import re
import signal
import subprocess
import sys
import urllib.error
import urllib.request

import yaml


def parse_args():
    """Parse --victoria-url / --config / --unit / --node / --since command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--victoria-url",
        required=True,
        help="main node's VictoriaMetrics base URL, e.g. http://localhost:8428",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="path to a YAML file listing the checkpoint regexes to match, see event-exporter.yml",
    )
    parser.add_argument(
        "--unit",
        action="append",
        dest="units",
        required=True,
        help="systemd unit to follow (repeatable), e.g. --unit aos-cm --unit aos-sm --unit aos-iam",
    )
    parser.add_argument(
        "--node",
        required=True,
        help='node this log is read from, e.g. main / secondary - matches the "node" label '
        "used by promscrape.yml, and is added as a label so events can be told apart",
    )
    parser.add_argument(
        "--since", default="now", help="journalctl --since value (default: now)"
    )
    return parser.parse_args()


def load_patterns(config_path):
    """Load and compile the checkpoint regexes listed under "patterns" in a YAML config file."""
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    return [re.compile(pattern) for pattern in config.get("patterns", [])]


def match_checkpoint(patterns, message):
    """Return the first pattern's match against message, or None if none of them match."""
    for pattern in patterns:
        match = pattern.search(message)
        if match:
            return match

    return None


def follow_journal(units, since):
    """Yield decoded journald entries for the given units, following the log as it grows."""
    journalctl_cmd = ["journalctl", "-o", "json", "-f", "--since", since]
    for unit in units:
        journalctl_cmd += ["-u", unit]

    proc = subprocess.Popen(journalctl_cmd, stdout=subprocess.PIPE, text=True)

    # SIGTERM's default disposition kills the process without running this, orphaning journalctl -
    # main() installs a handler that turns it into a SystemExit so this finally block still runs.
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    finally:
        proc.terminate()
        proc.wait()


def escape_label_value(value):
    """Escape a string for safe embedding inside a Prometheus exposition-format label value."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def format_precise_time(timestamp_us):
    """Format a microsecond epoch timestamp as "YYYY-MM-DD HH:MM:SS.ffffff" (UTC)."""
    # Exact integer arithmetic, not timestamp_us / 1e6 - float64 is right at the edge of enough
    # precision for a 10-digit epoch second count plus 6 more decimal digits, so this avoids any
    # risk of the last microsecond digit being wrong.
    seconds, microseconds = divmod(timestamp_us, 1_000_000)
    dt = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
    dt += datetime.timedelta(microseconds=microseconds)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


def push_event(victoria_url, timestamp_us, node, source, text):
    """Push a single checkpoint_event sample to VictoriaMetrics for this checkpoint."""
    labels = ",".join(
        f'{name}="{escape_label_value(value)}"'
        for name, value in (
            ("node", node),
            ("source", source),
            ("event", text),
            ("time_us", format_precise_time(timestamp_us)),
        )
    )
    # VictoriaMetrics' /api/v1/import/prometheus takes this optional timestamp field in seconds,
    # unlike the millisecond timestamps the standard Prometheus text exposition format documents -
    # confirmed empirically: a bare millisecond integer here lands the sample decades in the
    # future. Fractional seconds (e.g. "...858") are accepted, but VictoriaMetrics' own sample
    # timestamps are millisecond-precision only regardless (confirmed empirically: two points
    # pushed 500us apart both landed on the same millisecond) - the "time_us" label above is what
    # actually carries full precision, since labels aren't subject to that storage limit.
    time_s = timestamp_us / 1_000_000
    line = f"checkpoint_event{{{labels}}} 1 {time_s:.3f}"

    request = urllib.request.Request(
        f"{victoria_url.rstrip('/')}/api/v1/import/prometheus",
        data=line.encode(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
    except urllib.error.URLError as err:
        print(f"failed to push event: {err}", file=sys.stderr)


def _handle_sigterm(signum, frame):
    raise SystemExit(0)


def main():
    """Parse arguments and push each matching checkpoint line seen until interrupted."""
    signal.signal(signal.SIGTERM, _handle_sigterm)

    args = parse_args()
    patterns = load_patterns(args.config)

    for entry in follow_journal(args.units, args.since):
        message = entry.get("MESSAGE", "")

        match = match_checkpoint(patterns, message)
        if not match:
            continue

        # __REALTIME_TIMESTAMP is microseconds since epoch, as a string.
        timestamp_us = int(entry.get("__REALTIME_TIMESTAMP", "0"))

        source = entry.get("_SYSTEMD_UNIT", entry.get("SYSLOG_IDENTIFIER", "unknown"))

        push_event(args.victoria_url, timestamp_us, args.node, source, match.group(1))


if __name__ == "__main__":
    main()
