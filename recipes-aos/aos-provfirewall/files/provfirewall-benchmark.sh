#!/bin/sh

# Same as provfirewall.sh, plus one extra accept rule for VictoriaMetrics' query API (port 8428)
# so Grafana, running off-target, can reach it - see aos_core_cpp/scripts/monitoring and
# doc/benchmark.md. Only installed when DISTRO_FEATURES contains "benchmark" (see
# aos-provfirewall.bb); keep in sync with provfirewall.sh otherwise.

GATEWAY=$(ip route | grep default | awk '{print $3}' | head -n1)

if [ -z "$GATEWAY" ]; then
    echo "No default gateway found"
    exit 1
fi

# Recreate the table from scratch so re-runs stay idempotent.
nft delete table inet aos-provfw 2>/dev/null

nft -f - <<EOF
table inet aos-provfw {
    chain input {
        type filter hook input priority 0; policy accept;
        ct state established,related accept
        ip saddr ${GATEWAY} tcp dport 22 accept
        ip saddr ${GATEWAY} tcp dport 8428 accept
        ip saddr ${GATEWAY} drop
    }
}
EOF
