# 目标 Linux / VMware 环境记录

> 状态：`P1_TARGET_LINUX_VERIFIED / P3_TARGET_VERIFIED / P4_TARGET_VERIFIED / P5_TARGET_VERIFIED / P6_TARGET_VERIFIED`（P6 结果见 `evidence/20260712-2147-ubuntu-6.17.0-35-generic-p6/`）
>
> 用途：冻结目标 Linux 的构建、加载、联网和截图条件。请不要填写密码、GitHub Token、SSH 私钥、公网 IP 或其他凭据。

## 1. 基础系统信息

| 项目 | 用户填写/命令输出 |
|---|---|
| Linux 发行版与版本 | Ubuntu 24.04.4 LTS（Noble Numbat） |
| `/etc/os-release` 的 PRETTY_NAME | `Ubuntu 24.04.4 LTS` |
| 运行内核 `uname -r` | `6.17.0-35-generic` |
| 完整 `uname -a` | `Linux siqi 6.17.0-35-generic #35~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Tue May 26 19:30:42 UTC 2 x86_64 x86_64 x86_64 GNU/Linux` |
| 架构 `uname -m` | `x86_64` |
| 时区 `timedatectl` 摘要 | Asia/Shanghai（CST, +0800）；NTP service active，但采集时 `System clock synchronized: no` |
| VMware 虚拟机版本/产品 | `systemd-detect-virt` 返回 `vmware`；VMware 网络适配器已确认 NAT，具体产品版本不影响 P0 |

仓库旧 README 曾记录 Ubuntu 24.04.4、内核 6.17.0-35-generic；必须以本次实际输出为准。

## 2. 内核构建条件

| 项目 | 用户填写/命令输出 |
|---|---|
| `/lib/modules/$(uname -r)/build` 是否存在 | 是；链接到 `/usr/src/linux-headers-6.17.0-35-generic`，Makefile 存在 |
| 匹配内核 headers 包 | 已安装 `6.17.0-35-generic` 对应 headers |
| `gcc --version` 第一行 | `gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` |
| `make --version` 第一行 | `GNU Make 4.3` |
| `ld --version` 第一行 | `GNU ld (GNU Binutils for Ubuntu) 2.42` |
| `modinfo --version` 或 kmod 版本 | `/usr/sbin/modinfo` 存在；具体版本为非阻塞未知项 |
| Secure Boot 状态 | BIOS/legacy 启动，无 UEFI Secure Boot；kernel lockdown 接口不可用 |
| 当前用户是否可以 sudo | 需要密码，不是 passwordless sudo |
| 是否允许 `insmod/rmmod` 自编译模块 | 旧版 `vled` 当前已成功加载，说明模块加载流程历史可用；新版本装卸需正式重测 |

## 3. GitHub 同步条件

| 项目 | 用户填写/命令输出 |
|---|---|
| `git --version` | `git version 2.43.0` |
| Linux 端仓库绝对路径 | `/home/siqi/siqi_ws/V-LED`（由提示符 `~/siqi_ws/V-LED` 推定，待 `pwd` 确认） |
| remote URL 类型（HTTPS/SSH，仅写类型） | HTTPS：公开仓库 `https://github.com/qiaosiqi/V-LED.git` |
| 能否 `git fetch origin` | 是；2026-07-12 已成功 fetch |
| 当前分支 | `integration-promote-try`，跟踪 `origin/integration-promote-try` |
| P1 受测提交 `git rev-parse HEAD` | `d8c1c0dcd451c78a3df4d96730267fad16d89e4c` |
| 是否存在 Linux 端未提交改动 | 是；均为 P1 未跟踪构建产物、`get_env.sh`、`get_env_2.sh` 和已编译用户态工具；无待提交源码修改 |

同步规则：

1. Windows 端只将“待运行实现 + 对应测试 + 运行说明”成组提交到 `integration-promote-try`。
2. Linux 端只测试已推送的明确提交哈希。
3. Linux 端测试前记录 `git status` 和 `git rev-parse HEAD`。
4. 测试结果按运行编号提交回仓库，或先由用户传回 Windows 端整理。
5. 首次历史对齐已经完成；后续只允许普通 fast-forward 推送，禁止 force push。
6. 用户已明确 Linux checkout 仅用于测试，Windows 的 `integration-promote-try` 是权威工作副本；首次测试前可以用 Windows/GitHub 版本覆盖 Linux checkout。
7. 实际执行远端强制更新前仍展示命令和 lease 对象，避免覆盖动作期间出现的新远端提交。

### 3.1 远端引用与当前基线

| 引用 | 提交 |
|---|---|
| `origin/integration` | `a192f2c0c86f3a3254c4ca2df779b2beb735ba0d` |
| `origin/integration-promote-try`（P1 受测时） | `d8c1c0dcd451c78a3df4d96730267fad16d89e4c` |

Linux 已切换到 `integration-promote-try`，P1 在明确提交 `d8c1c0d` 上执行。

