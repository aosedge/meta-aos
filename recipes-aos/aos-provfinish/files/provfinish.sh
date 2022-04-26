#!/bin/sh

# remove unprovisioned flag
rm -rf /var/aos/.unprovisioned

# restart aos target
systemctl restart aos.target
