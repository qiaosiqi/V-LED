# V-LED 实验四长期实施路线与验收基线

> 本文档是 V-LED 项目的跨对话实施依据（Single Source of Truth）。
> 任何后续对话开始工作前，都应先阅读本文档的“当前状态”“下一步”和对应阶段的验收门槛。
>
> 当前执行门禁：**P1–P4 已关闭。P5 未获用户授权，不得开始 poll/wait queue 实现。**

## 0. 文档元信息

| 项目 | 当前值 |
|---|---|
| 最后更新日期 | 2026-07-12 |
| 目标实验 | 实验四：Linux 驱动程序 |
| 目标分支 | `integration-promote-try` |
| 本地实施起点 | `a192f2c`（与本地 `integration` 相同） |
| 当前已验证实现 | `abad494`（P1–P4 验收均通过） |
| 同步规则状态 | 首次 `--force-with-lease` 已完成；后续只允许 fast-forward 推送 |
| 当前执行状态 | `P1_TARGET_LINUX_PASS / P2_WINDOWS_PASS / P3_TARGET_PASS / P4_TARGET_EVIDENCE_PASS / P5_NOT_AUTHORIZED` |
| 当前允许动作 | 固化并汇报 P4 正式证据；不得提前进入 P5 |
| P0 产物 | `IMPLEMENTATION_ROADMAP.md`、`ACCEPTANCE_MATRIX.md`、`LINUX_ENVIRONMENT.md` |
| 下一动作 | 提交 P4 正式证据并向用户汇报；等待用户决定是否批准进入 P5 |

### 0.1 当前工作区保护事项

1. `docs/操作系统课程设计报告2026.doc` 存在用户未提交修改。
2. 任何 Git 操作都不得覆盖、还原、暂存或顺带提交该文件，除非用户单独授权。
3. 远端 `origin/integration-promote-try` 中的旧验证提交 `a40be52` 已被本地分支主动舍弃；它只能作为设计参考，不得直接 `pull`、合并或 cherry-pick。
4. 后续如需让远端分支与本地新历史一致，必须先展示提交图并单独取得 `--force-with-lease` 推送许可。
5. 每次开始工作前必须执行并记录：

```bash
git status --short --branch
git rev-parse HEAD integration integration-promote-try origin/integration-promote-try
```

### 0.2 Windows→GitHub→Linux 同步规则

1. 所有实现只基于 `integration-promote-try`；不得从 `main`、`integration` 或旧远端验证提交临时拼接未审计代码。
2. 遵循“要运行什么、要测什么，就推什么”：每个 Linux 测试批次必须同时包含待测实现、对应测试、运行说明和预期结果。
3. Linux 只测试 GitHub 上明确的提交哈希，不测试 Windows 未提交工作树。
4. 测试批次通过后，原始日志和截图按运行编号回传；失败证据不得覆盖。
5. P0 只有文档产物，不需要为 Linux 运行单独推送。
6. 第一个需要 Linux 运行的批次预计出现在 P1/P3；届时先提交并展示 diff/test 清单，再推送。
7. 由于远端仍指向旧 `a40be52`，第一次推送需要一次 `--force-with-lease` 对齐；必须在动作发生前再次取得用户许可。完成这一次后只允许 fast-forward 推送。

## 1. 总目标与完成定义

### 1.1 总目标

在 `integration-promote-try` 分支上完成以下长期目标：

1. 修正字符设备的 PAGE_SIZE 缓冲区和独立写偏移语义，使实现、说明和验收行为完全一致。
2. 修正 Windows 模拟器的 Tkinter 跨线程访问和共享状态竞态。
3. 将 PDF 明示要求、VLED 业务功能、边界行为和错误路径全部转化为可重复执行的显式验收项。
4. 在目标 Linux 环境执行自动化验证，保存不可伪造、可复核的原始日志和截图。
5. 在基础合规稳定后实现高价值扩展：`poll + wait queue` 事件驱动通知。
6. 统一命令名称、README、PLAN、测试脚本和演示脚本。
7. 将实验报告建设为约 50 页的技术报告，并完成图表编号、交叉引用、目录和逐页版式检查。

### 1.2 “真正完成”的定义

一个功能只有同时满足以下四项才可标记为完成：

- **实现**：代码路径真实存在，不是只打印成功信息。
- **自动验收**：有测试能让正确实现通过、错误实现失败。
- **原始证据**：保留命令、退出码、环境信息、日志或截图。
- **文档闭环**：README/PLAN/报告中的描述与实际行为一致。

仅有界面、日志文案、README 声明或无法失败的“测试”，均不算完成。

## 2. 不可妥协的实施原则

1. **合规优先**：先保证实验四 PDF 的所有明示要求，再做扩展。
2. **证据驱动**：先写验收契约，再改实现；每个修复必须有能捕获回归的测试。
3. **最小可审查提交**：驱动语义、模拟器线程、测试工具、文档、报告分别提交。
4. **不伪造 Linux 结果**：没有在目标 Linux 实际执行，就标记为“未验证”，不得补写 PASS 日志或截图。
5. **不以复杂代替正确**：不为凑工作量加入内核网络、无关动画或无法解释的功能。
6. **保留原始证据**：原始日志只追加、不手改；分析和结论写在独立 Markdown 中。
7. **报告不是代码仓库转储**：正文只放关键代码，并对设计、流程、测试结果和限制进行解释。
8. **阶段门禁**：上一阶段验收失败时，不进入依赖它的下一阶段。

