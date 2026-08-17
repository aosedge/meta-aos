#!/bin/bash
# Starts one or more sockperf server pairs (one UDP, one TCP) bound to a specific address, one
# pair per port starting at --start-port, for the network latency benchmark's "service to
# unit"/"service to external host" scenarios (see aos_core_cpp/doc/benchmark_execution.md,
# "Network" / "Latency" chapter).
#
# Runs in the foreground until interrupted (Ctrl+C) or terminated, then stops every sockperf
# server it started.

set -e

NUM_INSTANCES=1
START_PORT=11111
BIND_ADDRESS=

usage() {
    echo "Usage: $(basename "$0") -b BIND_ADDRESS [-n NUM_INSTANCES] [-p START_PORT]"
    echo
    echo "  -b BIND_ADDRESS   address to bind each sockperf server pair to (required)"
    echo "  -n NUM_INSTANCES  number of sockperf server pairs to start (default: 1)"
    echo "  -p START_PORT     first port to bind; pairs use START_PORT..START_PORT+NUM_INSTANCES-1"
    echo "                    (default: 11111)"
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
        echo "Stopping sockperf server(s):$PIDS"
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
    udp_log="/tmp/sockperf-${BIND_ADDRESS}-${port}-udp.log"
    tcp_log="/tmp/sockperf-${BIND_ADDRESS}-${port}-tcp.log"

    sockperf server -i "$BIND_ADDRESS" -p "$port" </dev/null >"$udp_log" 2>&1 &
    PIDS="$PIDS $!"
    echo "Started sockperf UDP server on ${BIND_ADDRESS}:${port} (pid $!, log: ${udp_log})"

    sockperf server -i "$BIND_ADDRESS" -p "$port" --tcp </dev/null >"$tcp_log" 2>&1 &
    PIDS="$PIDS $!"
    echo "Started sockperf TCP server on ${BIND_ADDRESS}:${port} (pid $!, log: ${tcp_log})"
done

echo "Press Ctrl+C to stop all servers."
wait
