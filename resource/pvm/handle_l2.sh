#!/bin/bash
# handle_l2.sh — unified L2 VM lifecycle manager (start / shutdown / boot / delete)
#
# Usage:
#   handle_l2.sh --start    [N|IP]    create + boot + wait SSH-ready   (default instance 0)
#   handle_l2.sh --shutdown [N|IP]    graceful guest poweroff, VM stays "Created" (rebootable)
#   handle_l2.sh --boot     [N|IP]    boot an existing Created VM (after --shutdown)
#   handle_l2.sh --pause    [N|IP]    pause a Running VM (snapshot prerequisite)
#   handle_l2.sh --resume   [N|IP]    resume a Paused VM (continue from pause point)
#   handle_l2.sh --delete   [N|IP]    destroy VM + VMM + tap (no args = delete ALL)
#   handle_l2.sh --status   [N|IP]    show VM state
#
# Target: <N|IP> is instance number (0,1,2... -> 192.168.249.(N+2)) or explicit IP in 192.168.249.0/24
# Machine-readable output:
#   SUCCESS: <l2_ip> | SHUTDOWN: <l2_ip> | BOOTED: <l2_ip> | DELETED: <name> | state=<State>
#   FAILED: <reason>
set -e

CMD=${1:-}
if [ -z "$CMD" ]; then
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
fi
[ "${CMD#--}" != "$CMD" ] || { echo "FAILED: invalid_argument (use --start/--shutdown/--boot/--pause/--resume/--delete/--status)"; exit 1; }
ARG=${2:-0}
[ "$CMD" = "--delete" ] && ARG=${2:-}   # --delete with no arg = delete ALL

# ── resolve target -> L2_IP / TAP / N ──────────────────────
if [[ "$ARG" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    L2_IP=$ARG
    S3=${L2_IP##*.}
    [ "$S3" -ge 1 ] && [ "$S3" -le 254 ] || { echo "FAILED: ip_last_octet_out_of_range"; exit 1; }
    case "$L2_IP" in 192.168.249.*) ;; *) echo "FAILED: ip_not_in_192.168.249.0/24"; exit 1;; esac
    TAP=tap$((S3-2)); N=$((S3-2))
else
    N=$ARG
    # --delete allows no-arg (N empty -> delete all instances)
    if [ "$CMD" != "--delete" ] || [ -n "$N" ]; then
        [ "$N" -ge 0 ] && [ "$N" -le 252 ] 2>/dev/null || { echo "FAILED: invalid_argument (use instance N or IP)"; exit 1; }
    fi
    L2_IP=192.168.249.$((N+2)); TAP=tap$N
fi
[ -n "${L2_IP:-}" ] || L2_IP=192.168.249.2

API_SOCK=/tmp/ch-$N.sock
VMM=${VMM:-/home/cube/cube-hypervisor}

API() { curl -s --unix-socket "$API_SOCK" "http://localhost/api/v1/$1"; }
api_state() { API vm.info | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])" 2>/dev/null; }
wait_ssh() {  # wait SSH ready on $L2_IP, max 60s
    for i in $(seq 1 60); do
        ssh -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=no "root@$L2_IP" true 2>/dev/null && return 0
        sleep 1
    done
    return 1
}

# ── --delete (supports no-arg = all) ───────────────────────
if [ "$CMD" = "--delete" ]; then
    if [ -z "$N" ]; then
        FOUND=0
        for sock in /tmp/ch-*.sock; do
            [ -e "$sock" ] || break
            X=$(basename "$sock" .sock); X=${X#ch-}
            bash "$0" --delete "$X" && FOUND=1
        done
        for tap in $(ls /sys/class/net 2>/dev/null | grep -E '^tap[0-9]+$' || true); do
            ip link del "$tap" 2>/dev/null || true
        done
        echo "DELETED: all"; exit 0
    fi
    if [ -S "$API_SOCK" ]; then
        pkill -9 -f "api-socket $API_SOCK" 2>/dev/null || true
        rm -f "$API_SOCK" "/tmp/vmcfg-$N.json" "/tmp/ch-$N-stdout.log" 2>/dev/null || true
        echo "DELETED: $N"
    fi
    ip link del "$TAP" 2>/dev/null || true
    exit 0
fi

# ── all other commands need a concrete N ──────────────────
case "$CMD" in
--status)
    if [ -S "$API_SOCK" ]; then
        echo "state=$(api_state)"
    else
        echo "state=absent"
    fi
    ;;

--shutdown)
    [ -S "$API_SOCK" ] || { echo "FAILED: vm_not_running"; exit 1; }
    ST=$(api_state)
    if [ "$ST" = "Created" ]; then
        echo "SHUTDOWN: $L2_IP (state=Created, already off)"
        exit 0
    fi
    # note: state flips to Created only AFTER guest finishes poweroff (a few seconds)
    if curl -sf --unix-socket "$API_SOCK" -X PUT http://localhost/api/v1/vm.shutdown >/dev/null 2>&1; then
        ST=""
        for i in $(seq 1 30); do
            ST=$(api_state) || true
            [ "$ST" = "Created" ] && break
            sleep 1
        done
        echo "SHUTDOWN: $L2_IP (state=${ST:-unknown})"
        [ "$ST" = "Created" ] || { echo "FAILED: shutdown_timeout (state=$ST)"; exit 1; }
    else
        echo "FAILED: shutdown_api"; exit 1
    fi
    ;;

