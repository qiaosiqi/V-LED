import socket
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, colorchooser
import threading
import time
import math

# ====================== 全局配置 ======================
UDP_PORT = 9000
DEFAULT_W = 32
DEFAULT_H = 16
LED_SIZE = 18
SCROLL_SPEED = 0.15

# 当前屏幕状态
screen_state = {
    "width": DEFAULT_W,
    "height": DEFAULT_H,
    "text": "",
    "color": [255, 255, 255],
    "brightness": 100,
    "mode": "static",
    "version": 0
}

# 手动颜色覆盖（如果开启，会覆盖UDP传来的颜色）
manual_color_override = False
manual_color = [255, 255, 255]  # 默认白色

# 手动亮度覆盖
manual_brightness_override = False
manual_brightness = 100  # 默认100%

last_raw_msg = ""
scroll_offset = 0
udp_socket = None

# ====================== 配色方案 ======================
COLORS = {
    'bg_dark': '#0a0a0f',
    'bg_panel': '#14141e',
    'bg_input': '#1a1a2e',
    'bg_canvas': '#050508',
    'border': '#2a2a3e',
    'text_primary': '#e8e8f0',
    'text_secondary': '#8888aa',
    'text_accent': '#4fc3f7',
    'green': '#4ade80',
    'red': '#f87171',
    'yellow': '#fbbf24',
    'purple': '#a78bfa',
    'orange': '#fb923c',
}

# ====================== GUI主窗口 ======================
root = tk.Tk()
root.title("虚拟LED模拟器")
root.resizable(False, False)
root.configure(bg=COLORS['bg_dark'])

# ====================== 自定义样式 ======================
style = ttk.Style(root)
style.theme_use("clam")

style.configure("Dark.TFrame", background=COLORS['bg_dark'])
style.configure("Panel.TFrame", background=COLORS['bg_panel'], relief="flat")
style.configure("Card.TFrame", background=COLORS['bg_panel'], relief="flat", borderwidth=1)

style.configure("Title.TLabel",
                background=COLORS['bg_dark'],
                foreground=COLORS['text_accent'],
                font=("Microsoft YaHei UI", 12, "bold")
                )
style.configure("Header.TLabel",
                background=COLORS['bg_panel'],
                foreground=COLORS['text_primary'],
                font=("Microsoft YaHei UI", 9, "bold")
                )
style.configure("Normal.TLabel",
                background=COLORS['bg_panel'],
                foreground=COLORS['text_secondary'],
                font=("Microsoft YaHei UI", 8)
                )
style.configure("Status.TLabel",
                background=COLORS['bg_panel'],
                foreground=COLORS['green'],
                font=("Microsoft YaHei UI", 8, "bold")
                )
style.configure("Version.TLabel",
                background=COLORS['bg_panel'],
                foreground=COLORS['purple'],
                font=("Consolas", 8, "bold")
                )

# 滑块样式
style.configure("Dark.Horizontal.TScale",
                background=COLORS['bg_panel'],
                troughcolor=COLORS['bg_input'],
                slidercolor=COLORS['text_accent'],
                sliderrelief="flat"
                )

style.configure("Accent.TButton",
                background=COLORS['text_accent'],
                foreground=COLORS['bg_dark'],
                font=("Microsoft YaHei UI", 8, "bold"),
                padding=(10, 4)
                )
style.map("Accent.TButton",
          background=[('active', '#81d4fa'), ('pressed', '#0288d1')]
          )

style.configure("Danger.TButton",
                background=COLORS['red'],
                foreground='white',
                font=("Microsoft YaHei UI", 8, "bold"),
                padding=(10, 4)
                )
style.map("Danger.TButton",
          background=[('active', '#fca5a5'), ('pressed', '#dc2626')]
          )

style.configure("Success.TButton",
                background=COLORS['green'],
                foreground='white',
                font=("Microsoft YaHei UI", 8, "bold"),
                padding=(10, 4)
                )
style.map("Success.TButton",
          background=[('active', '#86efac'), ('pressed', '#16a34a')]
          )

# ====================== 顶部标题栏 ======================
title_frame = ttk.Frame(root, style="Dark.TFrame", padding=(8, 4))
title_frame.pack(fill="x", padx=8, pady=(4, 2))

title_content = ttk.Frame(title_frame, style="Dark.TFrame")
title_content.pack()

ttk.Label(title_content, text="虚拟LED点阵模拟器", style="Title.TLabel").pack(side="left")
ttk.Label(title_content, text="v2.2", foreground=COLORS['text_secondary'],
          background=COLORS['bg_dark'], font=("Microsoft YaHei UI", 8)).pack(side="left", padx=(8, 0))

