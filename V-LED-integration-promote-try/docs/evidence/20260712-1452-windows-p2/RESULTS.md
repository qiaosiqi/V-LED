# P2 Windows 模拟器验收结果

## 结论

状态：`PASS / P2_WINDOWS_PASS`

在 Windows NT 10.0.26220.0、Python 3.12.9 上，对提交
`83caefb1cf88eb35c41dd134020280b0ea5e3537` 完成 12 项无 GUI 自动测试和
Windows 人工 GUI 视觉/交互复核。协议校验、完整状态替换、手动覆盖、恢复 UDP、
本地预览清屏、有界日志、高频更新和关闭清理均符合冻结语义。

该结论关闭 P2 门禁，但不代表 P3 跨机 UDP、P4 全链路证据或后续阶段已完成。

## 自动测试

命令：

```powershell
python -m unittest discover -s simulator/tests -v
```

退出码为 0，12 项全部通过；原始输出见 `01-unittest.log`。覆盖范围包括协议
合法/非法输入、不可变事件、有界队列/日志、真实 loopback UDP 收发、无 Tk
依赖的接收线程、覆盖模型、本地清屏和干净退出。

此前还临时把 `blink` 加入允许模式执行受控 mutation：非法 mode 负面测试以
退出码 1 失败；恢复正确实现后 12 项再次全部通过。mutation 未提交。

## 人工 GUI 复核

| ID | 实际观察 | 结果 |
|---|---|---|
| T-SIM-01 | version 11 static 与 version 12 scroll 均一次性显示完整文字、颜色、亮度、模式和版本 | PASS |
| T-SIM-02/03 | `not-json` 和 brightness=101 被明确记录；界面保持 version 12，未发生部分更新 | PASS |
| T-SIM-04 | 300 个连续合法报文后界面无冻结，最终收敛到 version 399、`Burst-299`、`#8040FF`、75% | PASS |
| T-SIM-05 | 手动红色/亮度 61% 覆盖期间收到 version 13；版本和文字更新，显示仍保持手动值及 `*` | PASS |
| T-SIM-06 | 点击两项“恢复 UDP”后立即采用 version 13 的绿色 `#00FF00` 和亮度 20% | PASS |
| T-SIM-07 | “本地预览清屏”只隐藏文字、保留 version 13，日志明确说明未向驱动发送 CLEAR；version 14 到达后文字恢复 | PASS |
| T-SIM-08 | 连续 240 个无效报文后 GUI 仍响应，日志计数严格保持 200 条 | PASS |
| T-SIM-09 | 点击关闭后窗口消失，模拟器 Python 进程退出，UDP 9000 不再监听 | PASS |

滚动模式下文字运动正常；无效报文日志分别给出 JSON 错误和 brightness 必须位于
0..100 的原因。全过程未观察到 Tk 跨线程异常、界面冻结或无界日志增长。

## 关闭后检查

关闭窗口后再次检查：

- `simulator python process: NOT RUNNING`
- `UDP 9000 endpoint: NOT LISTENING`

记录见 `02-close-check.txt`。

## 证据边界

- 本轮是 Windows 本机 loopback UDP 与人工 GUI 复核，不替代 P3/P4 的
  Linux→Windows 跨机 UDP 全链路验收。
- GUI 画面在复核会话中逐步检查。所用控制工具禁止把截图 URL 解码保存到本地，
  因而本目录保留操作序列和观察记录，不声称存在仓库截图文件。
- 自动测试输出、环境和关闭后检查分别独立保存；分析和结论只写在 Markdown 中。
