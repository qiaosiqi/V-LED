# P3 目标 Linux 与 Windows 跨机验收结果

## 结论

状态：`PASS / P3_TARGET_PASS`

VLED P3 在 Ubuntu 24.04.4、Linux 6.17.0-35-generic、x86_64、GCC 13.3.0
和 Python 3.12.3 环境完成严格构建、bridge 黑盒验收、P1 回归、全命令与错误
路径、并发压力、三轮模块生命周期、内核日志检查及 Linux→Windows UDP 9000
跨机演示。最终受测提交为
`b11d5c72a115c5608c5836236715eabcb9eaea6b`。

Windows 模拟器由 Codex 在演示前确认监听 `0.0.0.0:9000`；用户在演示后人工
确认 GUI 显示正常并关闭窗口。该结论关闭 P3，不代表 P4/P5 已获实施授权。

## 最终通过项

| 项目 | 结果 | 原始证据 |
|---|---|---|
| 环境与提交 | Ubuntu 24.04.4；6.17.0-35；GCC 13.3；Python 3.12.3；`b11d5c7` | `raw/p3-b11d5c7-environment.log` |
| 驱动与工具构建 | 匹配内核的 `x86_64-linux-gnu-gcc-13`；工具使用 `-Werror`；成功 | `raw/p3-b11d5c7-verify.log` |
| bridge 黑盒 | 非法状态拒绝、合法 UDP 一致、SIGTERM 干净退出 | `raw/p3-b11d5c7-verify.log` |
| P1 回归 | PAGE_SIZE、回滚、多 FD、快照、JSON 全部通过 | `raw/p3-b11d5c7-verify.log` |
| CLI 与命令 | `PASS T-CLI`、`PASS T-CMD`；状态、错误码和 version 实际核对 | `raw/p3-b11d5c7-verify.log` |
| 并发 | 4 writer + 4 reader；每条采样用 JSON 解析和值域检查；`PASS T-CON` | `raw/p3-b11d5c7-verify.log` |
| 生命周期 | 三轮卸载/加载通过；最终 trap 卸载成功，设备节点消失 | `raw/p3-b11d5c7-verify.log` |
| 内核日志 | 本次区间只有正常注册/注销，无 warning/oops/BUG/lockdep | `raw/p3-b11d5c7-verify.log` |
| 跨机 UDP | version 0..8 的完整 JSON 发往 `192.168.57.1:9000`；demo 退出码 0；GUI 人工确认正常 | `raw/p3-b11d5c7-demo.log` |

演示依次产生英文文字、红色、80% 亮度、scroll、中文、青色、static 和 CLEAR，
version 对实际变化精确递增至 8。bridge 最终输出 `UDP bridge stopped`，随后模块
卸载且 `/dev/vled` 消失。

## 失败到修复的时间线

1. `1b78283` 首次目标运行中，驱动构建、bridge、模块加载和 P1 回归均通过，
   但 `T-CMD` 把零长度 write 错误地当作空白命令并期待 `EINVAL`，因此正确驱动
   返回 0 时验收器失败。原始输出保存在 `raw/p3-1b78283-verify.log`。
2. `b11d5c7` 将负面用例改为三个空格，恢复冻结语义：零长度 write 返回 0，
   真正空白命令返回 `EINVAL`；同时显式选择内核记录的编译器可执行名。
3. 修复后完整自动验收退出码 0，随后跨机演示退出码 0；失败日志未被覆盖。

此外，P3 开发阶段临时移除 CLI 多余参数拒绝后，`read NUL extra` 从退出码 1
变为 0，证明负面参数测试能够捕获错误实现。mutation 已删除且未提交。

## 证据解释与限制

- 用户导出的源归档 SHA-256 在导入前核验，记录于 `SOURCE_ARCHIVE.sha256`；
  raw 文件由归档直接解包，没有人工编辑。
- 用户对最终日志执行的 `error:` 搜索命中了 Kbuild 命令行中的
  `-Werror=...` 参数，不是编译错误。最终日志没有 `warning:` 或 `FAIL` 行。
- demo 日志中有一处父脚本命令输出插入后台 bridge 行的终端交错；同一版本随后
  多次出现完整 JSON，Windows GUI 也正常显示，因此不是 UDP 数据截断。
- UDP 是无连接协议，`sendto()` 成功只证明本机提交报文；远端到达由本次 Windows
  GUI 实际显示确认。模拟器未监听时不能仅靠 UDP sender 获得远端确认，日志不得
  被解释为端到端成功。
- 本轮未导出 Windows 截图文件；Windows 正向收包结论来自演示期间的 GUI 观察和
  用户明确确认。后续 P4 正式证据若要求报告截图，应重新演示并保存截图。
- Linux 工作树中的内核构建产物、工具二进制和 `get_env*.sh` 均为未跟踪测试
  文件，没有纳入提交。