# ====================== 状态信息栏=====================
status_frame = ttk.Frame(root, style="Panel.TFrame", padding=6)
status_frame.pack(fill="x", padx=8, pady=2)

status_left = ttk.Frame(status_frame, style="Panel.TFrame")
status_left.pack(side="left")

status_dot = tk.Canvas(status_left, width=8, height=8, bg=COLORS['bg_panel'], highlightthickness=0)
status_dot.pack(side="left", padx=(0, 6))
status_dot.create_oval(1, 1, 7, 7, fill=COLORS['text_secondary'], outline="")

lbl_conn = ttk.Label(status_left, text="[等待数据]", style="Normal.TLabel")
lbl_conn.pack(side="left")

status_right = ttk.Frame(status_frame, style="Panel.TFrame")
status_right.pack(side="right")

ttk.Label(status_right, text="版本", style="Normal.TLabel").pack(side="left", padx=(0, 4))
lbl_ver = ttk.Label(status_right, text=f"#{screen_state['version']:04d}", style="Version.TLabel")
lbl_ver.pack(side="left")

ttk.Label(status_right, text="|", style="Normal.TLabel").pack(side="left", padx=6)
ttk.Label(status_right, text=f"{DEFAULT_W}x{DEFAULT_H}",
          style="Normal.TLabel").pack(side="left")

# ====================== LED画布======================
canvas_wrap = ttk.Frame(root, style="Panel.TFrame", padding=8)
canvas_wrap.pack(padx=8, pady=3)

canvas_container = tk.Frame(canvas_wrap, bg=COLORS['bg_canvas'],
                            highlightthickness=1, highlightbackground=COLORS['border'],
                            highlightcolor=COLORS['text_accent'])
canvas_container.pack()

canvas = tk.Canvas(
    canvas_container,
    bg=COLORS['bg_canvas'],
    width=DEFAULT_W * LED_SIZE,
    height=DEFAULT_H * LED_SIZE,
    highlightthickness=0
)
canvas.pack()

# ====================== 信息面板======================
info_panel = ttk.Frame(root, style="Panel.TFrame", padding=6)
info_panel.pack(fill="x", padx=8, pady=2)

# 当前文字
text_frame = ttk.Frame(info_panel, style="Panel.TFrame")
text_frame.pack(side="left", padx=(0, 12))
ttk.Label(text_frame, text="文字:", style="Normal.TLabel").pack(side="left", padx=(0, 6))
lbl_text_preview = ttk.Label(text_frame, text="(无内容)",
                             style="Header.TLabel", foreground=COLORS['text_accent'])
lbl_text_preview.pack(side="left")

# 颜色（整合快捷颜色）
color_frame = ttk.Frame(info_panel, style="Panel.TFrame")
color_frame.pack(side="left", padx=(0, 12))

ttk.Label(color_frame, text="颜色:", style="Normal.TLabel").pack(side="left", padx=(0, 6))

color_preview = tk.Canvas(color_frame, width=18, height=18, bg='#ffffff',
                          highlightthickness=1, highlightbackground=COLORS['border'],
                          cursor="hand2")
color_preview.pack(side="left", padx=(0, 4))

lbl_color_hex = ttk.Label(color_frame, text="#FFFFFF", style="Normal.TLabel")
lbl_color_hex.pack(side="left", padx=(0, 4))


def choose_color():
    global manual_color, manual_color_override

    current_rgb = manual_color if manual_color_override else screen_state["color"]
    current_hex = f"#{current_rgb[0]:02x}{current_rgb[1]:02x}{current_rgb[2]:02x}"

    color = colorchooser.askcolor(
        initialcolor=current_hex,
        title="选择LED显示颜色"
    )

    if color and color[0]:
        rgb = [int(c) for c in color[0]]
        manual_color = rgb
        manual_color_override = True

        hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        color_preview.config(bg=hex_color)
        lbl_color_hex.config(text=hex_color.upper())

        if screen_state["text"] == "":
            screen_state["color"] = rgb
            redraw_led()

        timestamp = time.strftime("%H:%M:%S")
        log_text.insert(tk.END, f"[{timestamp}] 手动设置颜色: {hex_color.upper()}\n", "info")
        log_text.see(tk.END)
        update_log_count()


color_preview.bind("<Button-1>", lambda e: choose_color())

# 颜色按钮组（选择 + UDP恢复）
color_btn_frame = ttk.Frame(color_frame, style="Panel.TFrame")
color_btn_frame.pack(side="left", padx=(4, 0))


