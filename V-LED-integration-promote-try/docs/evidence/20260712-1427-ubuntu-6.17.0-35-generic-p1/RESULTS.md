# P1 目标 Linux 验收结果

## 结论

状态：`PASS`

VLED P1 在目标 Ubuntu 24.04.4、Linux 6.17.0-35-generic、x86_64、GCC
13.3.0 环境中完成零警告构建、严格用户态工具构建、PAGE_SIZE/多 FD/快照/
原子回滚探针以及模块加载卸载检查。最终受测实现为
`d8c1c0dcd451c78a3df4d96730267fad16d89e4c`。

该结论只关闭 P1 门禁，不代表 P3 全功能、P4 全链路证据或 P5 poll 扩展已经
完成。

## 最终通过项

| 项目 | 结果 | 原始证据 |
|---|---|---|
| 目标环境与 Git 提交 | Ubuntu 24.04.4；6.17.0-35-generic；GCC 13.3；`d8c1c0d` | `00-environment.txt` |
| 驱动构建 | 退出码 0；`warning:`/`error:` 搜索无匹配 | `01-build-final-d8c1c0d.log` |
| 用户态工具构建 | `-Wall -Wextra -Werror -O2`，退出码 0 | `02-tools-final-d8c1c0d.log` |
| PAGE_SIZE 与版本 | T-BUF-01..06、T-VERSION、T-FOPS-05 通过 | `03-probe-final-d8c1c0d.log` |
| non-seekable | T-FOPS-04 通过，`lseek()` 返回 ESPIPE | `03-probe-final-d8c1c0d.log` |
| 原子回滚 | T-ROLLBACK 通过 | `03-probe-final-d8c1c0d.log` |
| 多 FD 与稳定快照 | T-FD-01/03/04、T-READ-03 通过 | `03-probe-final-d8c1c0d.log` |
| UTF-8 与 JSON 转义 | T-JSON-02..03 通过 | `03-probe-final-d8c1c0d.log` |
| 模块生命周期 | 正常注册和注销，无本次运行新增 warning/oops/BUG | `04-kernel-final-d8c1c0d.log` |

探针末行是 `VLED P1 probe: all checks passed`，用户记录的 build、tools、probe
和 rmmod 退出码均为 0。卸载后 `lsmod` 中无 vled，`/dev/vled` 已消失。

## 失败到修复的可追溯过程

1. `4c3c860` 首次构建失败：参数名 `current` 与内核宏冲突，且目标内核已移除
   `no_llseek`。原始失败输出保存在 `intermediate/01-build-4c3c860-failed.log`。
2. `3bd3b5f` 修复 API 兼容后可以构建和通过功能探针，但内核报告
   `vled_write` 栈帧 1136 字节超过 1024 字节阈值。原始构建输出保存在
   `intermediate/02-build-3bd3b5f-warning.log`；该次功能和内核日志也原样保留。
3. `d8c1c0d` 将候选状态移至堆分配。最终构建零警告，完整探针再次通过，
   注册和卸载日志干净，因此 P1 门禁关闭。

失败和中间警告证据没有被最终成功日志覆盖。

## 证据来源与限制

- 用户从 Linux `~/vled-test-logs` 导出两个 tar.gz；Windows 导入前核验的
  SHA-256 记录在 `SOURCE_ARCHIVES.sha256`。
- 原始日志按内容原样复制，仅文件名按证据角色规范化；解释只写在本文件中。
- Linux 测试工作树包含内核构建产物、用户态二进制和 `get_env*.sh`，均为
  未跟踪测试产物；没有把这些二进制纳入提交。
- `/dev/vled` 初始权限为 0600，本轮通过人工 `chmod 666` 运行普通用户探针。
  自动权限策略属于 P3/P6 后续闭环，不影响本次 P1 缓冲区与 per-open 语义结论。
- 历史 dmesg 中存在与 VLED 无关的 vmwgfx WARNING；最终运行区间日志只包含
  vled 注册与注销，不将历史告警误归因于本驱动。
