# P3 目标 Linux 验收运行手册

> 状态：`IMPLEMENTED_NOT_RUN_ON_TARGET_LINUX`
>
> P3 实现提交：`b0fb0b6`。请只测试推送后的 `integration-promote-try` 明确提交，
> 不要在 Linux 测试副本中临时修改源码。

## 1. 同步与清理构建产物

以下命令不会删除 `get_env.sh`、`get_env_2.sh` 或其他未跟踪文件：

```bash
cd "$HOME/siqi_ws/V-LED"
git status --short --branch

make -C driver clean
make -C tools clean

git fetch origin
git switch integration-promote-try
git pull --ff-only origin integration-promote-try
git status --short --branch
git rev-parse HEAD
```

确认 `HEAD` 与本轮汇报的 P3 批次头一致。未跟踪的 `get_env*.sh` 可以保留；
如果出现任何已跟踪源码修改，先停止并汇报，不要执行 `reset --hard` 或 `git clean`。

## 2. 确认旧模块已卸载

```bash
lsmod | grep '^vled' || echo 'vled module: NOT LOADED'
test ! -e /dev/vled && echo '/dev/vled: absent'
```

如果模块仍加载：

```bash
sudo rmmod vled
lsmod | grep '^vled' || echo 'vled unloaded'
test ! -e /dev/vled && echo '/dev/vled removed'
```

## 3. 运行自动验收并保留退出码

```bash
set -o pipefail
mkdir -p "$HOME/vled-test-logs"
run_id="p3-$(git rev-parse --short HEAD)"

./tools/vled_verify.sh 2>&1 \
    | tee "$HOME/vled-test-logs/${run_id}-verify.log"
verify_rc=${PIPESTATUS[0]}
echo "verify exit code: $verify_rc"
```

脚本会执行：

1. 驱动和工具 `-Werror` 构建；
2. bridge 对无效/合法状态的黑盒 UDP 校验及 SIGTERM 退出；
3. 模块加载、字符设备出现、权限和模块元信息检查；
4. P1 PAGE_SIZE、多 FD、快照和回滚回归；
5. CLI 参数、全部业务命令、错误码、版本、JSON 和 4 writer + 4 reader 压力；
6. 三轮模块装卸；
7. 本次运行区间内核日志严重诊断检查；
8. 无论成功或失败，通过 trap 尝试卸载模块。

通过条件：`verify exit code: 0`，末尾出现 `VLED P3 verify: PASS`，且模块已卸载、
设备节点消失。

```bash
lsmod | grep '^vled' || echo 'vled unloaded'
test ! -e /dev/vled && echo '/dev/vled removed'
```

如果脚本失败，请原样保留日志，不要覆盖；把日志传回后再创建新的修复运行编号。

## 4. Windows 跨机演示

自动验收通过后，重新加载模块并启动 Windows 模拟器：

```bash
sudo insmod driver/vled.ko
sudo chmod 666 /dev/vled
./tools/vled_demo.sh 192.168.57.1 /dev/vled 2>&1 \
    | tee "$HOME/vled-test-logs/${run_id}-demo.log"
demo_rc=${PIPESTATUS[0]}
echo "demo exit code: $demo_rc"
sudo rmmod vled
```

Windows GUI 应依次显示英文、红色、80% 亮度、scroll、中文、青色、static 和
最终清屏；version 应随实际变化单调递增。请同时保存 Linux 终端日志和 Windows
GUI 截图。ICMP ping 失败不等同于 UDP 失败，以 GUI 收包日志为准。

## 5. 回传环境摘要与归档

```bash
{
    date --iso-8601=seconds
    uname -a
    gcc --version | head -n 1
    git status --short --branch
    git rev-parse HEAD
} | tee "$HOME/vled-test-logs/${run_id}-environment.log"

cd "$HOME/vled-test-logs"
tar -czf "${run_id}-logs.tar.gz" \
    "${run_id}-environment.log" \
    "${run_id}-verify.log" \
    "${run_id}-demo.log"
sha256sum "${run_id}-logs.tar.gz"
```

若尚未执行跨机演示，不要创建假的 demo 日志或把 P3 标为 PASS；先回传自动验收
日志，并明确标记 `NETWORK_E2E_PENDING`。