def reset_to_udp_color():
    global manual_color_override
    manual_color_override = False

    rgb = screen_state["color"]
    hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    color_preview.config(bg=hex_color)
    lbl_color_hex.config(text=hex_color.upper())

    redraw_led()

    timestamp = time.strftime("%H:%M:%S")
    log_text.insert(tk.END, f"[{timestamp}] 恢复UDP颜色: {hex_color.upper()}\n", "info")
    log_text.see(tk.END)
    update_log_count()


ttk.Button(color_btn_frame, text="选择", style="Accent.TButton",
           command=choose_color, width=5).pack(side="left", padx=(0, 3))
ttk.Button(color_btn_frame, text="UDP", style="Success.TButton",
           command=reset_to_udp_color, width=5).pack(side="left")

# 快捷颜色（精简为一行小色块，放在颜色按钮后面）
preset_color_frame = ttk.Frame(color_frame, style="Panel.TFrame")
preset_color_frame.pack(side="left", padx=(6, 0))


def apply_preset_color(rgb):
    global manual_color, manual_color_override
    manual_color = rgb
    manual_color_override = True

    hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    color_preview.config(bg=hex_color)
    lbl_color_hex.config(text=hex_color.upper())

    if screen_state["text"] == "":
        screen_state["color"] = rgb
        redraw_led()

    timestamp = time.strftime("%H:%M:%S")
    log_text.insert(tk.END, f"[{timestamp}] 快捷颜色: {hex_color.upper()}\n", "info")
    log_text.see(tk.END)
    update_log_count()


# 精简的预设颜色（只保留常用6色）
quick_colors = [
    ([255, 255, 255], "#FFFFFF"),
    ([255, 0, 0], "#FF0000"),
    ([0, 255, 0], "#00FF00"),
    ([0, 0, 255], "#0000FF"),
    ([255, 255, 0], "#FFFF00"),
    ([0, 255, 255], "#00FFFF"),
]

for rgb, hex_color in quick_colors:
    btn = tk.Button(
        preset_color_frame,
        bg=hex_color,
        width=2,
        height=1,
        relief="flat",
        borderwidth=1,
        highlightthickness=1,
        highlightbackground=COLORS['border'],
        cursor="hand2",
        command=lambda r=rgb: apply_preset_color(r)
    )
    btn.pack(side="left", padx=1)

# ====================== 亮度控制======================
brightness_frame = ttk.Frame(root, style="Panel.TFrame", padding=(8, 4))
brightness_frame.pack(fill="x", padx=8, pady=2)

brightness_left = ttk.Frame(brightness_frame, style="Panel.TFrame")
brightness_left.pack(side="left", fill="x", expand=True)

ttk.Label(brightness_left, text="亮度:", style="Normal.TLabel").pack(side="left", padx=(0, 8))

brightness_var = tk.IntVar(value=100)
brightness_slider = ttk.Scale(
    brightness_left,
    from_=0,
    to=100,
    orient="horizontal",
    variable=brightness_var,
    style="Dark.Horizontal.TScale",
    length=150
)
brightness_slider.pack(side="left", padx=(0, 8))

lbl_brightness_value = ttk.Label(brightness_left, text="100%", style="Status.TLabel")
lbl_brightness_value.pack(side="left", padx=(0, 8))

brightness_right = ttk.Frame(brightness_frame, style="Panel.TFrame")
brightness_right.pack(side="right")


def on_brightness_change(value):
    global manual_brightness, manual_brightness_override
    brightness = int(float(value))
    manual_brightness = brightness
    manual_brightness_override = True

    lbl_brightness_value.config(text=f"{brightness}%")

    if screen_state["text"] != "":
        redraw_led()

    if not hasattr(on_brightness_change, 'last_log'):
        on_brightness_change.last_log = brightness
    if abs(brightness - on_brightness_change.last_log) >= 5:
        timestamp = time.strftime("%H:%M:%S")
        log_text.insert(tk.END, f"[{timestamp}] 手动设置亮度: {brightness}%\n", "info")
        log_text.see(tk.END)
        update_log_count()
        on_brightness_change.last_log = brightness


brightness_slider.configure(command=on_brightness_change)


def reset_to_udp_brightness():
    global manual_brightness_override
    manual_brightness_override = False

    udp_brightness = screen_state["brightness"]
    brightness_var.set(udp_brightness)
    lbl_brightness_value.config(text=f"{udp_brightness}%")

    redraw_led()

    timestamp = time.strftime("%H:%M:%S")
    log_text.insert(tk.END, f"[{timestamp}] 恢复UDP亮度: {udp_brightness}%\n", "info")
    log_text.see(tk.END)
    update_log_count()


