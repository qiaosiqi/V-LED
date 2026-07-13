# P9 第一次目标 Linux 回传结果（部分运行）

## 结论

状态：`FUNCTIONAL_OUTPUT_PASS / EVIDENCE_CAPTURE_FAIL / P9_NOT_CLOSED`

用户于 2026-07-13 回传了一份完整终端粘贴文本。原文件已逐字节复制到
`raw/pasted-terminal-output.txt`；复制前后 SHA-256 均为
`897AE421C3A85CE24E3EBEDFC102FB5DB12EAA9A069BAA05201AB5021A94E8C8`。

本次输出显示 P1–P5 功能回归实际运行到了最终 PASS，但不能作为 P9 正式证据批次
关闭门禁：运行时变量 `evidence` 未初始化，`tee` 报告
`/01-final-verify.log: 权限不够`，因此目标机没有生成约定的原始日志文件；回传中也
没有环境日志、显式 `verify_rc`、卸载后模块/节点检查、故障恢复彩排和 Windows
非开发成员盲演材料。

## 可确认事实

- `git pull --ff-only` 输出显示 Linux checkout 从 `2ea2346` fast-forward 到
  `ba1ab82`，并取得 P7/P8/P9 文档与报告文件。
- 三条提交/干净工作树 `test` 命令之后终端继续运行，但没有打印 `git rev-parse`
  的完整值和各条退出码，因此只作为辅助信息，不替代环境日志。
- 目标内核构建路径为 `6.17.0-35-generic`；驱动用
  `x86_64-linux-gnu-gcc-13` 构建，未出现编译 warning/error。
- tools 使用 `-Wall -Wextra -Werror -O2` 全部构建成功。
- bridge 黑盒、T-POLL-08、P1 探针、P3 业务/并发和 T-POLL-01..07 均打印 PASS。
- 生命周期第 1–20 轮均打印 PASS。
- 输出中的本轮内核区间只有 vled 注册/注销消息，没有
  warning/oops/BUG/lockdep/use-after-free/general protection fault。
- 验收器打印最终行
  `VLED P1-P5 verify: PASS (module will be unloaded by cleanup trap)`。

## 未满足的 P9 证据门槛

| ID | 本次状态 | 原因 |
|---|---|---|
| T-P9-01 | `PARTIAL` | pull 与构建输出存在，但缺少 00-environment.log、完整提交打印和显式退出码 |
| T-P9-02 | `FUNCTIONAL_OUTPUT_PASS / NOT_ACCEPTED_AS_FINAL` | 完整功能输出为 PASS，但 tee 失败且没有 `verify_rc`/EXIT_CODES |
| T-P9-03 | `PARTIAL` | 验收器内核区间干净，但缺少 cleanup 后独立模块、节点和最终内核日志检查 |
| T-P9-04 | `PENDING` | 两项受控故障恢复未回传 |
| T-P9-05 | `PENDING` | Windows 自动日志、GUI PNG 和非开发成员盲演未回传 |
| T-P9-06 | `LOCAL_PREFLIGHT_PASS` | Windows 权威工作区已完成；不替代上述目标运行与盲演门禁 |

## 下一步

在同一个目标 Linux 终端先定义并验证 `run_id`、`evidence` 和 `run_start`，创建新的
P9 运行目录，再完整重跑 `docs/P9_FINAL_RUNBOOK.md` 第 2–6 节。不得覆盖或删除本次
部分运行证据。