## 3. 范围边界

### 3.1 本路线包含

- Linux 虚拟字符设备驱动。
- Linux 用户态 CLI、UDP bridge、自动验证和演示脚本。
- Windows VLED 模拟器。
- 实验四的全链路测试、证据和课程设计报告。
- `poll + wait queue` 高价值扩展。

### 3.2 本路线不包含

- 实验一、二、三、五。
- 内核态直接连接 Windows 或直接发送 UDP。
- 在基础验收完成前开发像素级 framebuffer、复杂动画或 TCP 重传系统。
- 与实验四无关的“大而全”管理平台。

## 4. 已冻结技术口径

### 4.1 PAGE_SIZE 与独立偏移的目标语义

P0 于 2026-07-12 冻结以下口径。完整 Given/When/Then、错误码和测试 ID 见 `docs/ACCEPTANCE_MATRIX.md`：

1. `struct vled_device` 保留一个明确的 `PAGE_SIZE` 共享状态缓冲区。
2. 共享状态缓冲区始终保存最新、完整、可读取的 JSON 状态，并由 mutex 保护。
3. 每次 `open()` 分配独立 `vled_file_context`，至少包含：
   - `read_offset`；
   - `write_offset`；
   - 稳定的读取快照及其版本；
   - PAGE_SIZE 独立写入暂存区，使 `write_offset` 真正影响容量和数据落点。
4. `read()` 必须从 PAGE_SIZE 状态缓冲区捕获一致快照，并使用该 FD 自己的 `read_offset` 分段读取。
5. 一次 `write()` 是一条完整命令；成功写入落到该 FD 暂存页并推进自己的 `write_offset`。
6. `count >= PAGE_SIZE` 返回 `-EMSGSIZE`；累计空间不足返回 `-ENOSPC`，为 NUL 终止保留 1 字节。
7. 非法或失败写入必须原子回滚，不消耗写偏移，不改变共享状态、版本号或读快照。
8. 模块初始化后共享缓冲区已经包含默认版本 0 JSON；JSON 输出始终完整且小于 PAGE_SIZE。
9. `version` 只在可观察字段值实际变化时递增；重复设置、`STATUS` 和失败命令不递增。
10. `STATUS` 成功并消耗当前 FD 写偏移，同时刷新当前 FD 的读取快照，但不改变其他 FD 和全局版本。
11. 同一 FD 成功写入后，只允许重置该 FD 的读快照；不得重置其他 FD 的独立读取进度。
12. 设备为 non-seekable；独立偏移由每文件上下文维护，不向用户承诺 `lseek()`。

任何偏离该口径的实施都必须先更新 `ACCEPTANCE_MATRIX.md` 和本文档决策记录，说明替代设计、测试方法和迁移影响，并获得确认。

### 4.2 模拟器线程模型

1. UDP 后台线程只负责：socket 接收、UTF-8 解码、JSON 解析、协议校验、生成不可变事件并放入线程安全队列。
2. UDP 后台线程不得调用任何 Tkinter 控件方法。
3. Tk 主线程通过 `root.after()` 周期排空队列，并一次性替换完整状态。
4. GUI 渲染只读取主线程持有的状态快照。
5. 关闭窗口时设置停止事件、关闭 socket，并允许监听线程及时退出。
6. 手动颜色/亮度覆盖必须有明确优先级；恢复 UDP 状态时行为必须可测试。
7. 无效报文不能导致 GUI 崩溃，也不能部分更新状态。

### 4.3 协议校验规则

所有 `state` 报文至少验证：

- `type == "state"`；
- `width`、`height` 为正整数，且有合理上限；
- `text` 为字符串并限制长度；
- `color` 恰好包含 3 个 `0..255` 整数；
- `brightness` 为 `0..100` 整数；
- `mode` 只能是 `static` 或 `scroll`；
- `version` 为非负整数；
- 缺字段、错误类型、超限数据、非法 UTF-8 和超大 UDP 报文均明确拒绝并记录原因。

## 5. 阶段总览与依赖关系

| 阶段 | 名称 | 依赖 | 当前状态 |
|---|---|---|---|
| P0 | 基线冻结与验收契约 | 用户批准 | 已完成 |
| P1 | 缓冲区与独立写偏移修正 | P0 | 已通过目标 Linux 验收；证据已固化 |
| P2 | 模拟器线程安全与协议校验 | P0 | Windows 自动测试和人工 GUI 复核均通过；证据已固化 |
| P3 | 全功能自动验收与演示脚本 | P1、P2 | 目标 Linux 自动验收与 Windows 跨机演示均通过；证据已固化 |
| P4 | 目标 Linux 实测与证据固化 | P3、目标 Linux | 00–08 分项日志、Linux/Windows 截图和哈希清单均已通过并固化 |
| P5 | `poll + wait queue` 扩展 | P4 基础测试通过 | 未开始 |
| P6 | README、PLAN 与命令统一 | P3；P5 后复核 | 未开始 |
| P7 | 约 50 页报告骨架与内容填充 | P0 可建骨架；实测内容依赖 P4/P5 | 未开始 |
| P8 | 图表、引用、目录、版式与逐页 QA | P7 内容稳定 | 未开始 |
| P9 | 最终回归、演示彩排与交付检查 | P4–P8 | 未开始 |

