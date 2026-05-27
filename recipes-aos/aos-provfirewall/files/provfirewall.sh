#!/bin/sh

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
        ip saddr ${GATEWAY} drop
    }
}
EOF
