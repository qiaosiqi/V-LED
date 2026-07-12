# P2 Windows GUI 复核操作记录

## 启动与自动测试

```powershell
python simulator/vled_sim.py
python -m unittest discover -s simulator/tests -v
```

模拟器监听 `127.0.0.1:9000`。人工复核期间通过本机 UDP 发送器依次发送以下
完整 `state` 报文或无效数据；所有合法报文都包含 `type`、`width`、`height`、
`text`、`color`、`brightness`、`mode` 和 `version` 字段。

## 报文与界面操作序列

| 步骤 | 输入或操作 |
|---|---|
| 1 | 启动 GUI，确认默认版本 0、文本 `#0000`、UDP 9000 监听和初始日志 |
| 2 | 合法 state：version 11，`P2 Static OK`，`[255,0,0]`，80，`static` |
| 3 | 合法 state：version 12，`P2 Scroll OK`，`[0,255,255]`，60，`scroll` |
| 4 | 发送字节 `not-json` |
| 5 | 发送完整 state，但 brightness=101、version=99 |
| 6 | GUI 手动选择红色并调整亮度，确认两个覆盖标记 `*` |
| 7 | 合法 state：version 13，`Latest UDP`，`[0,255,0]`，20，`static` |
| 8 | 分别点击颜色和亮度的“恢复 UDP” |
| 9 | 点击“本地预览清屏” |
| 10 | 合法 state：version 14，`After Clear`，`[0,0,255]`，50，`static` |
| 11 | 连续发送 240 个无效报文，等待 GUI 消费完毕 |
| 12 | 连续发送 300 个合法 state，version 100..399，末条文本 `Burst-299`、颜色 `[128,64,255]`、亮度 75 |
| 13 | 点击窗口关闭按钮，等待接收线程退出，再检查 Python 进程和 UDP 9000 |

屏幕画面由 Windows GUI 控制工具在本次复核会话中逐步检查。该工具不允许把
返回的截图 URL 解码保存到工作区，因此证据目录不包含伪造或二次导出的截图；
实际观察值记录在 `RESULTS.md`。