允许 P1 与 P2 在不同提交中并行推进；P3 必须等待二者都通过各自测试。

## 6. 分阶段实施细则

## P0：基线冻结与验收契约

### 工作项

- [x] 重新核对目标分支和脏工作区，保护用户报告。
- [x] 回填目标环境全部必要信息；非阻塞未知项留到对应测试阶段复核。
- [x] 建立 `docs/ACCEPTANCE_MATRIX.md`，将 PDF 要求映射到源码、测试和证据。
- [x] 固定错误码、PAGE_SIZE 边界、版本号、快照和独立偏移语义。
- [x] 列出当前测试必须先失败的场景，防止测试只能验证表面输出。
- [x] 设计证据目录和运行编号。
- [x] 确认远端旧提交处理策略，但不推送。
- [x] 建立 `docs/LINUX_ENVIRONMENT.md` 环境信息模板和只读采集命令。

### 验收门槛

- 每条 PDF 明示要求都有唯一验收 ID。
- 每个业务命令都有正常、边界和非法输入测试。
- 所有待修改语义都已写成“给定—操作—预期”的可执行描述。
- 用户未提交的 DOC 文件保持原状且未被暂存。

### 建议提交

```text
docs: define VLED implementation roadmap and acceptance contract
```

## P1：缓冲区与独立写偏移修正

### 工作项

- [ ] 重构 `vled_file_context`，使读偏移和写偏移都真实参与行为。
- [ ] 确保用户写入经过受 PAGE_SIZE 约束的内核缓冲区。
- [ ] 确保 `read()` 返回稳定、完整的单版本 JSON 快照。
- [ ] 对失败写入执行状态、版本和偏移回滚。
- [ ] 明确零长度、PAGE_SIZE-1、PAGE_SIZE、超 PAGE_SIZE 写入行为。
- [ ] 明确同一 FD 连续写、多 FD 分别写、分段读和读到 EOF 的行为。
- [ ] 保持 `TEXT/COLOR/BRIGHTNESS/MODE/CLEAR/STATUS` 业务语义。
- [ ] 保留 JSON 转义，并补充引号、反斜杠、制表符和 UTF-8 文本测试。
- [ ] 检查 open 失败路径、内存释放和模块卸载资源顺序。

### 必须能够抓住的错误实现

- 写偏移仅递增但不影响容量或数据落点。
- 两个 FD 错误共享同一读偏移。
- 分段读取期间被另一写线程拼接成混合 JSON。
- 非法命令改变版本号、偏移或部分状态。
- PAGE_SIZE 边界发生截断却返回成功。
- JSON 转义后超过缓冲区造成无效 JSON。

### 验收门槛

- 驱动能在目标内核头文件下零警告构建。
- 单元/探针测试证明两个独立 `open()` 的读写进度互不影响。
- PAGE_SIZE 和失败原子性测试全部通过。
- `driver/README.md` 中的每条语义与代码一致。

### 建议提交

```text
driver: make PAGE_SIZE buffering and per-open offsets observable
```

## P2：模拟器线程安全与协议校验

### 工作项

- [x] 将网络接收与 Tk 更新通过 `queue.Queue` 隔离。
- [x] 将 JSON 解析和校验抽成不依赖 GUI 的纯函数/模块。
- [x] 使用完整状态对象替换，消除多字段竞态。
- [x] 为 socket 设置可退出机制并实现窗口关闭清理。
- [x] 限制日志条数，避免长时间演示造成内存无界增长。
- [x] 验证手动颜色、亮度覆盖和恢复 UDP 值的业务逻辑。
- [x] 区分“本地清屏”和“驱动 CLEAR”，避免界面文案误导。
- [x] 记录无效报文原因，但禁止部分更新 GUI。

### 自动测试

- [x] 合法 static/scroll 状态。
- [x] 缺字段、类型错误、范围错误、非法 mode。
- [x] 非法 UTF-8、非 JSON、非 state 报文。
- [x] 连续高频报文只在主线程更新 UI。
- [x] 手动覆盖期间 UDP 更新状态但不覆盖显示值；恢复后立即采用最新 UDP 值。
- [x] 关闭窗口后监听线程和 socket 能退出。

### 验收门槛

- 后台线程代码中不存在 Tkinter 控件调用。
- 协议解析测试不需要启动 GUI 即可运行。
- UDP 烟雾测试和人工 GUI 检查均通过。
- 连续运行测试无线程异常、界面冻结或无界日志增长。

### 建议提交

```text
simulator: marshal UDP events onto the Tk main thread
```

## P3：全功能自动验收与演示脚本

### 规范化工具名称