ttk.Button(brightness_right, text="UDP", style="Success.TButton",
           command=reset_to_udp_brightness, width=5).pack(side="left")

quick_brightness_frame = ttk.Frame(brightness_right, style="Panel.TFrame")
quick_brightness_frame.pack(side="left", padx=(6, 0))


def set_quick_brightness(value):
    brightness_var.set(value)
    on_brightness_change(value)


for val in [0, 25, 50, 75, 100]:
    btn = tk.Button(
        quick_brightness_frame,
        text=f"{val}",
        bg=COLORS['bg_input'],
        fg=COLORS['text_secondary'],
        font=("Microsoft YaHei UI", 7),
        relief="flat",
        padx=3,
        pady=0,
        cursor="hand2",
        command=lambda v=val: set_quick_brightness(v)
    )
    btn.pack(side="left", padx=1)

# ====================== 日志面板======================
log_wrap = ttk.Frame(root, style="Panel.TFrame", padding=6)
log_wrap.pack(fill="x", padx=8, pady=2)

log_header = ttk.Frame(log_wrap, style="Panel.TFrame")
log_header.pack(fill="x", pady=(0, 3))
ttk.Label(log_header, text="UDP日志", style="Header.TLabel").pack(side="left")

lbl_log_count = ttk.Label(log_header, text="0条", style="Normal.TLabel")
lbl_log_count.pack(side="right")

log_text = scrolledtext.ScrolledText(
    log_wrap,
    width=65,
    height=4,
    bg=COLORS['bg_input'],
    fg='#b8d4e8',
    insertbackground=COLORS['text_primary'],
    font=("Consolas", 8),
    relief="flat",
    highlightthickness=1,
    highlightbackground=COLORS['border'],
    highlightcolor=COLORS['text_accent']
)
log_text.pack(fill="x", pady=(0, 2))

log_text.tag_config("info", foreground=COLORS['text_accent'])
log_text.tag_config("success", foreground=COLORS['green'])
log_text.tag_config("error", foreground=COLORS['red'])

# ====================== 底部按钮栏======================
btn_frame = ttk.Frame(root, style="Dark.TFrame", padding=(8, 6))
btn_frame.pack(fill="x", padx=8, pady=(2, 6))

btn_left = ttk.Frame(btn_frame, style="Dark.TFrame")
btn_left.pack(side="left")


def clear_screen():
    global screen_state, scroll_offset
    screen_state["text"] = ""
    scroll_offset = 0
    redraw_led()
    log_text.insert(tk.END, "[系统] 屏幕已清空\n", "info")
    log_text.see(tk.END)


ttk.Button(btn_left, text="清屏", style="Danger.TButton",
           command=clear_screen).pack(side="left", padx=(0, 6))


def clear_log():
    log_text.delete(1.0, tk.END)
    update_log_count()


ttk.Button(btn_left, text="清日志", style="Accent.TButton",
           command=clear_log).pack(side="left")

btn_right = ttk.Frame(btn_frame, style="Dark.TFrame")
btn_right.pack(side="right")

ttk.Label(btn_right, text="UDP端口: 9000",
          foreground=COLORS['text_secondary'],
          background=COLORS['bg_dark'],
          font=("Consolas", 7)).pack(side="left", padx=(0, 6))

lbl_uptime = ttk.Label(btn_right, text="运行中", style="Normal.TLabel")
lbl_uptime.pack(side="left")
start_time = time.time()


def update_uptime():
    elapsed = int(time.time() - start_time)
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60
    lbl_uptime.config(text=f"运行 {hours:02d}:{minutes:02d}:{seconds:02d}")
    root.after(1000, update_uptime)


