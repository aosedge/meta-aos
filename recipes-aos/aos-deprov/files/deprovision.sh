#!/bin/sh

COMMAND="$1"

clear_disks() {
    echo "Remove IAM DB and PKCS11 storage"
    rm /var/aos/iam -rf
    /opt/aos/clearhsm.sh

    echo "Delete Aos disks"
    /opt/aos/setupdisk.sh delete

    sync
}

deprovision_async() {
    {
        sleep 1

        # use systemctl stop all aos.target services instead of systemctl stop aos.target, because this approach doesn't wait
        # all services really stopped.
        systemctl stop -- $(systemctl show -p Wants aos.target | cut -d= -f2)

        echo "Restore unprovisioned flag" | systemd-cat
        rm /var/aos/.provisionstate -f

        systemctl start aos.target
    } > /dev/null 2>&1 &
}

case "$COMMAND" in
async)
    deprovision_async
    ;;

*)
    clear_disks
    ;;
esac
