import os
import sys
import json
import time
import random
import ctypes
import hashlib
import threading
import queue
import mss
import numpy as np
import cv2
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# ============ DPI Aware ============
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
WEB_DIR = os.path.join(RESOURCE_DIR, "web")


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
    "descending": False,
    "mouse_mode": "instant",
    "human_jitter": 2,
    "click_jitter": 1,
    "_meta_v3": "",
    "template_pack_name": "",
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


# ============ 屏幕工具 ============
def grab_screen(region):
    with mss.mss() as sct:
        img = np.array(sct.grab(region))
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def to_black_white(img):
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


# ============ 选区（tkinter 独立线程） ============
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

# ============ 业务逻辑 ============
class ClickWorker:
    def __init__(self, cfg, region, template_dir, push_log):
        self.cfg = cfg
        self.region = region
        self.template_dir = template_dir
        self.push_log = push_log  # 回调函数 (msg, category)

    def run(self):
        try:
            self._do_click()
        except Exception as e:
            import traceback
            self.push_log(f"运行时错误: {e}", "error")
            self.push_log(traceback.format_exc(), "error")

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
            self.push_log("目标总时长小于 5 秒，已自动切换为瞬移模式", "warn")
            MOUSE_MODE = "instant"

        matcher = TemplateMatcher(template_dir=self.template_dir)

        self.push_log(f"{START_DELAY} 秒后开始，请切换到目标窗口...", "info")
        time.sleep(START_DELAY)

        self.push_log("正在截屏...", "info")
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
            self.push_log("没有识别到任何数字。", "error")
            return

        found = sorted(set(n for n, _, _, _ in results))
        expected = list(range(1, GRID_ROWS * GRID_COLS + 1))
        if found != expected:
            missing = [n for n in expected if n not in found]
            self.push_log(f"警告：数字不完整，缺失 {missing}", "warn")
        else:
            self.push_log(f"完整识别 1~{GRID_ROWS*GRID_COLS} 全部 {len(results)} 个数字", "success")

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

        self.push_log(f"模式: {MOUSE_MODE}  每步移动预算: {t_move*1000:.0f}ms", "info")
        if pause_after_index is not None:
            self.push_log(f"大停顿安排在点 #{pause_after_index} 之后，约 {big_pause_duration:.2f} 秒", "pause")
        self.push_log(f"目标总时长 {TARGET_TOTAL:.1f} 秒", "info")
        self.push_log("开始点击...", "info")

        start_ts = time.time()
        for i, (num, cx, cy, conf) in enumerate(results):
            abs_x = int(self.region["left"] + cx)
            abs_y = int(self.region["top"] + cy)
            do_move_and_click(abs_x, abs_y, MOUSE_MODE, t_move,
                              HUMAN_JITTER, CLICK_JITTER)
            actual = time.time() - start_ts
            self.push_log(f"点击 {num:>3} @ ({abs_x}, {abs_y})  {actual:.3f}s", "click")
            if i >= n - 1:
                break
            sleep_t = intervals[i]
            if pause_after_index is not None and i == pause_after_index:
                sleep_t += big_pause_duration
                self.push_log(f"大停顿 {big_pause_duration:.2f}s", "pause")
            if sleep_t > 0:
                time.sleep(sleep_t)

        self.push_log(f"总耗时 {time.time() - start_ts:.2f} 秒", "success")
        self.push_log("完成", "success")


# ============ JS API ============
class Api:
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

    def __init__(self):
        self.window = None
        self.cfg = load_config()
        self.region = None
        # 从 region.json 加载
        if os.path.exists(REGION_PATH):
            try:
                with open(REGION_PATH, "r", encoding="utf-8") as f:
                    self.region = json.load(f)
            except Exception:
                pass

        # 日志队列（Python 线程 → 前端）
        self.log_queue = queue.Queue()

        # 定时器：把队列里的日志推给前端
        self._start_log_pump()

    # ---------- 日志推送 ----------
    def _start_log_pump(self):
        def pump():
            while True:
                try:
                    msg, cat = self.log_queue.get(timeout=0.1)
                    if self.window:
                        payload = json.dumps({"msg": msg, "cat": cat})
                        self.window.evaluate_js(f"window.onBackendLog({payload})")
                except queue.Empty:
                    pass
                except Exception:
                    pass
                time.sleep(0.05)

        t = threading.Thread(target=pump, daemon=True)
        t.start()

    def push_log(self, msg, category="info"):
        self.log_queue.put((msg, category))

    # ---------- 暴露给 JS ----------
    def get_config(self):
        return {
            "config": self.cfg,
            "region": self.region,
            "packs": list_template_packs(),
        }

    def save_config(self, new_cfg):
        try:
            self.cfg.update(new_cfg)
            save_config(self.cfg)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def select_region(self):
        # 隐藏主窗口
        try:
            self.window.hide()
        except Exception:
            pass
        time.sleep(0.3)

        res = run_select_region()

        try:
            self.window.show()
        except Exception:
            pass

        if res:
            self.region = res
            with open(REGION_PATH, "w", encoding="utf-8") as f:
                json.dump(res, f)
            self.push_log(f"选区完成: {res}", "info")
            return {"ok": True, "region": res}
        else:
            self.push_log("选区取消", "warn")
            return {"ok": False, "region": self.region}

    def verify_code(self, code):
        h = hashlib.sha256(code.encode("utf-8")).hexdigest()
        expected = self._rebuild_hash()
        return bool(expected) and h == expected
    
    def start_click(self, override_cfg):
        # 前端传回最新的配置
        if override_cfg:
            self.cfg.update(override_cfg)
            save_config(self.cfg)

        if not self.region:
            return {"ok": False, "error": "请先选区"}

        # 邀请码
        if self.cfg["target_total_time"] < self.TARGET_TIME_LIMIT:
            stored = self.cfg.get("_meta_v3", "")
            expected_unlock = hashlib.sha256(
                (self._rebuild_hash() + self._SALT).encode()
            ).hexdigest()
            if stored != expected_unlock:
                return {"ok": False, "need_code": True}

        # 模板包
        packs = list_template_packs()
        if not packs:
            return {"ok": False, "error": "未找到任何模板包"}
        name = self.cfg.get("template_pack_name", "")
        template_dir = None
        for p in packs:
            if p["name"] == name:
                template_dir = p["dir"]
                break
        if not template_dir:
            template_dir = packs[0]["dir"]

        # 隐藏主窗口
        try:
            self.window.hide()
        except Exception:
            pass

        worker = ClickWorker(self.cfg, self.region, template_dir,
                             lambda msg, cat="info": self.push_log(msg, cat))

        def run():
            worker.run()
            # 完成后恢复主窗口
            try:
                self.window.show()
            except Exception:
                pass
            if self.window:
                self.window.evaluate_js("window.onClickFinished()")

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True}

    def unlock_with_code(self, code):
        h = hashlib.sha256(code.encode("utf-8")).hexdigest()
        expected = self._rebuild_hash()
        if expected and h == expected:
            self.cfg["_meta_v3"] = hashlib.sha256(
                (self._rebuild_hash() + self._SALT).encode()
            ).hexdigest()
            save_config(self.cfg)
            self.push_log("邀请码已记住，下次无需再输入。", "success")
            return {"ok": True}
        return {"ok": False, "error": "邀请码无效"}


# ============ 入口 ============
def run_web():
    import webview
    api = Api()
    index_path = os.path.join(WEB_DIR, "index.html")
    window = webview.create_window(
        "舒尔特方格自动点击器",
        index_path,
        js_api=api,
        width=920,
        height=760,
        min_size=(720, 560),
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    run_web()