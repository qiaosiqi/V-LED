# V-LED 实验四可执行验收矩阵

> 状态：`SPEC_FROZEN / P1_TARGET_LINUX_PASS / P2_WINDOWS_PASS / P3_TARGET_PASS / P4_NOT_AUTHORIZED`
>
> 本文档冻结“应该实现什么、怎样证明实现真实有效”。它不是测试结果。
> 只有目标 Linux 原始日志存在时，项目状态才可从 `NOT_RUN_ON_TARGET_LINUX` 改为 `PASS` 或 `FAIL`。

## 1. 状态与证据约定

| 状态 | 含义 |
|---|---|
| `SPEC_FROZEN` | 行为和验收方法已经冻结 |
| `NOT_IMPLEMENTED` | 当前实现尚未满足冻结语义或尚未补齐测试 |
| `IMPLEMENTED_NOT_RUN` | 已实现，但未在目标 Linux 执行 |
| `PASS` | 在记录的目标环境中通过，且有原始证据 |
| `FAIL` | 已执行但不满足预期，保留失败证据 |
| `BLOCKED` | 因环境或外部条件无法执行，必须写明原因 |

每个 PASS 至少需要：Git 提交、执行命令、退出码、原始日志路径和环境记录。

P3 实现提交为 `b0fb0b6`，目标修复提交为 `b11d5c7`：统一入口 `tools/vled_verify.sh` 会实际检查构建、设备、
错误码、状态、版本、JSON、并发、bridge UDP、信号退出、重复装卸和内核日志；
`tools/vled_demo.sh` 负责跨机演示。Windows 侧 14 项 Python 测试和脚本语法检查
已通过；目标 Linux 自动验收和 Linux→Windows 跨机演示也已通过。原始证据见
`docs/evidence/20260712-1544-ubuntu-windows-p3/`。

## 2. 冻结的驱动行为契约

### 2.1 缓冲区所有权

1. `struct vled_device` 持有一个 PAGE_SIZE 共享状态缓冲区。
2. 共享缓冲区始终包含最新完整 JSON 状态，不保存半条命令或半个 JSON。
3. 共享缓冲区和 `vled_state` 在同一 mutex 临界区内更新。
4. 模块初始化完成后，共享缓冲区已经包含版本 0 的默认 JSON。
5. 每个 `open()` 分配独立文件上下文：读偏移、写偏移、读取快照和 PAGE_SIZE 写入暂存区。

### 2.2 写入语义

1. 一次 `write()` 系统调用表示一条完整文本命令。
2. `count == 0` 返回 0，不改变偏移、状态、版本或快照。
3. 单次 `count >= PAGE_SIZE` 返回 `-EMSGSIZE`。
4. 每个 FD 的写入暂存区保留一个 NUL 字节；若 `write_offset + count >= PAGE_SIZE`，返回 `-ENOSPC`。
5. 写入数据必须先落到该 FD 的写入暂存区中，再解析本次新写入的命令片段。
6. 成功写入后该 FD 的 `write_offset += count`；另一个独立 `open()` 的写偏移不受影响。
7. 解析、范围或支持性检查失败时，清理本次暂存片段，并回滚写偏移、共享状态、版本和读快照。
8. 成功命令重建共享 JSON 缓冲区，并使当前 FD 下次读取重新捕获快照；不得重置其他 FD 的快照。
9. `STATUS` 是成功的非修改命令：消耗当前 FD 写偏移、刷新当前 FD 读快照，但不增加版本。

### 2.3 读取语义

1. 首次读取时，在 mutex 内从共享 PAGE_SIZE 缓冲区捕获一份稳定快照。
2. 分段读取只推进该 FD 的 `read_offset`。
3. 读取到 EOF 后，同一 FD 在 P1 基础语义下继续返回 0，直到该 FD 成功写入并刷新自己的读快照。
4. 其他 FD 更新状态时，已经开始读取的旧 FD 继续返回旧快照，不能拼接新旧 JSON。
5. 新打开的 FD 读取最新 JSON。
6. `count == 0` 返回 0，不捕获或推进快照。
7. 设备为 non-seekable；不承诺用户通过 `lseek()` 修改偏移。
8. P5 引入 poll 后，长期打开 FD 可在新版本到达时获取新快照；该扩展不得破坏 P1 的稳定快照保证。

### 2.4 状态版本语义

1. `version` 表示可观察设备状态修订号。
2. 只有字段值实际变化时才递增一次。
3. 写入与当前值相同的 TEXT/COLOR/BRIGHTNESS/MODE 返回成功，但版本不变。
4. 已经为空时再次 CLEAR 返回成功，但版本不变。
5. STATUS、非法命令、超长写入、复制失败和内存失败均不改变版本。
6. P5 中只有版本实际变化才唤醒 wait queue。

