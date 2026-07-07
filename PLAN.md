# VLED 开发规划

## 1. 项目目标

本实验实现一个 Linux 虚拟字符设备驱动程序，并通过 Windows 上的 VLED 模拟器展示虚拟 LED 屏效果。

整体方案分为三部分：

- A：驱动开发
- B：用户态测试与桥接
- C：Windows VLED 模拟器与演示

核心原则：

- Linux 内核模块只负责字符设备抽象、缓冲区管理和状态维护。
- Linux 用户态程序负责测试驱动，并把驱动状态桥接到 Windows。
- Windows VLED 模拟器只负责接收状态数据并可视化显示。

## 2. 总体架构

```text
Windows 主机
└── C. VLED 模拟器
    ├── 监听网络端口
    ├── 接收 VLED 帧数据或状态数据
    └── 渲染 LED 矩阵、文字、颜色、亮度等效果

VMware Linux 虚拟机
├── A. vled.ko 字符设备驱动
│   ├── 注册 /dev/vled
│   ├── 实现 open/read/write/release
│   ├── 管理 PAGE_SIZE 内核缓冲区
│   └── 维护 VLED 当前状态
│
└── B. 用户态测试与桥接
    ├── vledctl：命令行测试工具
    └── vled-bridge：读取 /dev/vled 状态并发送给 Windows 模拟器
```

## 3. A - 驱动开发

### 3.1 工作内容

A 负责开发 Linux 字符设备驱动 `vled.ko`。

主要内容：

1. 实现 Linux 内核模块基本结构：
   - `module_init`
   - `module_exit`
   - `MODULE_LICENSE`
   - `MODULE_AUTHOR`
   - `MODULE_DESCRIPTION`

2. 实现字符设备注册：
   - 使用 `alloc_chrdev_region` 自动分配设备号
   - 使用 `cdev_init` 初始化字符设备
   - 使用 `cdev_add` 注册字符设备
   - 使用 `class_create` 创建设备类
   - 使用 `device_create` 自动创建 `/dev/vled`

3. 实现文件操作回调：
   - `open`
   - `read`
   - `write`
   - `release`

4. 实现一页大小内核缓冲区：
   - 缓冲区大小固定为 `PAGE_SIZE`
   - 用户态 `write()` 写入缓冲区
   - 用户态 `read()` 读取缓冲区或设备状态
   - 写入长度超过缓冲区时返回错误或截断，具体策略需在代码中固定

5. 支持多进程打开同一设备：
   - 每个 `open()` 创建独立文件上下文
   - 每个文件描述符维护独立读写偏移
   - 共享设备状态需要加锁保护

6. 实现基础同步机制：
   - 使用 `mutex` 保护共享缓冲区和设备状态
   - 避免并发读写导致状态不一致

7. 维护 VLED 状态：
   - 屏幕宽度
   - 屏幕高度
   - 当前文字内容
   - 当前颜色
   - 当前亮度
   - 当前模式
   - 最后更新时间或版本号

### 3.2 建议命令协议

用户写入 `/dev/vled` 的数据使用文本命令，便于调试和展示。

```text
TEXT <content>
COLOR <r> <g> <b>
BRIGHTNESS <0-100>
CLEAR
PIXEL <x> <y> <r> <g> <b>
MODE <static|scroll>
STATUS
```

示例：

```bash
echo "TEXT Hello VLED" > /dev/vled
echo "COLOR 255 0 0" > /dev/vled
echo "BRIGHTNESS 80" > /dev/vled
cat /dev/vled
```

### 3.3 read 返回格式

`read()` 返回当前设备状态，推荐使用单行文本 JSON，便于 B 解析并转发。

```json
{"type":"state","width":32,"height":16,"text":"Hello VLED","color":[255,0,0],"brightness":80,"mode":"static","version":12}
```

如果实现像素级显示，也可返回帧数据：

```json
{"type":"frame","width":32,"height":16,"pixels":[[255,0,0],[0,0,0]],"brightness":80,"version":13}
```

第一阶段建议只实现 `state`，第二阶段再扩展 `frame`。

### 3.4 交付要求

A 的交付物：

- `driver/vled.c`
- `driver/Makefile`
- `README` 或简短使用说明

必须能完成以下验证：

```bash
make
sudo insmod vled.ko
ls -l /dev/vled
echo "TEXT Hello VLED" > /dev/vled
cat /dev/vled
sudo rmmod vled
dmesg | tail
```

必须覆盖实验要求：

- 实现 `open/read/write/release`
- 自动分配设备号
- 自动创建 `/dev/vled`
- 内置 `PAGE_SIZE` 缓冲区
- 支持多进程打开
- 支持模块动态加载和卸载

