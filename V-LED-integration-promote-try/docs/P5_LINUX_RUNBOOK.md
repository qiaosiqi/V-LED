# P5 poll + wait queue 目标 Linux 运行说明

> 状态：`PASS / P5_TARGET_PASS`；最终受测提交 `e142f2001315737b314c8800ac8800d511bbe6ab`

P5 只允许在 Windows 静态检查完成、实现与测试已提交并以普通 fast-forward
推送后，在目标 Ubuntu 24.04.4 / Linux 6.17.0-35-generic 上测试明确提交哈希。

## 覆盖范围

- `T-POLL-01`：新 FD 初次 `poll()` 立即可读，并读取有效当前 JSON。
- `T-POLL-02`：消费当前版本后 `poll()` 超时，不忙等、不重复事件。
- `T-POLL-03`：实际状态变化返回 `POLLIN | POLLRDNORM`。
- `T-POLL-04`：`STATUS`、重复值、非法写入不让独立 FD 产生 poll 可读事件；内部
  唤醒后版本条件仍为假。`fork/dup` 共享同一 file context 的刷新唤醒另由
  T-MP-04 验证。
- `T-POLL-05`：`O_NONBLOCK` 无新版本时 `read()` 返回 `EAGAIN`。
- `T-POLL-06`：阻塞 `read()` 被信号打断并返回标准中断错误。
- `T-POLL-07`：高频多写者后读取有效 JSON，并收敛到明确最终状态。
- `T-POLL-08`：bridge 单次打开设备、事件驱动发送；记录空闲 CPU、发送次数和响应延迟。

## 执行顺序

```bash
git fetch origin
git status --short --branch
git rev-parse HEAD origin/integration-promote-try
test "$(git rev-parse HEAD)" = "<P5_EXPLICIT_COMMIT>"

python3 tools/test_p5_contract.py
make -C driver clean
make -C driver V=1 CC=x86_64-linux-gnu-gcc-13
make -C tools clean
make -C tools CFLAGS='-Wall -Wextra -Werror -O2'

sudo insmod driver/vled.ko
sudo chmod 666 /dev/vled
tools/vled_fd_probe /dev/vled
tools/vled_poll_probe /dev/vled
python3 tools/vled_verify.py --device /dev/vled \
  --cli tools/vled_cli --iterations 200
python3 tools/vled_bridge_probe.py --bridge tools/vled_bridge
sudo rmmod vled
```

必须保留完整命令、退出码、目标提交、构建日志、探针日志、bridge 指标和本轮
`dmesg`/`journalctl -k` 区间。任一失败都保留原始证据并停止 P5 门禁，不进入 P6。