### 2.5 错误码

| 场景 | 冻结错误码/返回值 |
|---|---|
| 零长度 read/write | `0` |
| 单次写入达到或超过 PAGE_SIZE | `-EMSGSIZE` |
| 当前 FD 累计写入空间不足 | `-ENOSPC` |
| TEXT 内容超过 `VLED_TEXT_MAX-1` | `-EMSGSIZE` |
| 语法、参数数量、类型或范围错误 | `-EINVAL` |
| 已识别但未支持的 `PIXEL` | `-EOPNOTSUPP` |
| 用户内存复制失败 | `-EFAULT` 或内核复制 helper 的原始错误 |
| 文件上下文缺失 | `-EIO` |
| 分配失败 | `-ENOMEM` |
| P5 非阻塞且无新状态 | `-EAGAIN` |
| P5 阻塞等待被信号打断 | `-ERESTARTSYS` 或内核 wait helper 的标准返回 |

## 3. PDF 明示要求映射

| ID | 明示要求 | 实现位置 | 自动验收 | 目标证据 | 当前状态 |
|---|---|---|---|---|---|
| PDF4-01 | Linux 模块动态扩展，无需重启 | `vled_init/vled_exit` | `T-LIFE-01..04` | build、insmod、rmmod、dmesg | `NOT_RUN_ON_TARGET_LINUX` |
| PDF4-02 | 实现 open/read/write/close 回调 | `vled_fops`，close 对应 release | `T-FOPS-01..05` | probe/strace/驱动日志 | `NOT_RUN_ON_TARGET_LINUX` |
| PDF4-03 | 设备号管理 | `alloc_chrdev_region` | `T-LIFE-02` | `/proc/devices`、`stat` | `NOT_RUN_ON_TARGET_LINUX` |
| PDF4-04 | 字符设备注册 | `cdev_init/cdev_add` | `T-LIFE-01` | 模块加载日志 | `NOT_RUN_ON_TARGET_LINUX` |
| PDF4-05 | 自动创建设备文件 | `class_create/device_create` | `T-LIFE-02..03` | `/dev/vled` 出现/消失 | `NOT_RUN_ON_TARGET_LINUX` |
| PDF4-06 | 用户写入，内核接收并处理 | `vled_write`/命令解析 | `T-CMD-*` | 功能日志、状态 JSON | `NOT_RUN_ON_TARGET_LINUX` |
| PDF4-07 | 用户读取内核返回状态 | `vled_read`/JSON | `T-READ-*` | JSON 解析结果 | `NOT_RUN_ON_TARGET_LINUX` |
| PDF4-08 | 内置一页大小内核缓冲区 | PAGE_SIZE 共享状态缓冲区 | `T-BUF-*` | 边界日志、源码/构建 | `PASS` |
| PDF4-09 | 多进程同开、独立读写偏移 | per-open context | `T-FD-*` | 双 FD 探针、并发日志 | `PASS` |
| PDF4-10 | 动态装卸和节点注册测试 | 生命周期脚本 | `T-LIFE-*` | 完整生命周期日志 | `NOT_RUN_ON_TARGET_LINUX` |

## 4. 驱动生命周期验收

| ID | Given | When | Then | 防伪检查 |
|---|---|---|---|---|
| T-LIFE-01 | 匹配运行内核的 headers 已安装 | `make -C driver`，随后 `insmod` | 生成并加载 vled.ko，退出码为 0 | `modinfo` 与 `lsmod` 同时确认，不只匹配 make 输出 |
| T-LIFE-02 | 模块未加载 | 加载模块并读取 `/sys/class/vled`、`/proc/devices`、`stat /dev/vled` | major/minor 一致，设备是字符设备 | 比对 sysfs、stat 两个独立来源 |
| T-LIFE-03 | `/dev/vled` 已存在 | `rmmod vled` | 模块和设备节点均消失 | `lsmod` 与路径存在性同时检查 |
| T-LIFE-04 | 干净环境 | 连续加载/卸载至少 20 次 | 无失败、残留节点、warning/oops/BUG | 保存循环前后 dmesg 差异 |

## 5. 文件操作和缓冲区验收

