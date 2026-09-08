#!/bin/bash
# handle_l2_snap.sh — L2 VM snapshot / restore manager
#
# Usage:
#   handle_l2_snap.sh --full [N] <name>          full snapshot -> /home/snap-<name>/
#   handle_l2_snap.sh --inc [N] <name> <base>    incremental snapshot (base memory-ranges must exist in /home/snap-<base>/)
#   handle_l2_snap.sh --restore [N] <name>       stop VM + fresh VMM + restore from /home/snap-<name>/
#   handle_l2_snap.sh --list                     list local snapshots
#
# Snapshot dir layout: /home/snap-<name>/{config.json,state.json,memory-ranges}
# Machine-readable output: SNAPSHOT_OK: <name> | RESTORE_OK: <name> | FAILED: <reason>
set -e

VMM=${VMM:-/home/cube/cube-hypervisor}
CH_REMOTE=${CH_REMOTE:-/home/cube/ch-remote}
SNAP_ROOT=/home

CMD=$1; shift || true

usage() { sed -n "2,10p" "$0" | sed "s/^# \{0,1\}//"; exit 1; }
fail() { echo "FAILED: $1"; exit 1; }
[ -n "$CMD" ] || usage

api() { local s=$1; shift; curl -sf --unix-socket "$s" "$@"; }
vm_state() { api "$1" http://localhost/api/v1/vm.info | python3 -c "import sys,json;print(json.load(sys.stdin)[\"state\"])"; }
wait_state() { # sock state timeout_sec
    for i in $(seq 1 $3); do
        [ "$(vm_state $1 2>/dev/null || true)" = "$2" ] && return 0
        sleep 1
    done
    return 1
}
valid_name() { [[ "$1" =~ ^[A-Za-z0-9._-]+$ ]]; }

ensure_paused() { # sock
    local ST
    ST=$(vm_state "$1" 2>/dev/null || echo absent)
    case "$ST" in
        Paused) ;;
        Running) api "$1" -X PUT http://localhost/api/v1/vm.pause >/dev/null || fail pause_api ;;
        *) fail "vm_state=$ST" ;;
    esac
}

case "$CMD" in
--full|--inc|--restore)
    # resolve optional leading instance number N (default 0)
    if [[ "$1" =~ ^[0-9]+$ ]]; then N=$1; shift; else N=0; fi
    NAME=$1; [ -n "$NAME" ] || usage
    valid_name "$NAME" || fail invalid_name
    DEST=$SNAP_ROOT/snap-$NAME
    API_SOCK=/tmp/ch-$N.sock
    TAP=tap$N
    insmod /root/pvm/arch/arm64/kvm/kvm-pvm.ko 2>/dev/null || true
    lsmod | grep -q kvm_pvm || fail kvm_pvm_module
    ;;
esac

case "$CMD" in
--full)
    [ -S "$API_SOCK" ] || fail no_vmm
    [ -e "$DEST" ] && fail dest_exists
    ensure_paused "$API_SOCK"
    mkdir -p "$DEST"
    $CH_REMOTE --api-socket "$API_SOCK" snapshot "file://$DEST" >/dev/null || { rm -rf "$DEST"; fail snapshot_api; }
    echo "SNAPSHOT_OK: $NAME (full)"
    ;;

--inc)
    BASE=$2; [ -n "$BASE" ] || usage
    valid_name "$BASE" || fail invalid_base
    BASEDIR=$SNAP_ROOT/snap-$BASE
    [ -f "$BASEDIR/memory-ranges" ] || fail base_not_found
    [ -S "$API_SOCK" ] || fail no_vmm
    [ -e "$DEST" ] && fail dest_exists
    ensure_paused "$API_SOCK"
    mkdir -p "$DEST"
    cp "$BASEDIR/memory-ranges" "$DEST/memory-ranges"
    # incremental overwrites CoW anon pages in-place; config/state must be absent
    $CH_REMOTE --api-socket "$API_SOCK" snapshot --snapshot-type incremental "file://$DEST" >/dev/null || { rm -rf "$DEST"; fail snapshot_api; }
    echo "SNAPSHOT_OK: $NAME (incremental, base=$BASE)"
    ;;

--restore)
    # stop existing VM/VMM on the standard socket
    if [ -S "$API_SOCK" ]; then
        api "$API_SOCK" -X PUT http://localhost/api/v1/vm.shutdown >/dev/null 2>&1 || true
        sleep 1
    fi
    pkill -9 -f "api-socket $API_SOCK" 2>/dev/null || true
    rm -f "$API_SOCK"

    [ -f "$DEST/config.json" ] && [ -f "$DEST/state.json" ] && [ -f "$DEST/memory-ranges" ] || fail snapshot_incomplete

    # bridge + tap (VM keeps tap$N per config in snapshot)
    ip link show br-l2 >/dev/null 2>&1 || { ip link add br-l2 type bridge; ip addr add 192.168.249.1/24 dev br-l2; ip link set br-l2 up; }
    ip link del "$TAP" 2>/dev/null || true
    ip neigh flush dev br-l2 2>/dev/null || true
    ip tuntap add "$TAP" mode tap
    ip link set "$TAP" master br-l2
    ip link set "$TAP" up

    setsid "$VMM" --api-socket "$API_SOCK" > /tmp/ch-$N-stdout.log 2>&1 &
    for i in $(seq 1 60); do curl -s -o /dev/null --unix-socket "$API_SOCK" http://localhost/api/v1/vm.info && break; sleep 0.5; done
    [ -S "$API_SOCK" ] || fail vmm_start

    $CH_REMOTE --api-socket "$API_SOCK" restore "source_url=file://$DEST" >/dev/null || fail restore_api
    wait_state "$API_SOCK" Running 30 || fail "vm_state_timeout"
    echo "RESTORE_OK: $NAME (instance $N)"
    ;;

--list)
    for d in $SNAP_ROOT/snap-*/; do
        [ -d "$d" ] || continue
        n=$(basename "$d")
        if [ -f "$d/state.json" ]; then
            t=$(python3 -c "import json;d=json.load(open(\"$d/state.json\"));print(d.get(\"metadata\",{}).get(\"snapshot_type\",\"?\"))" 2>/dev/null || echo "?")
        else
            t="incomplete"
        fi
        printf "%-20s %s\n" "${n#snap-}" "$t"
    done
    ;;

*) usage ;;
esac
