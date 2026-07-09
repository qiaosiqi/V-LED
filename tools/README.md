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

B 部分位于 Linux 虚拟机用户态，包含两个程序：

1. `vled_cli`：直接操作 `/dev/vled`，测试驱动的 `open/read/write/close`。
2. `vled_bridge`：读取 `/dev/vled` 返回的 JSON 状态字符串，并通过 UDP 发送给 Windows 主机上的 VLED 模拟器。

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
- `500`：轮询间隔，单位毫秒。

## 报告可写说明

B 部分实现了 Linux 用户态与内核字符设备之间的数据交互，以及 Linux 到 Windows 模拟器的 UDP 转发。`vled_cli` 使用 `open()` 打开 `/dev/vled`，使用 `write()` 写入 `TEXT/COLOR/BRIGHTNESS/MODE/CLEAR/STATUS` 等文本命令，使用 `read()` 读取驱动返回的一行 JSON 状态字符串，最后使用 `close()` 关闭设备。`vled_bridge` 周期性读取 `/dev/vled` 的 JSON 状态，并通过 UDP 发送到 Windows 主机 `9000` 端口。Windows 模拟器收到 UTF-8 JSON 后调用 `json.loads()` 解析，并根据 `type == "state"` 的状态内容进行渲染。
