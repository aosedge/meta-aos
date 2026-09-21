#!/usr/bin/env python3
"""Prometheus-format /metrics endpoint for any container/instance's cgroup CPU/memory usage.

process-exporter can't identify individual container instances (their cmdline carries no
instance/container ID - confirmed on a real target: a "load-test" instance's workload process
cmdline is just "/load-test"), and treydock/cgroup_exporter hardcodes a path depth that doesn't fit
every runtime's cgroup layout (confirmed both by reading its source and by running the real binary
against an AosCore target: its "cgroup" label collapses to "/system.slice/system-aos.slice" for
every instance, losing the instance ID entirely).

This script instead reads the same cgroup v2 accounting files directly (cpu.stat, memory.current),
for whichever cgroup paths --config lists - not tied to any one container runtime's layout. Each
config entry is a glob matched against the live filesystem on every scrape, plus an optional regex
to pull the instance/container ID out of the matched path's basename (see cgroup-exporter.yml for
the AosCore, Podman and k3s entries shipped by default).

Exposes:
  container_cpu_usage_seconds_total{instance="<id>"}  (counter, cumulative - use rate())
  container_memory_bytes{instance="<id>"}             (gauge)

Usage:
    cgroup_exporter.py [--listen-address 0.0.0.0:9400] [--config /etc/cgroup-exporter/cgroups.yml]
"""

import argparse
import glob
import http.server
import os
import re

import yaml


def load_config(config_path):
    """Return the list of {"path_glob": ..., "id_pattern": re.Pattern or None} entries."""
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    entries = []
    for group in data.get("cgroups", []):
        id_pattern = group.get("id_pattern")
        entries.append(
            {
                "path_glob": group["path_glob"],
                "id_pattern": re.compile(id_pattern) if id_pattern else None,
            }
        )

    return entries


def instance_id(cgroup_dir, id_pattern):
    """Return the instance/container ID for a matched cgroup directory, or None to skip it.

    With no id_pattern, the directory's basename is the ID as-is (a flat one-directory-per-instance
    layout, e.g. AosCore's). With an id_pattern, it's searched against the basename and the first
    capture group is the ID (e.g. Podman's "libpod-<container-id>.scope" directories); a directory
    that doesn't match is skipped rather than exposed under a confusing raw name.
    """
    basename = os.path.basename(cgroup_dir.rstrip("/"))

    if id_pattern is None:
        return basename

    match = id_pattern.search(basename)
    return match.group(1) if match else None


def read_cpu_usage_seconds(cgroup_dir):
    """Return the cgroup's cumulative CPU usage in seconds, read from cpu.stat."""
    with open(os.path.join(cgroup_dir, "cpu.stat")) as f:
        for line in f:
            key, _, value = line.partition(" ")
            if key == "usage_usec":
                return int(value) / 1_000_000
    raise ValueError("usage_usec not found in cpu.stat")


def read_memory_bytes(cgroup_dir):
    """Return the cgroup's current memory usage in bytes, read from memory.current."""
    with open(os.path.join(cgroup_dir, "memory.current")) as f:
        return int(f.read().strip())


def collect_instances(entries):
    """Return (instance_id, cpu_seconds, memory_bytes) for every cgroup matched by entries."""
    instances = []

    for entry in entries:
        for cgroup_dir in sorted(glob.glob(entry["path_glob"])):
            if not os.path.isdir(cgroup_dir):
                continue

            inst_id = instance_id(cgroup_dir, entry["id_pattern"])
            if inst_id is None:
                continue

            # An instance can stop between the glob() above and these reads - skip it for this
            # scrape rather than erroring the whole endpoint.
            try:
                cpu_seconds = read_cpu_usage_seconds(cgroup_dir)
            except (FileNotFoundError, ValueError):
                cpu_seconds = None

            try:
                memory_bytes = read_memory_bytes(cgroup_dir)
            except FileNotFoundError:
                memory_bytes = None

            instances.append((inst_id, cpu_seconds, memory_bytes))

    return instances


def render_metrics(entries):
    """Render current instance CPU/memory metrics in Prometheus text exposition format."""
    instances = collect_instances(entries)

    lines = [
        "# HELP container_cpu_usage_seconds_total Cumulative CPU time used by the container's cgroup.",
        "# TYPE container_cpu_usage_seconds_total counter",
    ]
    for inst_id, cpu_seconds, _ in instances:
        if cpu_seconds is not None:
            lines.append(f'container_cpu_usage_seconds_total{{instance="{inst_id}"}} {cpu_seconds:.6f}')

    lines += [
        "# HELP container_memory_bytes Current memory usage of the container's cgroup.",
        "# TYPE container_memory_bytes gauge",
    ]
    for inst_id, _, memory_bytes in instances:
        if memory_bytes is not None:
            lines.append(f'container_memory_bytes{{instance="{inst_id}"}} {memory_bytes}')

    return "\n".join(lines) + "\n"


def make_handler(entries):
    """Build an HTTP handler class that serves render_metrics(entries) at GET /metrics."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            """Serve the current metrics snapshot, or 404 for any path other than /metrics."""
            if self.path != "/metrics":
                self.send_response(404)
                self.end_headers()
                return

            body = render_metrics(entries).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # keep quiet on every scrape, matching the other exporters' default verbosity

    return Handler


def parse_args():
    """Parse --listen-address / --config command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-address", default="0.0.0.0:9400")
    parser.add_argument("--config", default="/etc/cgroup-exporter/cgroups.yml")
    return parser.parse_args()


def main():
    """Parse arguments, load the cgroup list, and serve /metrics until interrupted."""
    args = parse_args()
    host, _, port = args.listen_address.rpartition(":")
    entries = load_config(args.config)

    server = http.server.ThreadingHTTPServer((host, int(port)), make_handler(entries))
    server.serve_forever()


if __name__ == "__main__":
    main()
