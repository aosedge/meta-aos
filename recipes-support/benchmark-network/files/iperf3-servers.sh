#!/bin/bash
# Starts one or more iperf3 servers bound to a specific address, one per port starting at
# --start-port, for the network bandwidth benchmark's "service to unit"/"service to external
# host" scenarios (see aos_core_cpp/doc/benchmark_execution.md, "Network" / "Bandwidth" chapter).
#
# Runs in the foreground until interrupted (Ctrl+C) or terminated, then stops every iperf3
# server it started.

set -e

NUM_INSTANCES=1
START_PORT=5201
BIND_ADDRESS=

usage() {
    echo "Usage: $(basename "$0") -b BIND_ADDRESS [-n NUM_INSTANCES] [-p START_PORT]"
    echo
    echo "  -b BIND_ADDRESS   address to bind each iperf3 server to (required)"
    echo "  -n NUM_INSTANCES  number of iperf3 servers to start (default: 1)"
    echo "  -p START_PORT     first port to bind; servers use START_PORT..START_PORT+NUM_INSTANCES-1"
    echo "                    (default: 5201)"
    echo
    echo "Runs in the foreground; press Ctrl+C to stop every server it started."
    exit 1
}

while getopts "b:n:p:h" opt; do
    case "$opt" in
    b) BIND_ADDRESS="$OPTARG" ;;
    n) NUM_INSTANCES="$OPTARG" ;;
    p) START_PORT="$OPTARG" ;;
    h | *) usage ;;
    esac
done

[ -n "$BIND_ADDRESS" ] || usage

PIDS=""
CLEANED_UP=""

cleanup() {
    [ -z "$CLEANED_UP" ] || return 0
    CLEANED_UP=1

    if [ -n "$PIDS" ]; then
        echo "Stopping iperf3 server(s):$PIDS"
        # shellcheck disable=SC2086
        kill $PIDS 2>/dev/null || true
        wait 2>/dev/null || true
    fi
}

trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

for i in $(seq 0 $((NUM_INSTANCES - 1))); do
    port=$((START_PORT + i))
    log="/tmp/iperf3-${BIND_ADDRESS}-${port}.log"

    iperf3 -s -p "$port" -B "$BIND_ADDRESS" </dev/null >"$log" 2>&1 &
    PIDS="$PIDS $!"

    echo "Started iperf3 server on ${BIND_ADDRESS}:${port} (pid $!, log: ${log})"
done

echo "Press Ctrl+C to stop all servers."

wait
