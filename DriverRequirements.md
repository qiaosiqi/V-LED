# Linux 驱动程序明示要求与验收映射

本文件只保留课程实验明示要求及其验收位置；扩展设计和操作步骤分别见
`docs/IMPLEMENTATION_ROADMAP.md`、`docs/ACCEPTANCE_MATRIX.md` 和根 `README.md`。

## 目标
1. 理解Linux内核模块机制
2. 理解Linux设备驱动注册原理
3. 理解Linux内核态与用户态数据交互方式
4. 掌握无重启内核的内核功能拓展技术
5. 开发一个**虚拟字符设备驱动程序**

## 开发虚拟字符设备驱动程序的具体要求
1. 实现设备的open、read、write、close内核回调函数
2. 包括设备号管理、字符设备注册、自动创建设备文件等模块
3. 用户态可向虚拟设备写入数据，内核态接收数据并处理，可读取内核返回的设备状态信息
4. 驱动内置一页大小内核缓冲区，用户read读缓冲区、write写入缓冲区
5. 支持多进程打开同一设备，独立读写偏移
6. 支持自动分配设备号、自动创建设备文件
7. 支持模块动态加载、卸载、设备节点注册测试

## 验收映射

| 明示要求 | 实现 | 自动验收 |
|---|---|---|
| `open/read/write/close` 回调 | `driver/vled.c` | T-LIFE、T-CLI、T-CMD |
| 设备号、cdev、class、设备节点 | `driver/vled.c` | T-LIFE-01..08 |
| 用户态写入与状态读取 | `/dev/vled` 文本命令/JSON | T-CLI、T-CMD |
| PAGE_SIZE 内核缓冲区 | 共享状态页与 per-open 写入页 | T-BUF、T-FD |
| 多进程独立读写偏移 | `vled_file_context` | T-FD、T-READ、T-CON |
| 动态加载和卸载 | `driver/Makefile`、模块清理路径 | T-LIFE、内核日志检查 |

`poll + wait queue`、阻塞/非阻塞 read、UDP bridge 和 Windows 模拟器是已完成的
工程扩展，不替代上述明示要求。完整 Given/When/Then、错误码和正式证据索引以
`docs/ACCEPTANCE_MATRIX.md` 为准。