以上表格保留 P1 运行时的历史引用。P6 启动时，Windows `HEAD`、本地
`integration-promote-try` 与 `origin/integration-promote-try` 均为 `6c51e5d`；
该提交包含 P5 正式证据，后续只从此基线普通 fast-forward 前进。

### 3.2 当前 Linux 工作树未跟踪内容

用户在 2026-07-12 提供的 `git status` 显示：

```text
driver/..module-common.o.cmd
driver/.Module.symvers.cmd
driver/.module-common.o
driver/.modules.order.cmd
driver/.vled.ko.cmd
driver/.vled.mod.cmd
driver/.vled.mod.o.cmd
driver/.vled.o.cmd
driver/Module.symvers
driver/modules.order
driver/vled.ko
driver/vled.mod
driver/vled.mod.c
driver/vled.mod.o
driver/vled.o
get_env.sh
tools/vled_bridge
tools/vled_cli
```

P1 最终环境记录还显示新增 `get_env_2.sh` 和 `tools/vled_fd_probe`，其余内容为
重新构建产生的同类内核产物。它们均为未跟踪测试文件；受测源码与
`origin/integration-promote-try` 一致。

处理规则：

1. 在切换到目标分支前，不执行 `git clean`，避免误删用户的 `get_env.sh`。
2. 驱动和工具构建产物可在用户确认后分别用 `make -C driver clean`、`make -C tools clean` 清理。
3. `get_env.sh` 应先由用户决定保留在虚拟机、移出仓库，还是后续审查后纳入工具目录。
4. 用户确认 Linux 端没有需要保留的重要修改，并允许首次测试时用 Windows/GitHub 版本覆盖该测试 checkout。
5. 第一次 Linux 测试前必须先卸载当前旧模块，再重新记录清理/覆盖后的 `git status`。

## 4. Python 与模拟器联调条件

| 项目 | 用户填写/命令输出 |
|---|---|
| `python3 --version` | `Python 3.12.3` |
| Python tkinter 是否可 import | 否：`ModuleNotFoundError: No module named 'tkinter'` |
| Linux 用户态工具编译后能否运行 | `tools/vled_cli`、`tools/vled_bridge` 构建产物存在；是否运行通过未确认 |
| Windows 模拟器运行的 Python 版本 | Windows 审计终端为 Python 3.12.9；实际 PyCharm/演示解释器待确认 |
| Windows Tk 版本（可选） | `UNKNOWN_NONBLOCKING`，P2 GUI 验收前记录 |

Linux 缺少 tkinter 不阻塞当前架构：Tk 模拟器运行在 Windows；Linux 只运行驱动、CLI、bridge 和无 GUI 验证脚本。

## 5. VMware 网络与 UDP 9000

| 项目 | 用户填写/命令输出 |
|---|---|
| VMware 网络模式（NAT/桥接/Host-only） | NAT（VMware 设置截图确认） |
| Linux 虚拟机 IPv4（仅内网地址） | `ens33: 192.168.57.139/24` |
| Windows 主机可供虚拟机访问的 IPv4（仅内网地址） | VMnet8：`192.168.57.1/24`（Windows 截图确认） |
| Linux 默认路由摘要 | `default via 192.168.57.2 dev ens33 proto dhcp src 192.168.57.139 metric 100` |
| Linux 能否 ping Windows 主机 | 否；对 `192.168.57.1` 两次测试均 100% packet loss |
| Windows 防火墙是否放行 Python/UDP 9000 | 历史 main 联调中 Windows 模拟器成功收包；当前版本正式测试时重新验证 |
| UDP 9000 是否被其他程序占用 | `TBD/未试` |
| 可用抓包工具（tcpdump/Wireshark） | `UNKNOWN_NONBLOCKING`，正式网络验收时按需检查 |

ICMP ping 失败不作为 UDP 链路失败结论。Windows 常见配置会阻止 ICMP Echo，但允许已授权应用接收 UDP。P3/P4 必须用实际 UDP 报文、模拟器日志和必要时的抓包结果验收 `192.168.57.1:9000`。

## 6. 桌面与截图条件

| 项目 | 用户填写/命令输出 |
|---|---|
| Linux 是否有桌面环境 | 是（用户提供 Ubuntu 终端截图） |
| 终端程序 | Ubuntu 图形终端，具体程序名为非阻塞未知项 |
| 可用截图工具 | 可截取 VMware/Ubuntu 终端画面；具体工具名不要求固定 |
| 能否在 VMware 中复制/导出 PNG | 是；用户已提供 Linux 终端截图 |
| 证据制作策略 | Linux 保存原始日志，传回 Windows 后统一制作报告证据页 |
| 终端字号和分辨率是否适合报告截图 | 当前截图可读；正式证据页再统一裁切和排版 |

## 7. 建议一次性采集命令

可在 Linux 终端执行以下只读命令，并把输出粘贴回对话。命令不读取凭据，不修改系统：

