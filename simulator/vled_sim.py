import socket
import json
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time

# ====================== 全局配置======================
UDP_PORT = 9000
DEFAULT_W = 32
DEFAULT_H = 16
LED_SIZE = 16       # 单个LED像素方块大小
SCROLL_SPEED = 0.15 # 滚动文字速度
# 当前屏幕状态
screen_state = {
    "width": DEFAULT_W,
    "height": DEFAULT_H,
    "text": "",
    "color": [255,255,255],
    "brightness": 100,
    "mode": "static",
    "version": 0
}
last_raw_msg = ""
scroll_offset = 0
udp_socket = None

# ====================== GUI主窗口 ======================
root = tk.Tk()
root.title("VLED Windows 模拟器 | 端口9000")
root.resizable(False, False)

# 顶部信息栏
info_frame = ttk.Frame(root, padding=5)
info_frame.pack(fill="x")
lbl_conn = ttk.Label(info_frame, text="连接状态：未接收数据")
lbl_ver = ttk.Label(info_frame, text=f"状态版本：{screen_state['version']}")
lbl_conn.pack(side="left")
lbl_ver.pack(side="right")

# LED画布区域
canvas_frame = ttk.Frame(root, padding=5)
canvas_frame.pack()
canvas = tk.Canvas(canvas_frame, bg="#000000", width=DEFAULT_W*LED_SIZE, height=DEFAULT_H*LED_SIZE)
canvas.pack()

# 调试日志区
log_frame = ttk.Frame(root, padding=5)
log_frame.pack(fill="x")
ttk.Label(log_frame, text="接收JSON日志：").pack(anchor="w")
log_text = scrolledtext.ScrolledText(log_frame, width=60, height=6)
log_text.pack()

# 底部控制按钮
btn_frame = ttk.Frame(root, padding=5)
btn_frame.pack()

def clear_screen():
    """手动清屏按钮"""
    global screen_state, scroll_offset
    screen_state["text"] = ""
    scroll_offset = 0
    redraw_led()

ttk.Button(btn_frame, text="手动清屏", command=clear_screen).pack()

# ====================== LED渲染核心函数 ======================
def calc_bright_color(r, g, b, br):
    """根据亮度0-100衰减RGB颜色"""
    ratio = br / 100.0
    nr = int(r * ratio)
    ng = int(g * ratio)
    nb = int(b * ratio)
    return f"#{nr:02x}{ng:02x}{nb:02x}"

def redraw_led():
    """重绘整个LED屏幕"""
    canvas.delete("all")
    w = screen_state["width"]
    h = screen_state["height"]
    r, g, b = screen_state["color"]
    br = screen_state["brightness"]
    text = screen_state["text"]
    mode = screen_state["mode"]
    color = calc_bright_color(r, g, b, br)

    # 绘制网格背景（黑色LED点阵底座）
    for y in range(h):
        for x in range(w):
            x1 = x * LED_SIZE
            y1 = y * LED_SIZE
            x2 = x1 + LED_SIZE - 1
            y2 = y1 + LED_SIZE - 1
            canvas.create_rectangle(x1, y1, x2, y2, fill="#111111", outline="#222222")

    # 文字偏移处理（滚动模式）
    global scroll_offset
    if mode == "scroll":
        scroll_offset += 0.08
        if scroll_offset > len(text) * 12:
            scroll_offset = -w * LED_SIZE
    else:
        scroll_offset = 0

    # 绘制文字到LED屏中央
    canvas.create_text(
        w*LED_SIZE//2 - scroll_offset,
        h*LED_SIZE//2,
        text=text,
        fill=color,
        font=("Consolas", 14, "bold")
    )

    # 更新界面版本号
    lbl_ver.config(text=f"状态版本：{screen_state['version']}")

# 定时刷新画布
def refresh_loop():
    redraw_led()
    root.after(30, refresh_loop)

# ====================== UDP数据接收线程 ======================
def udp_listen_task():
    global udp_socket, screen_state, last_raw_msg
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(("0.0.0.0", UDP_PORT))
    print(f"UDP监听启动 0.0.0.0:{UDP_PORT}")
    lbl_conn.config(text="连接状态：监听中，等待Linux数据...")

    while True:
        try:
            data, addr = udp_socket.recvfrom(2048)
            msg = data.decode("utf-8").strip()
            last_raw_msg = msg
            # 写入日志
            log_text.insert(tk.END, f"[{addr}] {msg}\n")
            log_text.see(tk.END)
            lbl_conn.config(text=f"连接状态：收到来自 {addr} 的数据")

            # 解析JSON
            data_json = json.loads(msg)
            if data_json.get("type") != "state":
                continue
            # 更新全局屏幕状态
            screen_state["width"] = data_json["width"]
            screen_state["height"] = data_json["height"]
            screen_state["text"] = data_json["text"]
            screen_state["color"] = data_json["color"]
            screen_state["brightness"] = data_json["brightness"]
            screen_state["mode"] = data_json["mode"]
            screen_state["version"] = data_json["version"]

        except Exception as e:
            print("UDP接收异常：", e)

# ====================== 程序入口 ======================
if __name__ == "__main__":
    # 启动UDP后台线程（守护线程，窗口关闭自动退出）
    udp_thread = threading.Thread(target=udp_listen_task, daemon=True)
    udp_thread.start()
    # 启动画布定时刷新
    refresh_loop()
    # 主GUI循环
    root.mainloop()
    # 关闭socket
    if udp_socket:
        udp_socket.close()
