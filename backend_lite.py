import os
import sys
import json
import time
import random
import ctypes
import hashlib
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import mss
import numpy as np
import cv2
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# ============ DPI Aware（放在 tkinter 之前） ============
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ============ 路径 ============
def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()
RESOURCE_DIR = get_resource_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
REGION_PATH = os.path.join(BASE_DIR, "region.json")

USER_TEMPLATE_ROOT = os.path.join(BASE_DIR, "matchTemplates")
BUILTIN_TEMPLATE_DIR = os.path.join(RESOURCE_DIR, "templates")


# ============ 配置 ============
DEFAULT_CONFIG = {
    "start_delay": 3,
    "target_total_time": 20.0,
    "fast_interval": 0.18,
    "slow_interval": 0.55,
    "big_pause_min": 1.5,
    "big_pause_max": 2.5,
    "grid_rows": 5,
    "grid_cols": 5,
    "cell_shrink": 0.15,
    "match_score_max": 0.15,
    "save_debug": False,
    "descending": False,
    "mouse_mode": "instant",
    "human_jitter": 2,
    "click_jitter": 1,
    "_meta_v3": "",
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            return dict(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


# ============ 模板包扫描 ============
def _has_all_templates(d):
    return all(os.path.exists(os.path.join(d, f"{i}.png")) for i in range(1, 26))


def list_template_packs():
    packs = []
    if os.path.isdir(USER_TEMPLATE_ROOT):
        subdirs = [d for d in os.listdir(USER_TEMPLATE_ROOT)
                   if os.path.isdir(os.path.join(USER_TEMPLATE_ROOT, d))]
        for d in sorted(subdirs):
            full = os.path.join(USER_TEMPLATE_ROOT, d)
            if _has_all_templates(full):
                packs.append({"name": d, "dir": full})
        if _has_all_templates(USER_TEMPLATE_ROOT):
            packs.insert(0, {"name": "默认", "dir": USER_TEMPLATE_ROOT})
    if not packs and os.path.isdir(BUILTIN_TEMPLATE_DIR):
        packs.append({"name": "内置", "dir": BUILTIN_TEMPLATE_DIR})
    return packs


# ============ 屏幕 ============
def grab_screen(region):
    with mss.mss() as sct:
        img = np.array(sct.grab(region))
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def to_black_white(img):
    """蓝色数字 -> 黑，其余 -> 白（硬编码，宽容差）"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([90, 80, 80])
    upper = np.array([130, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    result = np.full_like(img, 255)
    result[mask > 0] = (0, 0, 0)
    return result


# ============ 鼠标移动 ============
def smooth_move(target_x, target_y, max_time):
    duration = max(0.20, min(max_time, 0.40))
    pyautogui.moveTo(target_x, target_y, duration=duration, _pause=False)


def human_move(target_x, target_y, max_time, jitter):
    start_x, start_y = pyautogui.position()
    dx, dy = target_x - start_x, target_y - start_y
    distance = (dx * dx + dy * dy) ** 0.5

    if distance < 3 or max_time < 0.01:
        pyautogui.moveTo(target_x, target_y, _pause=False)
        return

    ctrl_off = min(distance * 0.2, 100)
    mid_x = (start_x + target_x) / 2 + random.uniform(-ctrl_off, ctrl_off)
    mid_y = (start_y + target_y) / 2 + random.uniform(-ctrl_off, ctrl_off)

    steps = max(12, min(50, int(distance / 10) + 12))
    step_dt = max_time / steps

    for i in range(1, steps + 1):
        t = i / steps
        te = 3 * t * t - 2 * t * t * t
        bx = (1 - te) ** 2 * start_x + 2 * (1 - te) * te * mid_x + te * te * target_x
        by = (1 - te) ** 2 * start_y + 2 * (1 - te) * te * mid_y + te * te * target_y
        bx += random.gauss(0, jitter * 0.4)
        by += random.gauss(0, jitter * 0.4)
        pyautogui.moveTo(int(bx), int(by), _pause=False)
        time.sleep(step_dt)

    pyautogui.moveTo(target_x, target_y, _pause=False)


def do_move_and_click(target_x, target_y, mode, move_budget, human_jitter, click_jitter):
    cx = target_x + random.randint(-click_jitter, click_jitter) if click_jitter > 0 else target_x
    cy = target_y + random.randint(-click_jitter, click_jitter) if click_jitter > 0 else target_y

    if mode == "instant":
        pyautogui.moveTo(target_x, target_y, _pause=False)
        pyautogui.click(cx, cy)
    elif mode == "smooth":
        smooth_move(target_x, target_y, move_budget)
        pyautogui.click(cx, cy)
    elif mode == "human":
        human_move(target_x, target_y, move_budget, human_jitter)
        pyautogui.click(cx, cy)
    else:
        pyautogui.click(cx, cy)


# ============ 选区（tkinter 全屏半透明） ============
def run_select_region():
    """在独立线程里跑 tkinter 选区，返回 region 或 None"""
    result = {"value": None}

    import tkinter as tk

    top = tk.Tk()
    top.attributes("-alpha", 0.35)
    top.attributes("-fullscreen", True)
    top.attributes("-topmost", True)
    top.configure(bg="#000000")
    top.config(cursor="crosshair")

    canvas = tk.Canvas(top, bg="#000000", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    start = {"x": 0, "y": 0}
    rect = {"id": None, "outer_id": None, "label_id": None}

    # 颜色常量
    OUTER_COLOR = "#ffffff"      # 白色外描边
    INNER_COLOR = "#ff2d55"      # 亮红内描边
    OUTER_W = 6
    INNER_W = 3

    def on_press(e):
        start["x"], start["y"] = e.x, e.y
        # 删除旧框
        for key in ("id", "outer_id", "label_id"):
            if rect.get(key):
                canvas.delete(rect[key])
        # 外层白框
        rect["outer_id"] = canvas.create_rectangle(
            e.x, e.y, e.x, e.y, outline=OUTER_COLOR, width=OUTER_W)
        # 内层红框
        rect["id"] = canvas.create_rectangle(
            e.x, e.y, e.x, e.y, outline=INNER_COLOR, width=INNER_W)
        # 尺寸标签
        rect["label_id"] = canvas.create_text(
            e.x, e.y, text="", anchor="nw",
            fill="#ffffff", font=("Microsoft YaHei UI", 12, "bold"))

    def on_drag(e):
        if rect["id"]:
            x1, y1 = start["x"], start["y"]
            x2, y2 = e.x, e.y
            canvas.coords(rect["id"], x1, y1, x2, y2)
            canvas.coords(rect["outer_id"], x1, y1, x2, y2)
            # 更新尺寸标签位置和文字
            w, h = abs(x2 - x1), abs(y2 - y1)
            tx = min(x1, x2)
            ty = min(y1, y2) - 26
            if ty < 0:
                ty = max(y1, y2) + 6
            canvas.coords(rect["label_id"], tx + 4, ty)
            canvas.itemconfig(rect["label_id"], text=f"{w} × {h}")

    def on_release(e):
        x1, y1 = start["x"], start["y"]
        x2, y2 = e.x, e.y
        left, top_y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        if w > 20 and h > 20:
            result["value"] = {"left": left, "top": top_y,
                               "width": w, "height": h}
        top.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    top.bind("<Escape>", lambda e: top.destroy())

    top.mainloop()
    return result["value"]

# ============ 工作线程 ============
class ClickWorker:
    def __init__(self, cfg, region, template_dir, log_fn):
        self.cfg = cfg
        self.region = region
        self.template_dir = template_dir
        self.log_fn = log_fn

    def run(self):
        try:
            self._do_click()
        except Exception as e:
            import traceback
            self.log_fn(f"运行时错误: {e}", "error")
            self.log_fn(traceback.format_exc(), "error")

    def _do_click(self):
        from template_match import TemplateMatcher

        cfg = self.cfg
        START_DELAY = cfg["start_delay"]
        TARGET_TOTAL = cfg["target_total_time"]
        FAST_INTERVAL = cfg["fast_interval"]
        SLOW_INTERVAL = cfg["slow_interval"]
        BIG_PAUSE_MIN = cfg["big_pause_min"]
        BIG_PAUSE_MAX = cfg["big_pause_max"]
        GRID_ROWS = cfg["grid_rows"]
        GRID_COLS = cfg["grid_cols"]
        CELL_SHRINK = cfg["cell_shrink"]
        MATCH_SCORE_MAX = cfg["match_score_max"]
        DESCENDING = cfg["descending"]
        MOUSE_MODE = cfg.get("mouse_mode", "instant")
        HUMAN_JITTER = cfg.get("human_jitter", 2)
        CLICK_JITTER = cfg.get("click_jitter", 1)

        if TARGET_TOTAL < 5 and MOUSE_MODE != "instant":
            self.log_fn("目标总时长小于 5 秒，已自动切换为瞬移模式", "warn")
            MOUSE_MODE = "instant"

        matcher = TemplateMatcher(template_dir=self.template_dir)

        self.log_fn(f"{START_DELAY} 秒后开始，请切换到目标窗口...", "info")
        time.sleep(START_DELAY)

        self.log_fn("正在截屏...", "info")
        screen = grab_screen(self.region)
        bw = to_black_white(screen)

        H, W = bw.shape[:2]
        cell_w = W / GRID_COLS
        cell_h = H / GRID_ROWS

        results = []
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                x1 = int(col * cell_w)
                y1 = int(row * cell_h)
                x2 = int((col + 1) * cell_w)
                y2 = int((row + 1) * cell_h)
                mx = int((x2 - x1) * CELL_SHRINK)
                my = int((y2 - y1) * CELL_SHRINK)
                cell_img = bw[y1 + my:y2 - my, x1 + mx:x2 - mx]

                digit, score = matcher.match(cell_img)
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                if digit is not None and score < MATCH_SCORE_MAX:
                    results.append((int(digit), cx, cy, 1.0 - score))

        if not results:
            self.log_fn("没有识别到任何数字。", "error")
            return

        found = sorted(set(n for n, _, _, _ in results))
        expected = list(range(1, GRID_ROWS * GRID_COLS + 1))
        if found != expected:
            missing = [n for n in expected if n not in found]
            self.log_fn(f"警告：数字不完整，缺失 {missing}", "warn")
        else:
            self.log_fn(f"完整识别 1~{GRID_ROWS*GRID_COLS} 全部 {len(results)} 个数字", "success")

        results.sort(key=lambda t: t[0], reverse=DESCENDING)
        n = len(results)
        if n == 0:
            return

        pause_after_index = random.randint(1, n - 3) if n >= 4 else None
        big_pause_duration = (
            random.uniform(BIG_PAUSE_MIN, BIG_PAUSE_MAX)
            if pause_after_index is not None else 0.0
        )

        if MOUSE_MODE == "instant":
            t_move = 0.0
        elif MOUSE_MODE == "smooth":
            t_move = 0.25
            budget = max(0.05, (TARGET_TOTAL - big_pause_duration - 0.1 * n) / n * 0.6)
            t_move = min(t_move, budget)
        else:
            t_move = 0.22
            budget = max(0.05, (TARGET_TOTAL - big_pause_duration - 0.1 * n) / n * 0.6)
            t_move = min(t_move, budget)

        intervals = [random.uniform(FAST_INTERVAL, SLOW_INTERVAL) for _ in range(n - 1)]
        click_overhead = 0.11 * n
        target_intervals_total = TARGET_TOTAL - big_pause_duration - click_overhead - n * t_move
        min_interval_total = 0.08 * (n - 1)
        if target_intervals_total < min_interval_total:
            target_intervals_total = min_interval_total
        if sum(intervals) > 0:
            scale = target_intervals_total / sum(intervals)
            intervals = [max(FAST_INTERVAL * 0.6, iv * scale) for iv in intervals]

        self.log_fn(f"模式: {MOUSE_MODE}  每步移动预算: {t_move*1000:.0f}ms", "info")
        if pause_after_index is not None:
            self.log_fn(f"大停顿安排在点 #{pause_after_index} 之后，约 {big_pause_duration:.2f} 秒", "pause")
        self.log_fn(f"目标总时长 {TARGET_TOTAL:.1f} 秒", "info")

        self.log_fn("开始点击...", "info")
        start_ts = time.time()
        for i, (num, cx, cy, conf) in enumerate(results):
            abs_x = int(self.region["left"] + cx)
            abs_y = int(self.region["top"] + cy)

            do_move_and_click(abs_x, abs_y, MOUSE_MODE, t_move,
                              HUMAN_JITTER, CLICK_JITTER)

            actual = time.time() - start_ts
            self.log_fn(f"点击 {num:>3} @ ({abs_x}, {abs_y})  {actual:.3f}s", "click")

            if i >= n - 1:
                break

            sleep_t = intervals[i]
            if pause_after_index is not None and i == pause_after_index:
                sleep_t += big_pause_duration
                self.log_fn(f"大停顿 {big_pause_duration:.2f}s", "pause")
            if sleep_t > 0:
                time.sleep(sleep_t)

        self.log_fn(f"总耗时 {time.time() - start_ts:.2f} 秒", "success")
        self.log_fn("完成", "success")


# ============ 主界面 ============
LOG_COLORS = {
    "info": "#222222",
    "success": "#108010",
    "warn": "#c08000",
    "error": "#c00000",
    "click": "#404040",
    "pause": "#6040a0",
}


class App:
    TARGET_TIME_LIMIT = 20.0
    _BLOB = "NTU2ZTllNTRiNmVmMTE4NGY0YWI2N2JlYmNlMGMxYTQ1MmMyNjAwZjY0NzA2MTUxYTMzZGQzNDk4YTExNjRhOA=="
    _SALT = "sg_2026_x9"
    _MAGIC = 0x5A3F

    @classmethod
    def _rebuild_hash(cls):
        import base64
        try:
            rev = base64.b64decode(cls._BLOB.encode()).decode()
            if len(rev) == 64:
                return rev[::-1]
        except Exception:
            pass
        return ""

    def __init__(self, root):
        self.root = root
        root.title("舒尔特方格自动点击器")

        # 自适应屏幕
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w = min(860, int(sw * 0.6))
        h = min(720, int(sh * 0.85))
        root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        root.minsize(680, 560)

        self.cfg = load_config()
        self.region = self._load_region()
        self.is_running = False
        self.all_logs = []

        self._build_ui()

        # ============ 设置窗口图标 ============
        try:
            ico_path = os.path.join(BASE_DIR, "app.ico")
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
        except Exception:
            pass
        # ====================================

        if ctypes.windll.shell32.IsUserAnAdmin() != 0:
            self.log("已以管理员身份运行。", "success")
        else:
            self.log("当前为普通权限。若点击无效，请以管理员身份重启程序。", "warn")

    # ---------- UI ----------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 5}

        # 区域
        f_region = ttk.LabelFrame(self.root, text="识别区域")
        f_region.pack(fill="x", **pad)
        self.lbl_region = ttk.Label(f_region, text=self._region_text(),
                                    font=("Consolas", 10))
        self.lbl_region.pack(side="left", padx=8, pady=6)
        ttk.Button(f_region, text="重新选区",
                   command=self.on_select).pack(side="right", padx=8, pady=6)

        # 参数
        f_param = ttk.LabelFrame(self.root, text="参数设置")
        f_param.pack(fill="x", **pad)

        self.entries = {}
        left_rows = [
            ("起始等待（秒）", "start_delay"),
            ("目标总时长（秒）", "target_total_time"),
            ("最快间隔（秒）", "fast_interval"),
            ("最慢间隔（秒）", "slow_interval"),
        ]
        right_rows = [
            ("大停顿最小（秒）", "big_pause_min"),
            ("大停顿最大（秒）", "big_pause_max"),
            ("格子边缘收缩比例", "cell_shrink"),
            ("匹配阈值（score<）", "match_score_max"),
        ]

        inner = ttk.Frame(f_param)
        inner.pack(fill="x", padx=8, pady=6)

        def add_row(parent, r, label, key, col):
            ttk.Label(parent, text=label).grid(row=r, column=col,
                                               sticky="w", padx=(4, 4), pady=3)
            e = ttk.Entry(parent, width=12)
            e.insert(0, str(self.cfg.get(key, DEFAULT_CONFIG[key])))
            e.grid(row=r, column=col + 1, sticky="w", padx=(0, 16), pady=3)
            self.entries[key] = e

        for i, (label, key) in enumerate(left_rows):
            add_row(inner, i, label, key, 0)
        for i, (label, key) in enumerate(right_rows):
            add_row(inner, i, label, key, 3)

        # 排序方向（单独一行）
        opt1 = ttk.Frame(f_param)
        opt1.pack(fill="x", padx=8, pady=(0, 4))

        ttk.Label(opt1, text="排序方向：").pack(side="left", padx=(4, 2))
        self.sort_var = tk.StringVar(value="desc" if self.cfg.get("descending") else "asc")
        ttk.Radiobutton(opt1, text="从小到大", variable=self.sort_var,
                        value="asc").pack(side="left", padx=2)
        ttk.Radiobutton(opt1, text="从大到小", variable=self.sort_var,
                        value="desc").pack(side="left", padx=2)

        # 鼠标模式（单独一行）
        opt2 = ttk.Frame(f_param)
        opt2.pack(fill="x", padx=8, pady=(0, 4))

        ttk.Label(opt2, text="鼠标模式：").pack(side="left", padx=(4, 2))
        self.mouse_var = tk.StringVar(value=self.cfg.get("mouse_mode", "instant"))
        ttk.Radiobutton(opt2, text="瞬移", variable=self.mouse_var,
                        value="instant").pack(side="left", padx=2)
        ttk.Radiobutton(opt2, text="平滑移动", variable=self.mouse_var,
                        value="smooth").pack(side="left", padx=2)
        ttk.Radiobutton(opt2, text="人类模拟", variable=self.mouse_var,
                        value="human").pack(side="left", padx=2)

        # 抖动（单独一行，也拆开保证显示完整）
        jit1 = ttk.Frame(f_param)
        jit1.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(jit1, text="人类模拟抖动（像素）：").pack(side="left", padx=(4, 2))
        self.entry_hj = ttk.Entry(jit1, width=6)
        self.entry_hj.insert(0, str(self.cfg.get("human_jitter", 2)))
        self.entry_hj.pack(side="left")

        jit2 = ttk.Frame(f_param)
        jit2.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(jit2, text="点击抖动（像素）：").pack(side="left", padx=(4, 2))
        self.entry_cj = ttk.Entry(jit2, width=6)
        self.entry_cj.insert(0, str(self.cfg.get("click_jitter", 1)))
        self.entry_cj.pack(side="left")

        # 模板包
        tpl = ttk.Frame(f_param)
        tpl.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(tpl, text="模板包：").pack(side="left", padx=(4, 2))
        self.template_combo = ttk.Combobox(tpl, width=32, state="readonly")
        self.template_combo.pack(side="left", padx=(0, 8))
        self._packs = list_template_packs()
        self.template_combo["values"] = [p["name"] for p in self._packs] or ["(未找到模板)"]
        saved = self.cfg.get("template_pack_name", "")
        if saved and saved in self.template_combo["values"]:
            self.template_combo.set(saved)
        else:
            self.template_combo.current(0)

        # 主按钮
        btns = ttk.Frame(self.root)
        btns.pack(fill="x", padx=8, pady=8)
        self.btn_start = ttk.Button(btns, text="开始点击", command=self.on_start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(btns, text="保存配置",
                   command=self.on_save).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(btns, text="帮助",
                   command=self.on_help).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(btns, text="退出",
                   command=self.root.destroy).pack(side="left", expand=True, fill="x", padx=(4, 0))

        # 日志
        f_log = ttk.LabelFrame(self.root, text="运行日志")
        f_log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        log_top = ttk.Frame(f_log)
        log_top.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(log_top, text="过滤：").pack(side="left")
        self.filter_var = tk.StringVar(value="全部")
        filter_combo = ttk.Combobox(log_top, textvariable=self.filter_var,
                                    values=["全部", "信息", "成功", "警告", "错误", "点击", "停顿"],
                                    width=8, state="readonly")
        filter_combo.pack(side="left", padx=(2, 12))
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_log_view())
        ttk.Button(log_top, text="清空",
                   command=self.on_clear_log).pack(side="right")

        self.txt_log = tk.Text(f_log, wrap="word", font=("Consolas", 10),
                               height=10, state="disabled", bg="white")
        self.txt_log.pack(fill="both", expand=True, padx=8, pady=6)

        for c, color in LOG_COLORS.items():
            self.txt_log.tag_configure(c, foreground=color)

    # ---------- 工具 ----------
    def _region_text(self):
        if self.region:
            r = self.region
            return f"({r['left']}, {r['top']})   宽 {r['width']} × 高 {r['height']}"
        return "未选区（请点“重新选区”）"

    def _load_region(self):
        if os.path.exists(REGION_PATH):
            try:
                with open(REGION_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def log(self, msg, category="info"):
        self.all_logs.append((msg, category))
        self.refresh_log_view()

    def refresh_log_view(self):
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        cat_map = {"全部": None, "信息": "info", "成功": "success",
                   "警告": "warn", "错误": "error",
                   "点击": "click", "停顿": "pause"}
        want = cat_map.get(self.filter_var.get())
        for msg, c in self.all_logs:
            if want and c != want:
                continue
            self.txt_log.insert("end", msg + "\n", c)
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def on_clear_log(self):
        self.all_logs = []
        self.refresh_log_view()

    # ---------- 帮助 ----------
    def on_help(self):
        win = tk.Toplevel(self.root)
        win.title("使用说明")
        win.geometry("720x600")
        txt = tk.Text(win, wrap="word", font=("Consolas", 10))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        help_text = """舒尔特方格自动点击器  v1.2（精简版）
=====================================================

【首次使用】
  1. 打开舒尔特方格网页/程序，让 25 个数字显示在屏幕上
  2. 双击 AutoClicker.exe 打开主窗口
  3. 点"重新选区"，屏幕变暗后拖框选中整个方格区域

【参数说明】
  起始等待        点击前的准备时间（给你切窗口）
  目标总时长      整套点击的目标耗时（秒）
  最快/最慢间隔   每个点之间的随机间隔范围（秒）
  大停顿最小/最大 模拟"卡住"的一次停顿，时长随机
  格子边缘收缩    识别时向内收缩的比例（避开边框）
  匹配阈值        数字识别的相似度阈值，越小越严格
  排序方向        从小到大 / 从大到小

【鼠标模式】
  瞬移        鼠标直接跳过去（默认，速度最快）
  平滑移动    直线匀速移动（200~400ms）
  人类模拟    贝塞尔曲线 + 速度变化 + 抖动，最像真人
  说明：目标总时长 < 5 秒时会自动强制为"瞬移"。

【模板包】
  数字模板存放在 exe 同级的 matchTemplates/ 文件夹中。

  支持两种结构：
    A. 单一字体：
         matchTemplates/1.png ~ 25.png
    B. 多字体：
         matchTemplates/字体A/1.png ~ 25.png
         matchTemplates/字体B/1.png ~ 25.png

  每个包必须包含 1.png ~ 25.png 共 25 张图。
  若 matchTemplates/ 不存在，程序会退回使用内置模板。

【邀请码】
  目标总时长 < 20 秒时，需要输入邀请码。
  验证成功后会在 config.json 里记住，下次无需再输入。

【常见问题】
  - 识别不全：重新选区，确保框住整个方格
  - 点击偏移：重新选区后重试
  - 点击无效：目标程序若以管理员运行，本程序也需以管理员身份运行

【免责声明】
  本工具仅供学习与自动化练习用途。使用者需自行承担使用行为带来的一切后果。

=====================================================
v1.2
"""
        txt.insert("1.0", help_text)
        txt.config(state="disabled")
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=(0, 8))

    # ---------- 邀请码 ----------
    def _check_code(self, target_time):
        if target_time >= self.TARGET_TIME_LIMIT:
            return True
        stored = self.cfg.get("_meta_v3", "")
        expected_unlock = hashlib.sha256(
            (self._rebuild_hash() + self._SALT).encode()
        ).hexdigest()
        if stored == expected_unlock:
            self.log("已使用本地保存的邀请码授权。", "info")
            return True
        
        dlg = tk.Toplevel(self.root)
        dlg.title("需要邀请码")
        dlg.geometry("380x160")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=f"目标总时长 < {self.TARGET_TIME_LIMIT:.0f} 秒需要邀请码。\n请向管理员索取后再输入。",
                  justify="center").pack(pady=(18, 8))
        var = tk.StringVar()
        ent = ttk.Entry(dlg, textvariable=var, width=36, show="*")
        ent.pack(pady=4)
        ent.focus_force()

        result = {"ok": False}

        def on_ok():
            code = var.get().strip()
            h = hashlib.sha256(code.encode("utf-8")).hexdigest()
            expected = self._rebuild_hash()
            if expected and h == expected:
                result["ok"] = True
                self.cfg["_meta_v3"] = hashlib.sha256(
                    (self._rebuild_hash() + self._SALT).encode()
                ).hexdigest()
                save_config(self.cfg)
                self.log("邀请码已记住，下次无需再输入。", "success")
                dlg.destroy()
            else:
                messagebox.showerror("邀请码错误", "邀请码无效，请重试。", parent=dlg)

        def on_cancel():
            dlg.destroy()

        frame = ttk.Frame(dlg)
        frame.pack(pady=8)
        ttk.Button(frame, text="确定", command=on_ok).pack(side="left", padx=6)
        ttk.Button(frame, text="取消", command=on_cancel).pack(side="left", padx=6)
        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: on_cancel())
        self.root.wait_window(dlg)
        return result["ok"]

    # ---------- 事件 ----------
    def on_select(self):
        self.log("进入选区模式...", "info")
        self.root.withdraw()
        self.root.update()   # 确保 withdraw 立即生效
        time.sleep(0.2)
        try:
            res = run_select_region(self.root)   # 传入主窗口
            if res:
                self.region = res
                with open(REGION_PATH, "w", encoding="utf-8") as f:
                    json.dump(res, f)
                self.lbl_region.config(text=self._region_text())
                self.log(f"选区完成: {res}", "info")
            else:
                self.log("选区取消", "warn")
        finally:
            self.root.deiconify()   # 恢复主窗口
            self.root.lift()
            self.root.focus_force()
            self.root.update()

    def _collect_config(self):
        cfg = dict(self.cfg)
        for key, entry in self.entries.items():
            raw = entry.get().strip()
            if key in ("start_delay", "grid_rows", "grid_cols"):
                cfg[key] = int(float(raw))
            else:
                cfg[key] = float(raw)
        cfg["human_jitter"] = float(self.entry_hj.get().strip())
        cfg["click_jitter"] = int(float(self.entry_cj.get().strip()))
        cfg["descending"] = (self.sort_var.get() == "desc")
        cfg["mouse_mode"] = self.mouse_var.get()
        cfg["template_pack_name"] = self.template_combo.get()
        cfg["save_debug"] = False
        return cfg

    def on_save(self):
        try:
            self.cfg = self._collect_config()
        except Exception as e:
            messagebox.showerror("参数错误", f"参数格式不对: {e}")
            return
        save_config(self.cfg)
        self.log("配置已保存。", "success")

    def on_start(self):
        if self.is_running:
            messagebox.showinfo("提示", "正在运行中...")
            return
        if not self.region:
            messagebox.showwarning("未选区", "请先点“重新选区”框出方格区域")
            return
        try:
            self.cfg = self._collect_config()
        except Exception as e:
            messagebox.showerror("参数错误", f"参数格式不对: {e}")
            return

        # 选模板目录
        idx = self.template_combo.current()
        if idx < 0 or idx >= len(self._packs):
            messagebox.showerror(
                "模板缺失",
                "未找到任何模板包。\n\n请在 exe 同级创建 matchTemplates/ 文件夹，"
                "并在其中放入 1.png ~ 25.png（也可以建子文件夹存放不同字体）。")
            return
        template_dir = self._packs[idx]["dir"]

        # 邀请码
        if not self._check_code(self.cfg["target_total_time"]):
            self.log("邀请码校验未通过，已取消。", "warn")
            return

        save_config(self.cfg)

        self.is_running = True
        self.btn_start.config(state="disabled")
        self.root.withdraw()

        worker = ClickWorker(self.cfg, self.region, template_dir,
                             lambda msg, cat="info": self.root.after(0, self.log, msg, cat))
        self.worker = worker
        threading.Thread(target=self._thread_wrapper, daemon=True).start()

    def _thread_wrapper(self):
        self.worker.run()
        self.root.after(0, self._on_finished)

    def _on_finished(self):
        self.is_running = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.btn_start.config(state="normal")


# ============ 入口 ============
def run_lite():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "winnative" in style.theme_names():
            style.theme_use("winnative")
    except Exception:
        pass
    App(root)
    root.mainloop()

if __name__ == "__main__":
    run_web()