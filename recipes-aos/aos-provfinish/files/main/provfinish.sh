#!/bin/sh

sync

# restart aos target
{
    sleep 1
    systemctl restart rpc-rquotad.service
    systemctl restart aos.target
} > /dev/null 2>&1 &
