#!/bin/sh

GATEWAY=$(ip route | grep default | awk '{print $3}' | head -n1)

if [ -z "$GATEWAY" ]; then
    echo "No default gateway found"
    exit 1
fi

apply_rules() {
    INTERFACE=$1
    SUBNET=$(ip -o -f inet addr show $INTERFACE | awk '{print $4}' | cut -d'/' -f1-2)
    
    if [ -z "$SUBNET" ]; then
        echo "No IP address found for $INTERFACE"
        return
    fi

    for PROTO in tcp udp; do
        iptables -A INPUT -s $GATEWAY/32 -d $SUBNET -i $INTERFACE -p $PROTO -m $PROTO --dport 8089 -j DROP
        iptables -A INPUT ! -s $SUBNET -d $SUBNET -i $INTERFACE -p $PROTO -m $PROTO --dport 8089 -j DROP
        iptables -A INPUT -s $SUBNET -d $SUBNET -i $INTERFACE -p $PROTO -m $PROTO --dport 8089 -j ACCEPT
    done
}

find /sys/class/net/*/device | cut -d/ -f5 |
    while read -r INTERFACE; do
        apply_rules "$INTERFACE"
    done
