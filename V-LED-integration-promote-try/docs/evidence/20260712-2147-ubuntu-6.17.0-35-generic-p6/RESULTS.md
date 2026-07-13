# P6 文档与统一命令目标 Linux 验证结果

## 结论

状态：`PASS / P6_TARGET_PASS`

2026-07-12 在 Ubuntu 24.04.4、Linux 6.17.0-35-generic、x86_64 目标环境验证
P6 明确提交：

```text
2ea234639cfd8abf65485f9380e0c3b3103a6813
```

该提交已经普通 fast-forward 推送到 `origin/integration-promote-try` 后才在
Linux 执行，符合阶段同步门禁。

## 验证命令

```bash
git rev-parse HEAD
sudo rmmod vled 2>/dev/null || true
./tools/vled_verify.sh
```

## 验证结果

- 匹配 Linux 6.17.0-35-generic 的驱动构建成功。
- `vled_cli`、`vled_bridge`、`vled_fd_probe`、`vled_poll_probe` 均以
  `-Wall -Wextra -Werror -O2` 构建成功。
- bridge 黑盒 T-BRIDGE-01..04 通过。
- T-POLL-08 事件驱动 bridge 通过：空闲观测 `0.351s`、CPU ticks `0`、发送
  `2` 次、响应延迟 `0.718ms`。该值仅是本次环境观测值，不作为通用基准。
- P1 PAGE_SIZE、per-open offset、稳定快照、原子回滚、version 和 JSON 回归通过。
- P3 T-CLI、T-CMD、T-CON 回归通过。
- P5 T-POLL-01..07 通过，覆盖 poll、wait queue、阻塞/非阻塞 read 与事件收敛。
- 三轮模块加载/卸载生命周期通过。
- 运行区间内核日志只有正常的 `/dev/vled` 注册与注销。
- 统一入口末行：`VLED P1-P5 verify: PASS (module will be unloaded by cleanup trap)`。

## 边界说明

`Skipping BTF generation for vled.ko due to unavailability of vmlinux` 是目标 headers
环境中已知的 BTF 提示；模块成功生成、加载、测试和卸载，不属于编译 warning/error。

本次验证关闭 P6，但不授权进入 P7，也不授权修改课程设计报告。
