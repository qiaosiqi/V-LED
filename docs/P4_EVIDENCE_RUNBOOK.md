# P4 正式目标环境证据运行手册

> 状态：`P4_AUTHORIZED / NOT_RUN`
>
> P4 只完成目标 Linux 与 Windows 截图证据闭环，不实施 P5 的 poll/wait queue。
> 每次运行使用新目录，失败日志不得覆盖。

## 1. 同步明确批次

```bash
cd "$HOME/siqi_ws/V-LED"
make -C driver clean
make -C tools clean
git fetch origin
git switch integration-promote-try
git pull --ff-only origin integration-promote-try
git status --short --branch
git rev-parse HEAD
```

如果存在已跟踪源码修改，立即停止；不要执行 `git reset --hard` 或 `git clean`。
`get_env*.sh` 和构建产物等未跟踪文件可以保留。

## 2. 创建唯一运行目录

```bash
set -o pipefail
run_id="$(date +%Y%m%d-%H%M)-ubuntu-$(uname -r)-p4"
evidence="$HOME/vled-test-logs/$run_id"
mkdir -p "$evidence/screenshots"
run_start=$(date --iso-8601=seconds)
echo "P4 evidence directory: $evidence"
```

本手册后续命令必须在同一个终端中执行，以保留 `evidence` 和 `run_start`。

## 3. 环境记录

```bash
{
    date --iso-8601=seconds
    cat /etc/os-release
    uname -a
    gcc --version | head -n 1
    x86_64-linux-gnu-gcc-13 --version | head -n 1
    make --version | head -n 1
    ld --version | head -n 1
    python3 --version
    git status --short --branch
    git rev-parse HEAD
    ls -ld "/lib/modules/$(uname -r)/build"
    ip -br -4 addr
    ip route show default
} 2>&1 | tee "$evidence/00-environment.txt"
env_rc=${PIPESTATUS[0]}
echo "00-environment exit code: $env_rc" | tee -a "$evidence/EXIT_CODES.txt"
```

## 4. 严格构建

```bash
{
    make -C driver clean
    make -C driver V=1 CC=x86_64-linux-gnu-gcc-13
    make -C tools clean
    make -C tools CFLAGS='-Wall -Wextra -Werror -O2'
} 2>&1 | tee "$evidence/01-build.log"
build_rc=${PIPESTATUS[0]}
echo "01-build exit code: $build_rc" | tee -a "$evidence/EXIT_CODES.txt"
test "$build_rc" -eq 0 || exit "$build_rc"
```

## 5. 模块生命周期

先确认没有旧模块：

```bash
lsmod | grep '^vled' || echo 'vled initially unloaded'
test ! -e /dev/vled && echo '/dev/vled initially absent'
```

然后运行三轮装卸，最后留下一个全新加载实例供后续测试：

```bash
{
    for cycle in 1 2 3; do
        sudo insmod driver/vled.ko
        test -c /dev/vled
        sudo chmod 666 /dev/vled
        echo "cycle=$cycle"
        ls -l /dev/vled
        lsmod | grep '^vled '
        modinfo driver/vled.ko
        sudo rmmod vled
        test ! -e /dev/vled
    done
    sudo insmod driver/vled.ko
    sudo chmod 666 /dev/vled
    test -c /dev/vled
} 2>&1 | tee "$evidence/02-module-lifecycle.log"
lifecycle_rc=${PIPESTATUS[0]}
echo "02-lifecycle exit code: $lifecycle_rc" | tee -a "$evidence/EXIT_CODES.txt"
test "$lifecycle_rc" -eq 0 || exit "$lifecycle_rc"
```

## 6. 功能命令与 CLI

```bash
python3 tools/vled_verify.py \
    --device /dev/vled --cli tools/vled_cli --groups cli,commands \
    2>&1 | tee "$evidence/03-command-functional.log"
functional_rc=${PIPESTATUS[0]}
echo "03-functional exit code: $functional_rc" | tee -a "$evidence/EXIT_CODES.txt"
test "$functional_rc" -eq 0 || exit "$functional_rc"
```

## 7. PAGE_SIZE、错误回滚与多 FD

`vled_fd_probe` 要求从 version 0 开始；两次均重新加载模块，使两个原始日志独立
可复核。探针本身会同时覆盖边界、回滚、JSON、快照和多 FD，文件名表示主要索引，
不是删减后的输出。