| 角色 | 规范名称 |
|---|---|
| 用户态命令工具 | `vled_cli` |
| UDP 桥接程序 | `vled_bridge` |
| 自动验收入口 | `vled_verify.sh` |
| 双 FD/偏移探针 | `vled_fd_probe` |
| 演示编排脚本 | `vled_demo.sh` |
| Windows UDP 烟雾发送器 | `test_udp.py` 或后续更明确名称 |

旧名称只能作为兼容说明，不再在 PLAN、README、报告和演示命令中混用。

### 验收矩阵

#### A. 模块和设备生命周期

- [x] `make` 成功并记录编译器、内核和模块元信息。
- [x] `insmod` 成功，`dmesg` 出现注册信息。
- [x] 自动分配 major/minor。
- [x] `/dev/vled` 自动出现，类型和权限正确。
- [x] `rmmod` 成功，设备节点消失且资源释放。
- [x] 重复加载/卸载循环无泄漏、崩溃或残留节点。

#### B. 文件操作与命令业务

- [x] `open/read/write/release` 可由用户态工具显式触发。
- [x] `TEXT`：空文本、ASCII、中文、引号、反斜杠。
- [x] `COLOR`：0、255、越界、缺参数、多参数、非数字。
- [x] `BRIGHTNESS`：0、100、越界和非数字。
- [x] `MODE`：static、scroll 和非法值。
- [x] `CLEAR`：清空文字但保留约定的其他状态。
- [x] `STATUS`：不改变状态版本。
- [x] 未知命令和暂不支持命令返回正确错误码。
- [x] 每次有效状态变化的 version 精确递增一次。

#### C. 缓冲区、偏移与并发

- [x] 零长度、PAGE_SIZE-1、PAGE_SIZE、超 PAGE_SIZE。
- [x] 两个独立 FD 从各自偏移 0 开始读取。
- [x] 分段读期间另一 FD 更新状态，旧 FD 仍得到完整旧快照。
- [x] 新 FD 得到最新状态。
- [x] 两个 FD 的写容量和写偏移互不影响。
- [x] 并发写不会产生字段混合或无效 JSON。
- [x] 并发读写压力后设备仍可用且模块可卸载。

#### D. 用户态工具与网络链路

- [x] CLI 参数、设备路径、退出码和错误信息。
- [x] bridge IP、端口、间隔和信号退出。
- [x] bridge 只发送通过校验的完整状态。
- [x] Windows 收到文字、颜色、亮度、模式和版本变化。
- [x] 设备不可用和无效状态有可诊断日志；UDP 无连接的远端确认边界已在证据中说明。

### 防止“表面验收”的要求

1. 测试必须检查退出码和设备实际状态，不能只匹配打印的 `PASS`。
2. 关键测试先对故意破坏的实现验证能够失败，再恢复正确实现。
3. 并发测试检查每行 JSON 可解析和字段约束，而不是只检查出现过 `type=state`。
4. 边界测试必须验证失败后状态、版本和偏移未改变。
5. 演示脚本不得吞掉命令错误；任一步失败应停止并给出恢复提示。

### 建议提交

```text
test: add executable compliance and business acceptance suite
tools: add reproducible VLED demonstration workflow
```

## P4：目标 Linux 实测与原始证据固化

### 前置条件

- 可访问目标 Ubuntu 主机或虚拟机。
- 安装与运行内核匹配的 headers、gcc、make。
- P1–P3 已在仓库中完成且静态检查通过。

### 证据目录规范

每次正式验证使用新的运行目录：

```text
docs/evidence/<YYYYMMDD-HHMM>-ubuntu-<kernel>/
├── 00-environment.txt
├── 01-build.log
├── 02-module-lifecycle.log
├── 03-command-functional.log
├── 04-boundary-and-errors.log
├── 05-multifd-offset.log
├── 06-concurrency-stress.log
├── 07-network-e2e.log
├── 08-kernel-log.txt
├── RESULTS.md
├── SHA256SUMS
└── screenshots/
```

### 原始证据规则

1. 使用 `script`、`tee` 或等价方式同时记录命令、stdout、stderr 和退出码。
2. `00-environment.txt` 至少包含：日期、发行版、`uname -a`、gcc、make、内核 headers、Git 提交哈希。
3. 原始 `.log` 不人工编辑；解释写入 `RESULTS.md`。
4. 截图必须包含终端命令和结果，不能只截一个孤立 PASS 字样。
5. 保存模块加载前后 `/dev/vled`、`lsmod`、`modinfo`、`dmesg` 的证据。
6. 生成 `SHA256SUMS`，使提交后的原始证据可复核。
7. 若某项失败，保留失败日志；修复后创建新运行目录，不覆盖旧证据。

### 验收门槛

- PDF 明示要求对应的验收 ID 全部有目标 Linux 原始证据。
- 所有测试退出码为 0，内核日志无 warning/oops/BUG。
- Windows 全链路演示有 Linux 端日志、UDP 证据和 Windows 截图。
- `RESULTS.md` 说明环境、结论、限制和失败后修复过程。

## P5：高价值扩展——poll + wait queue

### 设计目标

将 bridge 的周期轮询升级为状态变化驱动，体现 Linux 驱动的等待队列、阻塞 I/O、非阻塞 I/O 和 `poll()` 机制。

### 内核设计

