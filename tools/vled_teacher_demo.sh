#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
windows_ip=${1:-}
device=${2:-/dev/vled}
module="$repo_dir/driver/vled.ko"
cli="$repo_dir/tools/vled_cli"
bridge="$repo_dir/tools/vled_bridge"
fd_probe="$repo_dir/tools/vled_fd_probe"
multiprocess_probe="$repo_dir/tools/vled_multiprocess_probe.py"
run_start=$(date --iso-8601=seconds)
loaded=0
bridge_pid=
step_number=0
kernel_cc=${VLED_KERNEL_CC:-}

if [[ $# -gt 2 ]]; then
    echo "Usage: $0 [windows_ip] [device]" >&2
    echo "  no IP: Linux-only driver demonstration" >&2
    echo "  with IP: also forward state to the Windows simulator on UDP 9000" >&2
    exit 2
fi

if [[ -z $kernel_cc ]]; then
    if command -v x86_64-linux-gnu-gcc-13 >/dev/null 2>&1; then
        kernel_cc=x86_64-linux-gnu-gcc-13
    else
        kernel_cc=gcc
    fi
fi

section() {
    step_number=$((step_number + 1))
    printf '\n============================================================\n'
    printf '[STEP %02d] %s\n' "$step_number" "$1"
    printf '============================================================\n'
}

explain() {
    printf '  [说明] %s\n' "$1"
}

run() {
    printf '  [命令]'
    printf ' %q' "$@"
    printf '\n'
    "$@"
}

wait_for_device() {
    local attempt

    for attempt in {1..50}; do
        [[ -c $device ]] && return 0
        sleep 0.1
    done
    echo "FAIL: $device was not created as a character device" >&2
    return 1
}

stop_bridge() {
    if [[ -n ${bridge_pid:-} ]]; then
        explain "停止 Linux→Windows UDP bridge，等待它关闭设备 FD 和 socket。"
        kill -TERM "$bridge_pid" 2>/dev/null || true
        wait "$bridge_pid" 2>/dev/null || true
        bridge_pid=
    fi
}

unload_module() {
    if [[ $loaded -eq 1 ]]; then
        run sudo rmmod vled
        loaded=0
    fi
}

cleanup() {
    stop_bridge
    if [[ $loaded -eq 1 ]]; then
        sudo rmmod vled 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

if lsmod | awk '{print $1}' | grep -qx vled; then
    echo "Refusing to replace an already loaded vled module." >&2
    echo "Run 'sudo rmmod vled' first, then start this demonstration again." >&2
    exit 2
fi

section "确认演示范围和目标环境"
explain "本脚本只增加可观察性，不修改 VLED 命令、JSON、偏移或并发语义。"
run uname -a
run getconf PAGE_SIZE
run sudo -v
if [[ -n $windows_ip ]]; then
    explain "已启用 Windows 联动：状态将发送到 $windows_ip:9000。"
    explain "请先在 Windows 运行: python simulator/vled_sim.py"
else
    explain "未提供 Windows IP：本次只演示 Linux 字符设备驱动。"
fi

section "从源码干净构建内核模块和用户态工具"
explain "完整显示编译命令，并以 warning 作为错误处理用户态工具。"
run make -C "$repo_dir/driver" clean
run make -C "$repo_dir/driver" V=1 CC="$kernel_cc"
run make -C "$repo_dir/tools" clean
run make -C "$repo_dir/tools" CFLAGS=-Wall\ -Wextra\ -Werror\ -O2

section "加载模块并证明自动设备号和自动设备节点"
explain "加载时启用 trace_ops；常规验收不传该参数，详细日志默认关闭。"
run sudo insmod "$module" trace_ops=1
loaded=1
wait_for_device
run sudo chmod 666 "$device"
explain "字符设备节点中的 major/minor 应与 sysfs 中的十进制设备号一致。"
run ls -l "$device"
run cat /sys/class/vled/vled/dev
run stat -c 'type=%F permissions=%A major_hex=%t minor_hex=%T' "$device"
printf '  [命令] lsmod | grep %q\n' '^vled '
lsmod | grep '^vled '
printf '  [命令] grep %q /proc/devices\n' '[[:space:]]vled$'
grep -E '[[:space:]]vled$' /proc/devices
run modinfo "$module"

if [[ -n $windows_ip ]]; then
    section "启动可选的 Linux→Windows 状态转发"
    explain "bridge 长期打开设备，用 poll 等待版本变化，再发送 UDP 9000。"
    run test -x "$bridge"
    "$bridge" "$windows_ip" 9000 "$device" 200 &
    bridge_pid=$!
    printf '  [后台] vled_bridge pid=%d target=%s:9000\n' "$bridge_pid" "$windows_ip"
    sleep 1
    kill -0 "$bridge_pid" 2>/dev/null || {
        echo "FAIL: bridge exited during startup" >&2
        exit 1
    }
fi

section "展示用户态 write、内核处理和用户态 read"
export VLED_VERBOSE=1
explain "CLI 会打印 open/write/read/close；内核日志会记录对应 context、偏移和版本。"
run "$cli" read "$device"
run "$cli" write "TEXT VLED Teacher Demo" "$device"
run "$cli" read "$device"
sleep 1
run "$cli" write "COLOR 255 0 0" "$device"
run "$cli" read "$device"
sleep 1
run "$cli" write "BRIGHTNESS 80" "$device"
run "$cli" read "$device"
sleep 1
run "$cli" write "MODE scroll" "$device"
run "$cli" read "$device"
sleep 1
run "$cli" write "TEXT 中文演示" "$device"
run "$cli" read "$device"
sleep 1
if [[ -n $windows_ip ]]; then
    explain "Windows 模拟器此时应显示中文、红色、80% 亮度和 scroll 模式。"
fi
stop_bridge

section "卸载模块并证明设备节点自动删除"
unload_module
if [[ -e $device ]]; then
    echo "FAIL: $device remained after rmmod" >&2
    exit 1
fi
echo "  [PASS] vled 已从内核卸载，$device 已自动删除。"

section "重新加载全新模块，展示 PAGE_SIZE 和独立偏移"
run sudo insmod "$module" trace_ops=1
loaded=1
wait_for_device
run sudo chmod 666 "$device"
explain "重新加载得到 version 0，满足 PAGE_SIZE 探针的前置条件。"
run "$fd_probe" "$device"

section "使用真实 fork 进程展示同一设备和独立读写偏移"
explain "进程 A 写满自己的 4095 字节页面后返回 ENOSPC；进程 B 独立 open 仍可写。"
explain "小规模 4 writer + 4 reader 演示保留并发证据，同时控制现场日志长度。"
run python3 "$multiprocess_probe" --device "$device" --iterations 3

section "打印本次演示的 VLED 内核处理日志"
explain "日志中的 USER pid、内核 pid 和 OPEN id 可用于对应每次系统调用。"
set +e
sudo journalctl -k --since "$run_start" --no-pager | grep 'vled:'
pipeline_status=("${PIPESTATUS[@]}")
set -e
if [[ ${pipeline_status[0]} -ne 0 ]]; then
    echo "FAIL: unable to read kernel journal" >&2
    exit 1
fi
if [[ ${pipeline_status[1]} -ne 0 ]]; then
    echo "FAIL: no VLED kernel log was captured" >&2
    exit 1
fi

section "最终清理与交付结论"
unload_module
[[ ! -e $device ]] || { echo "FAIL: $device still exists" >&2; exit 1; }
if lsmod | awk '{print $1}' | grep -qx vled; then
    echo "FAIL: vled still appears in lsmod" >&2
    exit 1
fi
echo "  [PASS] 用户态/内核态交互、PAGE_SIZE、多进程独立偏移、动态设备号、"
echo "         自动设备节点和两轮动态加载/卸载均已展示。"
if [[ -n $windows_ip ]]; then
    echo "  [PASS] Linux 状态也已通过 UDP bridge 发送到 $windows_ip:9000。"
fi
echo "VLED teacher demonstration: PASS"
