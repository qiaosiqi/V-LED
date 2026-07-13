"""Tk VLED simulator. All widget access stays on the main thread."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import colorchooser, scrolledtext, ttk

try:
    from .vled_model import BoundedLog, SimulatorModel
    from .vled_receiver import ErrorEvent, ListenerEvent, StateEvent, UdpReceiver
except ImportError:  # `python vled_sim.py` from simulator/.
    from vled_model import BoundedLog, SimulatorModel
    from vled_receiver import ErrorEvent, ListenerEvent, StateEvent, UdpReceiver

UDP_PORT = 9000
LED_SIZE = 18
EVENT_QUEUE_SIZE = 1024
MAX_LOG_ENTRIES = 200

COLORS = {
    "bg_dark": "#0a0a0f",
    "bg_panel": "#14141e",
    "bg_input": "#1a1a2e",
    "bg_canvas": "#050508",
    "border": "#2a2a3e",
    "text_primary": "#e8e8f0",
    "text_secondary": "#8888aa",
    "text_accent": "#4fc3f7",
    "green": "#4ade80",
    "red": "#f87171",
    "yellow": "#fbbf24",
    "purple": "#a78bfa",
}


class VledSimulatorApp:
    def __init__(self, root: tk.Tk, port: int = UDP_PORT) -> None:
        self.root = root
        self.model = SimulatorModel()
        self.events: queue.Queue = queue.Queue(maxsize=EVENT_QUEUE_SIZE)
        self.receiver = UdpReceiver(self.events, port=port)
        self.log_history = BoundedLog(MAX_LOG_ENTRIES)
        self.main_thread_id = threading.get_ident()
        self.scroll_offset = 0.0
        self._updating_brightness = False
        self._closing = False
        self._close_deadline = 0.0
        self._last_canvas_size: tuple[int, int] | None = None

        self._configure_root()
        self._configure_styles()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.receiver.start()
        self.root.after(20, self._drain_events)
        self.root.after(30, self._render_loop)

    def _assert_main_thread(self) -> None:
        if threading.get_ident() != self.main_thread_id:
            raise RuntimeError("Tk update attempted outside the main thread")

    def _configure_root(self) -> None:
        self.root.title("虚拟 LED 模拟器")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg_dark"])

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Dark.TFrame", background=COLORS["bg_dark"])
        style.configure("Panel.TFrame", background=COLORS["bg_panel"])
        style.configure(
            "Title.TLabel",
            background=COLORS["bg_dark"],
            foreground=COLORS["text_accent"],
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        style.configure(
            "Normal.TLabel",
            background=COLORS["bg_panel"],
            foreground=COLORS["text_secondary"],
            font=("Microsoft YaHei UI", 8),
        )
        style.configure(
            "Value.TLabel",
            background=COLORS["bg_panel"],
            foreground=COLORS["text_primary"],
            font=("Microsoft YaHei UI", 8, "bold"),
        )
        style.configure(
            "Accent.TButton",
            background=COLORS["text_accent"],
            foreground=COLORS["bg_dark"],
            padding=(8, 4),
        )
        style.configure(
            "Danger.TButton",
            background=COLORS["red"],
            foreground="white",
            padding=(8, 4),
        )

    def _build_ui(self) -> None:
        title = ttk.Frame(self.root, style="Dark.TFrame", padding=(8, 5))
        title.pack(fill="x")
        ttk.Label(title, text="虚拟 LED 点阵模拟器", style="Title.TLabel").pack(
            side="left"
        )

        status = ttk.Frame(self.root, style="Panel.TFrame", padding=6)
        status.pack(fill="x", padx=8, pady=2)
        self.status_dot = tk.Canvas(
            status,
            width=8,
            height=8,
            bg=COLORS["bg_panel"],
            highlightthickness=0,
        )
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_label = ttk.Label(status, text="[启动中]", style="Normal.TLabel")
        self.status_label.pack(side="left")
        self.version_label = ttk.Label(status, text="#0000", style="Value.TLabel")
        self.version_label.pack(side="right")

        canvas_wrap = ttk.Frame(self.root, style="Panel.TFrame", padding=8)
        canvas_wrap.pack(padx=8, pady=3)
        initial = self.model.display_state
        self.canvas = tk.Canvas(
            canvas_wrap,
            bg=COLORS["bg_canvas"],
            width=initial.width * LED_SIZE,
            height=initial.height * LED_SIZE,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.canvas.pack()

        info = ttk.Frame(self.root, style="Panel.TFrame", padding=6)
        info.pack(fill="x", padx=8, pady=2)
        ttk.Label(info, text="文字:", style="Normal.TLabel").pack(side="left")
        self.text_label = ttk.Label(info, text="(无内容)", style="Value.TLabel")
        self.text_label.pack(side="left", padx=(4, 14))
        ttk.Label(info, text="颜色:", style="Normal.TLabel").pack(side="left")
        self.color_preview = tk.Canvas(
            info,
            width=18,
            height=18,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            cursor="hand2",
        )
        self.color_preview.pack(side="left", padx=4)
        self.color_preview.bind("<Button-1>", lambda _event: self.choose_color())
        self.color_label = ttk.Label(info, text="#FFFFFF", style="Value.TLabel")
        self.color_label.pack(side="left", padx=(0, 5))
        ttk.Button(
            info, text="选择", style="Accent.TButton", command=self.choose_color
        ).pack(side="left", padx=2)
        ttk.Button(
            info, text="恢复 UDP", style="Accent.TButton", command=self.restore_udp_color
        ).pack(side="left", padx=2)

        brightness = ttk.Frame(self.root, style="Panel.TFrame", padding=6)
        brightness.pack(fill="x", padx=8, pady=2)
        ttk.Label(brightness, text="亮度:", style="Normal.TLabel").pack(side="left")
        self.brightness_var = tk.DoubleVar(value=100)
        self.brightness_slider = ttk.Scale(
            brightness,
            from_=0,
            to=100,
            variable=self.brightness_var,
            command=self.set_manual_brightness,
            length=220,
        )
        self.brightness_slider.pack(side="left", padx=8)
        self.brightness_label = ttk.Label(brightness, text="100%", style="Value.TLabel")
        self.brightness_label.pack(side="left", padx=(0, 8))
        ttk.Button(
            brightness,
            text="恢复 UDP",
            style="Accent.TButton",
            command=self.restore_udp_brightness,
        ).pack(side="left")

        log_wrap = ttk.Frame(self.root, style="Panel.TFrame", padding=6)
        log_wrap.pack(fill="x", padx=8, pady=2)
        log_header = ttk.Frame(log_wrap, style="Panel.TFrame")
        log_header.pack(fill="x")
        ttk.Label(log_header, text="UDP 日志", style="Value.TLabel").pack(side="left")
        self.log_count_label = ttk.Label(log_header, text="0 条", style="Normal.TLabel")
        self.log_count_label.pack(side="right")
        self.log_text = scrolledtext.ScrolledText(
            log_wrap,
            width=76,
            height=6,
            bg=COLORS["bg_input"],
            fg=COLORS["text_primary"],
            font=("Consolas", 8),
            state="disabled",
        )
        self.log_text.pack(fill="x", pady=(3, 0))

        actions = ttk.Frame(self.root, style="Dark.TFrame", padding=(8, 6))
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="本地预览清屏",
            style="Danger.TButton",
            command=self.clear_local_preview,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="清日志",
            style="Accent.TButton",
            command=self.clear_log,
        ).pack(side="left", padx=6)
        ttk.Label(
            actions,
            text=f"UDP 端口: {UDP_PORT}",
            foreground=COLORS["text_secondary"],
            background=COLORS["bg_dark"],
        ).pack(side="right")

    def _set_connection(self, text: str, color: str) -> None:
        self._assert_main_thread()
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 7, 7, fill=color, outline="")
        self.status_label.configure(text=text, foreground=color)

    def _append_log(self, message: str) -> None:
        self._assert_main_thread()
        timestamp = time.strftime("%H:%M:%S")
        self.log_history.append(f"[{timestamp}] {message}")
        content = "\n".join(self.log_history.entries)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        if content:
            self.log_text.insert(tk.END, content + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see(tk.END)
        self.log_count_label.configure(text=f"{len(self.log_history)} 条")

    def clear_log(self) -> None:
        self.log_history.clear()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")
        self.log_count_label.configure(text="0 条")

    def choose_color(self) -> None:
        state = self.model.display_state
        initial = "#{:02x}{:02x}{:02x}".format(*state.color)
        chosen = colorchooser.askcolor(initialcolor=initial, title="选择 LED 显示颜色")
        if not chosen or chosen[0] is None:
            return
        color = tuple(int(value) for value in chosen[0])
        self.model.set_manual_color(color)
        self._append_log("启用手动颜色覆盖 " + "#{:02X}{:02X}{:02X}".format(*color))

    def restore_udp_color(self) -> None:
        self.model.restore_udp_color()
        self._append_log("取消手动颜色覆盖，恢复最新 UDP 值")

    def set_manual_brightness(self, raw_value: str) -> None:
        if self._updating_brightness:
            return
        value = int(float(raw_value))
        self.model.set_manual_brightness(value)
        self.brightness_label.configure(text=f"{value}% *")

    def restore_udp_brightness(self) -> None:
        self.model.restore_udp_brightness()
        self._append_log("取消手动亮度覆盖，恢复最新 UDP 值")

    def clear_local_preview(self) -> None:
        self.model.clear_local_preview()
        self.scroll_offset = 0
        self._append_log("仅清空本地预览；未向驱动写入 CLEAR")

    def _drain_events(self) -> None:
        self._assert_main_thread()
        if self._closing:
            return

        latest_state: StateEvent | None = None
        for _ in range(512):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, StateEvent):
                latest_state = event
            elif isinstance(event, ErrorEvent):
                source = ""
                if event.address:
                    source = f" {event.address[0]}:{event.address[1]}"
                self._append_log(f"拒绝报文{source}: {event.reason}")
            elif isinstance(event, ListenerEvent):
                if event.status == "listening" and event.address:
                    self._set_connection("[监听中]", COLORS["yellow"])
                    self._append_log(
                        f"UDP 监听启动 {event.address[0]}:{event.address[1]}"
                    )
                elif event.status == "stopped":
                    self._set_connection("[已停止]", COLORS["text_secondary"])

        if latest_state is not None:
            self.model.apply_udp(latest_state.state)
            self._set_connection(
                f"[已连接] {latest_state.address[0]}:{latest_state.address[1]}",
                COLORS["green"],
            )
            self._append_log(
                f"采用完整状态 version={latest_state.state.version} "
                f"mode={latest_state.state.mode}"
            )

        self.root.after(20, self._drain_events)

    @staticmethod
    def _bright_color(color: tuple[int, int, int], brightness: int) -> str:
        ratio = brightness / 100.0
        values = tuple(int(channel * ratio) for channel in color)
        return "#{:02x}{:02x}{:02x}".format(*values)

    def _render_loop(self) -> None:
        self._assert_main_thread()
        if self._closing:
            return
        state = self.model.display_state
        canvas_size = (state.width * LED_SIZE, state.height * LED_SIZE)
        if canvas_size != self._last_canvas_size:
            self.canvas.configure(width=canvas_size[0], height=canvas_size[1])
            self._last_canvas_size = canvas_size

        self.canvas.delete("all")
        for y in range(state.height):
            for x in range(state.width):
                x1 = x * LED_SIZE + 1
                y1 = y * LED_SIZE + 1
                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x1 + LED_SIZE - 2,
                    y1 + LED_SIZE - 2,
                    fill="#0d0d18",
                    outline="#1a1a2a",
                )

        if state.mode == "scroll" and state.text:
            self.scroll_offset += 1.2
            if self.scroll_offset > len(state.text) * 12 + canvas_size[0]:
                self.scroll_offset = 0
        else:
            self.scroll_offset = 0

        if state.text:
            self.canvas.create_text(
                canvas_size[0] / 2 - self.scroll_offset,
                canvas_size[1] / 2,
                text=state.text,
                fill=self._bright_color(state.color, state.brightness),
                font=("Consolas", 14, "bold"),
            )

        preview = state.text if len(state.text) <= 24 else state.text[:24] + "..."
        self.text_label.configure(text=preview or "(无内容)")
        marker = " *" if self.model.manual_color is not None else ""
        color_hex = "#{:02X}{:02X}{:02X}".format(*state.color)
        self.color_preview.configure(bg=color_hex)
        self.color_label.configure(text=color_hex + marker)
        self.version_label.configure(text=f"#{state.version:04d}")

        self._updating_brightness = True
        self.brightness_var.set(state.brightness)
        self._updating_brightness = False
        brightness_marker = " *" if self.model.manual_brightness is not None else ""
        self.brightness_label.configure(text=f"{state.brightness}%{brightness_marker}")
        self.root.after(30, self._render_loop)

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._close_deadline = time.monotonic() + 2.0
        self.receiver.stop()
        self.root.after(10, self._finish_close)

    def _finish_close(self) -> None:
        if self.receiver.join(0) or time.monotonic() >= self._close_deadline:
            self.root.destroy()
            return
        self.root.after(20, self._finish_close)


def main() -> None:
    root = tk.Tk()
    app = VledSimulatorApp(root)
    try:
        root.mainloop()
    finally:
        app.receiver.stop()
        app.receiver.join(1.0)


if __name__ == "__main__":
    main()
