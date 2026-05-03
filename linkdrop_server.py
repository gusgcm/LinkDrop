#!/usr/bin/env python3
# LinkDrop Server

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
from tkinter import ttk, filedialog, messagebox, scrolledtext
import tkinter.font as tkfont

# --- Bibliotecas opcionais ---
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

# --- Resource path para PyInstaller ---
def resource_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- Configuracoes Iniciais ---
APP_VERSION   = "1.0.0-XP"
DEFAULT_PORT  = 8765

HOME_DIR      = Path(os.path.expanduser("~"))
CONFIG_FOLDER = HOME_DIR / ".linkdrop"
CONFIG_FILE   = CONFIG_FOLDER / "config.json"
SHARE_FOLDER  = HOME_DIR / "LinkDrop"
LOG_FILE      = CONFIG_FOLDER / "server.log"

# Criacao de pastas
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

# --- Funcoes Auxiliares ---
def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def check_auth(headers):
    auth = headers.get("X-LinkDrop-Auth", "")
    return auth == hash_password(cfg["password"])

# --- Config Manager ---
class Config:
    _defaults = {
        "password":    "linkdrop123",
        "port":        DEFAULT_PORT,
        "host":        "0.0.0.0",
        "share_path":  str(SHARE_FOLDER),
        "autostart":   False,
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

cfg = Config()

# --- HTTP Request Handler ---
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
            self._send_json(200, {"status": "ok", "version": APP_VERSION,
                                  "name": socket.gethostname()})
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
                try:
                    text = pyperclip.paste()
                except Exception:
                    pass
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
            dest  = self._share_path() / fname
            body  = self._read_body()
            
            with open(str(dest), "wb") as f:
                f.write(body)
                
            log.info("Uploaded: {0} ({1} bytes)".format(fname, len(body)))
            self._notify_gui({
                "type":  "upload",
                "name":  fname,
                "size":  len(body),
                "time":  datetime.now().isoformat(),
            })
            self._send_json(200, {"status": "ok", "name": fname})
            return

        if path == "/text":
            try:
                data = json.loads(self._read_body().decode("utf-8"))
                text = data.get("text", "")
            except Exception:
                text = self._read_body().decode("utf-8", errors="replace")

            ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = "text_{0}.txt".format(ts)
            with open(str(self._share_path() / fname), "w", encoding="utf-8") as f:
                f.write(text)

            self._notify_gui({
                "type": "text", 
                "content": text, 
                "name": fname, 
                "time": datetime.now().isoformat()
            })
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
                try:
                    notification.notify(title="LinkDrop - Clipboard", message=text[:80], timeout=4)
                except Exception: pass
            self._send_json(200, {"status": "ok"})
            return

        if path == "/notify":
            try:
                data = json.loads(self._read_body().decode("utf-8"))
            except Exception:
                data = {}
            title = data.get("title", "Android Notification")
            msg   = data.get("message", "")
            self._notify_gui({
                "type":    "notification",
                "title":   title,
                "content": msg,
                "time":    datetime.now().isoformat(),
            })
            if NOTIFY_OK and cfg["notify"]:
                try:
                    notification.notify(
                        title="📱 {0}".format(title),
                        message=msg,
                        app_name="LinkDrop",
                        timeout=5,
                    )
                except Exception:
                    pass
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
                    os.remove(str(fpath))
                    self._notify_gui({"type": "delete", "name": fname, "time": datetime.now().isoformat()})
                    self._send_json(200, {"status": "deleted"})
                except Exception:
                    self._send_json(500, {"error": "Could not delete"})
            else:
                self._send_json(404, {"error": "File not found"})
            return
        self._send_json(404, {"error": "Not found"})

# --- Threading ---
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
            log.info("Server started on port {0}".format(self.port))
            self.server.serve_forever()
        except Exception as e:
            self.error = str(e)
            log.error("Server error: {0}".format(e))

    def stop(self):
        if self.server:
            self.server.shutdown()

# --- GUI ---
DARK_BG    = "#0d1117"
PANEL_BG   = "#161b22"
CARD_BG    = "#1c2128"
ACCENT     = "#00d4aa"
ACCENT2    = "#0099ff"
TEXT_MAIN  = "#e6edf3"
TEXT_DIM   = "#8b949e"
RED        = "#f85149"
GREEN      = "#3fb950"
BORDER     = "#30363d"

class LinkDropGUI:
    def __init__(self, root):
        self.root = root
        self.server_thread = None
        self.running = False
        self._activity_log = []

        self._setup_root()
        self._build_ui()
        self._start_server_auto()

        LinkDropHandler.gui_callback = self._on_event
        self._refresh_files()
        self.root.after(3000, self._auto_refresh)

    def _setup_root(self):
        self.root.title("LinkDrop")
        self.root.geometry("980x680")
        self.root.minsize(820, 560)
        self.root.configure(bg=DARK_BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.root.after(100, self._set_window_icon)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

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
        ico_path = resource_path("linkdrop.ico")
        try:
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
                self.root.tk.call("wm", "iconbitmap", self.root._w, ico_path)
        except Exception:
            pass

    def _build_ui(self):
        # Cabecalho
        header = tk.Frame(self.root, bg=PANEL_BG, height=56)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="LinkDrop", bg=PANEL_BG, fg=ACCENT, font=("Tahoma", 16, "bold")).pack(side="left", padx=18)
        tk.Label(header, text="v{0}".format(APP_VERSION), bg=PANEL_BG, fg=TEXT_DIM, font=("Tahoma", 9)).pack(side="left", padx=2)

        self.status_dot = tk.Label(header, text="O", bg=PANEL_BG, fg=RED, font=("Tahoma", 16))
        self.status_dot.pack(side="right", padx=6)
        
        self.status_lbl = tk.Label(header, text="Stopped", bg=PANEL_BG, fg=RED, font=("Tahoma", 10))
        self.status_lbl.pack(side="right")

        self.ip_lbl = tk.Label(header, text="", bg=PANEL_BG, fg=TEXT_DIM, font=("Courier", 9))
        self.ip_lbl.pack(side="right", padx=20)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        self._build_sidebar(main)
        self._build_notebook(main)

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=PANEL_BG, width=240)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Frame(sidebar, bg=BORDER, width=1).pack(side="right", fill="y")
        pad = {"padx": 16, "pady": 6}

        tk.Label(sidebar, text="SERVER", bg=PANEL_BG, fg=TEXT_DIM, font=("Tahoma", 8, "bold")).pack(anchor="w", **pad)

        self.btn_toggle = tk.Button(
            sidebar, text="> Start Server", bg=ACCENT, fg=DARK_BG,
            font=("Tahoma", 10, "bold"), bd=0, relief="flat", cursor="hand2",
            activebackground="#00b894", activeforeground=DARK_BG,
            command=self._toggle_server
        )
        self.btn_toggle.pack(fill="x", padx=16, pady=(4, 12))

        for attr, label, color in [
            ("lbl_files_count",  "Files in Share",  ACCENT),
            ("lbl_events_count", "Events Today",    ACCENT2),
        ]:
            card = tk.Frame(sidebar, bg=CARD_BG, bd=0)
            card.pack(fill="x", padx=12, pady=4)
            tk.Frame(card, bg=color, width=3).pack(side="left", fill="y")
            inner = tk.Frame(card, bg=CARD_BG)
            inner.pack(side="left", padx=10, pady=8, fill="x", expand=True)
            tk.Label(inner, text=label, bg=CARD_BG, fg=TEXT_DIM, font=("Tahoma", 8)).pack(anchor="w")
            lbl = tk.Label(inner, text="0", bg=CARD_BG, fg=color, font=("Tahoma", 20, "bold"))
            lbl.pack(anchor="w")
            setattr(self, attr, lbl)

        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=12, pady=12)
        tk.Label(sidebar, text="QUICK SEND", bg=PANEL_BG, fg=TEXT_DIM, font=("Tahoma", 8, "bold")).pack(anchor="w", **pad)

        self.quick_text = tk.Text(sidebar, height=4, bg=CARD_BG, fg=TEXT_MAIN,
                                  insertbackground=TEXT_MAIN, bd=0, padx=8, pady=6,
                                  font=("Tahoma", 9), wrap="word", relief="flat")
        self.quick_text.pack(fill="x", padx=12)

        tk.Button(
            sidebar, text="Send Text to Phone", bg="#1a3a5c", fg=ACCENT2,
            font=("Tahoma", 9, "bold"), bd=0, relief="flat", cursor="hand2",
            activebackground="#1e4a6e", activeforeground=ACCENT2,
            command=self._send_text_to_phone
        ).pack(fill="x", padx=12, pady=(4, 12))

        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=12, pady=4)
        tk.Label(sidebar, text="SHARE FOLDER", bg=PANEL_BG, fg=TEXT_DIM, font=("Tahoma", 8, "bold")).pack(anchor="w", **pad)

        self.path_lbl = tk.Label(sidebar, text=cfg["share_path"], bg=PANEL_BG, fg=TEXT_DIM,
                                 font=("Tahoma", 8), wraplength=210, anchor="w", justify="left")
        self.path_lbl.pack(anchor="w", padx=16)

        tk.Button(
            sidebar, text="Open Folder", bg=CARD_BG, fg=TEXT_MAIN,
            font=("Tahoma", 9), bd=0, relief="flat", cursor="hand2",
            activebackground=BORDER, activeforeground=TEXT_MAIN,
            command=lambda: os.startfile(cfg["share_path"])
        ).pack(fill="x", padx=12, pady=4)

        tk.Button(
            sidebar, text="Change Folder...", bg=CARD_BG, fg=TEXT_DIM,
            font=("Tahoma", 9), bd=0, relief="flat", cursor="hand2",
            activebackground=BORDER, activeforeground=TEXT_MAIN,
            command=self._change_folder
        ).pack(fill="x", padx=12, pady=(0, 4))

    def _build_notebook(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        self._build_files_tab(nb)
        self._build_activity_tab(nb)
        self._build_clipboard_tab(nb)
        self._build_settings_tab(nb)

    def _build_files_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Files  ")

        toolbar = tk.Frame(frame, bg=DARK_BG)
        toolbar.pack(fill="x", padx=12, pady=(10, 4))

        tk.Label(toolbar, text="Files in Share Folder", bg=DARK_BG, fg=TEXT_MAIN, font=("Tahoma", 12, "bold")).pack(side="left")

        for txt, cmd, col in [
            ("Upload File",   self._upload_file,   ACCENT),
            ("Refresh",       self._refresh_files, CARD_BG),
            ("Delete",        self._delete_file,   "#3d1f1f"),
        ]:
            tk.Button(toolbar, text=txt, bg=col,
                      fg=TEXT_MAIN if col != ACCENT else DARK_BG,
                      font=("Tahoma", 9, "bold"), bd=0, relief="flat",
                      cursor="hand2", activebackground=BORDER, activeforeground=TEXT_MAIN,
                      command=cmd).pack(side="right", padx=3)

        cols = ("name", "size", "modified", "type")
        self.file_tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for col, label, width in [
            ("name",     "Name",         300),
            ("size",     "Size",         90),
            ("modified", "Modified",     150),
            ("type",     "Type",         80),
        ]:
            self.file_tree.heading(col, text=label)
            self.file_tree.column(col, width=width, minwidth=60)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=vsb.set)

        self.file_tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=4)
        vsb.pack(side="left", fill="y", pady=4)
        self.file_tree.bind("<Double-1>", self._open_file)

    def _build_activity_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Activity  ")

        header = tk.Frame(frame, bg=DARK_BG)
        header.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(header, text="Activity Log", bg=DARK_BG, fg=TEXT_MAIN, font=("Tahoma", 12, "bold")).pack(side="left")
        tk.Button(header, text="Clear", bg=CARD_BG, fg=TEXT_DIM, bd=0, relief="flat", cursor="hand2",
                  font=("Tahoma", 9), activebackground=BORDER, activeforeground=TEXT_MAIN,
                  command=self._clear_log).pack(side="right")

        self.activity_box = scrolledtext.ScrolledText(
            frame, bg=CARD_BG, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
            font=("Courier", 9), bd=0, padx=10, pady=8, state="disabled", wrap="word"
        )
        self.activity_box.pack(fill="both", expand=True, padx=12, pady=4)

        self.activity_box.tag_config("time",   foreground=TEXT_DIM)
        self.activity_box.tag_config("upload", foreground=GREEN)
        self.activity_box.tag_config("text",   foreground=ACCENT2)
        self.activity_box.tag_config("clip",   foreground=ACCENT)
        self.activity_box.tag_config("notify", foreground="#e8b100")
        self.activity_box.tag_config("delete", foreground=RED)
        self.activity_box.tag_config("info",   foreground=TEXT_DIM)

    def _build_clipboard_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Clipboard  ")

        header = tk.Frame(frame, bg=DARK_BG)
        header.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(header, text="Clipboard Sync", bg=DARK_BG, fg=TEXT_MAIN, font=("Tahoma", 12, "bold")).pack(side="left")

        btn_row = tk.Frame(frame, bg=DARK_BG)
        btn_row.pack(fill="x", padx=12, pady=4)

        tk.Button(btn_row, text="Get PC Clipboard", bg=CARD_BG, fg=TEXT_MAIN, bd=0, relief="flat", cursor="hand2",
                  font=("Tahoma", 9), activebackground=BORDER,
                  command=self._load_pc_clipboard).pack(side="left", padx=3)

        tk.Button(btn_row, text="Copy to PC Clipboard", bg=ACCENT, fg=DARK_BG, bd=0, relief="flat", cursor="hand2",
                  font=("Tahoma", 9, "bold"), activebackground="#00b894",
                  command=self._copy_clip_to_pc).pack(side="left", padx=3)

        tk.Label(frame, text="Last received from phone:", bg=DARK_BG, fg=TEXT_DIM, font=("Tahoma", 9)).pack(anchor="w", padx=14, pady=(8, 2))

        self.clip_box = tk.Text(frame, height=8, bg=CARD_BG, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, bd=0, padx=10,
                                pady=8, font=("Tahoma", 10), wrap="word", relief="flat")
        self.clip_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_settings_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Settings  ")

        canvas = tk.Canvas(frame, bg=DARK_BG, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=DARK_BG)
        canvas.create_window(0, 0, window=inner, anchor="nw")

        def section(text):
            tk.Label(inner, text=text, bg=DARK_BG, fg=ACCENT, font=("Tahoma", 9, "bold")).pack(anchor="w", padx=20, pady=(16, 4))

        def row(label, widget_factory):
            r = tk.Frame(inner, bg=DARK_BG)
            r.pack(fill="x", padx=20, pady=3)
            tk.Label(r, text=label, bg=DARK_BG, fg=TEXT_MAIN, width=22, anchor="w", font=("Tahoma", 10)).pack(side="left")
            widget_factory(r)

        section("SECURITY")
        self.pwd_var = tk.StringVar(value=cfg["password"])
        row("Password", lambda r: ttk.Entry(r, textvariable=self.pwd_var, show="*", width=28).pack(side="left"))

        section("NETWORK")
        self.host_var = tk.StringVar(value=cfg["host"])
        row("Remote Address / DDNS", lambda r: ttk.Entry(r, textvariable=self.host_var, width=28).pack(side="left"))
        
        tk.Label(inner, text="Ex: 192.168.1.5, meudominio.ddns.net ou IP da VPN", 
                 bg=DARK_BG, fg=TEXT_DIM, font=("Tahoma", 8)).pack(anchor="w", padx=20)

        self.port_var = tk.IntVar(value=cfg["port"])
        row("Port", lambda r: ttk.Entry(r, textvariable=self.port_var, width=10).pack(side="left"))

        self.ip_info = tk.Label(inner, bg=DARK_BG, fg=TEXT_DIM, font=("Courier", 9), justify="left")
        self.ip_info.pack(anchor="w", padx=20, pady=10)
        self._update_ip_display()

        section("FEATURES")
        self.notify_var = tk.BooleanVar(value=cfg["notify"])
        self.clip_var   = tk.BooleanVar(value=cfg["clipboard_sync"])

        for var, text in [(self.notify_var, "Show desktop notifications"),
                          (self.clip_var,   "Sync clipboard automatically")]:
            r = tk.Frame(inner, bg=DARK_BG)
            r.pack(fill="x", padx=20, pady=2)
            tk.Checkbutton(r, variable=var, text=text, bg=DARK_BG, fg=TEXT_MAIN,
                           selectcolor=CARD_BG, activebackground=DARK_BG, activeforeground=TEXT_MAIN,
                           font=("Tahoma", 10)).pack(side="left")

        section("ABOUT")
        qr_info = tk.Label(inner, bg=DARK_BG, fg=TEXT_DIM, font=("Tahoma", 9),
                           text="Connect the Android app by entering your PC's IP and password above.",
                           wraplength=480, justify="left")
        qr_info.pack(anchor="w", padx=20)

        tk.Button(inner, text="Save Settings", bg=ACCENT, fg=DARK_BG,
                  font=("Tahoma", 10, "bold"), bd=0, relief="flat", cursor="hand2", padx=16, pady=8,
                  activebackground="#00b894", command=self._save_settings).pack(padx=20, pady=16, anchor="w")

    def _start_server_auto(self):
        self._start_server()

    def _start_server(self):
        if self.running: return
        port = cfg["port"]
        self.server_thread = ServerThread(port)
        self.server_thread.start()
        time.sleep(0.4)
        if self.server_thread.error:
            messagebox.showerror("LinkDrop", "Cannot start server on port {0}\n{1}".format(port, self.server_thread.error))
            return
        self.running = True
        self._set_status_running(True)
        self._log_event({"type": "info", "content": "Server started on port {0}".format(port), "time": datetime.now().isoformat()})

    def _stop_server(self):
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread = None
        self.running = False
        self._set_status_running(False)
        self._log_event({"type": "info", "content": "Server stopped", "time": datetime.now().isoformat()})

    def _toggle_server(self):
        if self.running:
            self._stop_server()
            self.btn_toggle.config(text="> Start Server", bg=ACCENT, fg=DARK_BG)
        else:
            self._start_server()
            self.btn_toggle.config(text="X Stop Server", bg=RED, fg="white")

    def _set_status_running(self, on):
        if on:
            self.status_dot.config(fg=GREEN)
            self.status_lbl.config(fg=GREEN, text="Running")
            self.btn_toggle.config(text="X Stop Server", bg=RED, fg="white")
            self._update_ip_display()
        else:
            self.status_dot.config(fg=RED)
            self.status_lbl.config(fg=RED, text="Stopped")
            self.btn_toggle.config(text="> Start Server", bg=ACCENT, fg=DARK_BG)
            self.ip_lbl.config(text="")

    def _on_event(self, event):
        self.root.after(0, lambda: self._handle_event(event))

    def _handle_event(self, event):
        self._activity_log.append(event)
        self._log_event(event)

        etype = event.get("type")
        if etype in ("upload", "text", "delete"):
            self._refresh_files()
        if etype == "clipboard":
            text = event.get("content", "")
            self.clip_box.delete("1.0", "end")
            self.clip_box.insert("end", text)
        count = len([e for e in self._activity_log if e.get("time", "").startswith(datetime.now().strftime("%Y-%m-%d"))])
        self.lbl_events_count.config(text=str(count))

    def _log_event(self, event):
        etype   = event.get("type", "info")
        ts      = event.get("time", "")[:19].replace("T", " ")
        content = event.get("content", event.get("name", ""))

        tag_map = {"upload": "upload", "text": "text", "clipboard": "clip", "notification": "notify", "delete": "delete"}
        icon_map = {"upload": "UP", "text": "TXT", "clipboard": "CLP", "notification": "NOT", "delete": "DEL", "info": "INF"}

        tag  = tag_map.get(etype, "info")
        icon = icon_map.get(etype, "*")
        line = "[{0}] {1}\n".format(icon, content[:80])

        box = self.activity_box
        box.config(state="normal")
        box.insert("end", "  {0}  ".format(ts), "time")
        box.insert("end", line, tag)
        box.see("end")
        box.config(state="disabled")

    def _clear_log(self):
        self.activity_box.config(state="normal")
        self.activity_box.delete("1.0", "end")
        self.activity_box.config(state="disabled")
        self._activity_log.clear()

    def _refresh_files(self):
        share = Path(cfg["share_path"])
        for row in self.file_tree.get_children():
            self.file_tree.delete(row)

        items = sorted(share.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True) if share.exists() else []

        for p in items:
            stat = p.stat()
            size = self._fmt_size(stat.st_size)
            mod  = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            ext  = p.suffix.lstrip(".").upper() or ("DIR" if p.is_dir() else "FILE")
            self.file_tree.insert("", "end", values=(p.name, size, mod, ext), tags=(str(p),))

        self.lbl_files_count.config(text=str(len(items)))

    def _auto_refresh(self):
        if self.running:
            self._refresh_files()
        self.root.after(5000, self._auto_refresh)

    def _open_file(self, _event=None):
        sel = self.file_tree.selection()
        if not sel: return
        tags = self.file_tree.item(sel[0], "tags")
        if tags:
            os.startfile(tags[0])

    def _upload_file(self):
        paths = filedialog.askopenfilenames(title="Select files to add to share")
        for src in paths:
            dst = Path(cfg["share_path"]) / Path(src).name
            shutil.copy2(src, str(dst))
        self._refresh_files()

    def _delete_file(self):
        sel = self.file_tree.selection()
        if not sel: return
        name = self.file_tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Delete", 'Delete "{0}" from share folder?'.format(name)):
            p = Path(cfg["share_path"]) / name
            if p.exists():
                try:
                    os.remove(str(p))
                except Exception:
                    pass
            self._refresh_files()

    def _load_pc_clipboard(self):
        if CLIPBOARD_OK:
            try:
                text = pyperclip.paste()
                self.clip_box.delete("1.0", "end")
                self.clip_box.insert("end", text)
            except Exception as e:
                messagebox.showerror("Clipboard", str(e))
        else:
            messagebox.showwarning("Clipboard", "pyperclip not installed.")

    def _copy_clip_to_pc(self):
        text = self.clip_box.get("1.0", "end").strip()
        if CLIPBOARD_OK:
            try:
                pyperclip.copy(text)
            except Exception:
                pass
        messagebox.showinfo("Done", "Text copied to clipboard!")

    def _send_text_to_phone(self):
        text = self.quick_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Send", "Type something first.")
            return
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = "from_pc_{0}.txt".format(ts)
        with open(str(Path(cfg["share_path"]) / fname), "w", encoding="utf-8") as f:
            f.write(text)
        self._refresh_files()
        messagebox.showinfo("Sent", 'Saved as "{0}" in share folder.\nPhone can now download it.'.format(fname))
        self.quick_text.delete("1.0", "end")

    def _save_settings(self):
        try:
            cfg["password"]       = self.pwd_var.get()
            cfg["host"]           = self.host_var.get().strip()
            cfg["port"]           = int(self.port_var.get())
            cfg["notify"]         = self.notify_var.get()
            cfg["clipboard_sync"] = self.clip_var.get()
            cfg.save()
            messagebox.showinfo("Saved", "Settings saved.\nRestart the server to apply changes.")
            self._update_ip_display()
        except ValueError:
            messagebox.showerror("Error", "Invalid Port number.")

    def _change_folder(self):
        new = filedialog.askdirectory(title="Select Share Folder", initialdir=cfg["share_path"])
        if new:
            cfg["share_path"] = new
            cfg.save()
            if not os.path.exists(new):
                try: os.makedirs(new)
                except Exception: pass
            self.path_lbl.config(text=new)
            self._refresh_files()

    @staticmethod
    def _get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _update_ip_display(self):
        try:
            real_ip = self._get_local_ip()
            user_host = self.host_var.get().strip()
            display_host = user_host if user_host and user_host != "0.0.0.0" else real_ip
            info_text = "Local network IP: {0}\nConnect URL: http://{1}:{2}".format(real_ip, display_host, cfg['port'])
            self.ip_info.config(text=info_text)
            if self.running:
                self.ip_lbl.config(text="http://{0}:{1}".format(display_host, cfg['port']))
        except Exception:
            pass

    @staticmethod
    def _fmt_size(b):
        for unit in ("B", "KB", "MB", "GB"):
            if b < 1024:
                return "{0:.1f} {1}".format(b, unit)
            b /= 1024
        return "{0:.1f} TB".format(b)

    def _on_close(self):
        self._stop_server()
        self.root.destroy()

def main():
    root = tk.Tk()
    ico_path = resource_path("linkdrop.ico")
    png_path = resource_path("linkdrop.png")
    log.info("ICO path: %s (exists: %s)" % (ico_path, os.path.exists(ico_path)))
    log.info("PNG path: %s (exists: %s)" % (png_path, os.path.exists(png_path)))
    icon_applied = False
    if os.path.exists(ico_path):
        try:
            root.iconbitmap(ico_path)
            icon_applied = True
            log.info("Icon applied via iconbitmap (ICO)")
        except Exception as e:
            log.error("Failed iconbitmap: %s" % str(e))
    if not icon_applied and os.path.exists(png_path) and PIL_OK:
        try:
            img = Image.open(png_path)
            photo = ImageTk.PhotoImage(img)
            root.tk.call('wm', 'iconphoto', root._w, '-default', photo)
            root._linkdrop_icon = photo
            icon_applied = True
            log.info("Icon applied via iconphoto (PNG)")
        except Exception as e:
            log.error("Failed iconphoto: %s" % str(e))
    if not icon_applied:
        log.error("No icon could be applied!")
    root.update()
    app  = LinkDropGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()