```bash
printf '%s\n' '=== OS ==='
cat /etc/os-release
uname -a
uname -r
uname -m

printf '%s\n' '=== TOOLCHAIN ==='
gcc --version | head -n 1
make --version | head -n 1
ld --version | head -n 1
git --version
python3 --version

printf '%s\n' '=== KERNEL BUILD DIRECTORY ==='
ls -ld "/lib/modules/$(uname -r)/build"
test -f "/lib/modules/$(uname -r)/build/Makefile" && echo 'kernel build Makefile: PRESENT' || echo 'kernel build Makefile: MISSING'

printf '%s\n' '=== MODULE / SECURE BOOT ==='
command -v insmod
command -v modinfo
if command -v mokutil >/dev/null 2>&1; then mokutil --sb-state; else echo 'mokutil: NOT INSTALLED'; fi

printf '%s\n' '=== PYTHON TK ==='
python3 -c 'import tkinter; print("tkinter import: OK; TkVersion=", tkinter.TkVersion)'

printf '%s\n' '=== VIRTUALIZATION / NETWORK ==='
systemd-detect-virt || true
ip -br -4 addr
ip route show default

printf '%s\n' '=== REPOSITORY ==='
git status --short --branch
git remote -v
git rev-parse HEAD
```

粘贴前请删除 remote URL 中可能存在的用户名、Token 或其他凭据；正常的公开 GitHub 仓库 URL 可以保留。

## 8. 手工补充问题结论

| 问题 | 用户结论 |
|---|---|
| VMware 网络模式 | NAT |
| Windows VMnet8 IPv4 | `192.168.57.1/24` |
| Linux ping Windows | 失败，100% packet loss；不作为 UDP 失败结论 |
| Windows UDP 9000 | 以前 main 联调曾成功收包；当前版本正式重测 |
| 证据页制作 | Linux 保存日志，传回 Windows 统一制作 |
| Linux 端重要未提交修改 | 无；Linux checkout 只用于测试，可由 Windows/GitHub 版本覆盖 |
| 远端/测试副本策略 | Windows `integration-promote-try` 为权威；首次推送使用 lease 保护，Linux 随后覆盖到明确提交 |

### 8.1 已执行的补充采集命令

```bash
printf '%s\n' '=== PATH / TIME ==='
pwd
timedatectl | sed -n '1,6p'

printf '%s\n' '=== PRIVILEGE / LOCKDOWN ==='
if sudo -n true 2>/dev/null; then echo 'passwordless sudo: YES'; else echo 'passwordless sudo: NO or password required'; fi
if [ -d /sys/firmware/efi ]; then echo 'boot mode: UEFI'; else echo 'boot mode: BIOS/legacy'; fi
if [ -r /sys/module/lockdown/parameters/lockdown ]; then cat /sys/module/lockdown/parameters/lockdown; else echo 'kernel lockdown: unavailable'; fi

printf '%s\n' '=== REMOTE REFS ==='
git fetch origin
git rev-parse origin/integration
git rev-parse origin/integration-promote-try

printf '%s\n' '=== CURRENT MODULE STATE ==='
lsmod | grep '^vled' || echo 'vled module: NOT LOADED'
```

这些命令不会加载/卸载模块，也不会清理或覆盖 Linux 工作树。`git fetch` 只更新远端引用，不修改当前分支和工作文件。

## 9. 信息确认记录

| 日期 | 信息来源 | 结论 | 记录人 |
|---|---|---|---|
| 2026-07-12 | 用户粘贴 `get_env.sh` 输出 | 核心 OS、内核、headers、工具链、Git、Python 和 Linux IP 已记录；仍待补充网络模式、权限、安全启动和截图策略 | Codex |
| 2026-07-12 | 用户粘贴 `get_env_2.sh` 输出和 3 张截图 | NAT、Windows VMnet8 IP、ping 失败、时区、BIOS/lockdown、Git refs、旧模块加载状态和证据策略已记录；P0 环境信息闭环 | Codex |
| 2026-07-12 | P1 两个原始日志归档及 Linux 终端输出 | `d8c1c0d` 零警告构建、tools 严格构建、P1 探针全通过、模块注册/注销干净；失败和中间警告证据保留 | Codex |

## 10. 首个 Linux 测试批次的环境前置动作

以下动作中的 P1 部分已于 2026-07-12 完成；P3/P4 正式运行前按同一原则复核：

1. 记录当前 `lsmod` 和 `/dev/vled`，使用需要密码的 sudo 卸载旧版 `vled` 模块。
2. 确认旧模块卸载后 `/dev/vled` 消失。
3. 保留需要的环境脚本/日志后，清理旧构建产物；不得无检查执行 `git clean`。
4. Windows 端完成待测提交，并在动作前再次确认一次 `--force-with-lease`。
5. Linux fetch 后切换/覆盖为 `origin/integration-promote-try` 的明确提交哈希。
6. 重新记录干净工作树、提交哈希、时间同步状态和工具链。
7. 若正式证据要求跨机时间线，先解决 `System clock synchronized: no` 或在结果中明确记录时钟偏差。
