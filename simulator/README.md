# VLED Windows 模拟器

模拟器在 Windows 上监听 UDP 9000，接收 Linux `vled_bridge` 发送的完整
状态 JSON，并渲染文字、颜色、亮度和静态/滚动模式。只使用 Python 标准
库，建议使用 Python 3.12；运行 GUI 的解释器必须包含 Tkinter。

## P2 线程模型

- `vled_protocol.py` 是纯协议模块，负责 UTF-8、JSON、必填字段、类型、
  范围和报文大小校验。
- `vled_receiver.py` 是不导入 Tkinter 的 UDP 后台接收器。它只接收报文、
  调用协议模块、生成不可变事件并写入有界 `queue.Queue`。
- `vled_model.py` 保存最新 UDP 状态和手动覆盖规则，不依赖 GUI。
- `vled_sim.py` 的 Tk 主线程用 `root.after()` 排空事件队列，并一次性替换
  完整状态。所有 Canvas、Label、Text 和窗口操作都只发生在主线程。
- 关闭窗口时先设置停止事件并关闭 socket，再等待接收线程退出后销毁窗口。
- 日志历史最多保留 200 条；事件队列最多保留 1024 个事件，满时淘汰最旧
  事件，因此高频报文不会造成无界内存增长。

导入 `simulator.vled_sim` 不会创建窗口；只有执行 `main()` 才创建 Tk 根窗口。

## 冻结协议

合法报文必须是 UTF-8 编码的单个 JSON 对象，且完整包含：

```json
{"type":"state","width":32,"height":16,"text":"Hello VLED","color":[255,0,0],"brightness":80,"mode":"static","version":12}
```

校验约束：

- 报文不超过 4096 字节；
- `type` 必须为 `state`；
- `width`、`height` 是 `1..128` 的普通整数，且像素总数不超过 4096；
- `text` 是字符串，UTF-8 编码后不超过 1023 字节；
- `color` 是恰好三个 `0..255` 普通整数组成的列表；
- `brightness` 是 `0..100` 普通整数；
- `mode` 只能是 `static` 或 `scroll`；
- `version` 是非负普通整数。

Python 的 `bool` 虽然是 `int` 子类，但协议中会明确拒绝。任何缺字段、类型
错误、越界、非法 UTF-8、非法 JSON、非 state 或超大报文都生成拒绝事件，
不会部分修改当前状态。

## 手动覆盖与本地清屏

手动颜色和亮度只覆盖显示值，不覆盖后台保存的最新 UDP 状态。覆盖期间到达
的新 UDP 状态仍会完整保存；点击“恢复 UDP”后立即显示最新 UDP 值。

“本地预览清屏”只隐藏当前预览文字，不向 Linux 驱动写入 `CLEAR`，日志会
明确说明这一点。下一条合法 UDP 状态到达时恢复显示其文字。

## 无 GUI 自动测试

在仓库根目录执行：

```powershell
python -m unittest discover -s simulator/tests -v
```

测试不会创建 Tk 窗口，覆盖：合法 static/scroll、缺字段、错误类型和值域、
非法 mode、非法 UTF-8、非 JSON、非 state、超大报文、手动覆盖恢复、仅本地
清屏、有界日志/队列、UDP 收发、不可变事件以及 socket/线程关闭。

## 启动与本机烟雾测试

```powershell
python simulator/vled_sim.py
```

另开终端发送一条合法报文：

```powershell
python simulator/test_udp.py
```

人工 GUI 门禁还需确认：窗口能显示报文、手动覆盖与恢复行为正确、日志条数
受限、关闭窗口后进程及时退出。Windows 人工检查通过不等同于 Linux 全链路
验收；跨机 UDP 证据留到 P3/P4。
