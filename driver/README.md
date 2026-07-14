# VLED 驱动开发说明

## 成员 A 任务

成员 A 负责开发 Linux 字符设备驱动 `vled.ko`。驱动模块只负责字符设备抽象、内核缓冲区管理和 VLED 状态维护，不直接连接 Windows 模拟器，网络桥接由用户态程序完成。

主要任务如下：

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

4. 实现一页大小的内核缓冲区：
   - 缓冲区大小固定为 `PAGE_SIZE`
   - 用户态通过 `write()` 写入缓冲区
   - 用户态通过 `read()` 读取缓冲区或设备状态
   - 写入长度超过缓冲区时，需要在代码中固定错误返回或截断策略

5. 支持多进程打开同一设备：
   - 每次 `open()` 创建独立文件上下文
   - 每个文件描述符维护独立读写偏移
   - 共享设备状态必须加锁保护

6. 实现基础同步机制：
   - 使用 `mutex` 保护共享缓冲区和设备状态
   - 避免并发读写导致状态不一致

7. 维护 VLED 当前状态：
   - 屏幕宽度
   - 屏幕高度
   - 当前文字内容
   - 当前颜色
   - 当前亮度
   - 当前模式
   - 最后更新时间或版本号

## 开发环境

- 当前编码环境：Windows
- 目标运行环境：Ubuntu 24.04.4
- 目标内核版本：`Linux siqi 6.17.0-35-generic #35~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Tue May 26 19:30:42 UTC 2 x86_64`

`Makefile` 使用 Linux 内核模块标准构建方式，不能在 Windows 上直接编译。请把 `driver/` 目录放到目标 Linux 环境后执行构建和加载测试。

## 交付物

- `driver/vled.c`
- `driver/Makefile`
- `driver/README.md`

## 已实现功能

- 自动分配设备号：`alloc_chrdev_region`
- 注册字符设备：`cdev_init`、`cdev_add`
- 自动创建 `/dev/vled`：`class_create`、`device_create`
- 文件操作回调：`open`、`read`、`write`、`release`
- 内置 `PAGE_SIZE` 共享内核缓冲区
- 每个 `open()` 分配独立文件上下文，维护独立读写偏移
- 使用 `mutex` 保护共享缓冲区和 VLED 状态
- `read()` 返回单行 JSON 状态，供用户态桥接程序转发给 Windows 模拟器

## 命令协议

向 `/dev/vled` 写入 UTF-8 文本命令：

```text
TEXT <content>
COLOR <r> <g> <b>
BRIGHTNESS <0-100>
CLEAR
MODE <static|scroll>
STATUS
```

说明：

- `TEXT` 设置显示文本。
- `COLOR` 设置 RGB 颜色，三个值范围均为 `0-255`。
- `BRIGHTNESS` 设置亮度，范围为 `0-100`。
- `CLEAR` 清空文本，保留颜色、亮度和模式。
- `MODE` 只支持 `static` 和 `scroll`。
- `STATUS` 不改变状态，只用于配合后续读取。
- `PIXEL` 和 `frame` 数据暂未实现，第一阶段只交付 `state` JSON。

一次 `write()` 表示一条完整命令。单次写入长度大于等于 `PAGE_SIZE`
时返回 `-EMSGSIZE`；当前 FD 的累计写入将无法再保留结尾 NUL 时返回
`-ENOSPC`。驱动不会截断命令。

每个 `open()` 都有自己的 PAGE_SIZE 写入暂存页和 `write_offset`。本次数据
先复制到该 FD 暂存页的当前偏移，再解析本次命令。成功后才推进该 FD 的
写偏移；复制、语法、范围、支持性或 JSON 构建失败时，会清除本次片段并
回滚偏移，共享状态、版本和读取快照均保持不变。另一个独立 `open()` 的
暂存页和写容量不受影响。

错误码约定：语法、参数数量、类型和范围错误返回 `-EINVAL`，`PIXEL`
返回 `-EOPNOTSUPP`，TEXT 超过上限或状态 JSON 无法完整放入一页时返回
`-EMSGSIZE`。用户内存复制失败返回 `-EFAULT`。

## read 返回格式

`cat /dev/vled` 会读取当前状态 JSON：

```json
{"type":"state","width":32,"height":16,"text":"Hello VLED","color":[255,0,0],"brightness":80,"mode":"static","version":12}
```

默认状态：

```json
{"type":"state","width":32,"height":16,"text":"","color":[255,255,255],"brightness":100,"mode":"static","version":0}
```

只有可观察字段的值实际发生变化时，`version` 才递增一次。重复设置相同
值、空状态下再次 `CLEAR`、`STATUS` 和任何失败写入均不递增版本。

`struct vled_device` 中的 PAGE_SIZE 共享缓冲区始终保存最新、完整的状态
JSON；模块初始化完成时它已经包含默认版本 0 JSON。命令解析使用每个 FD
自己的暂存页，只有候选状态和候选 JSON 都成功构建后，才在同一个设备
mutex 临界区内一次性替换共享状态和共享 JSON，避免暴露半条命令或截断
JSON。

