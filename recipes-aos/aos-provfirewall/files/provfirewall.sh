#!/bin/sh

GATEWAY=$(ip route | grep default | awk '{print $3}' | head -n1)

if [ -z "$GATEWAY" ]; then
    echo "No default gateway found"
    exit 1
fi

iptables -A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A INPUT -s ${GATEWAY}/32 -p tcp -m tcp --dport 22 -j ACCEPT
iptables -A INPUT -s ${GATEWAY}/32 -j DROP