--boot)
    [ -S "$API_SOCK" ] || { echo "FAILED: no_vmm (use --start)"; exit 1; }
    ST=$(api_state)
    if [ "$ST" = "Running" ]; then
        echo "BOOTED: $L2_IP (state=Running, already running)"
        exit 0
    fi
    [ "$ST" = "Created" ] || { echo "FAILED: vm_state=$ST (need Created, use --start for fresh VM)"; exit 1; }
    curl -sf --unix-socket "$API_SOCK" -X PUT http://localhost/api/v1/vm.boot || { echo "FAILED: boot_api"; exit 1; }
    wait_ssh && echo "BOOTED: $L2_IP" || { echo "FAILED: ssh_not_ready"; exit 1; }
    ;;

--pause)
    [ -S "$API_SOCK" ] || { echo "FAILED: no_vmm (use --start)"; exit 1; }
    ST=$(api_state)
    [ "$ST" = "Running" ] || { echo "FAILED: vm_state=$ST (need Running)"; exit 1; }
    curl -sf --unix-socket "$API_SOCK" -X PUT http://localhost/api/v1/vm.pause || { echo "FAILED: pause_api"; exit 1; }
    echo "PAUSED: $L2_IP"
    ;;

--resume)
    [ -S "$API_SOCK" ] || { echo "FAILED: no_vmm (use --start)"; exit 1; }
    ST=$(api_state)
    if [ "$ST" = "Running" ]; then
        echo "RESUMED: $L2_IP (state=Running, already running)"
        exit 0
    fi
    [ "$ST" = "Paused" ] || { echo "FAILED: vm_state=$ST (need Paused)"; exit 1; }
    curl -sf --unix-socket "$API_SOCK" -X PUT http://localhost/api/v1/vm.resume || { echo "FAILED: resume_api"; exit 1; }
    wait_ssh && echo "RESUMED: $L2_IP" || { echo "FAILED: ssh_not_ready"; exit 1; }
    ;;

--start)
    # kvm-pvm module (lost on L1 reboot — reload if missing)
    insmod /root/pvm/arch/arm64/kvm/kvm-pvm.ko 2>/dev/null || true
    lsmod | grep -q kvm_pvm || { echo "FAILED: kvm_pvm_module"; exit 1; }

    # bridge + per-instance tap
    if ! ip link show br-l2 >/dev/null 2>&1; then
        ip link add br-l2 type bridge
        ip addr add 192.168.249.1/24 dev br-l2
        ip link set br-l2 up
    fi
    ip link del "$TAP" 2>/dev/null || true
    ip neigh flush dev br-l2 2>/dev/null || true
    ip tuntap add "$TAP" mode tap
    ip link set "$TAP" master br-l2
    ip link set "$TAP" up

    # VMM (kill stale first, poll until socket answers)
    pkill -9 -f "api-socket $API_SOCK" 2>/dev/null || true
    rm -f "$API_SOCK"
    setsid "$VMM" --api-socket "$API_SOCK" > /tmp/ch-$N-stdout.log 2>&1 &
    VMM_READY=""
    for i in $(seq 1 60); do
        curl -s -o /dev/null --unix-socket "$API_SOCK" http://localhost/api/v1/vm.info && { VMM_READY=1; break; }
        sleep 0.5
    done
    [ -n "$VMM_READY" ] || { echo "FAILED: vmm_start (see /tmp/ch-$N-stdout.log)"; exit 1; }

    # per-instance vmcfg (inject IP via cmdline, unique MAC)
    VMTMP=/tmp/vmcfg-$N.json
    python3 - "$TAP" "$L2_IP" <<'PYEOF' > "$VMTMP"
import json, sys
tap, l2ip = sys.argv[1], sys.argv[2]
cfg = json.load(open("/home/vmcfg.json"))
cfg["payload"]["cmdline"] += f" ip={l2ip}"
cfg["net"][0]["tap"] = tap
cfg["net"][0]["mac"] = "52:54:00:" + ":".join(f"{int(x):02x}" for x in l2ip.split(".")[1:])
json.dump(cfg, sys.stdout)
PYEOF

    # create + boot + wait Running
    curl -sf --unix-socket "$API_SOCK" -X PUT \
      http://localhost/api/v1/vm.create \
      -H 'Content-Type: application/json' -d @"$VMTMP" || { echo "FAILED: vm_create"; exit 1; }
    curl -sf --unix-socket "$API_SOCK" -X PUT http://localhost/api/v1/vm.boot || { echo "FAILED: vm_boot"; exit 1; }
    STATE=""
    for i in $(seq 1 30); do
        STATE=$(api_state) || true
        [ "$STATE" = "Running" ] && break
        sleep 1
    done
    [ "$STATE" = "Running" ] || { echo "FAILED: vm_state=${STATE:-unknown}"; exit 1; }

    # console pty (for manual debug)
    PTY=$(API vm.info | python3 -c "import sys,json; print(json.load(sys.stdin)['config']['serial']['file'])")
    chmod 620 "$PTY" 2>/dev/null || true

    wait_ssh && echo "SUCCESS: $L2_IP" || { echo "FAILED: ssh_not_ready (console: screen $PTY)"; exit 1; }
    ;;

*) echo "FAILED: unknown_command"; exit 1 ;;
esac