每次 `open()` 都会创建独立文件上下文，其中分别保存读偏移、写偏移和
稳定的读取快照。第一次非零长度 `read()` 在设备 mutex 内捕获共享 JSON，
之后的分段读取只推进当前 FD 的 `read_offset`。即使其他 FD 更新设备，旧
FD 仍会读完旧快照。读完快照后，如果已有更新版本则下一次 read 捕获新快照；
否则阻塞 FD 在 wait queue 等待，`O_NONBLOCK` FD 返回 `EAGAIN`。当前 FD 成功写入（包括
`STATUS`）后才使自己的下一次读取重新捕获快照，其他 FD 的进度不受影响。
`dup()` 得到的描述符按 POSIX 语义共享同一个文件上下文。设备不可 seek，
`lseek()` 返回 `ESPIPE`。

## poll、阻塞 read 与 wait queue

新打开的 FD 可立即读取当前状态。每个文件上下文记录已消费版本；消费当前版本
后，`.poll` 只有在出现未消费版本时才返回 `POLLIN | POLLRDNORM`。成功写入会调用
`wake_up_interruptible()` 让等待者重新检查条件；只有实际变化才递增 version 并使
其他独立 FD 可读。重复设置和 `STATUS` 只允许 `fork/dup` 共享当前 file context 的
reader 处理本地刷新，不会让其他 FD 的 poll 返回可读；失败写入不唤醒。阻塞 read
可被信号中断，非阻塞 read 在没有新版本时返回 `EAGAIN`。

`tools/vled_poll_probe /dev/vled` 覆盖 T-POLL-01..08；
`python3 tools/vled_multiprocess_probe.py --device /dev/vled` 使用真实 fork 覆盖
T-MP-01..04，包括独立写偏移、4+4 进程压力和共享 FD 唤醒。统一入口
`tools/vled_verify.sh` 同时执行 P1–P5 与多进程回归。

## P1 自动验收

`tools/vled_fd_probe` 覆盖冻结矩阵中的 PAGE_SIZE 边界、独立写容量、双 FD
读偏移、稳定快照、`dup()` 语义、失败原子回滚、版本规则以及 UTF-8/JSON
转义。它必须在刚加载的新模块上运行，因为第一项会验证默认版本为 0。

目标 Linux 上的执行顺序：

```bash
make -C driver clean
make -C driver
make -C tools clean
make -C tools
sudo rmmod vled 2>/dev/null || true
sudo insmod driver/vled.ko
sudo chmod 666 /dev/vled
./tools/vled_fd_probe /dev/vled
sudo rmmod vled
```

预期结果是每个测试 ID 输出 `PASS`，末行输出
`VLED P1 probe: all checks passed`，进程退出码为 0。任一系统调用返回值、
errno、状态 JSON、版本、偏移或快照不符合冻结契约时，探针输出 `FAIL` 并
以非零状态退出。P1 已在目标 Linux 通过并固化证据；Windows 侧只能做静态检查，
不能替代目标 Linux 运行。

## 构建与加载

在目标 Linux 环境执行：

```bash
cd driver
make
sudo insmod vled.ko
ls -l /dev/vled
```

正常加载只保留注册和注销摘要。教师演示时可启用可选操作追踪：

```bash
sudo insmod vled.ko trace_ops=1
cat /sys/module/vled/parameters/trace_ops
sudo journalctl -k -f | grep 'vled:'
```

追踪会打印动态 major/minor、cdev/class/device 创建步骤，以及每个 open 的诊断 ID、
PID、读写偏移、快照版本、命令结果和设备页长度。诊断 ID 不是内核地址；命令内容会
限长并把控制/非 ASCII 字节归一化。`trace_ops` 默认关闭，压力测试应保持关闭，以免
大量日志干扰时序。该参数只影响日志，不参与命令解析、状态发布、锁、偏移或唤醒判断。

卸载：

```bash
sudo rmmod vled
dmesg | tail
```

## 验证命令

```bash
make
sudo insmod vled.ko
ls -l /dev/vled
echo "TEXT Hello VLED" > /dev/vled
cat /dev/vled
sudo rmmod vled
dmesg | tail
```

驱动必须覆盖以下要求：

- 实现 `open/read/write/release`
- 自动分配设备号
- 自动创建 `/dev/vled`
- 内置 `PAGE_SIZE` 缓冲区
- 支持多进程打开
- 支持模块动态加载和卸载

## 功能测试建议

基础读写：

```bash
echo "TEXT Hello VLED" | sudo tee /dev/vled
cat /dev/vled
echo "COLOR 255 0 0" | sudo tee /dev/vled
cat /dev/vled
echo "BRIGHTNESS 80" | sudo tee /dev/vled
cat /dev/vled
echo "MODE scroll" | sudo tee /dev/vled
cat /dev/vled
echo "CLEAR" | sudo tee /dev/vled
cat /dev/vled
```

错误输入：

```bash
echo "COLOR 256 0 0" | sudo tee /dev/vled
echo "BRIGHTNESS 101" | sudo tee /dev/vled
echo "MODE blink" | sudo tee /dev/vled
echo "UNKNOWN" | sudo tee /dev/vled
cat /dev/vled
```

多进程读写：

```bash
for i in $(seq 1 20); do echo "TEXT msg-$i" | sudo tee /dev/vled >/dev/null; done &
for i in $(seq 1 20); do echo "COLOR 0 255 0" | sudo tee /dev/vled >/dev/null; done &
for i in $(seq 1 20); do cat /dev/vled; done
wait
```
