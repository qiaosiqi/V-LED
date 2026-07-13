# P4 正式目标环境证据结果

## 结论

状态：`PASS / P4_TARGET_EVIDENCE_PASS`

VLED 在 Ubuntu 24.04.4、Linux 6.17.0-35-generic、x86_64、GCC 13.3.0、
Python 3.12.3 和 Windows VLED GUI 环境完成 P4 正式分项取证。受测提交为
`abad494dfad2044ad0c34e0c907ad9be4c549bc9`，00–08 九个阶段退出码全部为 0，
内核日志仅包含正常注册/注销，Linux→Windows UDP 演示和两张正式截图完整。

该结论关闭 P4。P5 尚未获用户授权，本轮没有实现或修改 poll/wait queue。

## 分项结果

| 文件 | 验收范围 | 结论 |
|---|---|---|
| `00-environment.txt` | OS、内核、工具链、headers、Git、网络 | 提交与环境明确，退出码 0 |
| `01-build.log` | 匹配 GCC 的内核模块构建、工具 `-Werror` 构建 | 成功；无真实 warning/error 诊断 |
| `02-module-lifecycle.log` | 三轮装卸、设备类型/权限、lsmod/modinfo、最终清理 | 全部通过，最终模块和节点消失 |
| `03-command-functional.log` | CLI 参数及全部命令/错误路径/version | `PASS T-CLI`、`PASS T-CMD` |
| `04-boundary-and-errors.log` | PAGE_SIZE、错误回滚、JSON、non-seekable | 探针全部通过 |
| `05-multifd-offset.log` | 多 FD、稳定快照、独立偏移、dup | 独立新实例上探针全部通过 |
| `06-concurrency-stress.log` | 4 writer + 4 reader、500 次/线程、JSON 解析 | `PASS T-CON` |
| `07-network-e2e.log` | Linux bridge→`192.168.57.1:9000`、状态序列、信号退出 | 退出码 0，`UDP bridge stopped` |
| `08-kernel-log.txt` | 完整正式运行区间 | 仅 vled 正常注册/注销 |
| `EXIT_CODES.txt` | 00–08 独立退出码 | 九项均为 0 |

`SHA256SUMS-LINUX` 是 Linux 导出前对日志的原始清单；`SHA256SUMS` 是 Windows
合并两张 PNG 和结果说明后的最终证据清单。

## 截图证据

- `screenshots/01-linux-terminal.png`：包含最终完整 JSON、`UDP bridge stopped`
  和 `07-network exit code: 0`。
- `screenshots/02-windows-gui.png`：包含来源 `192.168.57.139`、版本 1512、青色
  `#00FFFF`、亮度 80%、static 模式和 47 条 UDP 日志。

截图中的最终 version 为 1512 而非 8：本轮先执行 500 次并发压力，随后 demo 在
既有版本 1504 基础上产生 8 次实际状态变化。最终版本连续递增，符合冻结语义。
CLEAR 作为最后一步将文字清空，所以 Windows 截图中“无内容”是预期结果，不是
模拟器关闭或丢包。

## 真实性与限制

- Linux 源归档 SHA-256 在解包前与用户提供值核对，记录于
  `SOURCE_ARCHIVE.sha256`；`SHA256SUMS-LINUX` 全部复算匹配。
- 两张 PNG 来自用户本轮原始截图，未经过 Word 压缩；最终清单记录其字节哈希。
- 日志搜索中的字符串 `-Werror=...` 是 Kbuild 编译参数，不是 `error:` 诊断；
  使用行边界更严格的最终搜索没有 warning/error/FAIL/oops/BUG/lockdep 命中。
- 网络为 VMware NAT：Linux `192.168.57.139`，Windows VMnet8
  `192.168.57.1`。ICMP 历史失败不影响本轮实际 UDP GUI 收包证据。
- Linux 测试副本保留 `get_env*.sh` 和构建产物作为未跟踪文件，没有把它们纳入
  源码或证据提交。
