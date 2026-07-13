#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
windows_ip=${1:-}
device=${2:-/dev/vled}

if [[ -z $windows_ip || $# -gt 2 ]]; then
    echo "Usage: $0 <windows_ip> [device]" >&2
    exit 2
fi
if [[ ! -c $device ]]; then
    echo "$device is not a character device; load vled first" >&2
    exit 1
fi

cli="$repo_dir/tools/vled_cli"
bridge="$repo_dir/tools/vled_bridge"
[[ -x $cli && -x $bridge ]] || { echo "Run 'make -C tools' first" >&2; exit 1; }

bridge_pid=
cleanup() {
    if [[ -n ${bridge_pid:-} ]]; then
        kill -TERM "$bridge_pid" 2>/dev/null || true
        wait "$bridge_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

"$bridge" "$windows_ip" 9000 "$device" 200 &
bridge_pid=$!
sleep 1
kill -0 "$bridge_pid" 2>/dev/null || { echo "bridge exited during startup" >&2; exit 1; }

run() {
    echo "> $*"
    "$cli" write "$*" "$device"
    "$cli" read "$device"
    sleep 1
}

run "TEXT VLED P3 Demo"
run "COLOR 255 0 0"
run "BRIGHTNESS 80"
run "MODE scroll"
run "TEXT 中文演示"
run "COLOR 0 255 255"
run "MODE static"
run "CLEAR"

echo "Demo complete; stopping bridge cleanly."