```bash
sudo rmmod vled
sudo insmod driver/vled.ko
sudo chmod 666 /dev/vled
./tools/vled_fd_probe /dev/vled 2>&1 \
    | tee "$evidence/04-boundary-and-errors.log"
boundary_rc=${PIPESTATUS[0]}
echo "04-boundary exit code: $boundary_rc" | tee -a "$evidence/EXIT_CODES.txt"
test "$boundary_rc" -eq 0 || exit "$boundary_rc"

sudo rmmod vled
sudo insmod driver/vled.ko
sudo chmod 666 /dev/vled
./tools/vled_fd_probe /dev/vled 2>&1 \
    | tee "$evidence/05-multifd-offset.log"
multifd_rc=${PIPESTATUS[0]}
echo "05-multifd exit code: $multifd_rc" | tee -a "$evidence/EXIT_CODES.txt"
test "$multifd_rc" -eq 0 || exit "$multifd_rc"
```

## 8. 并发压力

```bash
python3 tools/vled_verify.py \
    --device /dev/vled --cli tools/vled_cli \
    --groups concurrency --iterations 500 \
    2>&1 | tee "$evidence/06-concurrency-stress.log"
concurrency_rc=${PIPESTATUS[0]}
echo "06-concurrency exit code: $concurrency_rc" | tee -a "$evidence/EXIT_CODES.txt"
test "$concurrency_rc" -eq 0 || exit "$concurrency_rc"
```

## 9. Linux→Windows 网络与截图

在 Windows 启动 `simulator/vled_sim.py`，确认日志显示监听 `0.0.0.0:9000`，然后
在 Linux 执行：

```bash
./tools/vled_demo.sh 192.168.57.1 /dev/vled 2>&1 \
    | tee "$evidence/07-network-e2e.log"
network_rc=${PIPESTATUS[0]}
echo "07-network exit code: $network_rc" | tee -a "$evidence/EXIT_CODES.txt"
test "$network_rc" -eq 0 || exit "$network_rc"
```

在演示过程中至少保存两张 PNG：

1. `screenshots/01-linux-terminal.png`：Linux 终端同时包含 demo 命令、version 8
   最终 JSON 和退出码 0；
2. `screenshots/02-windows-gui.png`：Windows 模拟器同时包含最新状态/版本和 UDP
   日志，不能只截孤立文字。

截图原图不要在 Word 中二次压缩后再导出。若无法复制 PNG，可直接上传给 Codex，
由 Windows 侧按原文件导入证据目录。

## 10. 卸载与内核日志

```bash
sudo rmmod vled
test ! -e /dev/vled
sudo journalctl -k --since "$run_start" --no-pager 2>&1 \
    | tee "$evidence/08-kernel-log.txt"
kernel_rc=${PIPESTATUS[0]}
echo "08-kernel exit code: $kernel_rc" | tee -a "$evidence/EXIT_CODES.txt"

lsmod | grep '^vled' || echo 'vled unloaded' | tee -a "$evidence/02-module-lifecycle.log"
test ! -e /dev/vled && echo '/dev/vled removed' | tee -a "$evidence/02-module-lifecycle.log"
```

检查最终日志。`error:` 可能匹配 Kbuild 的 `-Werror=...` 参数，应以完整行判断；
真正禁止的是诊断行中的 warning/error、FAIL、oops、BUG 和 lockdep：

```bash
grep -niE '(^|[[:space:]])(warning:|error:|FAIL|oops|BUG:|lockdep)' \
    "$evidence"/*.log "$evidence"/*.txt \
    || echo 'P4 logs: no diagnostic markers'
```

## 11. 生成清单与归档

```bash
cd "$evidence"
sha256sum 00-environment.txt 01-build.log 02-module-lifecycle.log \
    03-command-functional.log 04-boundary-and-errors.log \
    05-multifd-offset.log 06-concurrency-stress.log 07-network-e2e.log \
    08-kernel-log.txt EXIT_CODES.txt screenshots/*.png > SHA256SUMS

cd "$HOME/vled-test-logs"
tar -czf "${run_id}.tar.gz" "$run_id"
sha256sum "${run_id}.tar.gz"
```

上传 tar.gz 和两张原始 PNG，贴出 SHA-256。没有两张截图或任一退出码非 0 时，
不得把 P4 标记为 PASS。