## 4. B - 用户态测试与桥接

### 4.1 工作内容

B 负责 Linux 用户态程序，连接 A 和 C。

主要内容：

1. 开发 `vledctl` 命令行工具：
   - 向 `/dev/vled` 写入命令
   - 从 `/dev/vled` 读取状态
   - 用于测试驱动是否正常

2. 开发 `vled-bridge` 桥接程序：
   - 周期性读取 `/dev/vled`
   - 解析驱动返回的 JSON 状态
   - 通过 TCP 或 UDP 发送给 Windows VLED 模拟器
   - 打印发送日志，方便演示排错

3. 编写测试脚本：
   - 测试文本显示
   - 测试颜色切换
   - 测试亮度变化
   - 测试清屏
   - 测试多进程读写

### 4.2 vledctl 建议接口

```bash
./vledctl text "Hello VLED"
./vledctl color 255 0 0
./vledctl brightness 80
./vledctl mode scroll
./vledctl clear
./vledctl status
```

这些命令最终转换为写入 `/dev/vled` 的文本命令：

```text
TEXT Hello VLED
COLOR 255 0 0
BRIGHTNESS 80
MODE scroll
CLEAR
STATUS
```

### 4.3 vled-bridge 建议接口

```bash
./vled-bridge --device /dev/vled --host 192.168.1.10 --port 9000 --interval 100
```

参数说明：

- `--device`：字符设备路径，默认 `/dev/vled`
- `--host`：Windows 主机 IP
- `--port`：Windows VLED 模拟器监听端口
- `--interval`：读取和发送间隔，单位毫秒

### 4.4 桥接通信协议

推荐第一阶段使用 UDP。

理由：

- 实现简单
- 延迟低
- 演示场景下允许丢少量帧
- Windows 模拟器只需要监听端口即可

B 发送给 C 的数据格式与 A 的 `read()` 返回格式保持一致。

示例：

```json
{"type":"state","width":32,"height":16,"text":"Hello VLED","color":[255,0,0],"brightness":80,"mode":"static","version":12}
```

### 4.5 交付要求

B 的交付物：

- `tools/vledctl.c` 或 `tools/vledctl.py`
- `tools/vled-bridge.c` 或 `tools/vled-bridge.py`
- `tools/test_demo.sh`
- `tools/README.md`

必须能完成以下验证：

```bash
./vledctl text "Hello VLED"
./vledctl color 0 255 0
./vledctl brightness 60
./vledctl status
./vled-bridge --host <Windows-IP> --port 9000
```

## 5. C - Windows VLED 模拟器与演示

### 5.1 工作内容

C 负责 Windows 上的 VLED 可视化程序和最终演示效果。

主要内容：

1. 开发 VLED 模拟器界面：
   - 显示 LED 点阵屏
   - 支持配置宽度和高度，建议默认 `32 x 16`
   - 支持文字显示
   - 支持颜色显示
   - 支持亮度变化
   - 支持清屏
   - 支持静态和滚动模式

2. 实现网络接收：
   - 监听 UDP 端口，默认 `9000`
   - 接收 B 发送的 JSON 状态
   - 解析状态并刷新界面

3. 实现演示辅助功能：
   - 显示当前连接状态
   - 显示最近收到的原始 JSON
   - 显示版本号或更新时间
   - 提供手动清屏按钮

### 5.2 接收数据格式

C 必须支持以下状态格式：

```json
{"type":"state","width":32,"height":16,"text":"Hello VLED","color":[255,0,0],"brightness":80,"mode":"static","version":12}
```

字段说明：

- `type`：数据类型，第一阶段固定为 `state`
- `width`：LED 屏宽度
- `height`：LED 屏高度
- `text`：显示文本
- `color`：RGB 颜色数组
- `brightness`：亮度，范围 `0-100`
- `mode`：显示模式，支持 `static` 和 `scroll`
- `version`：状态版本号，每次驱动状态变化递增

### 5.3 交付要求

C 的交付物：

- Windows VLED 模拟器源码
- 可运行程序或启动脚本
- 演示说明

必须能完成以下验证：

1. 启动模拟器后监听 `9000` 端口。
2. 接收到 B 发送的 JSON 后更新显示。
3. 在界面上能看到文字、颜色、亮度、模式变化。
4. 能显示最近收到的数据，方便集成调试。

## 6. 三个工作之间的数据流

### 6.1 正向控制流

```text
用户命令
  ↓
B. vledctl
  ↓ 写入文本命令
/dev/vled
  ↓
A. vled.ko 驱动
  ↓ 解析命令并更新内核缓冲区和设备状态
A. read() 返回 JSON 状态
  ↓
B. vled-bridge
  ↓ UDP 发送 JSON
C. Windows VLED 模拟器
  ↓
刷新虚拟 LED 显示
```

