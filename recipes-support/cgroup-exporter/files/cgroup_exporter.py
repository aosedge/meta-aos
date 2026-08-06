#!/usr/bin/env python3
"""Prometheus-format /metrics endpoint for AosCore app instance cgroups.

process-exporter can't identify instances (their cmdline carries no instance ID - confirmed on a
real target: a "load-test" instance's workload process cmdline is just "/load-test"), and
treydock/cgroup_exporter hardcodes a path depth that doesn't fit AosCore's cgroup layout (confirmed
both by reading its source and by running the real binary against the target: its "cgroup" label
collapses to "/system.slice/system-aos.slice" for every instance, losing the instance ID entirely).
This script reads the same cgroup v2 files AosCore's own launcher::Monitoring class already reads
(src/sm/launcher/runtimes/container/monitoring.cpp) directly, with no assumptions beyond a flat
"one directory per instance ID" layout under CGROUP_ROOT.

Exposes:
  aos_instance_cpu_usage_seconds_total{instance="<id>"}  (counter, cumulative - use rate())
  aos_instance_memory_bytes{instance="<id>"}             (gauge)

Usage:
    cgroup_exporter.py [--listen-address 0.0.0.0:9400] [--cgroup-root PATH]
"""

import argparse
import http.server
import os

DEFAULT_CGROUP_ROOT = (
    "/sys/fs/cgroup/system.slice/system-aos.slice/system-aos-service.slice"
)


def read_cpu_usage_seconds(instance_dir):
    """Return the instance cgroup's cumulative CPU usage in seconds, read from cpu.stat."""
    with open(os.path.join(instance_dir, "cpu.stat")) as f:
        for line in f:
            key, _, value = line.partition(" ")
            if key == "usage_usec":
                return int(value) / 1_000_000
    raise ValueError("usage_usec not found in cpu.stat")


def read_memory_bytes(instance_dir):
    """Return the instance cgroup's current memory usage in bytes, read from memory.current."""
    with open(os.path.join(instance_dir, "memory.current")) as f:
        return int(f.read().strip())


def collect_instances(cgroup_root):
    """Return (instance_id, cpu_seconds, memory_bytes) for every instance dir under cgroup_root."""
    try:
        instance_ids = sorted(os.listdir(cgroup_root))
    except FileNotFoundError:
        return []

    instances = []
    for instance_id in instance_ids:
        instance_dir = os.path.join(cgroup_root, instance_id)
        if not os.path.isdir(instance_dir):
            continue

        # An instance can stop between the listdir() above and these reads - skip it for this
        # scrape rather than erroring the whole endpoint.
        try:
            cpu_seconds = read_cpu_usage_seconds(instance_dir)
        except (FileNotFoundError, ValueError):
            cpu_seconds = None

        try:
            memory_bytes = read_memory_bytes(instance_dir)
        except FileNotFoundError:
            memory_bytes = None

        instances.append((instance_id, cpu_seconds, memory_bytes))

    return instances


def render_metrics(cgroup_root):
    """Render current instance CPU/memory metrics in Prometheus text exposition format."""
    instances = collect_instances(cgroup_root)

    lines = [
        "# HELP aos_instance_cpu_usage_seconds_total Cumulative CPU time used by the instance's cgroup.",
        "# TYPE aos_instance_cpu_usage_seconds_total counter",
    ]
    for instance_id, cpu_seconds, _ in instances:
        if cpu_seconds is not None:
            lines.append(
                f'aos_instance_cpu_usage_seconds_total{{instance="{instance_id}"}} {cpu_seconds:.6f}'
            )

    lines += [
        "# HELP aos_instance_memory_bytes Current memory usage of the instance's cgroup.",
        "# TYPE aos_instance_memory_bytes gauge",
    ]
    for instance_id, _, memory_bytes in instances:
        if memory_bytes is not None:
            lines.append(f'aos_instance_memory_bytes{{instance="{instance_id}"}} {memory_bytes}')

    return "\n".join(lines) + "\n"


def make_handler(cgroup_root):
    """Build an HTTP handler class that serves render_metrics(cgroup_root) at GET /metrics."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            """Serve the current metrics snapshot, or 404 for any path other than /metrics."""
            if self.path != "/metrics":
                self.send_response(404)
                self.end_headers()
                return

            body = render_metrics(cgroup_root).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # keep quiet on every scrape, matching the other exporters' default verbosity

    return Handler


def parse_args():
    """Parse --listen-address / --cgroup-root command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-address", default="0.0.0.0:9400")
    parser.add_argument("--cgroup-root", default=DEFAULT_CGROUP_ROOT)
    return parser.parse_args()


def main():
    """Parse arguments and serve /metrics until interrupted."""
    args = parse_args()
    host, _, port = args.listen_address.rpartition(":")

    server = http.server.ThreadingHTTPServer((host, int(port)), make_handler(args.cgroup_root))
    server.serve_forever()


if __name__ == "__main__":
    main()
