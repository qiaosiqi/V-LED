# B 部分：Linux 用户态测试程序与 UDP 桥接程序

## 接口约定

A 组的 `/dev/vled` 对外是字符串协议，不是二进制结构体接口。

驱动内部可以使用 `struct vled_state` 保存状态，例如 `width/height/text/color/brightness/mode/version` 等字段；但用户态程序不直接读写这个 C 结构体。

用户态写入 `/dev/vled` 的内容是文本命令，例如：

```text
TEXT Hello VLED
COLOR 255 0 0
BRIGHTNESS 80
MODE scroll
CLEAR
STATUS
```

用户态读取 `/dev/vled` 时，驱动返回一行 JSON 字符串，例如：

```json
{"type":"state","width":32,"height":16,"text":"Hello VLED","color":[255,0,0],"brightness":80,"mode":"static","version":12}
```

Windows 模拟器要求收到 UTF-8 编码的 JSON，且字段 `type` 必须为 `"state"`。

## B 部分负责内容

B 部分位于 Linux 虚拟机用户态，包含程序和自动化入口：

1. `vled_cli`：直接操作 `/dev/vled`，测试驱动的 `open/read/write/close`。
2. `vled_bridge`：读取 `/dev/vled` 返回的 JSON 状态字符串，并通过 UDP 发送给 Windows 主机上的 VLED 模拟器。
3. `vled_fd_probe`：P1 自动验收探针，检查 PAGE_SIZE 边界、多 FD 独立偏移、稳定快照和失败原子回滚。
4. `vled_poll_probe`：P5 探针，检查 poll、wait queue、阻塞/非阻塞 read、信号中断和事件收敛。
5. `vled_multiprocess_probe.py`：真实 fork 多进程验收，检查分别 open、独立写偏移、共享状态、4+4 进程压力和共享 FD 唤醒。
6. `vled_verify.sh`：P1–P5 与多进程统一验收入口，负责严格构建、bridge 黑盒测试、模块生命周期、业务/错误码/并发/poll/多进程回归和内核日志检查。
7. `vled_demo.sh`：Linux→Windows 可复现演示编排；任一步失败都会停止。

驱动本身不直接联网，网络转发放在用户态 `vled_bridge` 程序中完成。

## 编译

```bash
make
```

也可以单独编译：

```bash
gcc -Wall -Wextra -O2 -o vled_cli vled_cli.c
gcc -Wall -Wextra -O2 -o vled_bridge vled_bridge.c
```

## 前置条件

驱动 A 部分加载完成后，应存在设备节点：

```bash
ls -l /dev/vled
```

如果权限不足，可以临时执行：

```bash
sudo chmod 666 /dev/vled
```

## CLI 测试

写入文本：

```bash
./vled_cli write "TEXT Hello VLED"
```

设置颜色：

```bash
./vled_cli write "COLOR 255 0 0"
```

设置亮度：

```bash
./vled_cli write "BRIGHTNESS 80"
```

读取 JSON 状态：

```bash
./vled_cli read
```

循环读取：

```bash
./vled_cli loop 1
```

这些命令可以证明用户态程序能够打开字符设备、向驱动写入文本命令、从设备读取 JSON 状态，并正常关闭设备。

## P1 文件上下文与边界探针

在刚加载的新模块上执行：

```bash
./vled_fd_probe /dev/vled
```

探针检查零长度和 PAGE_SIZE 边界、每个 open 的独立写容量、双 FD 分段
读取、更新期间的旧快照稳定性、失败命令对状态/版本/偏移/快照的回滚，
以及 JSON 转义。全部通过时退出码为 0；任何检查失败时退出码为 1。

## P1–P5 自动验收

先确认旧 `vled` 模块没有加载，然后执行：

```bash
./tools/vled_verify.sh
```

可通过环境变量调整设备、并发迭代和装卸轮数：

```bash
VLED_DEVICE=/dev/vled VLED_ITERATIONS=500 VLED_LIFECYCLE_CYCLES=5 \
    ./tools/vled_verify.sh
```

脚本拒绝直接替换已经加载的模块，失败时返回非零，并通过 trap 尝试清理本轮加载
的模块。它会运行 `vled_fd_probe`、业务/并发验收和 `vled_poll_probe`。加载、
卸载、临时 `chmod` 和受限内核日志读取需要 sudo；构建和探针本身以普通用户运行。
正式证据步骤见 `docs/P5_LINUX_RUNBOOK.md`。

也可以在已加载且普通用户可读写的设备上单独运行用户态验收：

```bash
python3 tools/vled_verify.py --device /dev/vled --iterations 200
python3 tools/vled_bridge_probe.py --bridge tools/vled_bridge
python3 tools/vled_multiprocess_probe.py --device /dev/vled --iterations 100
```

## UDP 桥接测试

Windows 模拟器 `simulator/vled_sim.py` 使用 UDP：

```python
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.bind(("0.0.0.0", 9000))
data, addr = udp_socket.recvfrom(2048)
```

因此 Linux 侧桥接程序只需要把 `/dev/vled` 读出的 JSON 状态字符串通过 UDP 发到 Windows 主机的 `9000` 端口。

默认端口为 `9000`：

```bash
./vled_bridge 192.168.1.10
```

完整参数示例：

```bash
./vled_bridge 192.168.1.10 9000 /dev/vled 500
```

参数含义：

- `192.168.1.10`：Windows 主机 IP。
- `9000`：Windows VLED 模拟器 UDP 监听端口。
- `/dev/vled`：Linux 字符设备节点。
- `500`：`poll()` 健康检查超时，单位毫秒；超时不会重复发送旧状态。

IP、端口和超时均严格校验；非法参数返回非零，不会静默退回默认值。bridge 只
打开设备一次，初次读取当前快照，随后通过 `poll()` 等待 wait queue 发布的新版本。
它仅
发送满足驱动规范完整字段、JSON 结构和值域的 canonical state；无效内容会记录
`skip non-state payload`，不会生成伪成功发送日志。SIGINT/SIGTERM 会使进程清理
socket 并退出。

## 跨机演示

Windows 启动 `simulator/vled_sim.py` 后，在 Linux 执行：

```bash
./tools/vled_demo.sh 192.168.57.1 /dev/vled
```

脚本依次演示 TEXT、COLOR、BRIGHTNESS、MODE、中文和 CLEAR，并在退出时终止
bridge。它不会加载模块或修改设备权限；这些前置动作由操作者显式完成。

## 报告可写说明

B 部分实现了 Linux 用户态与内核字符设备之间的数据交互，以及 Linux 到 Windows 模拟器的 UDP 转发。`vled_cli` 使用 `open()` 打开 `/dev/vled`，使用 `write()` 写入 `TEXT/COLOR/BRIGHTNESS/MODE/CLEAR/STATUS` 等文本命令，使用 `read()` 读取驱动返回的一行 JSON 状态字符串，最后使用 `close()` 关闭设备。`vled_bridge` 长期打开设备并使用 `poll()` 等待版本变化，读取完整 JSON 后通过 UDP 发送到 Windows 主机 `9000` 端口。Windows 模拟器收到 UTF-8 JSON 后严格校验协议，并在 Tk 主线程渲染。