- [ ] 在设备结构中增加 `wait_queue_head_t`。
- [ ] 每个文件上下文记录已消费版本和快照版本。
- [ ] 实现 `.poll`，状态变化时返回 `POLLIN | POLLRDNORM`。
- [ ] 成功改变状态后调用 `wake_up_interruptible()`。
- [ ] `STATUS` 或失败写入不得无意义唤醒。
- [ ] 阻塞 `read()` 在无新状态时等待；`O_NONBLOCK` 返回 `-EAGAIN`。
- [ ] 新版本出现时，同一长期打开 FD 能创建新快照并继续读取。
- [ ] 正确处理信号打断、模块卸载和虚假唤醒。

### bridge 设计

- [ ] 设备只打开一次。
- [ ] 使用 `poll()` 等待状态变化。
- [ ] 收到事件后读取完整 JSON 并发送 UDP。
- [ ] 可选超时只用于健康日志，不重复发送未变化状态。
- [ ] SIGINT/SIGTERM 能中断等待并干净退出。

### 扩展验收

- [ ] 初次打开能读取当前状态。
- [ ] 无状态变化时 `poll` 超时且不忙等。
- [ ] 每次有效写入触发一次可读事件。
- [ ] 非法写入和 STATUS 不触发状态事件。
- [ ] 高频写入不丢失“最终最新状态”，且不会生成无效 JSON。
- [ ] 比较轮询版和事件驱动版的空闲 CPU、发送次数和响应延迟。

### 建议提交

```text
driver: add wait-queue backed poll notification
tools: make the bridge event driven
```

## P6：README、PLAN、命令和演示资料统一

### 工作项

- [ ] 新增或完善仓库根 README，提供最短可运行路径。
- [ ] 更新 `DriverRequirements.md`，只记录 PDF 明示要求和验收映射。
- [ ] 将 `PLAN.md` 从旧草案更新为实际架构与真实文件名。
- [ ] 更新 `driver/README.md`：缓冲区、偏移、错误码、poll、加载卸载。
- [ ] 更新 `tools/README.md`：规范命令、自动测试、bridge、演示流程。
- [ ] 更新 `simulator/README.md`：删除旧分支说明，解释线程模型和协议校验。
- [ ] 所有文档统一使用 `vled_cli`、`vled_bridge`、`vled_verify.sh`、`vled_demo.sh`。
- [ ] 命令示例必须从空环境开始可复制执行。
- [ ] 文档注明哪些步骤需要 root、哪些只需要普通用户。
- [ ] 增加常见故障：headers 缺失、权限、UDP 防火墙、IP、端口占用。

### 验收门槛

- `rg` 搜索不到已废弃名称和错误分支说明。
- README 中所有命令在对应平台实际执行通过。
- 文档功能表与自动验收矩阵一一对应。
- 演示者只看根 README 能完成构建、加载、测试、联调和卸载。

## P7：约 50 页实验报告骨架与内容填充

### 文件策略

1. 保留学校原始 `.doc`，不得覆盖。
2. 经用户确认后复制/转换为可维护的 `.docx` 工作稿。
3. 使用 Word 真正的标题样式、自动目录、题注和交叉引用。
4. 骨架只建立章节、写作清单和占位标记，不通过空白页、超大字体或无分析截图凑页数。

### 建议页数预算

| 部分 | 目标页数 |
|---|---:|
| 封面、评分表、学校要求页 | 3 |
| 摘要、关键词、目录 | 2 |
| 第 1 章 项目背景、实验四要求、目标与分工 | 3 |
| 第 2 章 Linux 6.18 字符设备机制理解 | 5 |
| 第 3 章 需求分析、总体架构、协议与数据结构 | 6 |
| 第 4 章 驱动核心实现 | 8 |
| 第 5 章 用户态工具、UDP bridge 与模拟器 | 4 |
| 第 6 章 测试方法、结果、截图和问题分析 | 7 |
| 第 7 章 poll 扩展、优化、安全、局限性 | 3 |
| 第 8 章 团队协作与课程设计日志 | 2 |
| 第 9 章 总结与三人独立心得 | 3 |
| 参考文献 | 1 |
| 附录：协议、验收矩阵、关键日志 | 3 |
| 合计 | 约 50 |

### 各章必须回答的问题

#### 第 1 章

- PDF 实验四逐条要求是什么？
- 为什么选择虚拟 LED 字符设备？
- 三名成员的任务、接口和共同工作如何划分？

#### 第 2 章

- 源码阅读对象与实际运行内核版本分别是什么？
- 系统调用如何经 VFS 到达 `file_operations`？
- `inode`、`file`、`cdev`、`class`、`device`、`dev_t` 的关系是什么？
- 模块加载、设备注册、打开、读写和卸载流程是什么？

#### 第 3 章

- 功能、非功能、边界和错误要求是什么？
- 三端数据流、协议字段和错误码如何定义？
- 共享设备状态与每文件上下文如何分工？
- mutex、快照和独立偏移为什么这样设计？

#### 第 4 章

- 初始化/清理如何保证失败路径资源对称？
- PAGE_SIZE、用户复制、命令解析、JSON 转义如何实现？
- 多进程和稳定快照如何实现？
- 关键函数的输入、输出、不变量和错误码是什么？