# ====================== LED渲染核心函数 ======================
def calc_bright_color(r, g, b, br):
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

    if manual_color_override:
        display_color = manual_color
    else:
        display_color = screen_state["color"]

    if manual_brightness_override:
        display_brightness = manual_brightness
    else:
        display_brightness = screen_state["brightness"]

    r, g, b = display_color
    br = display_brightness
    text = screen_state["text"]
    mode = screen_state["mode"]
    color = calc_bright_color(r, g, b, br)

    for y in range(h):
        for x in range(w):
            x1 = x * LED_SIZE + 1
            y1 = y * LED_SIZE + 1
            x2 = x1 + LED_SIZE - 2
            y2 = y1 + LED_SIZE - 2

            canvas.create_rectangle(
                x1, y1, x2, y2,
                fill="#0a0a12",
                outline="#1a1a2a",
                width=1
            )
            if (x + y) % 2 == 0:
                canvas.create_rectangle(
                    x1 + 2, y1 + 2, x2 - 2, y2 - 2,
                    fill="#0d0d18",
                    outline=""
                )

    global scroll_offset
    if mode == "scroll":
        scroll_offset += 0.08
        if scroll_offset > len(text) * 12:
            scroll_offset = -w * LED_SIZE
    else:
        scroll_offset = 0

    if text:
        for offset in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            canvas.create_text(
                w * LED_SIZE // 2 - scroll_offset + offset[0],
                h * LED_SIZE // 2 + offset[1],
                text=text,
                fill="#000000" if br > 30 else color,
                font=("Consolas", 14, "bold")
            )

        canvas.create_text(
            w * LED_SIZE // 2 - scroll_offset,
            h * LED_SIZE // 2,
            text=text,
            fill=color,
            font=("Consolas", 14, "bold")
        )

    lbl_ver.config(text=f"#{screen_state['version']:04d}")

    if text:
        display_text = text[:20] + "..." if len(text) > 20 else text
        lbl_text_preview.config(text=display_text)
    else:
        lbl_text_preview.config(text="(无内容)")

    if manual_color_override:
        current_rgb = manual_color
        hex_color = f"#{current_rgb[0]:02x}{current_rgb[1]:02x}{current_rgb[2]:02x}"
        color_preview.config(bg=hex_color)
        lbl_color_hex.config(text=f"{hex_color.upper()} *")
    else:
        current_rgb = screen_state["color"]
        hex_color = f"#{current_rgb[0]:02x}{current_rgb[1]:02x}{current_rgb[2]:02x}"
        color_preview.config(bg=hex_color)
        lbl_color_hex.config(text=hex_color.upper())

    if manual_brightness_override:
        lbl_brightness_value.config(text=f"{manual_brightness}% *")
    else:
        lbl_brightness_value.config(text=f"{screen_state['brightness']}%")

    current_brightness = manual_brightness if manual_brightness_override else screen_state["brightness"]
    brightness_var.set(current_brightness)


def update_log_count():
    content = log_text.get(1.0, tk.END).strip()
    lines = len(content.split('\n')) if content else 0
    lbl_log_count.config(text=f"{lines}条")


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

    status_dot.delete("all")
    status_dot.create_oval(1, 1, 7, 7, fill=COLORS['yellow'], outline="")
    lbl_conn.config(text="[监听中]", foreground=COLORS['yellow'])

    while True:
        try:
            data, addr = udp_socket.recvfrom(2048)
            msg = data.decode("utf-8").strip()
            last_raw_msg = msg

            timestamp = time.strftime("%H:%M:%S")
            log_text.insert(tk.END, f"[{timestamp}] {addr[0]}:{addr[1]} -> {msg}\n", "info")
            log_text.see(tk.END)
            update_log_count()

            status_dot.delete("all")
            status_dot.create_oval(1, 1, 7, 7, fill=COLORS['green'], outline="")
            lbl_conn.config(text=f"[已连接] {addr[0]}:{addr[1]}", foreground=COLORS['green'])

            data_json = json.loads(msg)
            if data_json.get("type") != "state":
                continue

            screen_state["width"] = data_json["width"]
            screen_state["height"] = data_json["height"]
            screen_state["text"] = data_json["text"]

            if not manual_color_override:
                screen_state["color"] = data_json["color"]

            if not manual_brightness_override:
                screen_state["brightness"] = data_json["brightness"]

            screen_state["mode"] = data_json["mode"]
            screen_state["version"] = data_json["version"]

            current_width = canvas.winfo_width()
            expected_width = screen_state["width"] * LED_SIZE
            if current_width != expected_width:
                canvas.config(width=expected_width, height=screen_state["height"] * LED_SIZE)

        except json.JSONDecodeError as e:
            log_text.insert(tk.END, f"[{timestamp}] JSON解析错误: {e}\n", "error")
            log_text.see(tk.END)
            update_log_count()
        except Exception as e:
            print("UDP接收异常：", e)
            status_dot.delete("all")
            status_dot.create_oval(1, 1, 7, 7, fill=COLORS['red'], outline="")
            lbl_conn.config(text="[连接异常]", foreground=COLORS['red'])


# ====================== 程序入口 ======================
if __name__ == "__main__":
    udp_thread = threading.Thread(target=udp_listen_task, daemon=True)
    udp_thread.start()
    refresh_loop()
    update_uptime()
    root.mainloop()

    if udp_socket:
        udp_socket.close()