| ID | 操作 | 预期 | 必须验证的负面条件 |
|---|---|---|---|
| T-FOPS-01 | O_RDONLY 打开、读取、关闭 | open/read/release 全部成功 | 设备不存在或权限不足必须失败 |
| T-FOPS-02 | O_WRONLY 打开、写入、关闭 | open/write/release 全部成功 | 非法命令 write 必须返回失败 |
| T-FOPS-03 | O_RDWR 同一 FD 写 STATUS 后读 | 读取最新完整 JSON | STATUS 不增加版本 |
| T-FOPS-04 | 对设备调用 lseek | 返回 ESPIPE/不可定位 | 不得悄悄接受并破坏私有偏移 |
| T-FOPS-05 | 零长度 read/write | 返回 0 | 状态、版本、读写偏移不变 |
| T-BUF-01 | 新加载模块 | 直接读 | 返回可解析的默认版本 0 JSON，而非空内容 |
| T-BUF-02 | 新 FD 单次写入 PAGE_SIZE-1 字节：`STATUS` 后补空格至最大合法长度 | 返回完整 count，version 不变，write_offset 达到 PAGE_SIZE-1 | 证明最大合法页边界真实可用，不得截断 |
| T-BUF-03 | 单次写入 PAGE_SIZE 字节 | 返回 EMSGSIZE | 状态、版本、偏移不变 |
| T-BUF-04 | 单次写入 PAGE_SIZE+1 字节 | 返回 EMSGSIZE | 状态、版本、偏移不变 |
| T-BUF-05 | 同一 FD 累计写入将占满暂存页 | 最后一条返回 ENOSPC | 失败命令不得部分进入暂存区 |
| T-BUF-06 | FD A 已接近写满，FD B 新打开 | FD B 仍有完整 PAGE_SIZE 写容量 | 证明写偏移不是全局共享 |
| T-BUF-07 | 最大合法 text 经过最坏 JSON 转义 | 输出仍是完整可解析 JSON | 不允许闭合引号/花括号缺失 |

### 5.1 多 FD 独立偏移

| ID | Given/When | Then | 说明 |
|---|---|---|---|
| T-FD-01 | FD A、FD B 分别 `open()`，A 先读取一段，再让 B 读取 | B 从自己的 read_offset 0 开始 | 分别 open 才是两个独立文件上下文 |
| T-FD-02 | FD A 用 T-BUF-02 填满自己的写入页，再新开 FD B 写普通命令 | A 后续写 ENOSPC，B 写成功 | 证明 write_offset 和暂存页不是全局共享 |
| T-FD-03 | FD A 读取旧状态前缀，FD B 修改状态，A 继续读取 | A 得到完整旧快照；新 FD 得到新状态 | 同时证明独立读偏移和快照一致性 |
| T-FD-04 | 对同一个已打开 FD 执行 `dup()` 后交替读取 | 两个描述符共享同一文件上下文和偏移 | 明确 POSIX dup 语义，避免把“共享”误报为缺陷 |
| T-FD-05 | 多进程分别 open，任意一个进程 close | 其他进程上下文和设备状态保持有效 | 证明 release 只释放当前 file context |

## 6. 命令业务逻辑验收

### 6.1 TEXT

| ID | 输入 | 预期 |
|---|---|---|
| T-CMD-TEXT-01 | `TEXT Hello VLED` | text 更新，version +1 |
| T-CMD-TEXT-02 | 重复写相同 TEXT | 成功，version 不变 |
| T-CMD-TEXT-03 | `TEXT ` | text 变为空；仅实际变化时 version +1 |
| T-CMD-TEXT-04 | 中文、空格、引号、反斜杠、tab | JSON 可解析且解码后文本一致 |
| T-CMD-TEXT-05 | 达到文本上限 | 最大合法长度成功，超一字节返回 EMSGSIZE |

### 6.2 COLOR

| ID | 输入 | 预期 |
|---|---|---|
| T-CMD-COLOR-01 | `COLOR 0 0 0`、`COLOR 255 255 255` | 边界成功 |
| T-CMD-COLOR-02 | 合法普通值 | 三个通道准确更新，实际变化时 version +1 |
| T-CMD-COLOR-03 | -1、256、非数字 | EINVAL，状态/版本/偏移回滚 |
| T-CMD-COLOR-04 | 缺参数或多参数 | EINVAL，状态/版本/偏移回滚 |
| T-CMD-COLOR-05 | 重复相同值 | 成功，version 不变 |

### 6.3 BRIGHTNESS

| ID | 输入 | 预期 |
|---|---|---|
| T-CMD-BRIGHT-01 | 0、100 | 边界成功 |
| T-CMD-BRIGHT-02 | 1..99 | 准确更新，实际变化时 version +1 |
| T-CMD-BRIGHT-03 | -1、101、非数字、多参数 | EINVAL 且原子回滚 |
| T-CMD-BRIGHT-04 | 重复相同值 | 成功，version 不变 |