#### 第 5 章

- CLI 如何触发驱动文件操作？
- bridge 如何验证和转发状态？
- 模拟器如何保证线程安全、协议安全和正确渲染？

#### 第 6 章

- 每项测试的目标、步骤、预期、实际结果和结论是什么？
- 如何证明测试不是只匹配表面输出？
- 失败过什么、如何定位、如何修复、如何防止回归？

#### 第 7 章

- 轮询为何需要优化？
- wait queue、poll、阻塞和非阻塞语义是什么？
- 优化前后的 CPU、发送次数和延迟如何变化？
- 权限、输入限制、资源上限和工程伦理如何考虑？

### 推荐图表资产

- PDF 要求—代码—测试—证据矩阵。
- 系统总体架构图和三端时序图。
- syscall→VFS→driver 调用流程图。
- cdev 注册/清理流程图。
- 核心结构体关系图。
- PAGE_SIZE 缓冲区和文件上下文示意图。
- 双 FD 独立偏移与稳定快照时间线。
- mutex 并发序列图。
- 模拟器线程/队列模型图。
- poll/wait queue 唤醒流程图。
- 正常、边界、异常、并发和全链路测试表。
- 轮询与事件驱动的对比图。

## P8：目录、题注、交叉引用、版式和逐页 QA

### 工作项

- [ ] 统一标题编号，不再混用“0.x”“一、”“四、”和手写序号。
- [ ] 自动生成目录、图目录和表目录。
- [ ] 所有图表使用题注，并在正文通过交叉引用引用。
- [ ] 所有代码清单注明文件、函数和用途。
- [ ] 统一中文字体、英文字体、字号、行距、页边距、页眉和页码。
- [ ] 表格跨页重复表头，不截断文本。
- [ ] 图片保持可读分辨率，不拉伸，不用整页终端截图代替分析。
- [ ] 修复 `/PATH-TO-REPO` 等占位符和旧命令。
- [ ] 检查三人心得均不少于 500 字且内容独立。
- [ ] 检查课程设计日志完整、真实且与 Git/测试时间线一致。
- [ ] 渲染为逐页 PNG/PDF，逐页检查裁切、重叠、空白、编号和引用。

### 验收门槛

- 实际渲染页数大于 40，目标约 48–52 页。
- 目录、图号、表号和交叉引用可更新且无断链。
- 每一页完成 100% 视觉检查。
- 报告中的命令、哈希、环境和测试结论可由证据目录复核。

## P9：最终回归、演示彩排与交付

### 工作项

- [ ] 从干净构建开始执行完整验证。
- [ ] 运行模块生命周期、命令、边界、多 FD、并发、poll 和端到端测试。
- [ ] 按演示脚本由非开发成员完成一次盲演。
- [ ] 模拟常见故障并确认恢复说明有效。
- [ ] 对照 PDF、验收矩阵、README 和报告逐条勾选。
- [ ] 检查仓库无二进制构建产物、临时文件、Word 锁文件和敏感信息。
- [ ] 固化最终 Git 提交、证据运行编号和报告版本。

### 最终交付门槛

- PDF 明示要求 100% 有实现、自动测试、原始证据和报告说明。
- 演示流程可在目标 Linux 和 Windows 上重复执行。
- 内核日志无 warning/oops/BUG。
- 报告大于 40 页，目标约 50 页，逐页 QA 通过。
- README、PLAN、源码、脚本和报告无命名或行为冲突。

## 7. 建议提交序列

后续提交建议保持如下粒度，不把全部工作压成一个提交：

1. `docs: define roadmap and acceptance contract`
2. `test: add failing offset and boundary probes`
3. `driver: fix PAGE_SIZE and per-open write semantics`
4. `test: cover driver business and concurrency behavior`
5. `simulator: marshal UDP events onto Tk main thread`
6. `test: validate simulator protocol and override behavior`
7. `tools: add verifier and reproducible demo workflow`
8. `driver: add wait-queue backed poll notification`
9. `tools: make bridge event driven`
10. `docs: align README and PLAN with verified behavior`
11. `report: establish the 50-page report structure`
12. `report: add verified implementation and test evidence`
13. `report: finalize captions references and layout`

每个提交前后都运行与其范围匹配的测试；禁止使用 `git add .`，避免把用户报告或证据临时文件意外带入。

## 8. 跨对话接管协议

任何新对话接管本任务时，按以下顺序工作：

1. 阅读本文档第 0、1、5 节。
2. 查看本文档“当前检查点”和阶段表。
3. 运行 `git status --short --branch`，确认分支与脏文件。
4. 只选择一个未完成阶段或一个可独立验收的子任务。
5. 开始前说明将修改哪些文件、运行哪些测试、生成哪些证据。
6. 完成后更新本文档：状态、测试、证据路径、提交哈希、阻塞点、下一动作。
7. 未在目标 Linux 执行的项目必须标注 `NOT_RUN_ON_TARGET_LINUX`。
8. 不得因为上下文压缩或换对话而重新定义已经冻结的语义；如需改变，写入决策记录。

## 9. 决策记录

