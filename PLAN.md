# V-LED 已验证实现与维护计划

本文记录当前实现，不是候选设计草案。冻结语义以
`docs/IMPLEMENTATION_ROADMAP.md` 和 `docs/ACCEPTANCE_MATRIX.md` 为准。

## 1. 当前架构

```text
普通用户 vled_cli ──文本命令──> /dev/vled (driver/vled.ko)
                                      │
                                      ├─ PAGE_SIZE 共享状态 JSON
                                      ├─ per-open 读写上下文与稳定快照
                                      └─ wait queue + poll + version
                                               │
                         vled_bridge <──poll/read
                               │ UDP 9000 / UTF-8 state JSON
                               v
                 Windows simulator/vled_sim.py
                 UDP 后台线程 → 有界队列 → Tk 主线程
```

内核不直接联网。`vled_bridge` 单次打开 `/dev/vled`，先发送初始状态，之后用
`poll()` 等待有效版本变化；健康检查超时不重复发送旧状态。

## 2. 真实产物

- `driver/vled.c`、`driver/Makefile`：字符设备模块。
- `tools/vled_cli.c`：`read`、`write`、`loop` 用户态入口。
- `tools/vled_bridge.c`：事件驱动 UDP bridge。
- `tools/vled_verify.sh`：构建、模块生命周期及 P1–P5 回归入口。
- `tools/vled_fd_probe.c`：PAGE_SIZE、per-open offset、稳定快照和回滚。
- `tools/vled_poll_probe.c`：poll、wait queue、阻塞/非阻塞 read。
- `tools/vled_demo.sh`：跨机演示。
- `simulator/vled_protocol.py`、`vled_receiver.py`、`vled_model.py`、`vled_sim.py`：
  协议校验、UDP 接收、显示模型和 Tk GUI。

## 3. 固定接口

设备路径为 `/dev/vled`。每次 `write()` 是一条完整 UTF-8 命令：

```text
TEXT <content>
COLOR <r> <g> <b>
BRIGHTNESS <0-100>
MODE <static|scroll>
CLEAR
STATUS
```

`PIXEL` 未实现并返回 `EOPNOTSUPP`。读取结果是完整 `state` JSON：

```json
{"type":"state","width":32,"height":16,"text":"Hello VLED","color":[255,0,0],"brightness":80,"mode":"static","version":12}
```

UDP 使用 UTF-8、IPv4 和端口 9000；Windows 模拟器严格校验字段、类型和值域。

## 4. 冻结的并发与事件语义

1. 共享状态页由 mutex 保护；候选状态与 JSON 完整生成后才原子发布。
2. 每次 `open()` 拥有独立 `read_offset`、`write_offset`、写入页和读取快照。
3. 分段读取期间状态变化不影响旧快照；失败命令不改变状态、版本、偏移或快照。
4. `version` 仅在可观察字段实际变化时递增。`STATUS`、重复值和失败写入不递增。
5. 新 FD 可立即读取当前状态。消费当前版本后，阻塞 read 在 wait queue 等待；
   非阻塞 read 返回 `EAGAIN`，信号可中断阻塞等待。
6. `.poll` 对未消费版本返回 `POLLIN|POLLRDNORM`。有效变化通过
   `wake_up_interruptible()` 唤醒；无意义写入不唤醒。

## 5. 构建、测试与演示

Linux 从仓库根目录执行：

```bash
make -C driver
make -C tools
sudo insmod driver/vled.ko
sudo chmod 666 /dev/vled
./tools/vled_cli write "TEXT Hello VLED"
./tools/vled_cli read
sudo rmmod vled
```

完整验收：

```bash
sudo rmmod vled 2>/dev/null || true
./tools/vled_verify.sh
```

Windows 回归与 GUI：

```powershell
python -m unittest discover -s simulator/tests -v
python simulator/vled_sim.py
```

Linux 跨机演示：

```bash
./tools/vled_demo.sh <Windows-IPv4> /dev/vled
```

普通用户负责构建、CLI、bridge、probe 和 demo；root 只负责加载/卸载模块、
查看受限内核日志和设置设备访问权限。

## 6. 验收状态与后续门禁

P1–P6 目标环境验收已通过；P5/P6 正式证据分别位于
`docs/evidence/20260712-2127-ubuntu-6.17.0-35-generic-p5/` 与
`docs/evidence/20260712-2147-ubuntu-6.17.0-35-generic-p6/`。P7 内容和 P8 的
51 页报告版式已关闭。用户于 2026-07-13 将 P9 唯一落地成果调整为供老师汇报全部
业务逻辑和功能项、且每个关键命令均带中文注释的《运行指导手册》；该成果已完成，
先前规划的最终回归、盲演、故障彩排和新增证据不再属于 P9 门禁。

教师汇报和现场操作见 `docs/运行指导手册.md`。

Linux 只测试已提交并普通 fast-forward 推送到 `origin/integration-promote-try`
的明确哈希；禁止 force push。常见故障和最短操作路径见根 `README.md`。
