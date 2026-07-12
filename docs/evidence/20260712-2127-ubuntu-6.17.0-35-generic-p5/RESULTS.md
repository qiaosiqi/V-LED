# P5 poll + wait queue 目标 Linux 验收结果

## 结论

状态：`PASS / P5_TARGET_PASS`

VLED 在 Ubuntu 24.04.4、Linux 6.17.0-35-generic、x86_64、GCC 13.3.0
目标环境完成 P5 验收。最终受测提交为
`e142f2001315737b314c8800ac8800d511bbe6ab`。

最终运行中，匹配内核的驱动构建和用户态工具 `-Werror` 构建成功；P1 PAGE_SIZE、
per-open offset、稳定快照、原子回滚和 version 回归全部通过；P3 CLI、命令、
4 writer + 4 reader 并发与三轮模块生命周期通过；T-POLL-01..08 全部通过。
`full_verify exit=0`、`poll_probe exit=0`，完整运行区间内核日志只有正常注册/注销。

## P5 指标与覆盖

| 验收项 | 结果 |
|---|---|
| T-POLL-01 初始状态可读 | PASS |
| T-POLL-02 已消费版本超时且不忙等 | PASS |
| T-POLL-03 实际状态变化触发 `POLLIN/POLLRDNORM` | PASS |
| T-POLL-04 STATUS、重复值、非法写入不产生事件 | PASS |
| T-POLL-05 非阻塞无新版本返回 EAGAIN | PASS |
| T-POLL-06 阻塞 read 可被信号中断 | PASS |
| T-POLL-07 高频多写者收敛到有效最终状态 | PASS |
| T-POLL-08 bridge 单次打开和事件驱动指标 | PASS |

最终 bridge 指标：空闲观测 `0.351s`、CPU ticks `0`、发送次数 `2`、响应延迟
`0.429ms`。这是本轮目标环境的观测值，不主张为跨机器通用性能基准。

## 失败—修复链

1. `e71c5ef` 首次运行在 P1 `T-ROLLBACK` 后阻塞。`strace` 证明探针第二个
   FD 仍以阻塞 `O_RDWR` 打开，读完快照后驱动按 P5 契约等待新版本。修复为
   `O_RDWR | O_NONBLOCK`，继续断言 EAGAIN。
2. `dbd7063` 运行时 T-POLL-01..08 通过，但 P1 T-FD-03 helper 在读完整旧
   快照后额外读取，跨入新版本并拼接比较。修复为按旧快照剩余长度精确读取。
3. `ceddae9` 上 P1 与 T-POLL-01..08 通过，完整回归 T-CON 发现 Python 分段
   reader 同样跨入下一版本。修复为累计数据首次通过完整协议校验时立即返回，
   并新增连续双版本 mock read 回归。
4. `e142f20` 最终运行全部通过，证明上述失败来自测试 helper 对 P5 长期 FD
   语义的适配遗漏，而非稳定快照、wait queue 或版本发布实现错误。

失败日志均单独保留，没有被最终成功输出覆盖。

## 原始文件

- `00-e71c5ef-initial-timeout.log`：首次构建与 P1 probe 阻塞输出。
- `01-e71c5ef-strace-timeout.log`：限时 strace 与内核日志，定位阻塞 read。
- `02-ceddae9-regression-failure.log`：P1/T-POLL 通过、完整 T-CON 失败输出。
- `03-e142f20-final-pass.log`：最终明确提交的完整回归、poll probe 和内核日志。
- `SHA256SUMS`：上述原始文件和本结果说明的 SHA-256 清单。

## 边界

- `Skipping BTF generation ... vmlinux` 是目标 headers 环境的已知提示，不是
  编译 warning/error；模块成功生成和加载。
- P5 完成不授权进入 P6，也不授权修改课程设计报告。
