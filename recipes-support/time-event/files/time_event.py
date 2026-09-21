#!/usr/bin/env python3
"""Generic command-timing wrapper for the Podman and k3s benchmark scripts in this repo.

Runs the given command and pushes checkpoint_event samples bracketing it ("Start <name>" /
"Stop <name>"), the same shape of data the AosCore deployable items push themselves (see e.g.
diskio's diskio_benchmark.py), so the run shows up in the same Grafana Events table/annotations as
everything else. It does not compute or push a duration itself - a separate service calculates
that from the Start/Stop event pair, the same way every duration in doc/benchmark_execution_aos.md
is derived from checkpoint pairs rather than pushed pre-computed.

Not tied to any one benchmark scenario - --name/--node/--source are freely chosen labels, and the
command being timed is whatever follows `--`, so this can wrap `podman-compose start`,
`podman-compose stop`, `podman build`, or any other shell command:

    time_event.py --name "timing start 8 instances" -- podman-compose -p timing -f compose.yaml start
    time_event.py --name "timing stop 8 instances" -- podman-compose -p timing -f compose.yaml stop -t 0

Usage:
    time_event.py --name <measure name> [--node main] [--source script]
                   [--victoria-url http://10.0.0.100:8428] -- <command> [args...]
"""

import argparse
import datetime
import subprocess
import sys
import time
import urllib.error
import urllib.request


def escape_label_value(value):
    """Escape a string for safe embedding inside a Prometheus exposition-format label value."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def format_precise_time(timestamp_us):
    """Format a microsecond epoch timestamp as "YYYY-MM-DD HH:MM:SS.ffffff" (UTC)."""
    seconds, microseconds = divmod(timestamp_us, 1_000_000)
    dt = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
    dt += datetime.timedelta(microseconds=microseconds)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


def push_line(victoria_url, line):
    """POST a single Prometheus exposition-format line to VictoriaMetrics."""
    request = urllib.request.Request(
        f"{victoria_url.rstrip('/')}/api/v1/import/prometheus", data=line.encode(), method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
    except urllib.error.URLError as err:
        print(f"failed to push to VictoriaMetrics: {err}", file=sys.stderr)


def push_event(victoria_url, node, source, event):
    """Push a checkpoint_event sample (the same metric the AosCore deployable items push)."""
    timestamp_us = int(time.time() * 1_000_000)
    labels = ",".join(
        f'{name}="{escape_label_value(value)}"'
        for name, value in (
            ("node", node),
            ("source", source),
            ("event", event),
            ("time_us", format_precise_time(timestamp_us)),
        )
    )
    time_s = timestamp_us / 1_000_000

    push_line(victoria_url, f"checkpoint_event{{{labels}}} 1 {time_s:.3f}")


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--name", required=True, help="measure name (Start/Stop event suffix)")
    parser.add_argument("--node", default="main")
    parser.add_argument("--source", default="script")
    parser.add_argument("--victoria-url", default="http://10.0.0.100:8428")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command (and arguments) to run and time")
    return parser.parse_args()


def main():
    args = parse_args()

    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        print("error: no command given to measure (pass it after --)", file=sys.stderr)
        return 2

    push_event(args.victoria_url, args.node, args.source, f"Start {args.name}")

    start = time.monotonic()
    result = subprocess.run(command)
    elapsed_ms = (time.monotonic() - start) * 1000

    push_event(args.victoria_url, args.node, args.source, f"Stop {args.name}")

    print(f'"{args.name}": {elapsed_ms:.1f} ms (exit code {result.returncode})')

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