| 日期 | 决策 | 理由 | 状态 |
|---|---|---|---|
| 2026-07-12 | 使用现有 `docs/` 作为长期文档目录，不新建重复的 `doc/` | 仓库已有 `docs/` 且报告位于其中 | 已确认 |
| 2026-07-12 | 当前只写实施路线，不开始代码修改 | 用户要求先给计划并在许可后执行 | 已确认 |
| 2026-07-12 | 旧远端 `a40be52` 只作参考，不直接恢复 | 该版本已被用户暂时舍弃且未验证 | 已确认 |
| 2026-07-12 | 用户批准开始 P0，但 P1/P2 仍需下一阶段许可 | 保持阶段门禁，防止规划与实现混在同一批 | 已确认 |
| 2026-07-12 | PAGE_SIZE 与独立写偏移采用第 4.1 节和验收矩阵口径 | 让写偏移真实影响数据落点/容量，并保持 VLED JSON 业务接口 | 已冻结 |
| 2026-07-12 | Windows 端按“实现+测试+说明”成组推送，Linux 只测试明确提交 | 保证测试结果可追溯到 Git 哈希 | 已冻结 |
| 2026-07-12 | 首次 Linux 测试批次前用 `--force-with-lease` 替换旧远端历史 | 远端仍有已舍弃的 a40be52；动作发生前仍需确认 | 已规划 |
| 2026-07-12 | 目标 Linux 固定为 Ubuntu 24.04.4、6.17.0-35-generic、x86_64、GCC 13.3 | 用户提供的 `get_env.sh` 原始输出；匹配 headers 已存在 | 已记录 |
| 2026-07-12 | Linux 缺少 tkinter 不作为阻塞项 | Tk 模拟器位于 Windows；Linux 测试不依赖 GUI | 已确认 |
| 2026-07-12 | Linux 仓库当前仍在 `integration@f1fb191` 且有未跟踪构建产物 | 首个测试批次前必须保护 get_env.sh、清理构建产物并切到目标分支 | 已记录 |
| 2026-07-12 | VMware 为 NAT；Linux `192.168.57.139`，Windows VMnet8 `192.168.57.1` | 用户回答及 VMware/Windows/Linux 截图 | 已确认 |
| 2026-07-12 | ICMP ping 失败不作为 UDP 失败结论 | Windows 可能仅阻止 ICMP；历史 UDP 9000 联调成功，正式测试以实际 UDP 为准 | 已确认 |
| 2026-07-12 | Linux 只保存原始日志，证据页在 Windows 统一制作 | 便于统一版式，同时保留原始输出可复核 | 已确认 |
| 2026-07-12 | Linux checkout 可由 Windows/GitHub 权威版本覆盖 | 用户确认 Linux 仅用于测试，无重要本地修改 | 已确认 |
| 2026-07-12 | 旧版 `vled` 模块当前仍加载 | 首个新版本测试前必须先卸载并验证旧节点消失 | 已记录 |
| 2026-07-12 | P0 环境与验收契约闭环 | 目标环境、Git 同步、网络、证据和风险均已记录 | 已完成 |
| 2026-07-12 | 用户批准 P1 和 P2；P0 三份 Markdown 先独立提交 | 保持阶段门禁和最小可审查提交顺序 | 已完成 |
| 2026-07-12 | P1 拆为探针 `401c9e3` 和驱动修复 `7556beb` | 测试、实现和运行说明成组存在；Windows 只完成探针语法检查 | `IMPLEMENTED_NOT_RUN` |
| 2026-07-12 | P2 拆为实现 `4d19398`、测试 `866023a`、说明 `47dadca` | 协议和线程模型可脱离 GUI 验证；12 项 Windows 自动测试通过 | `WINDOWS_AUTOMATED_PASS` |
| 2026-07-12 | P2 临时允许 `blink` 的受控 mutation 被负面测试捕获 | 证明协议测试能对错误实现失败；mutation 已恢复且未提交 | 已完成 |
| 2026-07-12 | P2 GUI 人工复核覆盖合法/非法 UDP、覆盖恢复、本地清屏、日志上限、高频更新和关闭清理 | 所有 T-SIM-01..09 符合冻结语义；跨机 UDP 仍留给 P3/P4 | `P2_WINDOWS_PASS` |
| 2026-07-12 | 首次 lease 保护推送将旧远端 `a40be52` 对齐到本地实施历史 | 用户在看到显式 lease 对象和准确命令后确认执行；之后只 fast-forward | 已完成 |
| 2026-07-12 | P1 首次目标构建暴露 Linux 6.17 API/宏兼容错误 | 保留失败日志，在 `3bd3b5f` 中改名 `current` 参数并移除已废弃 `no_llseek` | 已修复 |
| 2026-07-12 | `3bd3b5f` 功能通过但存在 1136 字节内核栈帧警告 | P1 门禁要求零警告；`d8c1c0d` 将候选状态移至堆分配 | 已修复 |
| 2026-07-12 | `d8c1c0d` 在目标 Linux 零警告构建且 P1 探针全通过 | build/tools/probe/rmmod 退出码均为 0，本次内核区间仅正常注册/注销 | `P1_TARGET_LINUX_PASS` |
| 2026-07-12 | P1 原始失败、中间警告和最终成功日志分层固化 | 证据目录 `docs/evidence/20260712-1427-ubuntu-6.17.0-35-generic-p1/`，源归档哈希可复核 | 已完成 |
| 2026-07-12 | 用户授权开始 P3；实现提交 `b0fb0b6` | 增加统一验收器、bridge 黑盒探针、演示编排和参数化 Windows UDP 发送器；14 项 Windows 测试通过 | `IMPLEMENTED_NOT_RUN_TARGET_LINUX` |
| 2026-07-12 | P3 临时移除 CLI 多余参数拒绝 | 正确实现对 `read NUL extra` 返回 1，mutation 返回 0；证明 CLI 负面验收可捕获错误实现，mutation 已删除 | 已完成 |
| 2026-07-12 | P3 首次目标运行在 T-CMD 停止 | bridge、模块加载和 P1 回归均通过；验收器错误地把零长度 write 当作空白命令 EINVAL，现改用三个空格验证真正空白命令，并固定匹配内核的编译器可执行名 | 修复后待重跑 |
| 2026-07-12 | `b11d5c7` 目标 Linux 自动验收与 Windows 跨机演示通过 | 自动验收和 demo 退出码均为 0，三轮装卸与内核日志正常，用户确认 GUI 显示正常；证据目录 `docs/evidence/20260712-1544-ubuntu-windows-p3/` | `P3_TARGET_PASS` |
| 2026-07-12 | `abad494` P4 正式分项取证通过 | 00–08 九项退出码均为 0，正式运行区间内核日志干净，两张 PNG 包含 Linux 命令/退出码和 Windows 状态/UDP 日志；证据目录 `docs/evidence/20260712-1653-ubuntu-6.17.0-35-generic-p4/` | `P4_TARGET_EVIDENCE_PASS` |
| 待确认 | 高价值扩展采用 `poll + wait queue` | 与实验四主题高度一致，且可量化优化效果 | 待基础验收通过 |

