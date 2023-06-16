#!/bin/sh

set -e

# default values

MAPPED_DEVICE="aos"
TOKEN_LABEL="aoscore"
OBJECT_LABEL="diskencryption"
KEY_SLOT=0
TOKEN_ID=0

usage() {
    echo "Usage: ./$(basename -- "$0") [OPTIONS...] COMMAND DEVICE"
    echo "COMMAND is one of:"
    echo "    encrypt             Encrypt DEVICE"
    echo "    open                Open encrypted DEVICE"
    echo "OPTIONS:"
    echo "    -m  --module        PKCS11 module used to perform encrypt/decrypt operations"
    echo "    -t  --token-label   Label of PKCS11 token used for encrypt/decrypt operations"
    echo "    -i  --id            PKCS11 key/cert ID for encrypt/decrypt operations"
    echo "    -l  --label         PKCS11 key/cert label for encrypt/decrypt operations"
    echo "    -p  --user-pin      User pin for PKCS11 module used for encrypt/decrypt operations"
    echo "    -n  --mapped-device Mapped device name"
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

OPTIONS=$(getopt -o hm:t:i:l:p:n: --long help,module:,token-label:,id:,label:,pin:,mapped-device: -- "$@")

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

    -k | --id)
        shift
        OBJECT_ID="$1"
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

    --)
        shift
        break
        ;;
    *)
        usage
        ;;
    esac
done

if [ "$#" -ne 2 ]; then
    error "wrong number of arguments"
    usage
fi

if [ -z "${MODULE}" ]; then
    error "mandatory option --module is not set"
    usage
fi

COMMAND=$1
DEVICE=$2

# create run dir if not exist
mkdir -p -m 0700 /run/cryptsetup

create_uri() {
    local uri="pkcs11:"

    if [ -n "$TOKEN_LABEL" ]; then
        uri="${uri}token=$TOKEN_LABEL;"
    fi

    if [ -n "$OBJECT_LABEL" ]; then
        uri="${uri}object=$OBJECT_LABEL;"
    fi

    if [ -n "$OBJECT_ID" ]; then
        uri="${uri}id=$OBJECT_ID;"
    fi

    echo ${uri%;}
}

encrypt_device() {
    echo "Encrypting device: $DEVICE ..."

    local tmp_path="/tmp/aos"

    mkdir -p $tmp_path

    # generate random passcode half of RSA key len size (2048/2)
    local passcode=$(head -c 128 /dev/random | base64 -w 0)

    # encrypt passcode
    pkcs11-tool -r --module "$MODULE" ${USER_PIN:+-p "$USER_PIN"} ${TOKEN_LABEL:+--token-label "$TOKEN_LABEL"} \
        ${OBJECT_LABEL:+-a "$OBJECT_LABEL"} ${OBJECT_ID:+-d "$OBJECT_ID"} --type cert -o $tmp_path/encrypt.cert
    openssl x509 -inform DER -in $tmp_path/encrypt.cert -pubkey -out $tmp_path/encrypt.pub
    echo $passcode | base64 -d | openssl pkeyutl -encrypt -inkey $tmp_path/encrypt.pub -pubin -out $tmp_path/passcode.enc

    # encrypt disk
    echo $passcode | cryptsetup -q --type luks2 luksFormat $DEVICE

    local aos_token=$(jq -n -c \
        --arg type "aos-pkcs11" \
        --argjson keyslots [\"$KEY_SLOT\"] \
        --arg pkcs11-uri "$(create_uri)" \
        --arg pkcs11-key "$(base64 -w 0 $tmp_path/passcode.enc)" \
        '$ARGS.named')

    # set token
    echo $aos_token | cryptsetup token import --key-slot 0 $DEVICE

    rm -rf $tmp_path

    echo "Success"
}

parse_uri() {
    local proto=${1%:*}

    if [ "$proto" != "pkcs11" ]; then
        fatal "wrong protocol $proto"
    fi

    echo ${1#*:} | while IFS=';' read -r p; do
        local name="${p%=*}"
        local value="${p#*=}"

        case ${name} in
        token)
            # take token label from pkcs11 uri if not specified
            if [ -z "$TOKEN_LABEL" ]; then
                TOKEN_LABEL=$value
            fi
            ;;

        object)
            # take object label from pkcs11 uri if not specified
            if [ -z "$OBJECT_LABEL" ]; then
                OBJECT_LABEL=$value
            fi
            ;;

        id)
            # take object id from pkcs11 uri if not specified
            if [ -z "$OBJECT_ID" ]; then
                OBJECT_ID=$value
            fi
            ;;
        esac
    done

    IFS=' '
}

get_key_id() {
    pkcs11-tool -O --module "$MODULE" ${USER_PIN:+-p "$USER_PIN"} \
        ${TOKEN_LABEL:+--token-label "$TOKEN_LABEL"} ${OBJECT_LABEL:+-a "$OBJECT_LABEL"} \
        --type privkey | while read -r line; do
        local name=${line%:*}
        local value=${line##*:*[[:space:]]}

        case $name in
        label)
            current_label=$value
            ;;

        ID)
            if [ "$OBJECT_LABEL" == "$current_label" ]; then
                echo $value
            fi
            ;;
        esac
    done
}

open_device() {
    echo "Opening device: $DEVICE ..."

    local aos_token=$(cryptsetup token export "$DEVICE" --token-id "$TOKEN_ID")

    if [ -z "$aos_token" ]; then
        fatal "can't get Aos token from device"
    fi

    local pkcs11_uri=$(echo $aos_token | jq -r '."pkcs11-uri"')
    local pkcs11_key=$(echo $aos_token | jq -r '."pkcs11-key"')

    parse_uri $pkcs11_uri

    if [ -n "$OBJECT_LABEL" ] && [ -z "$OBJECT_ID" ]; then
        OBJECT_ID=$(get_key_id)

        if [ -z "$OBJECT_ID" ]; then
            fatal "key id not found"
        fi
    fi

    # decrypt passcode
    local passcode=$(echo $pkcs11_key | base64 -d | pkcs11-tool --decrypt -m RSA-PKCS --module "$MODULE" \
        ${USER_PIN:+-p "$USER_PIN"} ${TOKEN_LABEL:+--token-label "$TOKEN_LABEL"} ${OBJECT_ID:+-d "$OBJECT_ID"} |
        base64 -w 0)

    # open device
    echo $passcode | cryptsetup open "$DEVICE" "$MAPPED_DEVICE"

    echo "Success"
}

case $COMMAND in
encrypt)
    encrypt_device
    ;;

open)
    open_device
    ;;

*)
    error "wrong command $COMMAND"
    usage
    ;;
esac
