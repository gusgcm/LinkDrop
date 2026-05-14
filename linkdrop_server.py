import os
import sys
import json
import time
import shutil
import hashlib
import logging
import threading
import subprocess
import socket
import base64
import mimetypes
import ctypes
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, IntVar, Checkbutton
import tkinter.font as tkfont
import winreg
from collections import deque

try:
    import pyperclip
    CLIPBOARD_OK = True
except ImportError:
    CLIPBOARD_OK = False

try:
    from plyer import notification
    NOTIFY_OK = True
except ImportError:
    NOTIFY_OK = False

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

def resource_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

APP_VERSION   = "1.0.1"
DEFAULT_PORT  = 8765

HOME_DIR      = Path(os.path.expanduser("~"))
CONFIG_FOLDER = HOME_DIR / ".linkdrop"
CONFIG_FILE   = CONFIG_FOLDER / "config.json"
SHARE_FOLDER  = HOME_DIR / "LinkDrop"
LOG_FILE      = CONFIG_FOLDER / "server.log"

for p in [CONFIG_FOLDER, SHARE_FOLDER]:
    if not os.path.exists(str(p)):
        try:
            os.makedirs(str(p))
        except Exception:
            pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("linkdrop")

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def check_auth(headers):
    auth = headers.get("X-LinkDrop-Auth", "")
    return auth == hash_password(cfg["password"])

class Config:
    _defaults = {
        "password":    "linkdrop123",
        "port":        DEFAULT_PORT,
        "host":        "0.0.0.0",
        "share_path":  str(SHARE_FOLDER),
        "autostart":   False,
        "systray":     False,
        "notify":      True,
        "clipboard_sync": True,
    }

    def __init__(self):
        self._data = dict(self._defaults)
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(str(CONFIG_FILE), "r") as f:
                    self._data.update(json.load(f))
            except Exception:
                pass

    def save(self):
        with open(str(CONFIG_FILE), "w") as f:
            json.dump(self._data, f, indent=2)

    def __getitem__(self, k): return self._data.get(k, self._defaults.get(k))
    def __setitem__(self, k, v): self._data[k] = v
    def get(self, k, default=None): return self._data.get(k, self._defaults.get(k, default))

cfg = Config()

def unique_path_under_share(filename):
    share = Path(cfg["share_path"])
    name = Path(filename).name
    dest = share / name
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    for idx in range(1, 10000):
        cand = share / "{0}_{1}{2}".format(stem, idx, suffix)
        if not cand.exists():
            return cand
    return dest

def copy_tree_into_share(src_dir, dst_dir):
    src_dir = os.path.abspath(src_dir)
    dst_dir = os.path.abspath(dst_dir)
    if not os.path.isdir(src_dir):
        return 0, ["Origem nao e pasta: {0}".format(src_dir)]
    errs = []
    nfiles = 0
    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        if rel in (".", os.curdir):
            target_root = dst_dir
        else:
            target_root = os.path.join(dst_dir, rel)
        if not os.path.isdir(target_root):
            try:
                os.makedirs(target_root)
            except Exception as ex:
                errs.append("{0}: {1}".format(target_root, ex))
                continue
        for fn in files:
            sp = os.path.join(root, fn)
            dp = os.path.join(target_root, fn)
            try:
                shutil.copy2(sp, dp)
                nfiles += 1
            except Exception as ex:
                errs.append("{0}: {1}".format(sp, ex))
    return nfiles, errs

def import_local_path_to_share(src_path):
    src_path = os.path.abspath(src_path)
    base = os.path.basename(src_path.rstrip(os.sep))
    if not base:
        return "skip", "", ["caminho invalido"]
    dst = unique_path_under_share(base)
    dst_str = str(dst)
    try:
        if os.path.isfile(src_path):
            shutil.copy2(src_path, dst_str)
            return "file", dst.name, []
        if os.path.isdir(src_path):
            os.makedirs(dst_str)
            nfiles, errs = copy_tree_into_share(src_path, dst_str)
            if not nfiles and errs:
                try:
                    os.rmdir(dst_str)
                except Exception:
                    pass
                return "skip", "", errs
            return "dir", dst.name, errs
    except Exception as ex:
        return "skip", "", [str(ex)]
    return "skip", "", ["nao e arquivo nem pasta"]