## 10. 当前检查点

### 已完成

- [x] 核对 PDF 中实验四明示要求。
- [x] 审计当前驱动、用户态工具、模拟器、README、PLAN 和现有报告。
- [x] 确认当前本地 `integration-promote-try` 与 `integration` 内容一致。
- [x] 建立本长期实施路线文档。
- [x] 用户批准启动 P0。
- [x] 建立 PDF/业务/边界/并发/网络/模拟器验收矩阵。
- [x] 冻结缓冲区、独立偏移、版本和错误码语义。
- [x] 建立目标 Linux 环境信息模板和采集清单。
- [x] 回填 Ubuntu 24.04.4、内核 6.17.0-35、headers、GCC/Make/ld、Git、Python、仓库和 Linux IP。
- [x] 记录 Linux 工作树未跟踪构建产物与 `get_env.sh`，禁止未确认 `git clean`。
- [x] 记录 NAT、Windows VMnet8 IP、ping 结果、Git fetch、远端 refs、权限、启动模式和旧模块状态。
- [x] 完成 P0 全部验收门槛。

### 本批已实现但尚未完成全部阶段门禁

- [x] P1 PAGE_SIZE 共享状态页、per-open 写入暂存页、独立读写偏移、稳定快照和原子回滚实现已本地提交。
- [x] P1 边界、多 FD、快照、版本、JSON 和回滚探针已本地提交，并通过 Windows GCC 严格语法检查。
- [x] P1 在目标 Ubuntu 6.17.0-35-generic 使用匹配 GCC 完成零警告构建，探针全部通过，模块干净卸载。
- [x] P1 初始失败、栈帧警告和最终成功原始日志均已固化并生成 SHA-256 清单。
- [x] P2 协议校验、不可变事件、有界队列、Tk 主线程消费、覆盖模型和关闭清理已本地提交。
- [x] P2 无 GUI 自动测试在 Windows Python 3.12.9 下 12/12 通过；受控 mutation 能触发失败，恢复后全套再次通过。
- [x] P2 人工 GUI 视觉/交互复核完成；合法/非法 UDP、覆盖恢复、本地清屏、日志上限、高频更新和关闭清理均通过；跨机 UDP 留到 P3/P4。
- [x] 用户已授权 P3；统一验收入口、业务/错误码/并发测试、bridge 黑盒探针和演示脚本已实现。
- [x] P3 在目标 Linux 自动验收和 Windows 跨机链路均通过；首次失败、修复后成功和 demo 原始日志已固化。
- [x] 用户授权 P4；00–08 分项日志、退出码、原始哈希、Linux 终端截图和 Windows GUI 截图已完整固化。
- [ ] P5 未获用户授权，不得开始 poll/wait queue 实现。

### 当前阻塞/门禁

```text
P1_TARGET_LINUX_PASS
P2_WINDOWS_PASS
P3_TARGET_PASS
P4_TARGET_EVIDENCE_PASS
P5_NOT_AUTHORIZED
```

### 下一动作

1. 提交并 fast-forward 推送 P4 正式证据与阶段状态回填。
2. 向用户汇报 P4 已关闭及证据路径。
3. 等待用户决定是否批准进入 P5；未批准前不得实施 poll/wait queue。
