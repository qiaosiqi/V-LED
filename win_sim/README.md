# VLED Windows 模拟器（C端模块）
## 项目说明
本程序为VLED实验Windows可视化客户端，通过UDP 9000端口接收Linux虚拟机驱动上报的JSON状态，渲染虚拟LED点阵屏幕。
完全匹配项目约定通信协议，支持静态/滚动文字、RGB调色、亮度调节、实时状态日志调试。

## 运行环境
Python 3.8 及以上版本
仅使用Python标准库，无需额外pip安装第三方包：
- socket：UDP网络通信
- json：解析状态报文
- tkinter：GUI界面、LED画布渲染
- threading：后台异步监听网络，界面不卡顿

## 文件清单
1. `vled_sim.py`：主模拟器程序
   - UDP 0.0.0.0:9000持续监听
   - 解析标准state格式JSON
   - 渲染32×16 LED点阵，文字、颜色、亮度、滚动模式展示
   - 内置日志面板、连接状态、版本号显示、手动清屏按钮
2. `test_udp.py`：本地自测脚本
   - 本机自发自收测试JSON报文
   - 无需Linux虚拟机，快速验证界面渲染逻辑

## 启动步骤
### 方式1：PyCharm（推荐）
1. 使用PyCharm打开项目，切换至`windows-sim`分支
2. 右键 `vled_sim.py` → Run，弹出模拟器窗口即启动成功
3. 本地自测：右键 `test_udp.py` → Run，自动发送测试数据，屏幕出现滚动彩色文字

### 方式2：CMD命令行
```cmd
# 启动模拟器
python vled_sim.py

# 新开终端执行本地自测
python test_udp.py
