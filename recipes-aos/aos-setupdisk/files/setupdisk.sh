#!/bin/bash

set -e

# default values

TOKEN_LABEL="aoscore"
OBJECT_LABEL="diskencryption"
CONFIG_FILE="/opt/aos/aosdisk.cfg"
MAPPED_DEVICE="aos"

usage() {
    echo "Usage: ./$(basename -- "$0") [OPTIONS...] COMMAND [DEVICE]"
    echo "COMMAND:"
    echo "     create             Creates Aos disks"
    echo "     delete             Deletes Aos disks"
    echo "OPTIONS:"
    echo "    -m  --module        PKCS11 module used to open encrypted disk"
    echo "    -t  --token-label   Label of PKCS11 token used for encrypt/decrypt operations"
    echo "    -l  --label         PKCS11 object label for encrypt/decrypt operations"
    echo "    -p  --user-pin      User pin for PKCS11 module used for encrypt/decrypt operations"
    echo "    -n  --mapped-device Mapped device name"
    echo "    -c  --config        Setup disk configuration"
    echo "Help options:"
    echo "    -h, --help          Show this help message"

    exit 1
}

error() {
    echo "Error: $1" >&2
}

fatal() {
    error "$1"
    exit 1
}

get_mount_point() {
    while read -r device mount_point; do
        # skip comments
        if [[ $device = \#* ]]; then
            continue
        fi

        if [ "$1" == "$device" ]; then
            echo "$mount_point"
            return
        fi
    done <"/etc/fstab"

    fatal "mount point for $1 not found"
}

create_aos_disks() {
    device=$1

    if [ -z "${MODULE}" ]; then
        error "mandatory option --module is not set"
        usage
    fi

    if [ -z "$device" ]; then
        error "device is not specified"
        usage
    fi

    # encrypt disk
    diskencryption.sh encrypt "$device" -m "$MODULE" -t "$TOKEN_LABEL" -l "$OBJECT_LABEL"
    # open disk
    diskencryption.sh open "$device" -m "$MODULE" -t "$TOKEN_LABEL" -l "$OBJECT_LABEL" ${USER_PIN:+-p "$USER_PIN"} \
        -n "$MAPPED_DEVICE"

    # create logical disks

    # create run dir if not exist
    mkdir -p -m 0700 /run/lvm
    mkdir -p -m 0700 /run/lock/lvm

    pvcreate /dev/mapper/$MAPPED_DEVICE
    vgcreate "$AOS_GROUP" /dev/mapper/$MAPPED_DEVICE

    while read -r name size enable_quota; do
        # skip comments
        if [[ $name = \#* ]]; then
            continue
        fi

        lvcreate -l "$size" "$AOS_GROUP" -n "$name"
        mkfs.ext4 "/dev/$AOS_GROUP/$name"
        mkdir -p "$(get_mount_point "/dev/$AOS_GROUP/$name")"
    done <"$CONFIG_FILE"

    # wait all parts are mounted
    mount -a

    while read -r name size enable_quota; do
        # skip comments
        if [[ $name = \#* ]]; then
            continue
        fi

        if [ "$enable_quota" -eq 1 ]; then
            quotacheck -cum "/dev/$AOS_GROUP/$name"
        fi
    done <"$CONFIG_FILE"

    # on quota
    quotaon -aug
}

delete_aos_disks() {
    while read -r name size enable_quota; do
        # skip comments
        if [[ $name = \#* ]]; then
            continue
        fi

        mountdir=$(get_mount_point "/dev/$AOS_GROUP/$name")

        if mountpoint -q "$mountdir"; then
            umount "$mountdir"
        fi

    done <"$CONFIG_FILE"

    lvremove -f -q "$AOS_GROUP"
    cryptsetup close $MAPPED_DEVICE
}

OPTIONS=$(getopt -o hm:t:l:p:n:c: --long help,module:,token-label:,label:,user-pin:,mapped-device:,config: -- "$@")

eval set -- "$OPTIONS"

while :; do
    case "$1" in
    -h | --help)
        usage
        ;;

    -m | --module)
        shift
        MODULE="$1"
        shift
        ;;

    -t | --token-label)
        shift
        TOKEN_LABEL="$1"
        shift
        ;;

    -l | --label)
        shift
        OBJECT_LABEL="$1"
        shift
        ;;

    -p | --pin)
        shift
        USER_PIN="$1"
        shift
        ;;

    -n | --mapped-device)
        shift
        MAPPED_DEVICE="$1"
        shift
        ;;

    -c | --config)
        shift
        CONFIG_FILE="$1"
        shift
        ;;

    --)
        shift
        break
        ;;
    *)
        usage
        ;;
    esac
done

COMMAND="$1"
AOS_GROUP="aosvg"

case "$COMMAND" in
create)
    create_aos_disks "$2"
    ;;

delete)
    delete_aos_disks
    ;;

*)
    error "wrong command"
    usage
    ;;
esac