### 6.4 MODE、CLEAR、STATUS 和未知命令

| ID | 输入 | 预期 |
|---|---|---|
| T-CMD-MODE-01 | `MODE static`、`MODE scroll` | 合法；实际变化时 version +1 |
| T-CMD-MODE-02 | `MODE blink`、缺参、多参 | EINVAL 且原子回滚 |
| T-CMD-CLEAR-01 | 非空状态下 `CLEAR` | 只清空 text，其他字段保持，version +1 |
| T-CMD-CLEAR-02 | 空状态下 `CLEAR` | 成功，version 不变 |
| T-CMD-STATUS-01 | `STATUS` | 成功并允许当前 FD 重新读状态，version 不变 |
| T-CMD-UNSUP-01 | `PIXEL ...` | EOPNOTSUPP，全部回滚 |
| T-CMD-UNKNOWN-01 | 空白、UNKNOWN、大小写错误 | EINVAL，全部回滚 |

## 7. JSON 和快照验收

| ID | Given/When | Then |
|---|---|---|
| T-JSON-01 | 默认状态读取 | 必须包含固定字段、正确类型和值域 |
| T-JSON-02 | 文本含 `"`、`\`、tab 和控制字符 | JSON 可解析，反解文本符合约定 |
| T-JSON-03 | text 含 UTF-8 中文 | UTF-8 JSON 可解析且文本不乱码 |
| T-JSON-04 | 所有合法命令后读取 | 输出长度小于 PAGE_SIZE，恰好一个 JSON 对象 |
| T-READ-01 | FD A 分 1、7、32 字节读取 | 拼接结果与一次完整读取相同 |
| T-READ-02 | FD A 读前缀，FD B 更新状态，FD A 读剩余 | FD A 得到完整旧版本，不能混合新旧字段 |
| T-READ-03 | T-READ-02 后打开 FD C | FD C 得到最新版本 |
| T-READ-04 | 两个 FD 独立读取首块 | 两者都从各自偏移 0 获得相同前缀 |
| T-READ-05 | FD 读到 EOF 后再次读 | P1 返回 0，不自动重放快照 |

## 8. 并发和稳健性验收

| ID | 负载 | 通过条件 |
|---|---|---|
| T-CON-01 | 多线程并发 TEXT/COLOR/BRIGHTNESS | 每次读到的都是满足协议约束的完整状态 |
| T-CON-02 | 至少 4 writer + 4 reader，持续规定时长/次数 | 无死锁、崩溃、无效 JSON 或系统调用异常 |
| T-CON-03 | 并发期间反复 open/close | 无 use-after-free、双重释放或引用泄漏迹象 |
| T-CON-04 | 压力后执行正常命令和卸载 | 设备仍可用并能干净卸载 |
| T-CON-05 | 压力测试前后比较 dmesg | 无新增 warning/oops/BUG/lockdep 报告 |

并发测试必须用 JSON 解析器验证每一条采样状态；只检查字符串中出现 `"type":"state"` 不算通过。

## 9. 用户态工具和网络验收

| ID | 功能 | 通过条件 |
|---|---|---|
| T-CLI-01 | `vled_cli read/write/loop` 参数 | 合法参数成功，缺参和非法参数非零退出 |
| T-CLI-02 | 自定义设备路径 | 对指定路径操作，错误路径有明确错误 |
| T-CLI-03 | short read/write 和 errno | 不把短操作误报为完整成功 |
| T-BRIDGE-01 | IP、端口、设备、间隔参数 | 严格校验，非法输入非零退出，不静默回退 |
| T-BRIDGE-02 | 从设备读 JSON 并 UDP 发送 | 接收端解析内容与设备状态一致 |
| T-BRIDGE-03 | SIGINT/SIGTERM | 关闭 FD/socket 并在限定时间内退出 |
| T-BRIDGE-04 | 设备暂时不可用/Windows 未监听 | 可诊断，不生成伪成功日志 |
| T-NET-01 | Linux→Windows UDP 9000 | 文字、颜色、亮度、mode、version 全链路一致 |

## 10. Windows 模拟器验收

| ID | Given/When | Then |
|---|---|---|
| T-SIM-01 | 合法 state 报文 | 一次性更新完整状态 |
| T-SIM-02 | 缺字段、错误类型、越界、非法 mode | 拒绝且不部分更新旧状态 |
| T-SIM-03 | 非 JSON、非法 UTF-8、非 state 类型 | GUI 继续运行，日志给出明确原因 |
| T-SIM-04 | 高频 UDP 报文 | 网络线程不调用 Tk，GUI 无跨线程异常或冻结 |
| T-SIM-05 | 手动颜色/亮度覆盖期间收到新 UDP | 保存最新 UDP 值但显示保持手动值 |
| T-SIM-06 | 取消手动覆盖 | 立即显示最近一次 UDP 值 |
| T-SIM-07 | 清屏按钮 | 明确为本地预览清屏，不谎称已写入驱动 |
| T-SIM-08 | 日志长时间运行 | 日志数量有上限，内存不无界增长 |
| T-SIM-09 | 关闭窗口 | 停止事件生效，socket/线程可及时结束 |

### 10.1 P2 Windows 检查记录（2026-07-12）

- 实现提交：`4d19398`；无 GUI 测试提交：`866023a`；说明提交：`47dadca`。
- `python -m unittest discover -s simulator/tests -v` 在 Windows Python 3.12.9 下运行 12 项，全部通过。
- 测试包含真实 `127.0.0.1` 临时 UDP 端口收发、无效 JSON 拒绝、socket 关闭和非 daemon 接收线程及时退出。
- 临时把 `blink` 加入允许模式后，非法 mode 负面测试以退出码 1 失败；恢复正确实现后 12 项再次全部通过。mutation 未提交。
- GUI 人工复核完成：合法 static/scroll 完整更新；非 JSON 和越界亮度被拒绝且无部分更新；手动颜色/亮度覆盖保留最新 UDP 值并可立即恢复。
- 本地预览清屏未伪装为驱动 CLEAR；240 个无效报文后日志严格限制为 200 条；300 个高频状态后界面无冻结并收敛到最终版本。
- 关闭窗口后模拟器进程退出且 UDP 9000 不再监听。T-SIM-01..09 全部通过，证据见 `docs/evidence/20260712-1452-windows-p2/`。
- 上述结果关闭 P2 Windows 门禁，但不替代 P3/P4 的 Linux→Windows 跨机 UDP 和目标 Linux 证据。

## 11. P5 poll + wait queue 扩展验收

| ID | Given/When | Then |
|---|---|---|
| T-POLL-01 | 新 FD 初次 poll | 当前状态可读 |
| T-POLL-02 | 已消费当前版本且无变化 | poll 超时，不忙等、不重复发包 |
| T-POLL-03 | 有效且实际改变状态的写入 | poll 返回 POLLIN/POLLRDNORM |
| T-POLL-04 | STATUS、重复值、非法写入 | 不产生状态变化事件 |
| T-POLL-05 | O_NONBLOCK 且无新版本 | read 返回 EAGAIN |
| T-POLL-06 | 阻塞 read 被信号打断 | 标准中断错误，资源状态正常 |
| T-POLL-07 | 高频多写者 | bridge 最终收到最新状态，所有读取 JSON 有效 |
| T-POLL-08 | 对比旧轮询 | 记录空闲 CPU、发送次数和响应延迟数据 |

## 12. 测试真实性检查

正式验收前必须至少做一次受控 mutation test：

1. 临时破坏一个边界判断，确认对应 T-BUF 测试失败。
2. 临时让两个 FD 共享 offset，确认 T-READ/T-FD 测试失败。
3. 临时让非法命令增加 version，确认原子回滚测试失败。
4. 临时从 UDP 线程直接调用一个 Tk 控件，确认静态检查或线程测试失败。
5. mutation 只存在于临时本地提交或工作树，不得推入正式分支；恢复后重新运行测试。

## 13. 证据回填表

| 运行编号 | Git 提交 | Linux 环境 | 测试范围 | 结果 | 原始证据目录 |
|---|---|---|---|---|---|
| 20260712-1452-windows-p2 | `83caefb` | Windows NT 10.0.26220.0 / Python 3.12.9 | P2 12 项无 GUI 自动测试、人工 GUI T-SIM-01..09、关闭清理 | `PASS / P2_WINDOWS_PASS` | `docs/evidence/20260712-1452-windows-p2/` |
| 20260712-1427-p1 | `d8c1c0d` | Ubuntu 24.04.4 / 6.17.0-35-generic / GCC 13.3 | P1 PAGE_SIZE、版本、回滚、多 FD、快照、JSON、装卸 | `PASS` | `docs/evidence/20260712-1427-ubuntu-6.17.0-35-generic-p1/` |
| 20260712-1544-p3 | `b11d5c7` | Ubuntu 24.04.4 / 6.17.0-35 / GCC 13.3 / Python 3.12.3；Windows GUI | P3 构建、业务、边界、并发、生命周期、bridge 与跨机 UDP | `PASS / P3_TARGET_PASS` | `docs/evidence/20260712-1544-ubuntu-windows-p3/` |
