# V-LED：Linux 字符设备与 Windows 模拟器

V-LED 是实验四的完整实现：Linux 内核模块创建 `/dev/vled`，用户态工具通过
文本命令控制设备并读取状态 JSON，事件驱动的 `vled_bridge` 再把状态经 UDP
发送给 Windows Tkinter 模拟器。

当前已在 Ubuntu 24.04.4、Linux 6.17.0-35-generic、x86_64、GCC 13.3 上通过
P1–P6 验收，P7/P8 报告内容与 51 页版式已关闭；P9 教师汇报《运行指导手册》已完成。
本轮新增真实 fork 多进程与共享 FD 修复；静态契约和既有 Windows 回归已通过，
T-MP-01..04 仍须在目标 Ubuntu 上用本次构建的模块运行后才能标记为目标 PASS。
冻结契约、P5 证据和教师汇报手册分别见
[`docs/ACCEPTANCE_MATRIX.md`](docs/ACCEPTANCE_MATRIX.md) 与
[`docs/evidence/20260712-2127-ubuntu-6.17.0-35-generic-p5/RESULTS.md`](docs/evidence/20260712-2127-ubuntu-6.17.0-35-generic-p5/RESULTS.md)、
[`docs/运行指导手册.md`](docs/运行指导手册.md)。

## 最短可运行路径

Linux 需要与运行内核匹配的 headers、`make`、GCC、Python 3 和 `sudo` 权限。
从仓库根目录执行：

```bash
make -C driver
make -C tools
sudo insmod driver/vled.ko
sudo chmod 666 /dev/vled
./tools/vled_cli write "TEXT Hello VLED"
./tools/vled_cli read
sudo rmmod vled
```

`make` 和用户态命令使用普通用户；`insmod`、`rmmod` 及临时修改设备权限需要
root。`chmod 666` 仅适合隔离的课程实验机；共享系统应改用 udev 规则和专用组。

完整自动验收会自行构建、加载、设置临时权限、执行 P1–P5 回归并卸载模块：

```bash
sudo rmmod vled 2>/dev/null || true
./tools/vled_verify.sh
```

脚本内部需要 `sudo`，不要用 `sudo ./tools/vled_verify.sh` 运行整个脚本。

## 跨机演示

Windows 安装带 Tkinter 的 Python 3.12，在仓库根目录启动：

```powershell
python simulator/vled_sim.py
```

Linux 加载模块并允许普通用户访问 `/dev/vled` 后运行：

```bash
./tools/vled_demo.sh 192.168.57.1 /dev/vled
```

把示例 IP 替换为 Windows 在 VMware 网络中可达的 IPv4。模拟器默认监听 UDP
`9000`。`vled_demo.sh` 启动 `vled_bridge`，依次演示文字、颜色、亮度、模式、
中文和清屏，并在退出时停止 bridge；它不会加载模块或修改权限。

## 教师验收演示

下面的入口会从构建开始，详细打印用户态系统调用、内核处理、PAGE_SIZE 边界、
真实多进程独立偏移、自动设备号/设备节点以及两轮模块装卸：

```bash
# 纯 Linux 演示
./tools/vled_teacher_demo.sh

# 同时通过 UDP 9000 更新 Windows 模拟器
./tools/vled_teacher_demo.sh 192.168.57.1 /dev/vled
```

第二种形式要求 Windows 已运行 `python simulator/vled_sim.py`。教师脚本内部按需
调用 sudo，不要使用 `sudo ./tools/vled_teacher_demo.sh` 启动整个脚本。
终端输出会继续实时显示，同时完整保存到带启动时间的
`logs/vled-teacher-demo-YYYYmmdd-HHMMSS.log`；日志中的每一行也带有时间戳。

## 规范工具名称

| 工具 | 用途 |
|---|---|
| `vled_cli` | 普通用户读写 `/dev/vled` |
| `vled_bridge` | 单次打开设备，用 `poll()` 等待版本变化并发送 UDP |
| `vled_verify.sh` | Linux 全量验收入口 |
| `vled_fd_probe` | PAGE_SIZE、per-open offset、快照与回滚探针 |
| `vled_poll_probe` | poll、阻塞/非阻塞 read 与 wait queue 探针 |
| `vled_multiprocess_probe.py` | 真实 fork 多进程、独立写偏移、共享状态、并发无死锁与共享 FD 唤醒探针 |
| `vled_demo.sh` | Linux→Windows 演示编排 |
| `vled_teacher_demo.sh` | 五项驱动要求的详细教师验收，可选 Windows UDP 联动 |

## 已冻结的设备语义

- 共享状态 JSON 始终完整且小于 `PAGE_SIZE`；每个 `open()` 有独立读写上下文。
- 分段读取使用稳定快照；其他 FD 更新状态不会拼接新旧 JSON。
- 失败写入原子回滚；只有可观察状态真正变化才递增 `version`。
- 初次读取立即返回当前状态。读完已消费版本后，阻塞 FD 等待 wait queue 上的
  新版本，`O_NONBLOCK` FD 返回 `EAGAIN`。
- `.poll` 只在当前 FD 有未消费版本时报告 `POLLIN|POLLRDNORM`；重复设置、
  `STATUS` 和失败命令不发布事件。
- 每个独立 `open()` 分配自己的 file context、读写页、读写偏移和上下文锁；所有
  双锁路径固定为 `file context -> device`，等待队列睡眠前不持有 mutex。
- `fork/dup` 共享同一打开实例时，成功的无变化写入会唤醒该实例的阻塞读者；其他
  独立 FD 因 version 未变化仍不可读，不会产生重复状态事件。

详细错误码、命令和测试映射见 [driver/README.md](driver/README.md)；工具参数见
[tools/README.md](tools/README.md)；模拟器线程与协议见
[simulator/README.md](simulator/README.md)。

## 常见故障

- `.../build: No such file or directory`：安装与 `uname -r` 完全匹配的内核 headers。
- `Operation not permitted`：模块加载需要 root；Secure Boot/lockdown 也可能拒绝
  未签名模块，检查 `dmesg`。
- `/dev/vled` 不存在：确认 `insmod` 成功，查看 `lsmod` 和内核日志。
- 普通用户 `Permission denied`：由 root 临时 `chmod 666 /dev/vled`，或配置 udev。
- bridge 无 UDP 日志：核对 Windows IP、UDP 9000、防火墙和端口占用；ping 失败
  不能单独证明 UDP 不通。
- 自动验收拒绝启动：先 `sudo rmmod vled`，脚本不会替换已加载的旧模块。
- read 看似“卡住”：这是已消费当前版本后的阻塞语义；写入一次有效变化、使用
  `vled_poll_probe`，或用 `O_NONBLOCK` 客户端验证 `EAGAIN`。
