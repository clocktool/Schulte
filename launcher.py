import os
import sys
import ctypes

# DPI 感知（tkinter 版要用）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def main():
    # 1) 尝试用高级版（pywebview）
    try:
        from backend_web import run_web
        run_web()
        return
    except Exception as e:
        # 高级版失败 → 打印错误，然后降级
        print(f"[launcher] 高级版启动失败: {e}")
        import traceback
        traceback.print_exc()

    # 2) 降级到兼容版（tkinter）
    try:
        print("[launcher] 降级到兼容版（tkinter）")
        from backend_lite import run_lite
        run_lite()
    except Exception as e:
        import traceback
        print(f"[launcher] 兼容版也失败: {e}")
        traceback.print_exc()
        # 3) 都失败 → 弹出错误提示
        try:
            import tkinter.messagebox as mb
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            mb.showerror("启动失败", f"程序无法启动：\n{e}")
            root.destroy()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()