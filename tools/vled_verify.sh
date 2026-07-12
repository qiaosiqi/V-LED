#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
device=${VLED_DEVICE:-/dev/vled}
iterations=${VLED_ITERATIONS:-200}
cycles=${VLED_LIFECYCLE_CYCLES:-3}
module="$repo_dir/driver/vled.ko"
loaded=0
run_start=$(date --iso-8601=seconds)

cleanup() {
    if [[ $loaded -eq 1 ]]; then
        sudo rmmod vled || true
    fi
}
trap cleanup EXIT INT TERM

if lsmod | awk '{print $1}' | grep -qx vled; then
    echo "Refusing to replace an already loaded vled module; run 'sudo rmmod vled' first." >&2
    exit 2
fi

echo "== build driver and tools =="
make -C "$repo_dir/driver" clean
make -C "$repo_dir/driver" V=1
make -C "$repo_dir/tools" clean
make -C "$repo_dir/tools" CFLAGS='-Wall -Wextra -Werror -O2'

echo "== bridge black-box acceptance =="
python3 "$repo_dir/tools/vled_bridge_probe.py" --bridge "$repo_dir/tools/vled_bridge"

echo "== load module and validate device =="
sudo insmod "$module"
loaded=1
for _ in {1..50}; do
    [[ -c $device ]] && break
    sleep 0.1
done
[[ -c $device ]] || { echo "$device was not created as a character device" >&2; exit 1; }
sudo chmod 666 "$device"
ls -l "$device"
lsmod | grep '^vled '
modinfo "$module"

echo "== P1 regression probe =="
"$repo_dir/tools/vled_fd_probe" "$device"

echo "== P3 business and concurrency acceptance =="
python3 "$repo_dir/tools/vled_verify.py" --device "$device" \
    --cli "$repo_dir/tools/vled_cli" --iterations "$iterations"

echo "== repeated module lifecycle =="
for ((cycle=1; cycle<=cycles; cycle++)); do
    sudo rmmod vled
    loaded=0
    [[ ! -e $device ]] || { echo "$device remained after rmmod cycle $cycle" >&2; exit 1; }
    sudo insmod "$module"
    loaded=1
    for _ in {1..50}; do
        [[ -c $device ]] && break
        sleep 0.1
    done
    [[ -c $device ]] || { echo "$device missing after insmod cycle $cycle" >&2; exit 1; }
    echo "PASS lifecycle cycle $cycle"
done

echo "== kernel log check =="
kernel_log=$(sudo journalctl -k --since "$run_start" --no-pager)
printf '%s\n' "$kernel_log"
if grep -Eqi 'warning|oops|BUG:|lockdep|use-after-free|general protection fault' <<<"$kernel_log"; then
    echo "Kernel log contains a severe diagnostic during the P3 run" >&2
    exit 1
fi

echo "VLED P3 verify: PASS (module will be unloaded by cleanup trap)"