class LinkDropHandler(BaseHTTPRequestHandler):
    gui_callback = None

    def log_message(self, fmt, *args):
        log.info("HTTP {0} - {1}".format(self.address_string(), fmt % args))

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "application/octet-stream"
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", size)
        self.send_header("Content-Disposition", 'attachment; filename="{0}"'.format(path.name))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(str(path), "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _notify_gui(self, event):
        if self.gui_callback:
            self.gui_callback(event)

    def _share_path(self):
        return Path(cfg["share_path"])

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-LinkDrop-Auth, Content-Type, X-Filename")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        if path == "/ping":
            self._send_json(200, {"status": "ok", "version": APP_VERSION, "name": socket.gethostname()})
            return
        if not check_auth(self.headers):
            self._send_json(401, {"error": "Unauthorized"})
            return
        if path == "/files":
            items = []
            for p in sorted(self._share_path().iterdir()):
                items.append({
                    "name":     p.name,
                    "size":     p.stat().st_size,
                    "is_dir":   p.is_dir(),
                    "modified": p.stat().st_mtime,
                })
            self._send_json(200, {"files": items})
            return
        if path.startswith("/files/"):
            fname = unquote(path[7:])
            fpath = self._share_path() / fname
            if fpath.exists() and fpath.is_file():
                self._send_file(fpath)
            else:
                self._send_json(404, {"error": "File not found"})
            return
        if path == "/clipboard":
            text = ""
            if CLIPBOARD_OK:
                try: text = pyperclip.paste()
                except Exception: pass
            self._send_json(200, {"text": text, "timestamp": time.time()})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        if not check_auth(self.headers):
            self._send_json(401, {"error": "Unauthorized"})
            return
        if path == "/upload":
            default_name = "file_{0}".format(int(time.time()))
            fname = unquote(self.headers.get("X-Filename", default_name))
            fname = Path(fname).name
            dest  = unique_path_under_share(fname)
            body  = self._read_body()
            with open(str(dest), "wb") as f: f.write(body)
            saved = dest.name
            log.info("Uploaded: {0} ({1} bytes)".format(saved, len(body)))
            self._notify_gui({"type": "upload", "name": saved, "size": len(body), "time": datetime.now().isoformat()})
            self._send_json(200, {"status": "ok", "name": saved})
            return
        if path == "/text":
            try:
                data = json.loads(self._read_body().decode("utf-8"))
                text = data.get("text", "")
            except Exception:
                text = self._read_body().decode("utf-8", errors="replace")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = "text_{0}.txt".format(ts)
            with open(str(self._share_path() / fname), "w", encoding="utf-8") as f: f.write(text)
            self._notify_gui({"type": "text", "content": text, "name": fname, "time": datetime.now().isoformat()})
            self._send_json(200, {"status": "ok"})
            return
        if path == "/clipboard":
            try:
                data = json.loads(self._read_body().decode("utf-8"))
                text = data.get("text", "")
            except Exception:
                text = self._read_body().decode("utf-8", errors="replace")
            if CLIPBOARD_OK and cfg["clipboard_sync"]:
                try: pyperclip.copy(text)
                except Exception: pass
            self._notify_gui({"type": "clipboard", "content": text, "time": datetime.now().isoformat()})
            if NOTIFY_OK and cfg["notify"]:
                try: notification.notify(title="LinkDrop - Clipboard", message=text[:80], timeout=4)
                except Exception: pass
            self._send_json(200, {"status": "ok"})
            return
        if path == "/notify":
            try: data = json.loads(self._read_body().decode("utf-8"))
            except Exception: data = {}
            title, msg = data.get("title", "Android Notification"), data.get("message", "")
            self._notify_gui({"type": "notification", "title": title, "content": msg, "time": datetime.now().isoformat()})
            if NOTIFY_OK and cfg["notify"]:
                try: notification.notify(title="Tel: {0}".format(title), message=msg, app_name="LinkDrop", timeout=5)
                except Exception: pass
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "Not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        if not check_auth(self.headers):
            self._send_json(401, {"error": "Unauthorized"})
            return
        if path.startswith("/files/"):
            fname = unquote(path[7:])
            fpath = Path(cfg["share_path"]) / Path(fname).name
            if fpath.exists():
                try:
                    if fpath.is_dir(): shutil.rmtree(str(fpath))
                    else: os.remove(str(fpath))
                    self._notify_gui({"type": "delete", "name": fname, "time": datetime.now().isoformat()})
                    self._send_json(200, {"status": "deleted"})
                except Exception: self._send_json(500, {"error": "Could not delete"})
            else: self._send_json(404, {"error": "File not found"})
            return
        self._send_json(404, {"error": "Not found"})

class ServerThread(threading.Thread):
    def __init__(self, port):
        threading.Thread.__init__(self)
        self.daemon = True
        self.port   = port
        self.server = None
        self.error  = None
    def run(self):
        try:
            self.server = HTTPServer(("0.0.0.0", self.port), LinkDropHandler)
            log.info("Server listening on all interfaces at port {0}".format(self.port))
            self.server.serve_forever()
        except Exception as e:
            self.error = str(e)
            log.error("Server error: {0}".format(e))
    def stop(self):
        if self.server: self.server.shutdown()

# --- GUI ---
DARK_BG, PANEL_BG, CARD_BG = "#0d1117", "#161b22", "#1c2128"
ACCENT, ACCENT2, TEXT_MAIN = "#00d4aa", "#0099ff", "#e6edf3"
TEXT_DIM, RED, GREEN, BORDER = "#8b949e", "#f85149", "#3fb950", "#30363d"

class LinkDropGUI:
    def __init__(self, root):
        self.root = root
        self.server_thread = None
        self.running = False
        self._activity_log = []
        self._is_dragging = False 

        self.automation_var  = IntVar()
        self.systray_var     = IntVar()
        self.stop_automation = threading.Event()
        self._tray_active    = False
        self._tray_hwnd      = None
        self._tray_thread    = None
        self._hicon_small    = None
        self._hicon_large    = None

        self._ui_queue = deque()
        self._ui_lock  = threading.Lock()

        self._setup_root()
        self._build_ui()
        self._load_checkbox_state()
        self._start_server_auto()

        LinkDropHandler.gui_callback = self._on_event
        self._refresh_files()
        self.root.after(3000, self._auto_refresh)
        self.root.after(80, self._pump_ui_queue)

    def _setup_root(self):
        self.root.title("LinkDrop")
        self.root.geometry("980x680")
        self.root.minsize(820, 560)
        self.root.configure(bg=DARK_BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._set_window_icon)
        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("TFrame", background=DARK_BG)
        style.configure("TLabel", background=DARK_BG, foreground=TEXT_MAIN, font=("Tahoma", 10))
        style.configure("TButton", background=ACCENT, foreground=DARK_BG, font=("Tahoma", 9, "bold"), borderwidth=0, relief="flat", padding=(10, 6))
        style.map("TButton", background=[("active", "#00b894"), ("disabled", "#3d4450")])
        style.configure("Treeview", background=CARD_BG, foreground=TEXT_MAIN, fieldbackground=CARD_BG, rowheight=26, font=("Tahoma", 9))
        style.configure("Treeview.Heading", background=PANEL_BG, foreground=TEXT_DIM, font=("Tahoma", 9, "bold"))
        style.map("Treeview", background=[("selected", "#264f78")])
        style.configure("TEntry", fieldbackground=CARD_BG, foreground=TEXT_MAIN, insertcolor=TEXT_MAIN, borderwidth=1, relief="solid")
        style.configure("TNotebook", background=DARK_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_BG, foreground=TEXT_DIM, padding=(14, 8), font=("Tahoma", 10))
        style.map("TNotebook.Tab", background=[("selected", CARD_BG)], foreground=[("selected", ACCENT)])

    def _set_window_icon(self):
        try:
            u32 = ctypes.windll.user32
            LR_LOADFROMFILE, LR_SHARED, LR_DEFAULTSIZE = 0x00000010, 0x00008000, 0x00000040
            IMAGE_ICON, IDI_APPLICATION, WM_SETICON = 1, 32512, 0x0080
            ico_path = resource_path("linkdrop.ico")
            if os.path.exists(ico_path):
                try: self.root.iconbitmap(ico_path)
                except Exception: pass
                self._hicon_small = u32.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                self._hicon_large = u32.LoadImageW(None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            if not self._hicon_small:
                self._hicon_small = u32.LoadImageW(None, ctypes.c_wchar_p(IDI_APPLICATION), IMAGE_ICON, 0, 0, LR_SHARED | LR_DEFAULTSIZE)
            if not self._hicon_large: self._hicon_large = self._hicon_small
            def _apply_taskbar():
                try:
                    hwnd = u32.GetParent(self.root.winfo_id())
                    if hwnd == 0: self.root.after(150, _apply_taskbar); return
                    if self._hicon_small: u32.SendMessageW(hwnd, WM_SETICON, 0, ctypes.c_long(self._hicon_small))
                    if self._hicon_large: u32.SendMessageW(hwnd, WM_SETICON, 1, ctypes.c_long(self._hicon_large))
                except Exception: pass
            self.root.after(200, _apply_taskbar)
            try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LinkDrop.Server.Application")
            except Exception: pass
        except Exception: pass

    def _pump_ui_queue(self):
        try:
            with self._ui_lock:
                batch = [self._ui_queue.popleft() for _ in range(min(len(self._ui_queue), 30))]
            for msg_type, payload in batch:
                if msg_type == "refresh": self._refresh_files()
        except Exception: pass
        self.root.after(80, self._pump_ui_queue)

    def toggle_automation(self):
        cfg["autostart"] = (self.automation_var.get() == 1)
        self._set_autostart(cfg["autostart"])
        self._log_event({"type": "info", "content": "Automacao " + ("ativada" if cfg["autostart"] else "desativada"), "time": datetime.now().isoformat()})
        cfg.save()

    def _set_autostart(self, enable):
        key_path, app_name = r"Software\Microsoft\Windows\CurrentVersion\Run", "LinkDrop"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enable:
                exe_path = os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, '"{0}"'.format(exe_path))
            else:
                try: winreg.DeleteValue(key, app_name)
                except OSError: pass
            winreg.CloseKey(key)
        except Exception as e: log.warning("Erro autostart: {0}".format(e))

    _WM_TRAY, _TRAY_ID = 0x8002, 2
    def toggle_systray(self):
        cfg["systray"] = bool(self.systray_var.get())
        cfg.save()

    def _hide_to_tray(self):
        if self._tray_active: return
        self._tray_active = True
        self.root.withdraw()
        if self._tray_thread is None or not self._tray_thread.is_alive():
            t = threading.Thread(target=self._tray_loop, daemon=True)
            self._tray_thread = t
            t.start()

    def _show_from_tray(self):
        self._stop_tray_loop()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _tray_loop(self):
        u32, s32, k32 = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
        WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_int)
        WM_DESTROY, WM_TRAY, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0002, self._WM_TRAY, 0x0203, 0x0205
        NIM_ADD, NIM_DELETE, NIF_MESSAGE, NIF_ICON, NIF_TIP = 0, 2, 1, 2, 4
        TPM_RETURNCMD, TPM_RIGHTBUTTON, MF_STRING, IDM_RESTORE, IDM_QUIT = 0x0100, 0x0002, 0x0000, 2001, 2002

        class WNDCLASSEX(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROCTYPE), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p), ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p), ("lpszMenuName", ctypes.c_wchar_p), ("lpszClassName", ctypes.c_wchar_p), ("hIconSm", ctypes.c_void_p)]
        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("hWnd", ctypes.c_void_p), ("uID", ctypes.c_uint), ("uFlags", ctypes.c_uint), ("uCallbackMessage", ctypes.c_uint), ("hIcon", ctypes.c_void_p), ("szTip", ctypes.c_wchar * 128)]
        class POINT(ctypes.Structure): _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        class MSG(ctypes.Structure): _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint), ("wParam", ctypes.c_void_p), ("lParam", ctypes.c_void_p), ("time", ctypes.c_ulong), ("pt", POINT)]

        cls_name, hinstance = "LinkDropTray_{0}".format(id(self)), k32.GetModuleHandleW(None)
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAY:
                evt = lparam & 0xFFFF
                if evt == WM_LBUTTONDBLCLK: self.root.after(0, self._show_from_tray)
                elif evt == WM_RBUTTONUP:
                    pt = POINT(); u32.GetCursorPos(ctypes.byref(pt))
                    hmenu = u32.CreatePopupMenu()
                    u32.AppendMenuW(hmenu, MF_STRING, IDM_RESTORE, "Restaurar")
                    u32.AppendMenuW(hmenu, MF_STRING, IDM_QUIT, "Sair")
                    u32.SetForegroundWindow(hwnd)
                    cmd = u32.TrackPopupMenu(hmenu, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
                    u32.DestroyMenu(hmenu)
                    if cmd == IDM_RESTORE: self.root.after(0, self._show_from_tray)
                    elif cmd == IDM_QUIT: self.root.after(0, self._on_close)
                return 0
            return u32.DefWindowProcW(hwnd, msg, wparam, lparam)

        wnd_proc_cb = WNDPROCTYPE(wnd_proc)
        try:
            wc = WNDCLASSEX(cbSize=ctypes.sizeof(WNDCLASSEX), lpfnWndProc=wnd_proc_cb, hInstance=hinstance, lpszClassName=cls_name)
            u32.RegisterClassExW(ctypes.byref(wc))
            hwnd = u32.CreateWindowExW(0, cls_name, "LinkDrop Tray", 0, 0, 0, 0, 0, 0, 0, hinstance, None)
            self._tray_hwnd, hicon = hwnd, (self._hicon_small or 0)
            nid = NOTIFYICONDATA(cbSize=ctypes.sizeof(NOTIFYICONDATA), hWnd=hwnd, uID=self._TRAY_ID, uFlags=NIF_MESSAGE|NIF_ICON|NIF_TIP, uCallbackMessage=WM_TRAY, hIcon=hicon, szTip="LinkDrop Server")
            s32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
            msg_struct = MSG()
            while self._tray_active:
                if u32.GetMessageW(ctypes.byref(msg_struct), hwnd, 0, 0) <= 0: break
                u32.TranslateMessage(ctypes.byref(msg_struct)); u32.DispatchMessageW(ctypes.byref(msg_struct))
            s32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            u32.DestroyWindow(hwnd); u32.UnregisterClassW(cls_name, hinstance)
        except Exception as ex: log.warning("Erro tray_loop: {0}".format(ex))
        finally: self._tray_active = False

    def _stop_tray_loop(self):
        self._tray_active = False
        try:
            if self._tray_hwnd: ctypes.windll.user32.PostMessageW(self._tray_hwnd, 0x0012, 0, 0)
        except Exception: pass

    def _load_checkbox_state(self):
        if cfg["autostart"]: self.automation_var.set(1)
        if cfg.get("systray", False):
            self.systray_var.set(1)
            self.root.after(400, self._hide_to_tray)

    def _on_unmap(self, event):
        if event.widget is self.root and self.systray_var.get() == 1 and not self._tray_active:
            self.root.after(50, self._hide_to_tray)

    def _build_ui(self):
        header = tk.Frame(self.root, bg=PANEL_BG, height=56)
        header.pack(fill="x", side="top"); header.pack_propagate(False)
        tk.Label(header, text="LinkDrop", bg=PANEL_BG, fg=ACCENT, font=("Tahoma", 16, "bold")).pack(side="left", padx=18)
        tk.Label(header, text="v{0}".format(APP_VERSION), bg=PANEL_BG, fg=TEXT_DIM, font=("Tahoma", 9)).pack(side="left", padx=2)
        self.status_dot = tk.Label(header, text="O", bg=PANEL_BG, fg=RED, font=("Tahoma", 16))
        self.status_dot.pack(side="right", padx=6)
        self.status_lbl = tk.Label(header, text="Parado", bg=PANEL_BG, fg=RED, font=("Tahoma", 10))
        self.status_lbl.pack(side="right")
        self.ip_lbl = tk.Label(header, text="", bg=PANEL_BG, fg=TEXT_DIM, font=("Courier", 9))
        self.ip_lbl.pack(side="right", padx=20)
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        main = ttk.Frame(self.root); main.pack(fill="both", expand=True)
        self._build_sidebar(main)
        self._build_notebook(main)

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=PANEL_BG, width=240)
        sidebar.pack(side="left", fill="y"); sidebar.pack_propagate(False)
        tk.Frame(sidebar, bg=BORDER, width=1).pack(side="right", fill="y")
        tk.Label(sidebar, text="SERVER", bg=PANEL_BG, fg=TEXT_DIM, font=("Tahoma", 8, "bold")).pack(anchor="w", padx=16, pady=6)
        self.btn_toggle = tk.Button(sidebar, text="> Ativar Compartilhamento", bg=ACCENT, fg=DARK_BG, font=("Tahoma", 10, "bold"), bd=0, relief="flat", cursor="hand2", activebackground="#00b894", activeforeground=DARK_BG, command=self._toggle_server)
        self.btn_toggle.pack(fill="x", padx=16, pady=(4, 12))
        for attr, label, color in [("lbl_files_count", "Arquivos Compartilhados", ACCENT), ("lbl_events_count", "Eventos hoje", ACCENT2)]:
            card = tk.Frame(sidebar, bg=CARD_BG, bd=0); card.pack(fill="x", padx=12, pady=4)
            tk.Frame(card, bg=color, width=3).pack(side="left", fill="y")
            inner = tk.Frame(card, bg=CARD_BG); inner.pack(side="left", padx=10, pady=8, fill="x", expand=True)
            tk.Label(inner, text=label, bg=CARD_BG, fg=TEXT_DIM, font=("Tahoma", 8)).pack(anchor="w")
            lbl = tk.Label(inner, text="0", bg=CARD_BG, fg=color, font=("Tahoma", 20, "bold"))
            lbl.pack(anchor="w"); setattr(self, attr, lbl)
        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=12, pady=12)
        tk.Label(sidebar, text="Envio Rápido", bg=PANEL_BG, fg=TEXT_DIM, font=("Tahoma", 8, "bold")).pack(anchor="w", padx=16, pady=6)
        self.quick_text = tk.Text(sidebar, height=4, bg=CARD_BG, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, bd=0, padx=8, pady=6, font=("Tahoma", 9), wrap="word", relief="flat")
        self.quick_text.pack(fill="x", padx=12)
        tk.Button(sidebar, text="Enviar texto ao celular", bg="#1a3a5c", fg=ACCENT2, font=("Tahoma", 9, "bold"), bd=0, relief="flat", cursor="hand2", activebackground="#1e4a6e", command=self._send_text_to_phone).pack(fill="x", padx=12, pady=(4, 12))
        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=12, pady=4)
        tk.Label(sidebar, text="Diretório compartilhado", bg=PANEL_BG, fg=TEXT_DIM, font=("Tahoma", 8, "bold")).pack(anchor="w", padx=16, pady=6)
        self.path_lbl = tk.Label(sidebar, text=cfg["share_path"], bg=PANEL_BG, fg=TEXT_DIM, font=("Tahoma", 8), wraplength=210, anchor="w", justify="left")
        self.path_lbl.pack(anchor="w", padx=16)
        tk.Button(sidebar, text="Abrir pasta", bg=CARD_BG, fg=TEXT_MAIN, font=("Tahoma", 9), bd=0, relief="flat", cursor="hand2", command=lambda: os.startfile(cfg["share_path"])).pack(fill="x", padx=12, pady=4)
        tk.Button(sidebar, text="Alterar pasta compartilhada", bg=CARD_BG, fg=TEXT_DIM, font=("Tahoma", 9), bd=0, relief="flat", cursor="hand2", command=self._change_folder).pack(fill="x", padx=12, pady=(0, 4))

    def _build_notebook(self, parent):
        nb = ttk.Notebook(parent); self._main_notebook = nb
        nb.pack(fill="both", expand=True, padx=0, pady=0)
        self._build_files_tab(nb)
        self._build_activity_tab(nb)
        self._build_clipboard_tab(nb)
        self._build_settings_tab(nb)

    def _build_files_tab(self, nb):
        frame = ttk.Frame(nb); nb.add(frame, text="  Arquivos  ")
        toolbar = tk.Frame(frame, bg=DARK_BG); toolbar.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(toolbar, text="Arquivos na pasta compartilhada", bg=DARK_BG, fg=TEXT_MAIN, font=("Tahoma", 12, "bold")).pack(side="left")
        tk.Button(toolbar, text="Adicionar Pastas", bg="#1a3a5c", fg=ACCENT2, font=("Tahoma", 9, "bold"), bd=0, relief="flat", cursor="hand2", command=self._dialog_add_folder).pack(side="right", padx=3)
        tk.Button(toolbar, text="Adicionar Arquivos", bg=ACCENT, fg=DARK_BG, font=("Tahoma", 9, "bold"), bd=0, relief="flat", cursor="hand2", command=self._dialog_add_files).pack(side="right", padx=3)
        for txt, cmd, col in [("Refresh", self._refresh_files, CARD_BG), ("Delete", self._delete_file, "#3d1f1f")]:
            tk.Button(toolbar, text=txt, bg=col, fg=TEXT_MAIN, font=("Tahoma", 9, "bold"), bd=0, relief="flat", cursor="hand2", command=cmd).pack(side="right", padx=3)
        self._drop_hint = tk.Label(frame, text="Arraste arquivos aqui ou use os botões acima para adicionar ao compartilhamento", bg="#1a2a1a", fg=GREEN, font=("Tahoma", 9), pady=6)
        self._drop_hint.pack(fill="x", padx=12, pady=(0, 2))
        cols = ("name", "size", "modified", "type")
        self.file_tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        for col, lbl, w in [("name", "Nome", 300), ("size", "Tamanho", 90), ("modified", "Data de modificacao", 150), ("type", "Extensao", 80)]:
            self.file_tree.heading(col, text=lbl); self.file_tree.column(col, width=w, minwidth=60)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=vsb.set)
        self.file_tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=4)
        vsb.pack(side="left", fill="y", pady=4)

        self.file_tree.bind("<ButtonPress-1>", self._on_drag_select_start)
        self.file_tree.bind("<B1-Motion>", self._on_drag_select_motion)
        self.file_tree.bind("<ButtonRelease-1>", self._on_drag_release)
        self.file_tree.bind("<Double-1>",  self._open_file)
        self.file_tree.bind("<Button-3>",  self._show_context_menu)
        self._drag_start_item = None
        self._drag_start_y = 0
        self._setup_drag_and_drop()

    def _on_drag_select_start(self, event):
        self._is_dragging = True 
        item = self.file_tree.identify_row(event.y)
        self._drag_start_y = event.y
        self._drag_start_item = item
        
        if not item and not (event.state & 0x0004):
            self.file_tree.selection_set([])
        
        if item: self.file_tree.focus(item)

    def _on_drag_select_motion(self, event):
        all_items = self.file_tree.get_children()
        if not all_items: return

        y1, y2 = self._drag_start_y, event.y
        top, bottom = (y1, y2) if y1 <= y2 else (y2, y1)
        
        selection = []
        if self._drag_start_item:
            item_end = self.file_tree.identify_row(event.y)
            if item_end:
                try:
                    idx_start = all_items.index(self._drag_start_item)
                    idx_end = all_items.index(item_end)
                    s, e = (idx_start, idx_end) if idx_start <= idx_end else (idx_end, idx_start)
                    selection = all_items[s : e + 1]
                except ValueError: pass
        else:
            for i in all_items:
                bbox = self.file_tree.bbox(i)
                if bbox: # bbox = (x, y, w, h)
                    if (bbox[1] + bbox[3]) >= top and bbox[1] <= bottom:
                        selection.append(i)

        if selection:
            if event.state & 0x0004: 
                self.file_tree.selection_add(selection)
            else:
                self.file_tree.selection_set(selection)

    def _on_drag_release(self, event):
        self._is_dragging = False 

    def _setup_drag_and_drop(self):
        self._dnd_installed = False
        self.root.after(500, self._register_win32_drop_targets)

    def _get_toplevel_hwnd(self):
        try:
            rid = self.root.winfo_id()
            if not rid: return 0
            return ctypes.windll.user32.GetAncestor(ctypes.c_void_p(int(rid)), 2)
        except: return 0

    def _register_win32_drop_targets(self):
        if self._dnd_installed: return
        hwnd = self._get_toplevel_hwnd()
        if not hwnd: self.root.after(500, self._register_win32_drop_targets); return
        if self._install_drop_hook(hwnd): self._dnd_installed = True
        else: self.root.after(500, self._register_win32_drop_targets)

    def _install_drop_hook(self, hwnd_val):
        try:
            u32, s32 = ctypes.windll.user32, ctypes.windll.shell32
            is64 = (ctypes.sizeof(ctypes.c_void_p) == 8)
            PTR_T, UPTR_T = (ctypes.c_int64, ctypes.c_uint64) if is64 else (ctypes.c_int32, ctypes.c_uint32)
            try: GetWL, SetWL = u32.GetWindowLongPtrW, u32.SetWindowLongPtrW
            except AttributeError: GetWL, SetWL = u32.GetWindowLongW, u32.SetWindowLongW
            
            old_proc = GetWL(PTR_T(hwnd_val), -4)
            if not old_proc: return False
            self._dnd_old_proc, self._dnd_hwnd = old_proc, hwnd_val

            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == 0x0233: # WM_DROPFILES
                    try:
                        num = s32.DragQueryFileW(UPTR_T(wparam), 0xFFFFFFFF, None, 0)
                        paths = []
                        for i in range(num):
                            buf = ctypes.create_unicode_buffer(512)
                            s32.DragQueryFileW(UPTR_T(wparam), i, buf, 512)
                            if buf.value: paths.append(buf.value)
                        if paths: self.root.after(10, lambda: self._import_paths_list(paths))
                    finally: s32.DragFinish(UPTR_T(wparam))
                    return 0
                return u32.CallWindowProcW(PTR_T(self._dnd_old_proc), PTR_T(hwnd), ctypes.c_uint(msg), UPTR_T(wparam), PTR_T(lparam))

            self._dnd_new_proc = ctypes.WINFUNCTYPE(PTR_T, PTR_T, ctypes.c_uint, UPTR_T, PTR_T)(wnd_proc)
            s32.DragAcceptFiles(PTR_T(hwnd_val), 1)
            SetWL(PTR_T(hwnd_val), -4, PTR_T(ctypes.cast(self._dnd_new_proc, ctypes.c_void_p).value))
            return True
        except: return False

    def _teardown_win32_drop_targets(self):
        if not self._dnd_hwnd or not self._dnd_old_proc: return
        try:
            u32 = ctypes.windll.user32
            is64 = (ctypes.sizeof(ctypes.c_void_p) == 8)
            PTR_T = ctypes.c_int64 if is64 else ctypes.c_int32
            try: SetWL = u32.SetWindowLongPtrW
            except AttributeError: SetWL = u32.SetWindowLongW
            SetWL(PTR_T(self._dnd_hwnd), -4, PTR_T(self._dnd_old_proc))
            ctypes.windll.shell32.DragAcceptFiles(PTR_T(self._dnd_hwnd), 0)
        except: pass

    def _import_paths_list(self, paths):
        added = 0
        for p in paths:
            t, d, e = import_local_path_to_share(p)
            if t in ("file", "dir"):
                added += 1
                sz = os.path.getsize(p) if os.path.isfile(p) else 0
                self._log_event({"type": "upload", "name": d, "content": "Drag & Drop: "+d, "size": sz, "time": datetime.now().isoformat()})
        if added > 0: self._refresh_files()

    def _show_context_menu(self, event):
        row = self.file_tree.identify_row(event.y)
        if row: self.file_tree.selection_set(row)
        menu = tk.Menu(self.root, tearoff=0, bg=CARD_BG, fg=TEXT_MAIN, activebackground="#264f78", activeforeground=TEXT_MAIN, font=("Tahoma", 9), bd=1, relief="solid")
        if row:
            menu.add_command(label="Abrir", command=self._open_file)
            menu.add_command(label="Abrir como administrador", command=self._open_as_admin)
            menu.add_command(label="Abrir local do arquivo", command=self._reveal_in_explorer)
            menu.add_separator()
            menu.add_command(label="Deletar", command=self._delete_file, foreground=RED, activeforeground=RED)
        else:
            menu.add_command(label="Adicionar arquivos...", command=self._dialog_add_files)
            menu.add_command(label="Adicionar pasta...", command=self._dialog_add_folder)
            menu.add_separator()
            menu.add_command(label="Atualizar lista", command=self._refresh_files)
            menu.add_command(label="Abrir pasta share", command=lambda: os.startfile(cfg["share_path"]))
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()

    def _open_as_admin(self):
        sel = self.file_tree.selection()
        if sel:
            try: ctypes.windll.shell32.ShellExecuteW(None, "runas", self.file_tree.item(sel[0], "tags")[0], None, None, 1)
            except Exception as e: messagebox.showerror("Erro", str(e))

    def _reveal_in_explorer(self):
        sel = self.file_tree.selection()
        if not sel: return
        fpath = Path(cfg["share_path"]) / self.file_tree.item(sel[0], "values")[0]
        if fpath.exists():
            try:
                s32 = ctypes.windll.shell32
                pf, pi = s32.ILCreateFromPathW(str(fpath.parent)), s32.ILCreateFromPathW(str(fpath))
                if pf and pi:
                    s32.SHOpenFolderAndSelectItems(pf, 1, (ctypes.c_void_p * 1)(pi), 0)
                    s32.ILFree(pf); s32.ILFree(pi)
                else: raise Exception()
            except: subprocess.Popen(["explorer", "/select," + str(fpath)])

    def _build_activity_tab(self, nb):
        frame = ttk.Frame(nb); nb.add(frame, text="  Registro  ")
        h = tk.Frame(frame, bg=DARK_BG); h.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(h, text="Logs de atividades", bg=DARK_BG, fg=TEXT_MAIN, font=("Tahoma", 12, "bold")).pack(side="left")
        tk.Button(h, text="Limpar", bg=CARD_BG, fg=TEXT_DIM, bd=0, relief="flat", command=self._clear_log).pack(side="right")
        self.activity_box = scrolledtext.ScrolledText(frame, bg=CARD_BG, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, font=("Courier", 9), bd=0, padx=10, pady=8, state="disabled", wrap="word")
        self.activity_box.pack(fill="both", expand=True, padx=12, pady=4)
        for t, c in [("time", TEXT_DIM), ("upload", GREEN), ("text", ACCENT2), ("clip", ACCENT), ("notify", "#e8b100"), ("delete", RED), ("info", TEXT_DIM)]:
            self.activity_box.tag_config(t, foreground=c)

    def _build_clipboard_tab(self, nb):
        frame = ttk.Frame(nb); nb.add(frame, text="  Clipboard  ")
        h = tk.Frame(frame, bg=DARK_BG); h.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(h, text="Sinconização Clipboard", bg=DARK_BG, fg=TEXT_MAIN, font=("Tahoma", 12, "bold")).pack(side="left")
        r = tk.Frame(frame, bg=DARK_BG); r.pack(fill="x", padx=12, pady=4)
        tk.Button(r, text="Mostrar texto copiado do PC", bg=CARD_BG, fg=TEXT_MAIN, bd=0, command=self._load_pc_clipboard).pack(side="left", padx=3)
        tk.Button(r, text="Copiar texto ao clipboard do PC", bg=ACCENT, fg=DARK_BG, bd=0, font=("Tahoma", 9, "bold"), command=self._copy_clip_to_pc).pack(side="left", padx=3)
        tk.Label(frame, text="Último recebimento do celular:", bg=DARK_BG, fg=TEXT_DIM, font=("Tahoma", 9)).pack(anchor="w", padx=14, pady=(8, 2))
        self.clip_box = tk.Text(frame, height=8, bg=CARD_BG, fg=TEXT_MAIN, bd=0, padx=10, pady=8, font=("Tahoma", 10), wrap="word", relief="flat")
        self.clip_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_settings_tab(self, nb):
        frame = ttk.Frame(nb); nb.add(frame, text="  Configurações  ")
        canvas = tk.Canvas(frame, bg=DARK_BG, highlightthickness=0); canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=DARK_BG); canvas.create_window(0, 0, window=inner, anchor="nw")
        def sec(t): tk.Label(inner, text=t, bg=DARK_BG, fg=ACCENT, font=("Tahoma", 9, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
        def row(l, wf):
            r = tk.Frame(inner, bg=DARK_BG); r.pack(fill="x", padx=20, pady=3)
            tk.Label(r, text=l, bg=DARK_BG, fg=TEXT_MAIN, width=22, anchor="w", font=("Tahoma", 10)).pack(side="left"); wf(r)
        sec("SEGURANÇA"); self.pwd_var = tk.StringVar(value=cfg["password"])
        row("Senha", lambda r: ttk.Entry(r, textvariable=self.pwd_var, show="*", width=28).pack(side="left"))
        sec("NETWORK"); self.host_var = tk.StringVar(value=cfg["host"])
        row("IP / DDNS / VPN", lambda r: ttk.Entry(r, textvariable=self.host_var, width=28).pack(side="left"))
        self.port_var = tk.IntVar(value=cfg["port"])
        row("Porta", lambda r: ttk.Entry(r, textvariable=self.port_var, width=10).pack(side="left"))
        self.ip_info = tk.Label(inner, bg=DARK_BG, fg=TEXT_DIM, font=("Courier", 9), justify="left")
        self.ip_info.pack(anchor="w", padx=20, pady=10); self._update_ip_display()
        sec("EXTRAS"); self.notify_var, self.clip_var = tk.BooleanVar(value=cfg["notify"]), tk.BooleanVar(value=cfg["clipboard_sync"])
        for v, t in [(self.notify_var, "Mostrar notificações no Desktop"), (self.clip_var, "Sincronizar clipboard automaticamente")]:
            r = tk.Frame(inner, bg=DARK_BG); r.pack(fill="x", padx=20, pady=2)
            tk.Checkbutton(r, variable=v, text=t, bg=DARK_BG, fg=TEXT_MAIN, selectcolor=CARD_BG, font=("Tahoma", 10)).pack(side="left")
        for v, t, c in [(self.automation_var, "Iniciar com o Windows", self.toggle_automation), (self.systray_var, "Minimizar para Systray", self.toggle_systray)]:
            r = tk.Frame(inner, bg=DARK_BG); r.pack(fill="x", padx=20, pady=2)
            Checkbutton(r, variable=v, text=t, command=c, bg=DARK_BG, fg=TEXT_MAIN, selectcolor=CARD_BG, font=("Tahoma", 10)).pack(side="left")
        self.root.bind("<Unmap>", self._on_unmap)
        tk.Button(inner, text="Salvar configurações", bg=ACCENT, fg=DARK_BG, font=("Tahoma", 10, "bold"), bd=0, padx=16, pady=8, command=self._save_settings).pack(padx=20, pady=16, anchor="w")

    def _start_server_auto(self): self._start_server()
    def _start_server(self):
        if self.running: return
        self.server_thread = ServerThread(cfg["port"]) 
        self.server_thread.start()
        time.sleep(0.4)
        if self.server_thread.error:
            messagebox.showerror("LinkDrop", "Erro na porta {0}: {1}".format(cfg["port"], self.server_thread.error))
            return
        self.running = True
        self._set_status_running(True)
        self._log_event({"type": "info", "content": "Server started", "time": datetime.now().isoformat()})

    def _stop_server(self):
        if self.server_thread: self.server_thread.stop(); self.server_thread = None
        self.running = False; self._set_status_running(False)
        self._log_event({"type": "info", "content": "Server stopped", "time": datetime.now().isoformat()})

    def _toggle_server(self):
        if self.running: self._stop_server()
        else: self._start_server()

    def _set_status_running(self, on):
        c, t = (GREEN, "Rodando") if on else (RED, "Parado")
        self.status_dot.config(fg=c); self.status_lbl.config(fg=c, text=t)
        self.btn_toggle.config(text=("X Parar Compartilhamento" if on else "> Compartilhar"), bg=(RED if on else ACCENT), fg=("white" if on else DARK_BG))
        if on: self._update_ip_display()
        else: self.ip_lbl.config(text="")

    def _on_event(self, event): self.root.after(0, lambda: self._handle_event(event))
    def _handle_event(self, event):
        self._activity_log.append(event); self._log_event(event)
        if event.get("type") in ("upload", "text", "delete"): self._refresh_files()
        if event.get("type") == "clipboard":
            self.clip_box.delete("1.0", "end"); self.clip_box.insert("end", event.get("content", ""))
        cnt = len([e for e in self._activity_log if e.get("time", "").startswith(datetime.now().strftime("%Y-%m-%d"))])
        self.lbl_events_count.config(text=str(cnt))

    def _log_event(self, event):
        etype, ts, content = event.get("type", "info"), event.get("time", "")[:19].replace("T", " "), event.get("content", event.get("name", ""))
        tm, im = {"upload": "upload", "text": "text", "clipboard": "clip", "notification": "notify", "delete": "delete"}, {"upload": "UP", "text": "TXT", "clipboard": "CLP", "notification": "NOT", "delete": "DEL", "info": "INF"}
        self.activity_box.config(state="normal")
        self.activity_box.insert("end", "  {0}  ".format(ts), "time")
        self.activity_box.insert("end", "[{0}] {1}\n".format(im.get(etype, "*"), content[:80]), tm.get(etype, "info"))
        self.activity_box.see("end"); self.activity_box.config(state="disabled")

    def _clear_log(self):
        self.activity_box.config(state="normal"); self.activity_box.delete("1.0", "end"); self.activity_box.config(state="disabled"); self._activity_log.clear()

    def _refresh_files(self):
        if self._is_dragging: return
        
        share = Path(cfg["share_path"])
        cur_sel = [self.file_tree.item(i, "values")[0] for i in self.file_tree.selection() if self.file_tree.item(i, "values")]
        for row in self.file_tree.get_children(): self.file_tree.delete(row)
        items = sorted(share.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True) if share.exists() else []
        for p in items:
            stat = p.stat()
            sz = "-" if p.is_dir() else self._fmt_size(stat.st_size)
            mod = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            ext = p.suffix.lstrip(".").upper() or ("DIR" if p.is_dir() else "FILE")
            node = self.file_tree.insert("", "end", values=(p.name, sz, mod, ext), tags=(str(p),))
            if p.name in cur_sel: self.file_tree.selection_add(node)
        self.lbl_files_count.config(text=str(len(items)))

    def _auto_refresh(self):
        if self.running: self._refresh_files()
        self.root.after(5000, self._auto_refresh)

    def _open_file(self, _e=None):
        sel = self.file_tree.selection()
        if sel: os.startfile(self.file_tree.item(sel[0], "tags")[0])

    def _dialog_add_files(self):
        ps = filedialog.askopenfilenames(title="Selecionar Arquivos")
        if ps: self._import_paths_list(list(ps))

    def _dialog_add_folder(self):
        f = filedialog.askdirectory(title="Selecionar Pasta")
        if f: self._import_paths_list([f])

    def _delete_file(self):
        sel = self.file_tree.selection()
        if not sel: return
        names = [self.file_tree.item(i, "values")[0] for i in sel]
        if messagebox.askyesno("Delete", "Deletar {0} item(s)?".format(len(names))):
            for n in names:
                p = Path(cfg["share_path"]) / n
                try:
                    if p.is_dir(): shutil.rmtree(str(p))
                    else: os.remove(str(p))
                except: pass
            self._refresh_files()

    def _load_pc_clipboard(self):
        if CLIPBOARD_OK:
            self.clip_box.delete("1.0", "end"); self.clip_box.insert("end", pyperclip.paste())
        else: messagebox.showwarning("Clipboard", "pyperclip não instalado.")

    def _copy_clip_to_pc(self):
        text = self.clip_box.get("1.0", "end").strip()
        if CLIPBOARD_OK:
            try:
                pyperclip.copy(text)
            except Exception:
                pass
        messagebox.showinfo("Clipboard", "Texto copiado ao clipboard!")

    def _send_text_to_phone(self):
        txt = self.quick_text.get("1.0", "end").strip()
        if not txt: return
        fn = "from_pc_{0}.txt".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        with open(str(Path(cfg["share_path"]) / fn), "w", encoding="utf-8") as f: f.write(txt)
        self._refresh_files(); self.quick_text.delete("1.0", "end")

    def _save_settings(self):
        try:
            cfg["password"], cfg["host"], cfg["port"] = self.pwd_var.get(), self.host_var.get().strip(), int(self.port_var.get())
            cfg["notify"], cfg["clipboard_sync"] = self.notify_var.get(), self.clip_var.get()
            cfg.save(); self._update_ip_display()
            messagebox.showinfo("Saved", "Configurações salvas!")
        except: messagebox.showerror("Error", "Porta inválida.")

    def _change_folder(self):
        n = filedialog.askdirectory(initialdir=cfg["share_path"])
        if n: cfg["share_path"] = n; cfg.save(); self.path_lbl.config(text=n); self._refresh_files()

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"

    def _update_ip_display(self):
        rip = self._get_local_ip()
        conf_host = self.host_var.get().strip()
        
        disp = conf_host if conf_host and conf_host != "0.0.0.0" else rip
        
        self.ip_info.config(text="IP Local: {0}\nConnect: http://{1}:{2}".format(rip, disp, cfg['port']))
        if self.running: 
            self.ip_lbl.config(text="http://{0}:{1}".format(disp, cfg['port']))

    @staticmethod
    def _fmt_size(b):
        for u in ("B", "KB", "MB", "GB"):
            if b < 1024: return "{0:.1f} {1}".format(b, u)
            b /= 1024
        return "{0:.1f} TB".format(b)

    def _on_close(self):
        if self.systray_var.get() == 1: self._hide_to_tray(); return
        self._stop_tray_loop(); self._teardown_win32_drop_targets(); self._stop_server()
        cfg.save(); self.root.destroy()

def main():
    try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LinkDrop.Server.Application")
    except: pass
    root = tk.Tk()
    ico_path, png_path = resource_path("linkdrop.ico"), resource_path("linkdrop.png")
    if os.path.exists(ico_path):
        try: root.iconbitmap(default=ico_path)
        except: pass
    elif os.path.exists(png_path) and PIL_OK:
        try:
            img = Image.open(png_path); photo = ImageTk.PhotoImage(img)
            root.tk.call("wm", "iconphoto", root._w, "-default", photo); root._linkdrop_icon = photo
        except: pass
    root.update(); app = LinkDropGUI(root); root.mainloop()

if __name__ == "__main__": main()