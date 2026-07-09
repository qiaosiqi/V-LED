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

写入长度大于等于 `PAGE_SIZE` 时返回 `-EMSGSIZE`，不会截断写入，避免状态半更新。非法命令返回 `-EINVAL`，状态保持不变。

## read 返回格式

`cat /dev/vled` 会读取当前状态 JSON：

```json
{"type":"state","width":32,"height":16,"text":"Hello VLED","color":[255,0,0],"brightness":80,"mode":"static","version":12}
```

默认状态：

```json
{"type":"state","width":32,"height":16,"text":"","color":[255,255,255],"brightness":100,"mode":"static","version":0}
```

每次有效状态变更后，`version` 递增。

## 构建与加载

在目标 Linux 环境执行：

```bash
cd driver
make
sudo insmod vled.ko
ls -l /dev/vled
```

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