### 6.2 状态读取流

```text
B. vled-bridge
  ↓ read(/dev/vled)
A. vled.ko
  ↓ 返回当前 JSON 状态
B. vled-bridge
  ↓ sendto(Windows-IP:9000)
C. Windows VLED 模拟器
  ↓ 解析 JSON 并渲染
```

### 6.3 手工测试流

```text
Linux Shell
  ↓
echo "TEXT Hello" > /dev/vled
  ↓
A. vled.ko 更新状态
  ↓
cat /dev/vled
  ↓
输出 JSON 状态
```

### 6.4 集成时必须固定的接口

为避免最后集成失败，三方必须提前固定以下接口：

1. 字符设备路径：

```text
/dev/vled
```

2. 写入驱动的命令格式：

```text
TEXT <content>
COLOR <r> <g> <b>
BRIGHTNESS <0-100>
CLEAR
MODE <static|scroll>
STATUS
```

3. 驱动 `read()` 返回格式：

```json
{"type":"state","width":32,"height":16,"text":"Hello VLED","color":[255,0,0],"brightness":80,"mode":"static","version":12}
```

4. 桥接发送协议：

```text
UDP
```

5. Windows 模拟器监听端口：

```text
9000
```

6. 字符编码：

```text
UTF-8
```

## 7. 集成计划

### 7.1 第一阶段：驱动单独可用

目标：

- `/dev/vled` 能自动创建
- `echo` 能写入命令
- `cat` 能读取 JSON 状态
- `insmod` 和 `rmmod` 正常工作

验收命令：

```bash
sudo insmod vled.ko
echo "TEXT Hello VLED" > /dev/vled
cat /dev/vled
sudo rmmod vled
```

### 7.2 第二阶段：用户态工具可用

目标：

- `vledctl` 能控制 `/dev/vled`
- `vled-bridge` 能读出 JSON 并发送 UDP

验收命令：

```bash
./vledctl text "Hello VLED"
./vledctl color 255 0 0
./vledctl status
./vled-bridge --host <Windows-IP> --port 9000
```

### 7.3 第三阶段：Windows 模拟器可用

目标：

- Windows 模拟器能独立接收测试 JSON
- 收到 JSON 后能刷新界面

验收方式：

- 使用临时 UDP 发送脚本向 Windows 端发送测试 JSON。
- 检查模拟器是否正确显示文字、颜色、亮度和模式。

### 7.4 第四阶段：全链路集成

目标：

- Linux 命令能驱动 Windows VLED 模拟器显示变化。

验收流程：

```bash
sudo insmod vled.ko
./vled-bridge --host <Windows-IP> --port 9000
./vledctl text "Operating System Driver"
./vledctl color 0 255 0
./vledctl brightness 75
./vledctl mode scroll
```

Windows VLED 模拟器应同步显示变化。

## 8. 风险与规避

### 8.1 不建议内核驱动直接连接 Windows

风险：

- 内核网络编程复杂度高
- 调试困难
- 容易偏离课程考核重点

规避：

- 内核驱动只维护 `/dev/vled`
- 网络通信全部放在用户态 `vled-bridge`

### 8.2 JSON 在内核中生成要保持简单

风险：

- 内核中不适合引入复杂 JSON 库

规避：

- 使用固定字段和 `snprintf` 生成简单 JSON
- 限制文本长度，避免缓冲区溢出

### 8.3 VMware 网络可能影响集成

风险：

- Linux 虚拟机无法访问 Windows 主机 IP
- Windows 防火墙阻止 UDP 端口

规避：

- 优先使用桥接网络或 NAT 下可访问的主机 IP
- Windows 防火墙放行模拟器或 UDP `9000` 端口
- C 端显示最近收到的数据，方便判断是否收到包

### 8.4 三方协议不一致

风险：

- A 返回字段和 C 解析字段不一致
- B 转发格式与 C 接收格式不一致

规避：

- 以本文件第 6.4 节为固定接口
- 任何字段变更必须同步更新 A、B、C

## 9. 最小可交付版本

如果时间紧张，最小版本只需要实现：

- A：`/dev/vled` 支持 `TEXT`、`COLOR`、`BRIGHTNESS`、`CLEAR`，`read()` 返回 `state` JSON
- B：`vledctl` 写命令，`vled-bridge` 周期读取并 UDP 转发
- C：Windows 界面显示文字、颜色和亮度

暂缓内容：

- 像素级 `PIXEL` 命令
- 完整帧数据 `frame`
- 复杂动画
- TCP 可靠连接
- 图形化配置页面
