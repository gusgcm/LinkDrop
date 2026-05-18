import os, sys, json, time, shutil, hashlib, logging, threading, subprocess, socket, mimetypes, ctypes, winreg
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote, quote
import urllib.request, urllib.error, http.client
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, IntVar, Checkbutton
from collections import deque
import pyperclip

def _try_import(mod, attr=None):
    try:
        m = __import__(mod)
        return getattr(m, attr) if attr else m
    except ImportError:
        return None

CLIPBOARD_OK = False; NOTIFY_OK = False; PIL_OK = False
_pyperclip = None; _notification = None; _PIL = None

def _get_pyperclip():
    global _pyperclip, CLIPBOARD_OK
    if _pyperclip is None:
        _pyperclip = _try_import("pyperclip")
        CLIPBOARD_OK = _pyperclip is not None
    return _pyperclip

def _get_notification():
    global _notification, NOTIFY_OK
    if _notification is None:
        try:
            from plyer import notification as _n
            _notification = _n; NOTIFY_OK = True
        except ImportError:
            NOTIFY_OK = False
    return _notification

def _get_pil():
    global _PIL, PIL_OK
    if _PIL is None:
        try:
            from PIL import Image, ImageTk
            _PIL = (Image, ImageTk); PIL_OK = True
        except ImportError:
            PIL_OK = False
    return _PIL

def resource_path(rp):
    base = sys._MEIPASS if (getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')) else os.path.abspath(".")
    return os.path.join(base, rp)

APP_VERSION  = "1.0.3"
DEFAULT_PORT = 8765
_HOSTNAME    = socket.gethostname()
if not _HOSTNAME:
    try:
        import platform
        _HOSTNAME = platform.node() or "LinkDrop-PC"
    except:
        _HOSTNAME = "LinkDrop-PC"
_CHUNK       = 131072  # 128KB

TRANSLATIONS = {
    "pt": {
        "status_running": "Rodando", "status_stopped": "Parado",
        "server_section": "SERVER", "btn_start": "> Ativar Compartilhamento",
        "btn_stop": "X Parar Compartilhamento", "btn_share": "> Compartilhar",
        "label_files_shared": "Arquivos Compartilhados", "label_events_today": "Eventos hoje",
        "quick_send": "Envio Rápido", "btn_send_text": "Enviar texto ao celular",
        "shared_dir": "Diretório compartilhado", "btn_open_folder": "Abrir pasta",
        "btn_change_folder": "Alterar pasta compartilhada",
        "tab_files": "  Arquivos  ", "tab_activity": "  Registro  ",
        "tab_clipboard": "  Clipboard  ", "tab_settings": "  Configurações  ",
        "files_title": "Arquivos na pasta compartilhada", "btn_add_folders": "Adicionar Pastas",
        "btn_add_files": "Adicionar Arquivos", "btn_refresh": "Atualizar", "btn_delete": "Deletar",
        "drop_hint": "Arraste arquivos aqui ou use os botões acima para adicionar ao compartilhamento",
        "col_name": "Nome", "col_size": "Tamanho", "col_modified": "Data de modificação", "col_type": "Extensão",
        "ctx_open": "Abrir", "ctx_open_admin": "Abrir como administrador",
        "ctx_reveal": "Abrir local do arquivo", "ctx_delete": "Deletar",
        "ctx_add_files": "Adicionar arquivos...", "ctx_add_folder": "Adicionar pasta...",
        "ctx_refresh": "Atualizar lista", "ctx_open_share": "Abrir pasta share",
        "activity_title": "Logs de atividades", "btn_clear": "Limpar",
        "clip_title": "Sincronização Clipboard", "btn_show_clip": "Mostrar texto copiado do PC",
        "btn_copy_clip": "Copiar texto ao clipboard do PC", "clip_last": "Último recebimento do celular:",
        "sec_security": "SEGURANÇA", "lbl_password": "Senha", "sec_network": "NETWORK",
        "lbl_host": "IP / DDNS / VPN", "lbl_port": "Porta", "sec_extras": "EXTRAS",
        "chk_notify": "Mostrar notificações no Desktop", "chk_clip_sync": "Sincronizar clipboard automaticamente",
        "chk_autostart": "Iniciar com o Windows", "chk_systray": "Minimizar para Systray",
        "btn_save": "Salvar configurações", "lbl_language": "Idioma", "lbl_theme": "Tema",
        "theme_dark": "Escuro", "theme_light": "Claro",
        "dlg_saved_title": "Salvo", "dlg_saved_msg": "Configurações salvas!",
        "dlg_invalid_port": "Porta inválida.", "dlg_delete_confirm": "Deletar {0} item(s)?",
        "dlg_no_pyperclip": "pyperclip não instalado.", "dlg_clip_copied": "Texto copiado ao clipboard!",
        "dlg_select_files": "Selecionar Arquivos", "dlg_select_folder": "Selecionar Pasta",
        "tray_restore": "Restaurar", "tray_quit": "Sair",
        "log_auto_on": "Automação ativada", "log_auto_off": "Automação desativada",
        "log_server_started": "Servidor iniciado", "log_server_stopped": "Servidor parado",
        "log_drag_drop": "Arrastar & Soltar: ",
        "tab_pcs": "  PCs  ", "pcs_title": "PCs Remotos", "btn_add_pc": "Adicionar PC",
        "btn_connect_pc": "Conectar", "btn_disconnect_pc": "Desconectar",
        "btn_download": "Baixar", "btn_send_to_pc": "Enviar arquivo",
        "lbl_pc_name": "Nome / Apelido", "lbl_pc_host": "IP / DDNS / VPN",
        "lbl_pc_port": "Porta", "lbl_pc_pass": "Senha",
        "pc_status_online": "Online", "pc_status_offline": "Offline", "pc_status_connecting": "Conectando...",
        "pc_files_title": "Arquivos em", "pc_no_selection": "Selecione um PC e clique em Conectar",
        "pc_connect_error": "Erro ao conectar: ", "pc_download_ok": "Arquivo baixado: ",
        "pc_download_error": "Erro no download: ", "pc_upload_ok": "Arquivo enviado: ",
        "pc_upload_error": "Erro no envio: ", "dlg_add_pc_title": "Adicionar PC Remoto",
        "dlg_pc_exists": "Este host/porta já está na lista.",
        "col_pc_name": "Nome", "col_pc_host": "Endereço", "col_pc_status": "Status",
        "btn_edit_pc": "Editar", "btn_upload_file": "Enviar Arquivo", "btn_upload_folder": "Enviar Pasta",
        "dlg_edit_pc_title": "Editar PC Remoto", "pc_double_click_connect": "Duplo clique para conectar",
        "logs_title": "Logs Internos do Sistema (server.log)",
    },
    "en": {
        "status_running": "Running", "status_stopped": "Stopped",
        "server_section": "SERVER", "btn_start": "> Enable Sharing",
        "btn_stop": "X Stop Sharing", "btn_share": "> Share",
        "label_files_shared": "Shared Files", "label_events_today": "Events today",
        "quick_send": "Quick Send", "btn_send_text": "Send text to phone",
        "shared_dir": "Shared directory", "btn_open_folder": "Open folder",
        "btn_change_folder": "Change shared folder",
        "tab_files": "  Files  ", "tab_activity": "  Log  ",
        "tab_clipboard": "  Clipboard  ", "tab_settings": "  Settings  ",
        "files_title": "Files in shared folder", "btn_add_folders": "Add Folders",
        "btn_add_files": "Add Files", "btn_refresh": "Refresh", "btn_delete": "Delete",
        "drop_hint": "Drag files here or use the buttons above to add to sharing",
        "col_name": "Name", "col_size": "Size", "col_modified": "Date modified", "col_type": "Extension",
        "ctx_open": "Open", "ctx_open_admin": "Open as administrator",
        "ctx_reveal": "Show in Explorer", "ctx_delete": "Delete",
        "ctx_add_files": "Add files...", "ctx_add_folder": "Add folder...",
        "ctx_refresh": "Refresh list", "ctx_open_share": "Open share folder",
        "activity_title": "Activity log", "btn_clear": "Clear",
        "clip_title": "Clipboard Sync", "btn_show_clip": "Show text copied from PC",
        "btn_copy_clip": "Copy text to PC clipboard", "clip_last": "Last received from phone:",
        "sec_security": "SECURITY", "lbl_password": "Password", "sec_network": "NETWORK",
        "lbl_host": "IP / DDNS / VPN", "lbl_port": "Port", "sec_extras": "EXTRAS",
        "chk_notify": "Show Desktop notifications", "chk_clip_sync": "Auto-sync clipboard",
        "chk_autostart": "Start with Windows", "chk_systray": "Minimize to Systray",
        "btn_save": "Save settings", "lbl_language": "Language", "lbl_theme": "Theme",
        "theme_dark": "Dark", "theme_light": "Light",
        "dlg_saved_title": "Saved", "dlg_saved_msg": "Settings saved!",
        "dlg_invalid_port": "Invalid port.", "dlg_delete_confirm": "Delete {0} item(s)?",
        "dlg_no_pyperclip": "pyperclip not installed.", "dlg_clip_copied": "Text copied to clipboard!",
        "dlg_select_files": "Select Files", "dlg_select_folder": "Select Folder",
        "tray_restore": "Restore", "tray_quit": "Quit",
        "log_auto_on": "Autostart enabled", "log_auto_off": "Autostart disabled",
        "log_server_started": "Server started", "log_server_stopped": "Server stopped",
        "log_drag_drop": "Drag & Drop: ",
        "tab_pcs": "  PCs  ", "pcs_title": "Remote PCs", "btn_add_pc": "Add PC",
        "btn_connect_pc": "Connect", "btn_disconnect_pc": "Disconnect",
        "btn_download": "Download", "btn_send_to_pc": "Send file",
        "lbl_pc_name": "Name / Alias", "lbl_pc_host": "IP / DDNS / VPN",
        "lbl_pc_port": "Port", "lbl_pc_pass": "Password",
        "pc_status_online": "Online", "pc_status_offline": "Offline", "pc_status_connecting": "Connecting...",
        "pc_files_title": "Files on", "pc_no_selection": "Select a PC and click Connect",
        "pc_connect_error": "Connection error: ", "pc_download_ok": "File downloaded: ",
        "pc_download_error": "Download error: ", "pc_upload_ok": "File sent: ",
        "pc_upload_error": "Upload error: ", "dlg_add_pc_title": "Add Remote PC",
        "dlg_pc_exists": "This host/port is already in the list.",
        "col_pc_name": "Name", "col_pc_host": "Address", "col_pc_status": "Status",
        "btn_edit_pc": "Edit", "btn_upload_file": "Upload File", "btn_upload_folder": "Upload Folder",
        "dlg_edit_pc_title": "Edit Remote PC", "pc_double_click_connect": "Double-click to connect",
        "logs_title": "Internal System Logs (server.log)",
    },
    "es": {
        "status_running": "Activo", "status_stopped": "Detenido",
        "server_section": "SERVIDOR", "btn_start": "> Activar Compartición",
        "btn_stop": "X Detener Compartición", "btn_share": "> Compartir",
        "label_files_shared": "Archivos Compartidos", "label_events_today": "Eventos hoy",
        "quick_send": "Envío Rápido", "btn_send_text": "Enviar texto al móvil",
        "shared_dir": "Directorio compartido", "btn_open_folder": "Abrir carpeta",
        "btn_change_folder": "Cambiar carpeta compartida",
        "tab_files": "  Archivos  ", "tab_activity": "  Registro  ",
        "tab_clipboard": "  Portapapeles  ", "tab_settings": "  Configuración  ",
        "files_title": "Archivos en carpeta compartida", "btn_add_folders": "Agregar Carpetas",
        "btn_add_files": "Agregar Archivos", "btn_refresh": "Actualizar", "btn_delete": "Eliminar",
        "drop_hint": "Arrastre archivos aquí o use los botones para agregar al compartido",
        "col_name": "Nombre", "col_size": "Tamaño", "col_modified": "Fecha de modificación", "col_type": "Extensión",
        "ctx_open": "Abrir", "ctx_open_admin": "Abrir como administrador",
        "ctx_reveal": "Mostrar en Explorador", "ctx_delete": "Eliminar",
        "ctx_add_files": "Agregar archivos...", "ctx_add_folder": "Agregar carpeta...",
        "ctx_refresh": "Actualizar lista", "ctx_open_share": "Abrir carpeta compartida",
        "activity_title": "Registro de actividad", "btn_clear": "Limpiar",
        "clip_title": "Sincronización Portapapeles", "btn_show_clip": "Mostrar texto copiado del PC",
        "btn_copy_clip": "Copiar texto al portapapeles del PC", "clip_last": "Último recibido del móvil:",
        "sec_security": "SEGURIDAD", "lbl_password": "Contraseña", "sec_network": "RED",
        "lbl_host": "IP / DDNS / VPN", "lbl_port": "Puerto", "sec_extras": "EXTRAS",
        "chk_notify": "Mostrar notificaciones en escritorio", "chk_clip_sync": "Sincronizar portapapeles automáticamente",
        "chk_autostart": "Iniciar con Windows", "chk_systray": "Minimizar a bandeja del sistema",
        "btn_save": "Guardar configuración", "lbl_language": "Idioma", "lbl_theme": "Tema",
        "theme_dark": "Oscuro", "theme_light": "Claro",
        "dlg_saved_title": "Guardado", "dlg_saved_msg": "¡Configuración guardada!",
        "dlg_invalid_port": "Puerto inválido.", "dlg_delete_confirm": "¿Eliminar {0} elemento(s)?",
        "dlg_no_pyperclip": "pyperclip no instalado.", "dlg_clip_copied": "¡Texto copiado al portapapeles!",
        "dlg_select_files": "Seleccionar Archivos", "dlg_select_folder": "Seleccionar Carpeta",
        "tray_restore": "Restaurar", "tray_quit": "Salir",
        "log_auto_on": "Inicio automático activado", "log_auto_off": "Inicio automático desactivado",
        "log_server_started": "Servidor iniciado", "log_server_stopped": "Servidor detenido",
        "log_drag_drop": "Arrastar y soltar: ",
        "tab_pcs": "  PCs  ", "pcs_title": "PCs Remotos", "btn_add_pc": "Agregar PC",
        "btn_connect_pc": "Conectar", "btn_disconnect_pc": "Desconectar",
        "btn_download": "Descargar", "btn_send_to_pc": "Enviar archivo",
        "lbl_pc_name": "Nombre / Alias", "lbl_pc_host": "IP / DDNS / VPN",
        "lbl_pc_port": "Puerto", "lbl_pc_pass": "Contraseña",
        "pc_status_online": "En línea", "pc_status_offline": "Desconectado", "pc_status_connecting": "Conectando...",
        "pc_files_title": "Archivos en", "pc_no_selection": "Seleccione un PC y haga clic en Conectar",
        "pc_connect_error": "Error de conexión: ", "pc_download_ok": "Archivo descargado: ",
        "pc_download_error": "Error de descarga: ", "pc_upload_ok": "Archivo enviado: ",
        "pc_upload_error": "Error de envío: ", "dlg_add_pc_title": "Agregar PC Remoto",
        "dlg_pc_exists": "Este host/puerto ya está en la lista.",
        "col_pc_name": "Nombre", "col_pc_host": "Dirección", "col_pc_status": "Estado",
        "btn_edit_pc": "Editar", "btn_upload_file": "Subir Archivo", "btn_upload_folder": "Subir Carpeta",
        "dlg_edit_pc_title": "Editar PC Remoto", "pc_double_click_connect": "Doble clic para conectar",
        "logs_title": "Logs Internos del Sistema (server.log)",
    },
}

THEMES = {
    "dark": {
        "DARK_BG": "#0d1117", "PANEL_BG": "#161b22", "CARD_BG": "#1c2128",
        "ACCENT": "#00d4aa", "ACCENT2": "#0099ff", "TEXT_MAIN": "#e6edf3",
        "TEXT_DIM": "#8b949e", "RED": "#f85149", "GREEN": "#3fb950", "BORDER": "#30363d",
    },
    "light": {
        "DARK_BG": "#f0f2f5", "PANEL_BG": "#ffffff", "CARD_BG": "#e8ecf0",
        "ACCENT": "#00917a", "ACCENT2": "#0066cc", "TEXT_MAIN": "#1a1a2e",
        "TEXT_DIM": "#555f6e", "RED": "#d7263d", "GREEN": "#2d7a3a", "BORDER": "#c0c8d2",
    },
}

HOME_DIR      = os.path.expanduser("~")
CONFIG_FOLDER = os.path.join(HOME_DIR, ".linkdrop")
CONFIG_FILE   = os.path.join(CONFIG_FOLDER, "config.json")
SHARE_FOLDER  = os.path.join(HOME_DIR, "LinkDrop")
LOG_FILE      = os.path.join(CONFIG_FOLDER, "server.log")

for _p in (CONFIG_FOLDER, SHARE_FOLDER):
    try: os.makedirs(_p)
    except: pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("linkdrop")

_auth_cache = None

def _hash_pwd(pwd):
    return hashlib.sha256((pwd or "linkdrop123").encode()).hexdigest()

def hash_password(pwd):
    global _auth_cache
    _auth_cache = _hash_pwd(pwd)
    return _auth_cache

def check_auth(headers):
    global _auth_cache
    if not _auth_cache:
        _auth_cache = _hash_pwd(cfg["password"])
    provided = headers.get("X-LinkDrop-Auth", "")
    return bool(provided) and provided == _auth_cache


class Config:
    _defaults = dict(password="linkdrop123", port=DEFAULT_PORT, host="0.0.0.0",
        share_path=SHARE_FOLDER, autostart=False, systray=False, notify=True,
        clipboard_sync=True, language="pt", theme="dark", remote_pcs=[])

    def __init__(self):
        self._data = dict(self._defaults)
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    self._data.update(json.load(f))
            except: pass

    def save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    def __getitem__(self, k): return self._data.get(k, self._defaults.get(k))
    def __setitem__(self, k, v):
        global _auth_cache
        if k == "password": _auth_cache = None
        self._data[k] = v
    def get(self, k, d=None): return self._data.get(k, self._defaults.get(k, d))

cfg = Config()

_current_theme = "dark"
_current_lang  = "pt"
_theme_cache   = {}  
_trans_cache   = {}  

def _reload_colors():
    global _theme_cache
    _theme_cache = THEMES.get(_current_theme, THEMES["dark"])

def _reload_lang():
    global _trans_cache
    _trans_cache = TRANSLATIONS.get(_current_lang, TRANSLATIONS["pt"])

def _T(key):
    return _trans_cache.get(key) or TRANSLATIONS["pt"].get(key, key)

def _C(key):
    return _theme_cache.get(key) or THEMES["dark"][key]

_reload_colors(); _reload_lang()

def DARK_BG():  return _C("DARK_BG")
def PANEL_BG(): return _C("PANEL_BG")
def CARD_BG():  return _C("CARD_BG")
def ACCENT():   return _C("ACCENT")
def ACCENT2():  return _C("ACCENT2")
def TEXT_MAIN():return _C("TEXT_MAIN")
def TEXT_DIM(): return _C("TEXT_DIM")
def RED():      return _C("RED")
def GREEN():    return _C("GREEN")
def BORDER():   return _C("BORDER")


class TransferCancelled(Exception):
    pass


def unique_path_under_share(filename):
    share = cfg["share_path"]
    name  = os.path.basename(filename)
    dest  = os.path.join(share, name)
    if not os.path.exists(dest):
        return dest
    stem, suffix = os.path.splitext(name)
    for idx in range(1, 10000):
        cand = os.path.join(share, "%s_%d%s" % (stem, idx, suffix))
        if not os.path.exists(cand):
            return cand
    return dest


def copy_tree_into_share(src_dir, dst_dir):
    src_dir = os.path.abspath(src_dir)
    dst_dir = os.path.abspath(dst_dir)
    if not os.path.isdir(src_dir):
        return 0, ["Origem nao e pasta: " + src_dir]
    errs = []; nfiles = 0
    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target_root = dst_dir if rel in (".", os.curdir) else os.path.join(dst_dir, rel)
        if not os.path.isdir(target_root):
            try: os.makedirs(target_root)
            except Exception as ex:
                errs.append("%s: %s" % (target_root, ex)); continue
        for fn in files:
            try:
                shutil.copy2(os.path.join(root, fn), os.path.join(target_root, fn))
                nfiles += 1
            except Exception as ex:
                errs.append("%s: %s" % (os.path.join(root, fn), ex))
    return nfiles, errs


def import_local_path_to_share(src_path):
    src_path = os.path.abspath(src_path)
    base = os.path.basename(src_path.rstrip(os.sep))
    if not base:
        return "skip", "", ["caminho invalido"]
    try:
        if os.path.isfile(src_path):
            dst = unique_path_under_share(base)
            shutil.copy2(src_path, dst)
            return "file", os.path.basename(dst), []
        if os.path.isdir(src_path):
            share_abs = os.path.abspath(cfg["share_path"])
            files_created = []
            errors = []
            for item in os.listdir(src_path):
                src_item = os.path.join(src_path, item)
                if os.path.isfile(src_item):
                    dst = unique_path_under_share(item)
                    try:
                        shutil.copy2(src_item, dst)
                        files_created.append(item)
                    except Exception as e:
                        errors.append("%s: %s" % (item, e))
                elif os.path.isdir(src_item):
                    dst = os.path.join(share_abs, item)
                    if os.path.exists(dst):
                        dst = unique_path_under_share(item)
                    try:
                        os.makedirs(dst)
                        nfiles, errs = copy_tree_into_share(src_item, dst)
                        files_created.append(item)
                        errors.extend(errs)
                    except Exception as ex:
                        errors.append("%s: %s" % (item, ex))
            if not files_created and errors:
                return "skip", "", errors
            return "dir", base, errors
    except Exception as ex:
        return "skip", "", [str(ex)]
    return "skip", "", ["nao e arquivo nem pasta"]


def _fmt_size(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024: return "%.1f %s" % (b, u)
        b /= 1024.0
    return "%.1f TB" % b


def _now_iso():
    return datetime.now().isoformat()

class RemotePCClient:
    def __init__(self, host, port, password, timeout=10, gui_callback=None):
        self.host          = host.strip()
        self.port          = int(port)
        self.password      = password
        self.timeout       = timeout
        self._working_host = None
        self.gui_callback  = gui_callback
        self._active_dl_conn = None
        self._dl_lock        = threading.Lock()

    def abort_download(self):
        with self._dl_lock:
            conn, self._active_dl_conn = self._active_dl_conn, None
        if conn:
            try: conn.close()
            except: pass

    def _notify(self, event_type, content):
        if self.gui_callback:
            self.gui_callback({"type": event_type, "content": content, "time": _now_iso()})

    def _base_url(self, host=None):
        return "http://%s:%d" % (host or self._working_host or self.host, self.port)

    def _auth_header(self):
        return {"X-LinkDrop-Auth": _hash_pwd(self.password)}

    @staticmethod
    def _get_local_ips():
        ips = set()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)); ips.add(s.getsockname()[0]); s.close()
        except: pass
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None):
                if info[0] == socket.AF_INET:
                    ips.add(info[4][0])
        except: pass
        ips.discard("127.0.0.1")
        return ips

    def _check_tcp_connection(self, host, port, timeout=1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            return True
        except: return False

    def _try_host(self, host, short_timeout):
        if not self._check_tcp_connection(host, self.port, 1):
            raise Exception("Conexão falhou")
        url  = "http://%s:%d/ping" % (host, self.port)
        req  = urllib.request.Request(url, headers=self._auth_header(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=short_timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401: raise Exception("Conexão falhou")
            raise Exception("Conexão falhou")
        except Exception as e:
            raise Exception("Conexão falhou")

    def ping(self):
        try:
            info = self._try_host(self.host, 1)
            self._working_host = self.host
            self._notify("info", "Conectado ao PC Remoto: %s (%s)" % (info.get("name", self.host), self.host))
            return True, info
        except Exception as e:
            error_msg = str(e)
        return False, "Falha na conexão"

    def _request(self, method, path, data=None, extra_headers=None):
        url  = self._base_url() + path
        hdrs = self._auth_header()
        if extra_headers: hdrs.update(extra_headers)
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            resp = urllib.request.urlopen(req, timeout=1)
        except Exception as e:
            raise Exception("Falha na conexão")
        with resp: return resp.status, resp.read()

    def list_files(self, sub_dir=""):
        path = "/files" + ("?dir=" + quote(sub_dir) if sub_dir else "")
        _, body = self._request("GET", path)
        return json.loads(body.decode("utf-8")).get("files", [])

    def download_file(self, rel_path, dest_dir, progress_cb=None, cancel_event=None, resume_from=0, state=None):
        filename = os.path.basename(rel_path)
        dest     = os.path.join(dest_dir, filename)
        host     = self._working_host or self.host

        if state is not None:
            state.update(dest_path=dest, rel_path=rel_path, dest_dir=dest_dir, downloaded=resume_from)

        if cancel_event and cancel_event.is_set():
            raise TransferCancelled()

        _SOCKET_ERRS = (OSError, EOFError, http.client.HTTPException, ConnectionError, socket.error)

        def _open_conn():
            return http.client.HTTPConnection(host, self.port, timeout=10)

        conn = _open_conn()
        with self._dl_lock: self._active_dl_conn = conn

        try:
            hdrs = self._auth_header()
            if resume_from > 0:
                hdrs["Range"] = "bytes=%d-" % resume_from
            conn.request("GET", "/files/" + quote(rel_path), headers=hdrs)
            resp = conn.getresponse()

            if resp.status == 401:
                raise Exception("Falha na conexão")
            if resp.status == 416 and resume_from > 0:
                with self._dl_lock: self._active_dl_conn = None
                conn.close(); resume_from = 0
                if state: state["downloaded"] = 0
                if cancel_event and cancel_event.is_set(): raise TransferCancelled()
                conn = _open_conn()
                with self._dl_lock: self._active_dl_conn = conn
                conn.request("GET", "/files/" + quote(rel_path), headers=self._auth_header())
                resp = conn.getresponse()
                if resp.status == 401:
                    raise Exception("Falha na conexão")
            if resp.status not in (200, 206):
                raise IOError("HTTP %d ao baixar %s" % (resp.status, rel_path))

            total      = int(resp.getheader("Content-Length", 0)) + resume_from
            downloaded = resume_from
            start      = time.time()
            last_rpt   = 0.0

            mode = "ab" if resume_from > 0 else "wb"
            with open(dest, mode) as f:
                if resume_from > 0: f.seek(0, 2)
                while True:
                    if cancel_event and cancel_event.is_set():
                        if state: state["downloaded"] = downloaded
                        raise TransferCancelled()
                    try:
                        chunk = resp.read(_CHUNK)
                    except _SOCKET_ERRS + (BrokenPipeError,):
                        if state: state["downloaded"] = downloaded
                        raise TransferCancelled()
                    if not chunk: break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if state: state["downloaded"] = downloaded
                    if progress_cb:
                        now = time.time()
                        if now - last_rpt >= 0.1 or downloaded >= total:
                            elapsed = now - start
                            speed   = (downloaded - resume_from) / elapsed if elapsed > 0 else 0
                            eta     = (total - downloaded) / speed if speed > 0 and total else 0
                            progress_cb(downloaded, total, speed, eta)
                            last_rpt = now

        except TransferCancelled: raise
        except PermissionError: raise
        except _SOCKET_ERRS + (BrokenPipeError,):
            if state: state["downloaded"] = downloaded if "downloaded" in dir() else resume_from
            raise TransferCancelled()
        finally:
            with self._dl_lock: self._active_dl_conn = None
            try: conn.close()
            except: pass

        self._notify("info", "Download concluido do PC Remoto [%s]: %s" % (self.host, filename))
        return dest

    def _open_upload_conn(self, rel_path, file_size):
        host = self._working_host or self.host
        conn = http.client.HTTPConnection(host, self.port, timeout=self.timeout)
        conn.putrequest("POST", "/upload")
        conn.putheader("X-LinkDrop-Auth", _hash_pwd(self.password))
        conn.putheader("X-Filename", rel_path)
        conn.putheader("Content-Length", str(file_size))
        conn.endheaders()
        return conn

    def _finish_upload(self, conn, local_path):
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        if resp.status == 401:
            raise Exception("Falha na conexão")
        saved = json.loads(body.decode("utf-8")).get("name", os.path.basename(local_path))
        self._notify("info", "Upload concluído para o PC Remoto [%s]: %s" % (self.host, saved))
        return saved

    def upload_file(self, local_path):
        file_size = os.path.getsize(local_path)
        conn = self._open_upload_conn(os.path.basename(local_path), file_size)
        with open(local_path, "rb") as f:
            while True:
                chunk = f.read(_CHUNK)
                if not chunk: break
                conn.send(chunk)
        return self._finish_upload(conn, local_path)

    def upload_file_progress(self, local_path, progress_cb=None, cancel_event=None):
        file_size = os.path.getsize(local_path)
        conn      = self._open_upload_conn(os.path.basename(local_path), file_size)
        sent = 0; start = last_rpt = time.time()
        with open(local_path, "rb") as f:
            while True:
                if cancel_event and cancel_event.is_set(): raise TransferCancelled()
                chunk = f.read(_CHUNK)
                if not chunk: break
                conn.send(chunk); sent += len(chunk)
                if progress_cb:
                    now = time.time()
                    if now - last_rpt >= 0.1 or sent >= file_size:
                        elapsed = now - start
                        speed   = sent / elapsed if elapsed > 0 else 0
                        eta     = (file_size - sent) / speed if speed > 0 else 0
                        progress_cb(sent, file_size, speed, eta)
                        last_rpt = now
        return self._finish_upload(conn, local_path)

    def upload_folder(self, local_dir, progress_cb=None, cancel_event=None, file_done_cb=None):
        folder_name  = os.path.basename(local_dir.rstrip(os.sep))
        parent_dir   = os.path.dirname(local_dir.rstrip(os.sep))
        total_bytes  = total_files = 0
        file_list    = []
        for root, _dirs, files in os.walk(local_dir):
            for fn in files:
                fp  = os.path.join(root, fn)
                rel = os.path.relpath(fp, parent_dir)
                sz  = os.path.getsize(fp)
                total_files += 1; total_bytes += sz
                file_list.append((fp, rel, sz))
        file_list.sort(key=lambda x: x[1])

        done_bytes = completed = 0
        for fp, rel, sz in file_list:
            if cancel_event and cancel_event.is_set(): raise TransferCancelled()
            conn = self._open_upload_conn(rel, sz)
            try:
                with open(fp, "rb") as f:
                    while True:
                        if cancel_event and cancel_event.is_set(): raise TransferCancelled()
                        chunk = f.read(_CHUNK)
                        if not chunk: break
                        conn.send(chunk)
                resp = conn.getresponse(); body = resp.read()
                if resp.status == 401: raise Exception("Falha na conexão")
                done_bytes += sz; completed += 1
                if progress_cb: progress_cb(done_bytes, total_bytes, 0, 0)
                if file_done_cb: file_done_cb(rel, completed, total_files)
            finally: conn.close()
        self._notify("info", "Upload de pasta concluído para o PC Remoto [%s]: %d arquivos" % (self.host, completed))
        return completed

class LinkDropHandler(BaseHTTPRequestHandler):
    gui_callback = None

    def log_message(self, fmt, *args):
        log.info("HTTP %s - %s" % (self.address_string(), fmt % args))

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        mime  = mimetypes.guess_type(path)[0] or "application/octet-stream"
        size  = os.path.getsize(path)
        start = 0
        range_hdr = self.headers.get("Range", "")
        if range_hdr.startswith("bytes="):
            try:
                start = int(range_hdr[6:].split("-", 1)[0])
                if start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", "bytes */%d" % size)
                    self.end_headers(); return
            except: start = 0
        remaining = size - start
        code = 206 if start > 0 else 200
        self.send_response(code)
        if start > 0:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, size - 1, size))
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", remaining)
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % os.path.basename(path))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with open(path, "rb") as f:
            if start > 0: f.seek(start)
            while True:
                buf = f.read(_CHUNK)
                if not buf: break
                self.wfile.write(buf)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _notify_gui(self, event):
        if self.gui_callback: self.gui_callback(event)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-LinkDrop-Auth, Content-Type, X-Filename")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")

        if path == "/ping":
            auth_header = self.headers.get("X-LinkDrop-Auth", "")
            if auth_header:
                if not check_auth(self.headers):
                    self._send_json(401, {"error": "Unauthorized"}); return
            self._send_json(200, {"status": "ok", "version": APP_VERSION, "name": _HOSTNAME}); return

        if not check_auth(self.headers):
            self._send_json(401, {"error": "Unauthorized"}); return

        if path == "/files":
            sub_dir   = parse_qs(parsed.query).get("dir", [""])[0]
            share_abs = os.path.abspath(cfg["share_path"])
            target    = os.path.abspath(os.path.join(share_abs, sub_dir))
            if not target.startswith(share_abs):
                self._send_json(403, {"error": "Acesso proibido"}); return
            if not os.path.exists(target):
                self._send_json(404, {"error": "Pasta nao encontrada"}); return
            items = []
            try: names = os.listdir(target)
            except: self._send_json(500, {"error": "list error"}); return
            for name in sorted(names):
                full = os.path.join(target, name)
                try:
                    st      = os.stat(full)
                    rel_path = full[len(share_abs) + 1:].replace("\\", "/")
                    items.append({"name": name, "rel_path": rel_path,
                        "size": st.st_size if os.path.isfile(full) else 0,
                        "is_dir": os.path.isdir(full), "modified": st.st_mtime})
                except: pass
            self._send_json(200, {"files": items}); return

        if path.startswith("/files/"):
            fname     = unquote(path[7:])
            share_abs = os.path.abspath(cfg["share_path"])
            fpath     = os.path.abspath(os.path.join(share_abs, fname))
            if fpath.startswith(share_abs) and os.path.isfile(fpath):
                self._send_file(fpath)
            else:
                self._send_json(404, {"error": "Arquivo nao encontrado"})
            return

        if path == "/clipboard":
            pc = _get_pyperclip()
            text = pc.paste() if pc else ""
            self._send_json(200, {"text": text, "timestamp": time.time()}); return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        if not check_auth(self.headers):
            self._send_json(401, {"error": "Unauthorized"}); return
        now_iso = _now_iso()

        if path == "/upload":
            raw = unquote(self.headers.get("X-Filename", "file_%d" % int(time.time()))).replace("\\", "/").lstrip("/")
            if "/" in raw:
                dest = os.path.normpath(os.path.join(cfg["share_path"], raw))
                if not dest.startswith(os.path.normpath(cfg["share_path"])):
                    self._send_json(403, {"error": "Forbidden"}); return
                try: os.makedirs(os.path.dirname(dest))
                except: pass
            else:
                dest = unique_path_under_share(raw)
            length = int(self.headers.get("Content-Length", 0))
            total  = 0
            with open(dest, "wb") as f:
                while total < length:
                    chunk = self.rfile.read(min(_CHUNK, length - total))
                    if not chunk: break
                    f.write(chunk); total += len(chunk)
            saved = os.path.basename(dest) if "/" not in raw else raw
            log.info("Uploaded: %s (%d bytes)" % (saved, total))
            self._notify_gui({"type": "upload", "name": saved, "size": total, "time": now_iso})
            self._send_json(200, {"status": "ok", "name": saved}); return

        if path == "/text":
            try: text = json.loads(self._read_body().decode("utf-8")).get("text", "")
            except: text = self._read_body().decode("utf-8", errors="replace")
            fname = "text_%s.txt" % datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(os.path.join(cfg["share_path"], fname), "w", encoding="utf-8") as f:
                f.write(text)
            self._notify_gui({"type": "text", "content": text, "name": fname, "time": now_iso})
            self._send_json(200, {"status": "ok"}); return

        if path == "/clipboard":
            try: text = json.loads(self._read_body().decode("utf-8")).get("text", "")
            except: text = self._read_body().decode("utf-8", errors="replace")
            self._notify_gui({"type": "clipboard", "content": text, "time": now_iso})
            notif = _get_notification()
            if notif and cfg["notify"]:
                try: notif.notify(title="LinkDrop - Clipboard", message=text[:80], timeout=4)
                except: pass
            self._send_json(200, {"status": "ok"}); return

        if path == "/notify":
            try: data = json.loads(self._read_body().decode("utf-8"))
            except: data = {}
            title, msg = data.get("title", "Android Notification"), data.get("message", "")
            self._notify_gui({"type": "notification", "title": title, "content": msg, "time": now_iso})
            notif = _get_notification()
            if notif and cfg["notify"]:
                try: notif.notify(title="Tel: %s" % title, message=msg, app_name="LinkDrop", timeout=5)
                except: pass
            self._send_json(200, {"status": "ok"}); return

        self._send_json(404, {"error": "Not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        if not check_auth(self.headers):
            self._send_json(401, {"error": "Unauthorized"}); return
        if path.startswith("/files/"):
            fname = unquote(path[7:])
            fpath = os.path.join(cfg["share_path"], os.path.basename(fname))
            if os.path.exists(fpath):
                try:
                    if os.path.isdir(fpath): shutil.rmtree(fpath)
                    else: os.remove(fpath)
                    self._notify_gui({"type": "delete", "name": fname, "time": _now_iso()})
                    self._send_json(200, {"status": "deleted"})
                except: self._send_json(500, {"error": "Could not delete"})
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
            log.info("Server listening on port %d" % self.port)
            self.server.serve_forever()
        except Exception as e:
            self.error = str(e)
            log.error("Server error: %s" % e)

    def stop(self):
        if self.server: self.server.shutdown()

class LinkDropGUI:
    _LOG_MAX = 2000  

    def __init__(self, root):
        self.root          = root
        self.server_thread = None
        self.running       = False
        self._activity_log = deque(maxlen=self._LOG_MAX)
        self._is_dragging  = False
        self._dnd_installed = False
        self._current_local_dir  = ""
        self._current_remote_dir = ""

        global _current_theme, _current_lang
        _current_theme = cfg.get("theme", "dark")
        _current_lang  = cfg.get("language", "pt")
        _reload_colors(); _reload_lang()

        self.automation_var = IntVar()
        self.systray_var    = IntVar()
        self._tray_active   = False
        self._tray_hwnd     = None
        self._tray_thread   = None
        self._hicon_small   = None
        self._hicon_large   = None

        self._ui_queue    = deque()
        self._cancel_event = threading.Event()
        self._cancel_is_user_action = False
        self._pending_transfers = {}
        self._ui_lock = threading.Lock()

        self._dnd_hwnd     = None
        self._dnd_old_proc = None

        self._refresh_interval = 3000   
        self._last_activity_ts = 0.0

        self._setup_root()
        self._build_ui()
        self._load_checkbox_state()
        self._start_server_auto()

        LinkDropHandler.gui_callback = self._on_event
        self._refresh_files()
        self.root.after(self._refresh_interval, self._auto_refresh)
        self.root.after(100, self._pump_ui_queue)

    def _apply_theme(self, theme_key):
        global _current_theme
        _current_theme = theme_key
        _reload_colors()
        cfg["theme"] = theme_key
        self.root.after(10, self._rebuild_ui)

    def _apply_language(self, lang_key):
        global _current_lang
        _current_lang = lang_key
        _reload_lang()
        cfg["language"] = lang_key
        self.root.after(10, self._rebuild_ui)

    def _rebuild_ui(self):
        was_running = self.running
        self.automation_var = IntVar()
        self.systray_var    = IntVar()
        for w in self.root.winfo_children():
            try: w.destroy()
            except: pass
        self._setup_root()
        self._build_ui()
        self._load_checkbox_state()
        if was_running:
            self._set_status_running(True)
        self._refresh_files()
        cfg.save()

    def _setup_root(self):
        self.root.title("LinkDrop")
        self.root.geometry("980x680")
        self.root.minsize(820, 560)
        self.root.configure(bg=DARK_BG())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._set_window_icon)

        style = ttk.Style()
        try: style.theme_use("clam")
        except: pass

        DB = DARK_BG(); PB = PANEL_BG(); CB = CARD_BG()
        AC = ACCENT();  TM = TEXT_MAIN(); TD = TEXT_DIM()
        BOR = BORDER()

        style.configure("TFrame",           background=DB)
        style.configure("TLabel",           background=DB, foreground=TM, font=("Tahoma", 10))
        style.configure("TButton",          background=AC, foreground=DB, font=("Tahoma", 9, "bold"),
                         borderwidth=0, relief="flat", padding=(10, 6))
        style.map("TButton",                background=[("active", "#00b894"), ("disabled", "#3d4450")])
        style.configure("Treeview",         background=CB, foreground=TM, fieldbackground=CB,
                         rowheight=26, font=("Tahoma", 9))
        style.configure("Treeview.Heading", background=PB, foreground=TD, font=("Tahoma", 9, "bold"))
        style.map("Treeview",               background=[("selected", "#264f78")])
        style.configure("TEntry",           fieldbackground=CB, foreground=TM, insertcolor=TM,
                         borderwidth=1, relief="solid")
        style.configure("TNotebook",        background=DB, borderwidth=0)
        style.configure("TNotebook.Tab",    background=PB, foreground=TD, padding=(14, 8), font=("Tahoma", 10))
        style.map("TNotebook.Tab",          background=[("selected", CB)], foreground=[("selected", AC)])
        style.configure("TCombobox",        fieldbackground=CB, background=PB, foreground=TM, arrowcolor=TM)
        style.map("TCombobox",              fieldbackground=[("readonly", CB)],
                                            foreground=[("readonly", TM)], background=[("readonly", PB)])

        self.root.option_add("*TCombobox*Listbox.background",       CB)
        self.root.option_add("*TCombobox*Listbox.foreground",       TM)
        self.root.option_add("*TCombobox*Listbox.selectBackground", AC)
        self.root.option_add("*TCombobox*Listbox.selectForeground", DB)
        self.root.option_add("*TCombobox*Listbox.font", ("Tahoma", 10))

    def _set_window_icon(self):
        try:
            u32 = ctypes.windll.user32
            LR_LOADFROMFILE = 0x00000010; LR_SHARED = 0x00008000; LR_DEFAULTSIZE = 0x00000040
            IMAGE_ICON = 1; IDI_APPLICATION = 32512; WM_SETICON = 0x0080
            ico_path = resource_path("linkdrop.ico")
            if os.path.exists(ico_path):
                try: self.root.iconbitmap(ico_path)
                except: pass
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
                except: pass
            self.root.after(200, _apply_taskbar)
            try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LinkDrop.Server.Application")
            except: pass
        except: pass

    def _pump_ui_queue(self):
        try:
            with self._ui_lock:
                batch = [self._ui_queue.popleft() for _ in range(min(len(self._ui_queue), 20))]
            for msg_type, _payload in batch:
                if msg_type == "refresh": self._refresh_files()
        except: pass
        self.root.after(50, self._pump_ui_queue)

    def toggle_automation(self):
        cfg["autostart"] = (self.automation_var.get() == 1)
        self._set_autostart(cfg["autostart"])
        self._log_event({"type": "info", "content": "Automacao " + ("ativada" if cfg["autostart"] else "desativada"), "time": _now_iso()})
        cfg.save()

    def _set_autostart(self, enable):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "LinkDrop"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enable:
                exe = os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, '"%s"' % exe)
            else:
                try: winreg.DeleteValue(key, app_name)
                except OSError: pass
            winreg.CloseKey(key)
        except Exception as e: log.warning("Erro autostart: %s" % e)

    _WM_TRAY, _TRAY_ID = 0x8002, 2

    def toggle_systray(self):
        cfg["systray"] = bool(self.systray_var.get())
        cfg.save()

    def _hide_to_tray(self):
        if self._tray_active: return
        self._tray_active = True
        self.root.withdraw()
        if not (self._tray_thread and self._tray_thread.is_alive()):
            self._tray_thread = threading.Thread(target=self._tray_loop, daemon=True)
            self._tray_thread.start()

    def _show_from_tray(self):
        self._stop_tray_loop()
        self.root.deiconify(); self.root.lift(); self.root.focus_force()

    def _tray_loop(self):
        u32, s32, k32 = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
        WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_int)
        WM_DESTROY = 0x0002; WM_TRAY = self._WM_TRAY
        WM_LBUTTONDBLCLK = 0x0203; WM_RBUTTONUP = 0x0205
        NIM_ADD = 0; NIM_DELETE = 2; NIF_MESSAGE = 1; NIF_ICON = 2; NIF_TIP = 4
        TPM_RETURNCMD = 0x0100; TPM_RIGHTBUTTON = 0x0002
        MF_STRING = 0x0000; IDM_RESTORE = 2001; IDM_QUIT = 2002

        class WNDCLASSEX(ctypes.Structure):
            _fields_ = [("cbSize",ctypes.c_uint),("style",ctypes.c_uint),("lpfnWndProc",WNDPROCTYPE),
                ("cbClsExtra",ctypes.c_int),("cbWndExtra",ctypes.c_int),("hInstance",ctypes.c_void_p),
                ("hIcon",ctypes.c_void_p),("hCursor",ctypes.c_void_p),("hbrBackground",ctypes.c_void_p),
                ("lpszMenuName",ctypes.c_wchar_p),("lpszClassName",ctypes.c_wchar_p),("hIconSm",ctypes.c_void_p)]
        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [("cbSize",ctypes.c_ulong),("hWnd",ctypes.c_void_p),("uID",ctypes.c_uint),
                ("uFlags",ctypes.c_uint),("uCallbackMessage",ctypes.c_uint),("hIcon",ctypes.c_void_p),
                ("szTip",ctypes.c_wchar*128)]
        class POINT(ctypes.Structure): _fields_ = [("x",ctypes.c_long),("y",ctypes.c_long)]
        class MSG(ctypes.Structure):
            _fields_ = [("hwnd",ctypes.c_void_p),("message",ctypes.c_uint),
                ("wParam",ctypes.c_void_p),("lParam",ctypes.c_void_p),("time",ctypes.c_ulong),("pt",POINT)]

        cls_name  = "LinkDropTray_%d" % id(self)
        hinstance = k32.GetModuleHandleW(None)

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAY:
                evt = lparam & 0xFFFF
                if evt == WM_LBUTTONDBLCLK:
                    self.root.after(0, self._show_from_tray)
                elif evt == WM_RBUTTONUP:
                    pt = POINT(); u32.GetCursorPos(ctypes.byref(pt))
                    hmenu = u32.CreatePopupMenu()
                    u32.AppendMenuW(hmenu, MF_STRING, IDM_RESTORE, _T("tray_restore"))
                    u32.AppendMenuW(hmenu, MF_STRING, IDM_QUIT, _T("tray_quit"))
                    u32.SetForegroundWindow(hwnd)
                    cmd = u32.TrackPopupMenu(hmenu, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
                    u32.DestroyMenu(hmenu)
                    if cmd == IDM_RESTORE: self.root.after(0, self._show_from_tray)
                    elif cmd == IDM_QUIT: self.root.after(0, self._on_close)
                return 0
            return u32.DefWindowProcW(hwnd, msg, wparam, lparam)

        wnd_proc_cb = WNDPROCTYPE(wnd_proc)
        try:
            wc = WNDCLASSEX(cbSize=ctypes.sizeof(WNDCLASSEX), lpfnWndProc=wnd_proc_cb,
                hInstance=hinstance, lpszClassName=cls_name)
            u32.RegisterClassExW(ctypes.byref(wc))
            hwnd = u32.CreateWindowExW(0, cls_name, "LinkDrop Tray", 0, 0, 0, 0, 0, 0, 0, hinstance, None)
            self._tray_hwnd = hwnd
            hicon = self._hicon_small or 0
            nid = NOTIFYICONDATA(cbSize=ctypes.sizeof(NOTIFYICONDATA), hWnd=hwnd, uID=self._TRAY_ID,
                uFlags=NIF_MESSAGE|NIF_ICON|NIF_TIP, uCallbackMessage=WM_TRAY, hIcon=hicon, szTip="LinkDrop Server")
            s32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
            msg_struct = MSG()
            while self._tray_active:
                if u32.GetMessageW(ctypes.byref(msg_struct), hwnd, 0, 0) <= 0: break
                u32.TranslateMessage(ctypes.byref(msg_struct))
                u32.DispatchMessageW(ctypes.byref(msg_struct))
            s32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            u32.DestroyWindow(hwnd)
            u32.UnregisterClassW(cls_name, hinstance)
        except Exception as ex: log.warning("Erro tray_loop: %s" % ex)
        finally: self._tray_active = False

    def _stop_tray_loop(self):
        self._tray_active = False
        try:
            if self._tray_hwnd:
                ctypes.windll.user32.PostMessageW(self._tray_hwnd, 0x0012, 0, 0)
        except: pass

    def _load_checkbox_state(self):
        if cfg["autostart"]: self.automation_var.set(1)
        if cfg.get("systray", False):
            self.systray_var.set(1)
            self.root.after(400, self._hide_to_tray)

    def _on_unmap(self, event):
        if event.widget is self.root and self.systray_var.get() == 1 and not self._tray_active:
            self.root.after(50, self._hide_to_tray)

    def _build_ui(self):
        DB = DARK_BG(); PB = PANEL_BG(); AC = ACCENT(); TD = TEXT_DIM(); TM = TEXT_MAIN()
        BOR = BORDER(); RE = RED()

        header = tk.Frame(self.root, bg=PB, height=56)
        header.pack(fill="x", side="top"); header.pack_propagate(False)
        tk.Label(header, text="LinkDrop", bg=PB, fg=AC, font=("Tahoma", 16, "bold")).pack(side="left", padx=18)
        tk.Label(header, text="v%s" % APP_VERSION, bg=PB, fg=TD, font=("Tahoma", 9)).pack(side="left", padx=2)
        self.status_dot = tk.Label(header, text="O", bg=PB, fg=RE, font=("Tahoma", 16))
        self.status_dot.pack(side="right", padx=6)
        self.status_lbl = tk.Label(header, text=_T("status_stopped"), bg=PB, fg=RE, font=("Tahoma", 10))
        self.status_lbl.pack(side="right")
        self.ip_lbl = tk.Label(header, text="", bg=PB, fg=TD, font=("Courier", 9))
        self.ip_lbl.pack(side="right", padx=20)
        tk.Frame(self.root, bg=BOR, height=1).pack(fill="x")
        main = ttk.Frame(self.root); main.pack(fill="both", expand=True)
        self._build_sidebar(main)
        self._build_notebook(main)

    def _build_sidebar(self, parent):
        DB = DARK_BG(); PB = PANEL_BG(); CB = CARD_BG()
        AC = ACCENT(); AC2 = ACCENT2(); TM = TEXT_MAIN(); TD = TEXT_DIM(); BOR = BORDER()

        sidebar = tk.Frame(parent, bg=PB, width=240)
        sidebar.pack(side="left", fill="y"); sidebar.pack_propagate(False)
        tk.Frame(sidebar, bg=BOR, width=1).pack(side="right", fill="y")
        tk.Label(sidebar, text=_T("server_section"), bg=PB, fg=TD, font=("Tahoma", 8, "bold")).pack(anchor="w", padx=16, pady=6)
        self.btn_toggle = tk.Button(sidebar, text=_T("btn_start"), bg=AC, fg=DB,
            font=("Tahoma", 10, "bold"), bd=0, relief="flat", cursor="hand2",
            activebackground=AC, activeforeground=DB, command=self._toggle_server)
        self.btn_toggle.pack(fill="x", padx=16, pady=(4, 12))

        for attr, label_key, color in [("lbl_files_count", "label_files_shared", AC), ("lbl_events_count", "label_events_today", AC2)]:
            card  = tk.Frame(sidebar, bg=CB, bd=0); card.pack(fill="x", padx=12, pady=4)
            tk.Frame(card, bg=color, width=3).pack(side="left", fill="y")
            inner = tk.Frame(card, bg=CB); inner.pack(side="left", padx=10, pady=8, fill="x", expand=True)
            tk.Label(inner, text=_T(label_key), bg=CB, fg=TD, font=("Tahoma", 8)).pack(anchor="w")
            lbl = tk.Label(inner, text="0", bg=CB, fg=color, font=("Tahoma", 20, "bold"))
            lbl.pack(anchor="w"); setattr(self, attr, lbl)

        tk.Frame(sidebar, bg=BOR, height=1).pack(fill="x", padx=12, pady=12)
        tk.Label(sidebar, text=_T("quick_send"), bg=PB, fg=TD, font=("Tahoma", 8, "bold")).pack(anchor="w", padx=16, pady=6)
        self.quick_text = tk.Text(sidebar, height=4, bg=CB, fg=TM, insertbackground=TM,
            bd=0, padx=8, pady=6, font=("Tahoma", 9), wrap="word", relief="flat")
        self.quick_text.pack(fill="x", padx=12)
        tk.Button(sidebar, text=_T("btn_send_text"), bg="#1a3a5c", fg=AC2,
            font=("Tahoma", 9, "bold"), bd=0, relief="flat", cursor="hand2",
            activebackground="#1e4a6e", command=self._send_text_to_phone).pack(fill="x", padx=12, pady=(4, 12))

        tk.Frame(sidebar, bg=BOR, height=1).pack(fill="x", padx=12, pady=4)
        tk.Label(sidebar, text=_T("shared_dir"), bg=PB, fg=TD, font=("Tahoma", 8, "bold")).pack(anchor="w", padx=16, pady=6)
        self.path_lbl = tk.Label(sidebar, text=cfg["share_path"], bg=PB, fg=TD,
            font=("Tahoma", 8), wraplength=210, anchor="w", justify="left")
        self.path_lbl.pack(anchor="w", padx=16)
        tk.Button(sidebar, text=_T("btn_open_folder"), bg=CB, fg=TM, font=("Tahoma", 9),
            bd=0, relief="flat", cursor="hand2",
            command=lambda: os.startfile(cfg["share_path"])).pack(fill="x", padx=12, pady=4)
        tk.Button(sidebar, text=_T("btn_change_folder"), bg=CB, fg=TD, font=("Tahoma", 9),
            bd=0, relief="flat", cursor="hand2", command=self._change_folder).pack(fill="x", padx=12, pady=(0, 4))

    def _build_notebook(self, parent):
        nb = ttk.Notebook(parent); self._main_notebook = nb
        nb.pack(fill="both", expand=True)
        self._build_files_tab(nb)
        self._build_activity_tab(nb)
        self._build_clipboard_tab(nb)
        self._build_pcs_tab(nb)
        self._build_settings_tab(nb)

    def _build_files_tab(self, nb):
        DB = DARK_BG(); CB = CARD_BG(); AC = ACCENT(); AC2 = ACCENT2()
        TM = TEXT_MAIN(); GR = GREEN(); RE = RED()

        frame = ttk.Frame(nb); nb.add(frame, text=_T("tab_files"))
        toolbar = tk.Frame(frame, bg=DB); toolbar.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(toolbar, text=_T("files_title"), bg=DB, fg=TM, font=("Tahoma", 12, "bold")).pack(side="left")
        tk.Button(toolbar, text=_T("btn_add_folders"), bg="#1a3a5c", fg=AC2,
            font=("Tahoma", 9, "bold"), bd=0, relief="flat", cursor="hand2",
            command=self._dialog_add_folder).pack(side="right", padx=3)
        tk.Button(toolbar, text=_T("btn_add_files"), bg=AC, fg=DB,
            font=("Tahoma", 9, "bold"), bd=0, relief="flat", cursor="hand2",
            command=self._dialog_add_files).pack(side="right", padx=3)
        for txt_key, cmd, col in [("btn_refresh", self._refresh_files, CB), ("btn_delete", self._delete_file, "#3d1f1f")]:
            tk.Button(toolbar, text=_T(txt_key), bg=col, fg=TM, font=("Tahoma", 9, "bold"),
                bd=0, relief="flat", cursor="hand2", command=cmd).pack(side="right", padx=3)

        self._drop_hint = tk.Label(frame, text=_T("drop_hint"), bg="#1a2a1a", fg=GR, font=("Tahoma", 9), pady=6)
        self._drop_hint.pack(fill="x", padx=12, pady=(0, 2))

        cols = ("name", "size", "modified", "type")
        self.file_tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        for col, lbl_key, w in [("name","col_name",300),("size","col_size",90),("modified","col_modified",150),("type","col_type",80)]:
            self.file_tree.heading(col, text=_T(lbl_key)); self.file_tree.column(col, width=w, minwidth=60)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=vsb.set)
        self.file_tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=4)
        vsb.pack(side="left", fill="y", pady=4)

        self.file_tree.bind("<ButtonPress-1>",   self._on_drag_select_start)
        self.file_tree.bind("<B1-Motion>",       self._on_drag_select_motion)
        self.file_tree.bind("<ButtonRelease-1>", self._on_drag_release)
        self.file_tree.bind("<Double-1>",        self._open_file)
        self.file_tree.bind("<Button-3>",        self._show_context_menu)
        self._drag_start_item = None
        self._drag_start_y    = 0
        self._setup_drag_and_drop()

    def _on_drag_select_start(self, event):
        self._is_dragging   = True
        item = self.file_tree.identify_row(event.y)
        self._drag_start_y    = event.y
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
                    s = all_items.index(self._drag_start_item)
                    e = all_items.index(item_end)
                    if s > e: s, e = e, s
                    selection = all_items[s:e + 1]
                except ValueError: pass
        else:
            for i in all_items:
                bbox = self.file_tree.bbox(i)
                if bbox and (bbox[1] + bbox[3]) >= top and bbox[1] <= bottom:
                    selection.append(i)
        if selection:
            if event.state & 0x0004: self.file_tree.selection_add(selection)
            else: self.file_tree.selection_set(selection)

    def _on_drag_release(self, event): self._is_dragging = False

    def _setup_drag_and_drop(self):
        if not self._dnd_installed:
            self.root.after(500, self._register_win32_drop_targets)

    def _get_toplevel_hwnd(self):
        try:
            rid = self.root.winfo_id()
            return ctypes.windll.user32.GetAncestor(ctypes.c_void_p(int(rid)), 2) if rid else 0
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
            PTR_T  = ctypes.c_int64  if is64 else ctypes.c_int32
            UPTR_T = ctypes.c_uint64 if is64 else ctypes.c_uint32
            try: GetWL, SetWL = u32.GetWindowLongPtrW, u32.SetWindowLongPtrW
            except AttributeError: GetWL, SetWL = u32.GetWindowLongW, u32.SetWindowLongW
            old_proc = GetWL(PTR_T(hwnd_val), -4)
            if not old_proc: return False
            self._dnd_old_proc = old_proc; self._dnd_hwnd = hwnd_val

            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == 0x0233:
                    try:
                        num   = s32.DragQueryFileW(UPTR_T(wparam), 0xFFFFFFFF, None, 0)
                        paths = []
                        for i in range(num):
                            buf = ctypes.create_unicode_buffer(512)
                            s32.DragQueryFileW(UPTR_T(wparam), i, buf, 512)
                            if buf.value: paths.append(buf.value)
                        if paths: self.root.after(10, lambda p=paths[:]: self._import_paths_list(p))
                    finally: s32.DragFinish(UPTR_T(wparam))
                    return 0
                try:
                    return u32.CallWindowProcW(PTR_T(self._dnd_old_proc), PTR_T(hwnd), ctypes.c_uint(msg), UPTR_T(wparam), PTR_T(lparam))
                except OSError: return 0

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

    def _progress_show(self):
        self._progress_bar.pack(side="left", padx=(8, 4))
        self._lbl_progress_eta.pack(side="left")
        self._btn_cancel.pack(side="left", padx=(4, 0))

    def _progress_hide(self):
        self._progress_bar.pack_forget()
        self._lbl_progress_eta.pack_forget()
        self._btn_cancel.pack_forget()

    def _progress_start(self, file_count, total_bytes):
        if hasattr(self, "_hide_timer") and self._hide_timer:
            try: self.root.after_cancel(self._hide_timer)
            except: pass
            self._hide_timer = None
        self._cancel_event.clear()
        self._progress_bar["value"]   = 0
        self._progress_bar["maximum"] = max(total_bytes, 1)
        self._progress_show()

    def _progress_update(self, done_bytes, total_bytes, speed, eta):
        self._progress_bar["maximum"] = max(total_bytes, 1)
        self._progress_bar["value"]   = min(done_bytes, max(total_bytes, 1))
        if speed > 0:
            rem = max(0, eta)
            if rem < 60:    eta_text = "%.0fs" % rem
            elif rem < 3600: eta_text = "%.0fm %.0fs" % (rem // 60, rem % 60)
            else:            eta_text = "%.0fh %.0fm" % (rem // 3600, (rem % 3600) // 60)
            self._lbl_progress_eta.config(text=eta_text)

    def _cancel_transfer(self):
        self._cancel_is_user_action = True
        self._cancel_event.set()
        self._lbl_progress_eta.config(text="Cancelando...")

    def _progress_finish(self):
        self._progress_bar["value"] = self._progress_bar["maximum"]
        self._lbl_progress_eta.config(text="")
        self._hide_timer = self.root.after(1000, self._progress_hide)

    def _copy_single_file_progress(self, src, dst, report_cb):
        total = os.path.getsize(src)
        copied = 0; start = last_rpt = time.time()
        try:
            with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
                while True:
                    if self._cancel_event.is_set(): raise TransferCancelled()
                    buf = fsrc.read(_CHUNK)
                    if not buf: break
                    fdst.write(buf); copied += len(buf)
                    now = time.time()
                    if now - last_rpt >= 0.25:
                        elapsed = now - start
                        speed   = copied / elapsed if elapsed > 0 else 0
                        eta     = (total - copied) / speed if speed > 0 else 0
                        report_cb(copied, total, speed, eta)
                        last_rpt = now
        except TransferCancelled:
            try: os.remove(dst)
            except: pass
            raise
        report_cb(copied, total, 0, 0)
        return total

    def _import_paths_list(self, paths):
        try:
            mouse_x = self.root.winfo_pointerx()
            mouse_y = self.root.winfo_pointery()
            widget_under_mouse = self.root.winfo_containing(mouse_x, mouse_y)
            if widget_under_mouse and hasattr(self, 'remote_files_tree'):
                try:
                    remote_tree_parent = self.remote_files_tree.winfo_parent()
                except:
                    remote_tree_parent = ""
                is_over_remote_tree = (widget_under_mouse == self.remote_files_tree or remote_tree_parent in str(widget_under_mouse))
                if is_over_remote_tree and self._current_connected_iid and self._current_connected_iid in self._remote_clients:
                    client = self._remote_clients[self._current_connected_iid]
                    is_folder = any(os.path.isdir(p) for p in paths)
                    self.root.after(0, lambda c=client, ps=paths, fg=is_folder: self._start_upload(c, ps, fg))
                    return
        except Exception as e:
            pass

        total_bytes = 0; copy_ops = []
        for p in paths:
            p    = os.path.abspath(p)
            base = os.path.basename(p.rstrip(os.sep))
            if not base: continue
            if os.path.isfile(p):
                total_bytes += os.path.getsize(p)
                copy_ops.append((p, unique_path_under_share(base), None))
            elif os.path.isdir(p):
                share_abs = os.path.abspath(cfg["share_path"])
                parent_dir = os.path.dirname(p.rstrip(os.sep))
                for root, _dirs, files in os.walk(p):
                    for fn in files:
                        src_fp = os.path.join(root, fn)
                        rel    = os.path.relpath(src_fp, parent_dir)
                        dst_fp = os.path.join(share_abs, rel)
                        try: os.makedirs(os.path.dirname(dst_fp))
                        except: pass
                        total_bytes += os.path.getsize(src_fp)
                        copy_ops.append((src_fp, dst_fp, rel))
        if not copy_ops: return
        self._progress_start(len(copy_ops), total_bytes)

        def worker():
            done_bytes = added = 0; cancelled = False
            for src, dst, relname in copy_ops:
                if self._cancel_event.is_set(): cancelled = True; break
                try:
                    db = done_bytes
                    def report(c, t, s, e, db=db):
                        self.root.after(0, lambda: self._progress_update(db + c, total_bytes, s, e))
                    size = self._copy_single_file_progress(src, dst, report)
                    done_bytes += size; added += 1
                    d = relname or os.path.basename(src)
                    self.root.after(0, lambda d=d, s=size: self._log_event(
                        {"type":"upload","name":d,"content":"Drag & Drop: "+d,"size":s,"time":_now_iso()}))
                except TransferCancelled: cancelled = True; break
                except: pass
            self.root.after(0, self._progress_finish)
            if added > 0 and not cancelled:
                self.root.after(0, self._refresh_files)

        threading.Thread(target=worker, daemon=True).start()

    def _show_context_menu(self, event):
        row = self.file_tree.identify_row(event.y)
        if row: self.file_tree.selection_set(row)
        CB = CARD_BG(); TM = TEXT_MAIN(); RE = RED()
        menu = tk.Menu(self.root, tearoff=0, bg=CB, fg=TM, activebackground="#264f78",
            activeforeground=TM, font=("Tahoma", 9), bd=1, relief="solid")
        if row:
            menu.add_command(label=_T("ctx_open"),       command=self._open_file)
            menu.add_command(label=_T("ctx_open_admin"), command=self._open_as_admin)
            menu.add_command(label=_T("ctx_reveal"),     command=self._reveal_in_explorer)
            menu.add_separator()
            menu.add_command(label=_T("ctx_delete"), command=self._delete_file, foreground=RE, activeforeground=RE)
        else:
            menu.add_command(label=_T("ctx_add_files"),  command=self._dialog_add_files)
            menu.add_command(label=_T("ctx_add_folder"), command=self._dialog_add_folder)
            menu.add_separator()
            menu.add_command(label=_T("ctx_refresh"),    command=self._refresh_files)
            menu.add_command(label=_T("ctx_open_share"), command=lambda: os.startfile(cfg["share_path"]))
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
        name  = self.file_tree.item(sel[0], "values")[0]
        fpath = os.path.join(cfg["share_path"], name)
        if os.path.exists(fpath):
            try:
                s32 = ctypes.windll.shell32
                pf = s32.ILCreateFromPathW(os.path.dirname(fpath))
                pi = s32.ILCreateFromPathW(fpath)
                if pf and pi:
                    s32.SHOpenFolderAndSelectItems(pf, 1, (ctypes.c_void_p * 1)(pi), 0)
                    s32.ILFree(pf); s32.ILFree(pi)
                else: raise Exception()
            except: subprocess.Popen(["explorer", "/select," + fpath])

    def _build_activity_tab(self, nb):
        DB = DARK_BG(); CB = CARD_BG(); TM = TEXT_MAIN(); TD = TEXT_DIM()
        GR = GREEN(); AC = ACCENT(); AC2 = ACCENT2(); RE = RED()

        frame = ttk.Frame(nb); nb.add(frame, text=_T("tab_activity"))
        h = tk.Frame(frame, bg=DB); h.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(h, text=_T("activity_title"), bg=DB, fg=TM, font=("Tahoma", 12, "bold")).pack(side="left")
        tk.Button(h, text=_T("btn_clear"), bg=CB, fg=TD, bd=0, relief="flat", command=self._clear_log).pack(side="right")
        self.activity_box = scrolledtext.ScrolledText(frame, bg=CB, fg=TM, insertbackground=TM,
            font=("Courier", 9), bd=0, padx=10, pady=8, state="disabled", wrap="word")
        self.activity_box.pack(fill="both", expand=True, padx=12, pady=4)
        for t, c in [("time",TD),("upload",GR),("text",AC2),("clip",AC),("notify","#e8b100"),("delete",RE),("info",TD)]:
            self.activity_box.tag_config(t, foreground=c)

    def _build_clipboard_tab(self, nb):
        DB = DARK_BG(); CB = CARD_BG(); AC = ACCENT(); TM = TEXT_MAIN(); TD = TEXT_DIM()

        frame = ttk.Frame(nb); nb.add(frame, text=_T("tab_clipboard"))
        h = tk.Frame(frame, bg=DB); h.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(h, text=_T("clip_title"), bg=DB, fg=TM, font=("Tahoma", 12, "bold")).pack(side="left")
        r = tk.Frame(frame, bg=DB); r.pack(fill="x", padx=12, pady=4)
        tk.Button(r, text=_T("btn_show_clip"), bg=CB, fg=TM, bd=0, command=self._load_pc_clipboard).pack(side="left", padx=3)
        tk.Button(r, text=_T("btn_copy_clip"), bg=AC, fg=DB, bd=0, font=("Tahoma", 9, "bold"), command=self._copy_clip_to_pc).pack(side="left", padx=3)
        tk.Label(frame, text=_T("clip_last"), bg=DB, fg=TD, font=("Tahoma", 9)).pack(anchor="w", padx=14, pady=(8, 2))
        self.clip_box = tk.Text(frame, height=8, bg=CB, fg=TM, bd=0, padx=10, pady=8,
            font=("Tahoma", 10), wrap="word", relief="flat")
        self.clip_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_pcs_tab(self, nb):
        DB = DARK_BG(); CB = CARD_BG(); AC = ACCENT(); AC2 = ACCENT2()
        TM = TEXT_MAIN(); TD = TEXT_DIM(); RE = RED(); GR = GREEN()

        frame = ttk.Frame(nb); nb.add(frame, text=_T("tab_pcs"))
        toolbar = tk.Frame(frame, bg=DB); toolbar.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(toolbar, text=_T("pcs_title"), bg=DB, fg=TM, font=("Tahoma", 12, "bold")).pack(side="left")
        tk.Button(toolbar, text=_T("btn_edit_pc"), bg=CB, fg=TM, bd=0, cursor="hand2", command=self._edit_selected_pc).pack(side="right", padx=3)
        tk.Button(toolbar, text=_T("btn_add_pc"), bg=AC2, fg=DB, font=("Tahoma", 9, "bold"), bd=0, cursor="hand2", command=self._add_pc_dialog).pack(side="right", padx=3)
        self.btn_disconnect_pc = tk.Button(toolbar, text=_T("btn_disconnect_pc"), bg=RE, fg="white",
            font=("Tahoma", 9, "bold"), bd=0, cursor="hand2", command=self._disconnect_pc, state="disabled")
        self.btn_disconnect_pc.pack(side="right", padx=3)
        tk.Button(toolbar, text=_T("btn_connect_pc"), bg=AC, fg=DB, font=("Tahoma", 9, "bold"), bd=0, cursor="hand2", command=self._connect_selected_pc).pack(side="right", padx=3)
        self.btn_upload_folder = tk.Button(toolbar, text=_T("btn_upload_folder"), bg="#1a3a5c", fg=AC2,
            font=("Tahoma", 9, "bold"), bd=0, cursor="hand2", command=self._upload_folder_to_pc, state="disabled")
        self.btn_upload_folder.pack(side="right", padx=3)
        self.btn_upload_file = tk.Button(toolbar, text=_T("btn_upload_file"), bg="#1a3a5c", fg=AC2,
            font=("Tahoma", 9, "bold"), bd=0, cursor="hand2", command=self._upload_file_to_pc, state="disabled")
        self.btn_upload_file.pack(side="right", padx=3)

        paned = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        left_frame = ttk.Frame(paned); paned.add(left_frame, weight=1)
        self.pc_tree = ttk.Treeview(left_frame, columns=("name","host","status"), show="headings", selectmode="browse")
        for col, lbl, w in [("name","col_pc_name",120),("host","col_pc_host",120),("status","col_pc_status",80)]:
            self.pc_tree.heading(col, text=_T(lbl)); self.pc_tree.column(col, width=w)
        self.pc_tree.pack(fill=tk.BOTH, expand=True)

        right_frame = ttk.Frame(paned); paned.add(right_frame, weight=2)
        header_frame = tk.Frame(right_frame, bg=DB); header_frame.pack(fill=tk.X, anchor="w", pady=(0, 5))
        self.lbl_remote_files = tk.Label(header_frame, text=_T("pc_files_title"), bg=DB, fg=TM, font=("Tahoma", 10, "bold"))
        self.lbl_remote_files.pack(side="left")
        self._progress_bar = ttk.Progressbar(header_frame, mode="determinate", length=120)
        self._lbl_progress_eta = tk.Label(header_frame, text="", bg=DB, fg=TD, font=("Tahoma", 8))
        self._btn_cancel = tk.Button(header_frame, text="Cancelar", bg=RE, fg="white",
            font=("Tahoma", 8, "bold"), bd=0, cursor="hand2", command=self._cancel_transfer)
        style = ttk.Style()
        style.configure("green.Horizontal.TProgressbar", background=GR, troughcolor="#333333")
        self._progress_bar.configure(style="green.Horizontal.TProgressbar")
        self._hide_timer = None
        self._progress_hide()

        self.remote_files_tree = ttk.Treeview(right_frame, columns=("size","modified","type"), show="tree headings")
        for col, lbl, w, anc in [("#0","col_name",220,"w"),("size","col_size",80,"e"),("modified","col_modified",120,"w"),("type","col_type",60,"w")]:
            if col == "#0": self.remote_files_tree.heading(col, text=_T(lbl)); self.remote_files_tree.column(col, width=w)
            else: self.remote_files_tree.heading(col, text=_T(lbl)); self.remote_files_tree.column(col, width=w, anchor=anc)
        self.remote_files_tree.pack(fill=tk.BOTH, expand=True)

        self.pc_tree.bind("<Double-1>", lambda e: self._connect_selected_pc())
        self.pc_tree.bind("<Button-3>", self._show_pc_context_menu)
        self.remote_files_tree.bind("<Double-1>", self._remote_item_double_click)

        self._remote_clients          = {}
        self._current_connected_iid   = None
        self._remote_auto_refresh_active = False
        self._remote_auto_refresh_id  = None
        self._load_pcs_from_config()

    def _load_pcs_from_config(self):
        self.pc_tree.delete(*self.pc_tree.get_children())
        self._remote_clients.clear()
        for idx, pc in enumerate(cfg.get("remote_pcs", [])):
            iid = str(idx)
            hp  = "%s:%s" % (pc.get("host"), pc.get("port"))
            self.pc_tree.insert("", tk.END, iid=iid, values=(pc.get("name"), hp, _T("pc_status_offline")))
            self._remote_clients[iid] = RemotePCClient(pc.get("host"), pc.get("port"), pc.get("password", ""))
        if cfg.get("remote_pcs"): self._refresh_pc_list()

    def _refresh_pc_list(self):
        for idx, pc in enumerate(cfg.get("remote_pcs", [])):
            iid = str(idx)
            if not self.pc_tree.exists(iid): continue
            hp = "%s:%d" % (pc.get("host"), pc.get("port"))
            def check(ti, cl):
                ok, _ = cl.ping()
                status = _T("pc_status_online") if ok else _T("pc_status_offline")
                def _upd(ti=ti, status=status):
                    if self.pc_tree.exists(ti):
                        v = self.pc_tree.item(ti, "values")
                        self.pc_tree.item(ti, values=(v[0], v[1], status))
                self.root.after(0, _upd)
            threading.Thread(target=check, args=(iid, self._remote_clients[iid]), daemon=True).start()

    def _stop_remote_auto_refresh(self):
        self._remote_auto_refresh_active = False
        if self._remote_auto_refresh_id:
            try: self.root.after_cancel(self._remote_auto_refresh_id)
            except: pass
            self._remote_auto_refresh_id = None

    def _disconnect_pc(self):
        self._pending_transfers.clear()
        self._cancel_is_user_action = True
        self._cancel_event.set()
        iid = self._current_connected_iid
        pc_name = ""
        pc_host = ""
        if iid:
            client = self._remote_clients.get(iid)
            if client:
                pc_name = self.pc_tree.item(iid, "values")[0] if self.pc_tree.exists(iid) else ""
                pc_host = self.pc_tree.item(iid, "values")[1] if self.pc_tree.exists(iid) else ""
                client.abort_download()
            if self.pc_tree.exists(iid):
                self.pc_tree.item(iid, values=(pc_name, pc_host, _T("pc_status_offline")))
        for state in self._pending_transfers.values():
            dp = state.get("dest_path", "")
            if dp and os.path.isfile(dp):
                try: os.remove(dp)
                except: pass
        self._stop_remote_auto_refresh()
        self._current_connected_iid = None
        self.remote_files_tree.delete(*self.remote_files_tree.get_children())
        self.lbl_remote_files.config(text=_T("pc_files_title"))
        self.btn_disconnect_pc.config(state="disabled")
        self.btn_upload_file.config(state="disabled")
        self.btn_upload_folder.config(state="disabled")
        self._progress_hide()
        self._pending_transfers.clear()

    def _connect_selected_pc(self):
        selected = self.pc_tree.selection()
        if not selected: messagebox.showinfo("LinkDrop", _T("pc_no_selection")); return
        iid    = selected[0]
        client = self._remote_clients.get(iid)
        if not client: return
        self._stop_remote_auto_refresh()
        self._cancel_event.clear()
        self._pending_transfers.clear()
        pc_name = self.pc_tree.item(iid, "values")[0]
        pc_host = self.pc_tree.item(iid, "values")[1]
        self.lbl_remote_files.config(text="%s %s..." % (_T("pc_files_title"), pc_name))
        self.remote_files_tree.delete(*self.remote_files_tree.get_children())
        self.remote_files_tree.insert("", tk.END, text=_T("pc_status_connecting"), values=("","",""))
        self.btn_disconnect_pc.config(state="disabled")
        self._current_connected_iid      = iid
        self._remote_auto_refresh_active = True

        def fetch():
            success, info = client.ping()
            if not success:
                self.root.after(0, lambda: self.pc_tree.item(iid, values=(pc_name, pc_host, _T("pc_status_offline"))))
                self.root.after(0, lambda: self._show_remote_error("Falha na conexão")); return
            self.root.after(0, lambda: self.pc_tree.item(iid, values=(pc_name, pc_host, _T("pc_status_online"))))
            try:
                self._current_remote_dir = ""
                files = client.list_files("")
                self.root.after(0, lambda: self._render_remote_files(iid, files))
                for b in ("disconnect_pc", "upload_file", "upload_folder"):
                    self.root.after(0, lambda b=b: getattr(self, "btn_" + b).config(state="normal"))
                self.root.after(0, lambda: self._schedule_remote_refresh(iid, client))
            except Exception as e:
                self.root.after(0, lambda: self._show_remote_error("Falha na conexão"))

        threading.Thread(target=fetch, daemon=True).start()

    def _show_remote_error(self, message):
        self.remote_files_tree.delete(*self.remote_files_tree.get_children())
        self.remote_files_tree.insert("", tk.END, text="%s%s" % (_T("pc_connect_error"), message), values=("","",""))

    def _schedule_remote_refresh(self, iid, client, interval_ms=500):
        if not self._remote_auto_refresh_active or self._current_connected_iid != iid: return

        def silent_fetch():
            if not self._remote_auto_refresh_active or self._current_connected_iid != iid: return
            try:
                files = client.list_files(self._current_remote_dir)
                self.root.after(0, lambda: self._render_remote_files(iid, files))
            except:
                if self._remote_auto_refresh_active and self._current_connected_iid == iid:
                    pc_name = self.pc_tree.item(iid, "values")[0] if self.pc_tree.exists(iid) else ""
                    pc_host = self.pc_tree.item(iid, "values")[1] if self.pc_tree.exists(iid) else ""
                    self.root.after(0, lambda: self.pc_tree.item(iid, values=(pc_name, pc_host, _T("pc_status_offline"))))
                    self._stop_remote_auto_refresh()
                    self._current_connected_iid = None
                    self.root.after(0, lambda: self.btn_disconnect_pc.config(state="disabled"))
                    self.root.after(0, lambda: self.btn_upload_file.config(state="disabled"))
                    self.root.after(0, lambda: self.btn_upload_folder.config(state="disabled"))
                    self.root.after(0, lambda: self._show_remote_error("Falha na conexão"))
                return
            if self._remote_auto_refresh_active and self._current_connected_iid == iid:
                self._remote_auto_refresh_id = self.root.after(
                    interval_ms, lambda: self._schedule_remote_refresh(iid, client, interval_ms))

        self._remote_auto_refresh_id = self.root.after(
            interval_ms, lambda: threading.Thread(target=silent_fetch, daemon=True).start())

    def _render_remote_files(self, target_iid, files_list):
        if self._current_connected_iid != target_iid: return
        tree = self.remote_files_tree

        for item in list(tree.get_children()):
            if not tree.item(item, "tags"): tree.delete(item)

        existing = {}; back_item = None
        for item in tree.get_children():
            tags = tree.item(item, "tags")
            if tags and tags[0] == "__back__": back_item = item
            elif tags: existing[tags[0]] = item

        if self._current_remote_dir:
            parent_dir = os.path.dirname(self._current_remote_dir.rstrip("/\\"))
            if back_item: tree.item(back_item, tags=("__back__", parent_dir))
            else: tree.insert("", tk.END, text="..", values=("","","DIR"), tags=("__back__", parent_dir))
        elif back_item:
            tree.delete(back_item)

        if not files_list:
            for item in existing.values(): tree.delete(item)
            if not tree.get_children():
                tree.insert("", tk.END, text="(Vazia)", values=("","",""))
            return

        kids = tree.get_children()
        if kids and tree.item(kids[0], "text") == "(Vazia)":
            tree.delete(kids[0])

        sorted_files = sorted(files_list, key=lambda x: (not x.get("is_dir", False), x.get("name", "").lower()))
        seen = set()
        for f in sorted_files:
            key      = f.get("rel_path", f.get("name", ""))
            seen.add(key)
            size_str = "-" if f.get("is_dir") else _fmt_size(f.get("size", 0))
            mod_time = datetime.fromtimestamp(f.get("modified", 0)).strftime("%Y-%m-%d %H:%M")
            ext      = "DIR" if f.get("is_dir") else "FILE"
            name     = f.get("name", "Unknown")
            if key in existing:
                tree.item(existing[key], text=name, values=(size_str, mod_time, ext), tags=(key,))
            else:
                tree.insert("", tk.END, text=name, values=(size_str, mod_time, ext), tags=(key,))
        for key, item in list(existing.items()):
            if key not in seen: tree.delete(item)

    def _remote_item_double_click(self, _event=None):
        sel = self.remote_files_tree.selection()
        if not sel or not self._current_connected_iid: return
        item   = sel[0]
        text   = self.remote_files_tree.item(item, "text")
        values = self.remote_files_tree.item(item, "values")
        tags   = self.remote_files_tree.item(item, "tags")
        if text in ("(Vazia)", _T("pc_status_connecting")): return
        if tags and tags[0] == "__back__":
            self._current_remote_dir = tags[1]
            self._refresh_remote_current_dir(); return
        rel_path = tags[0] if tags else ""
        ext      = values[2] if len(values) > 2 else ""
        if ext == "DIR":
            self._current_remote_dir = rel_path
            self._refresh_remote_current_dir(); return
        self._download_remote_file()

    def _refresh_remote_current_dir(self):
        if not self._current_connected_iid: return
        client = self._remote_clients.get(self._current_connected_iid)
        if not client: return
        cur_iid = self._current_connected_iid
        cur_dir = self._current_remote_dir
        def fetch():
            try:
                files = client.list_files(cur_dir)
                self.root.after(0, lambda: self._render_remote_files(cur_iid, files))
            except Exception as e:
                self.root.after(0, lambda: self._show_remote_error("Falha na conexão"))
        threading.Thread(target=fetch, daemon=True).start()

    def _download_remote_file(self):
        sel = self.remote_files_tree.selection()
        if not sel or not self._current_connected_iid: return
        filename = self.remote_files_tree.item(sel[0], "text")
        if filename in ("(Vazia)", _T("pc_status_connecting")) or filename.startswith(_T("pc_connect_error")): return
        client = self._remote_clients.get(self._current_connected_iid)
        if not client: return
        dest_dir = filedialog.askdirectory(title=_T("dlg_select_folder"), initialdir=cfg["share_path"])
        if not dest_dir: return
        self._start_download(client, filename, dest_dir)

    def _start_download(self, client, filename, dest_dir, resume_from=0):
        self._cancel_is_user_action = False
        self._progress_start(1, 0)
        dest_path = os.path.join(dest_dir, os.path.basename(filename))
        state     = {"rel_path": filename, "dest_dir": dest_dir, "dest_path": dest_path, "downloaded": resume_from}

        def do_download():
            try:
                def rep(d, t, s, e):
                    self.root.after(0, lambda d=d, t=t, s=s, e=e: self._progress_update(d, t, s, e))
                client.download_file(filename, dest_dir, progress_cb=rep,
                    cancel_event=self._cancel_event, resume_from=resume_from, state=state)
                self.root.after(0, self._progress_finish)
                if not self._cancel_event.is_set():
                    self.root.after(0, lambda: messagebox.showinfo("Download", "%s %s" % (_T("pc_download_ok"), filename)))
                    self.root.after(0, self._refresh_files)
            except TransferCancelled:
                dp = state.get("dest_path", "")
                if dp and os.path.isfile(dp):
                    try: os.remove(dp)
                    except: pass
                self.root.after(0, self._progress_hide)
            except Exception as e:
                self.root.after(0, self._progress_hide)
                self.root.after(0, lambda: messagebox.showerror("Download", "%s %s" % (_T("pc_download_error"), e)))

        threading.Thread(target=do_download, daemon=True).start()

    def _upload_file_to_pc(self):
        if not self._current_connected_iid: return
        client = self._remote_clients.get(self._current_connected_iid)
        if not client: return
        paths = filedialog.askopenfilenames(title=_T("dlg_select_files"))
        if paths: self._start_upload(client, list(paths), False)

    def _upload_folder_to_pc(self):
        if not self._current_connected_iid: return
        client = self._remote_clients.get(self._current_connected_iid)
        if not client: return
        folder = filedialog.askdirectory(title=_T("dlg_select_folder"))
        if folder: self._start_upload(client, [folder], True)

    def _start_upload(self, client, paths, is_folder):
        self._cancel_is_user_action = False
        connected_iid = self._current_connected_iid

        if is_folder:
            folder = paths[0]
            fc = tb = 0
            for root, _dirs, files in os.walk(folder):
                for fn in files:
                    fc += 1; tb += os.path.getsize(os.path.join(root, fn))
            self._progress_start(fc, tb)
            def do_uf():
                try:
                    def rep(d, t, s, e):
                        self.root.after(0, lambda d=d, t=t, s=s, e=e: self._progress_update(d, t, s, e))
                    def fd(name, dc, tc):
                        pn = self.pc_tree.item(connected_iid, "values")[0] if self.pc_tree.exists(connected_iid) else ""
                        self.root.after(0, lambda: self.lbl_remote_files.config(
                            text="%s %s (%d/%d)" % (pn, _T("pc_files_title"), dc, tc)))
                    client.upload_folder(folder, progress_cb=rep, cancel_event=self._cancel_event, file_done_cb=fd)
                    self.root.after(0, self._progress_finish)
                    if not self._cancel_event.is_set():
                        self.root.after(0, lambda: messagebox.showinfo("Upload", "%s%s" % (_T("pc_upload_ok"), os.path.basename(folder))))
                        self._refresh_remote_current_dir()
                except TransferCancelled: self.root.after(0, self._progress_hide)
                except Exception as e:
                    self.root.after(0, self._progress_hide)
                    self.root.after(0, lambda: messagebox.showerror("Upload", "%s%s" % (_T("pc_upload_error"), e)))
            threading.Thread(target=do_uf, daemon=True).start()
        else:
            total_bytes = sum(os.path.getsize(p) for p in paths)
            self._progress_start(len(paths), total_bytes)
            def do_uf():
                done_bytes = 0; cancelled = False
                for idx, path in enumerate(paths):
                    if self._cancel_event.is_set(): cancelled = True; break
                    try:
                        db = done_bytes
                        def rep(sent, total, speed, eta, db=db):
                            self.root.after(0, lambda d=db+sent, t=total_bytes, s=speed, e=eta: self._progress_update(d, t, s, e))
                        client.upload_file_progress(path, progress_cb=rep, cancel_event=self._cancel_event)
                        done_bytes += os.path.getsize(path)
                        bn = os.path.basename(path)
                        self.root.after(0, lambda bn=bn: self._log_event(
                            {"type":"upload","name":bn,"content":"Upload: "+bn,"time":_now_iso()}))
                        self.root.after(0, lambda i=idx+1, t=len(paths): self.lbl_remote_files.config(
                            text="%s (%d/%d)" % (_T("pc_files_title"), i, t)))
                    except TransferCancelled: cancelled = True; break
                    except Exception as e:
                        self.root.after(0, lambda: messagebox.showerror("Upload", "%s - %s" % (path, e))); break
                self.root.after(0, self._progress_finish)
                if not cancelled:
                    self.root.after(0, lambda: messagebox.showinfo("Upload", "%s%d arquivo(s)" % (_T("pc_upload_ok"), len(paths))))
                    self._refresh_remote_current_dir()
            threading.Thread(target=do_uf, daemon=True).start()

    def _add_pc_dialog(self):
        self._open_pc_form_dialog(_T("dlg_add_pc_title"), {}, None)

    def _edit_selected_pc(self):
        sel = self.pc_tree.selection()
        if not sel: return
        idx = int(sel[0]); pcs = cfg.get("remote_pcs", [])
        if idx < len(pcs): self._open_pc_form_dialog(_T("dlg_edit_pc_title"), pcs[idx], idx)

    def _delete_selected_pc(self):
        sel = self.pc_tree.selection()
        if not sel: return
        idx = int(sel[0]); pcs = cfg.get("remote_pcs", [])
        if idx < len(pcs):
            name = pcs[idx].get("name", "")
            if messagebox.askyesno("LinkDrop", _T("dlg_delete_confirm").format(name)):
                pcs.pop(idx); cfg["remote_pcs"] = pcs; cfg.save()
                self._load_pcs_from_config()
                if self._current_connected_iid == str(idx):
                    self.remote_files_tree.delete(*self.remote_files_tree.get_children())
                    self.lbl_remote_files.config(text=_T("pc_files_title"))
                    self._current_connected_iid = None

    def _open_pc_form_dialog(self, title, data, edit_idx=None):
        DB = DARK_BG(); AC = ACCENT(); TM = TEXT_MAIN()
        dlg = tk.Toplevel(self.root)
        dlg.title(title); dlg.geometry("340x220"); dlg.resizable(False, False)
        dlg.transient(self.root); dlg.grab_set(); dlg.configure(bg=DB)
        dlg.geometry("+%d+%d" % (self.root.winfo_x() + 50, self.root.winfo_y() + 50))
        frame = tk.Frame(dlg, bg=DB); frame.pack(fill="both", expand=True, padx=20, pady=15)
        fields = [("lbl_pc_name","name",""), ("lbl_pc_host","host",""), ("lbl_pc_port","port",str(DEFAULT_PORT)), ("lbl_pc_pass","password","")]
        entries = {}
        for row_idx, (lbl_key, field, default) in enumerate(fields):
            tk.Label(frame, text=_T(lbl_key), bg=DB, fg=TM).grid(row=row_idx, column=0, sticky="w", pady=4)
            e = ttk.Entry(frame, width=24, show="*" if field=="password" else "")
            e.insert(0, str(data.get(field, default)))
            e.grid(row=row_idx, column=1, pady=4, sticky="e")
            entries[field] = e

        def save():
            name = entries["name"].get().strip()
            host = entries["host"].get().strip()
            pwd  = entries["password"].get()
            try: port = int(entries["port"].get().strip())
            except: messagebox.showerror("Erro", "Porta inválida.", parent=dlg); return
            if not name or not host:
                messagebox.showerror("Erro", "Campos obrigatórios faltando.", parent=dlg); return
            new_data = {"name": name, "host": host, "port": port, "password": pwd}
            pcs = cfg.get("remote_pcs", [])
            if edit_idx is not None: pcs[edit_idx] = new_data
            else: pcs.append(new_data)
            cfg["remote_pcs"] = pcs; cfg.save()
            self._load_pcs_from_config(); dlg.destroy()

        tk.Button(frame, text=_T("btn_save"), bg=AC, fg=DB, bd=0, font=("Tahoma", 9, "bold"),
            command=save).grid(row=len(fields), column=0, columnspan=2, pady=(15, 0), sticky="we")

    def _show_pc_context_menu(self, event):
        row = self.pc_tree.identify_row(event.y)
        if row: self.pc_tree.selection_set(row)
        CB = CARD_BG(); TM = TEXT_MAIN(); AC = ACCENT(); DB = DARK_BG()
        menu = tk.Menu(self.root, tearoff=0, bg=CB, fg=TM, activebackground=AC, activeforeground=DB,
            font=("Tahoma", 9), bd=1, relief="solid")
        if row:
            menu.add_command(label=_T("btn_connect_pc"), command=self._connect_selected_pc)
            menu.add_command(label=_T("btn_edit_pc"),    command=self._edit_selected_pc)
            menu.add_separator()
            menu.add_command(label=_T("btn_delete"),     command=self._delete_selected_pc)
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()

    def _build_settings_tab(self, nb):
        DB = DARK_BG(); CB = CARD_BG(); AC = ACCENT(); TM = TEXT_MAIN(); TD = TEXT_DIM()

        frame = ttk.Frame(nb); nb.add(frame, text=_T("tab_settings"))
        canvas = tk.Canvas(frame, bg=DB, highlightthickness=0); canvas.pack(fill="both", expand=True)
        inner  = tk.Frame(canvas, bg=DB); canvas.create_window(0, 0, window=inner, anchor="nw")

        def sec(t): tk.Label(inner, text=t, bg=DB, fg=AC, font=("Tahoma", 9, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
        def row(l, wf):
            r = tk.Frame(inner, bg=DB); r.pack(fill="x", padx=20, pady=3)
            tk.Label(r, text=l, bg=DB, fg=TM, width=22, anchor="w", font=("Tahoma", 10)).pack(side="left"); wf(r)

        sec(_T("sec_security")); self.pwd_var = tk.StringVar(value=cfg["password"])
        row(_T("lbl_password"), lambda r: ttk.Entry(r, textvariable=self.pwd_var, show="*", width=28).pack(side="left"))
        sec(_T("sec_network"));  self.host_var = tk.StringVar(value=cfg["host"])
        row(_T("lbl_host"),     lambda r: ttk.Entry(r, textvariable=self.host_var, width=28).pack(side="left"))
        self.port_var = tk.IntVar(value=cfg["port"])
        row(_T("lbl_port"),     lambda r: ttk.Entry(r, textvariable=self.port_var, width=10).pack(side="left"))
        self.ip_info = tk.Label(inner, bg=DB, fg=TD, font=("Courier", 9), justify="left")
        self.ip_info.pack(anchor="w", padx=20, pady=10); self._update_ip_display()

        sec(_T("sec_extras"))
        self.notify_var = tk.BooleanVar(value=cfg["notify"])
        self.clip_var   = tk.BooleanVar(value=cfg["clipboard_sync"])
        for v, t in [(self.notify_var, _T("chk_notify")), (self.clip_var, _T("chk_clip_sync"))]:
            r = tk.Frame(inner, bg=DB); r.pack(fill="x", padx=20, pady=2)
            tk.Checkbutton(r, variable=v, text=t, bg=DB, fg=TM, selectcolor=CB, font=("Tahoma", 10)).pack(side="left")
        for v, t, c in [(self.automation_var, _T("chk_autostart"), self.toggle_automation),
                        (self.systray_var,    _T("chk_systray"),   self.toggle_systray)]:
            r = tk.Frame(inner, bg=DB); r.pack(fill="x", padx=20, pady=2)
            Checkbutton(r, variable=v, text=t, command=c, bg=DB, fg=TM, selectcolor=CB, font=("Tahoma", 10)).pack(side="left")

        def build_lang_cb(r):
            lang_labels = ["Português", "English", "Español"]
            lang_codes  = ["pt", "en", "es"]
            cb = ttk.Combobox(r, values=lang_labels, state="readonly", width=20)
            cb.pack(side="left")
            try: cb.current(lang_codes.index(_current_lang))
            except: cb.current(0)
            cb.bind("<<ComboboxSelected>>", lambda e: self._apply_language(lang_codes[cb.current()]))
        row(_T("lbl_language"), build_lang_cb)

        def build_theme_cb(r):
            theme_labels = [_T("theme_dark"), _T("theme_light")]
            theme_codes  = ["dark", "light"]
            cb = ttk.Combobox(r, values=theme_labels, state="readonly", width=20)
            cb.pack(side="left")
            try: cb.current(theme_codes.index(_current_theme))
            except: cb.current(0)
            cb.bind("<<ComboboxSelected>>", lambda e: self._apply_theme(theme_codes[cb.current()]))
        row(_T("lbl_theme"), build_theme_cb)

        self.root.bind("<Unmap>", self._on_unmap)
        tk.Button(inner, text=_T("btn_save"), bg=AC, fg=DB, font=("Tahoma", 10, "bold"),
            bd=0, padx=16, pady=8, command=self._save_settings).pack(padx=20, pady=16, anchor="w")

    def _start_server_auto(self): self._start_server()

    def _start_server(self):
        if self.running: return
        self.server_thread = ServerThread(cfg["port"])
        self.server_thread.start()
        time.sleep(0.4)
        if self.server_thread.error:
            messagebox.showerror("LinkDrop", "Erro na porta %d: %s" % (cfg["port"], self.server_thread.error)); return
        self.running = True
        self._set_status_running(True)
        self._log_event({"type": "info", "content": "Server started", "time": _now_iso()})

    def _stop_server(self):
        if self.server_thread: self.server_thread.stop(); self.server_thread = None
        self.running = False; self._set_status_running(False)
        self._log_event({"type": "info", "content": "Server stopped", "time": _now_iso()})

    def _toggle_server(self):
        if self.running: self._stop_server()
        else: self._start_server()

    def _set_status_running(self, on):
        c, t = (GREEN(), _T("status_running")) if on else (RED(), _T("status_stopped"))
        self.status_dot.config(fg=c)
        self.status_lbl.config(fg=c, text=t)
        self.btn_toggle.config(
            text=(_T("btn_stop") if on else _T("btn_start")),
            bg=(RED() if on else ACCENT()),
            fg=("white" if on else DARK_BG()))
        if on: self._update_ip_display()
        else:  self.ip_lbl.config(text="")

    def _on_event(self, event):
        self.root.after(0, lambda: self._handle_event(event))

    def _handle_event(self, event):
        self._activity_log.append(event)
        self._log_event(event)
        etype = event.get("type", "")
        if etype in ("upload", "text", "delete"):
            self._refresh_files()
        if etype == "clipboard":
            self.clip_box.delete("1.0", "end")
            self.clip_box.insert("end", event.get("content", ""))
        today = datetime.now().strftime("%Y-%m-%d")
        cnt   = sum(1 for e in self._activity_log if e.get("time", "").startswith(today))
        self.lbl_events_count.config(text=str(cnt))
        self._last_activity_ts = time.time()

    _LOG_TYPE_TAG = {"upload":"upload","text":"text","clipboard":"clip","notification":"notify","delete":"delete"}
    _LOG_TYPE_LBL = {"upload":"UP","text":"TXT","clipboard":"CLP","notification":"NOT","delete":"DEL","info":"INF"}

    def _log_event(self, event):
        etype   = event.get("type", "info")
        ts      = event.get("time", "")[:19].replace("T", " ")
        content = event.get("content", event.get("name", ""))
        tag     = self._LOG_TYPE_TAG.get(etype, "info")
        lbl     = self._LOG_TYPE_LBL.get(etype, "*")
        self.activity_box.config(state="normal")
        self.activity_box.insert("end", "  %s  " % ts, "time")
        self.activity_box.insert("end", "[%s] %s\n" % (lbl, content[:80]), tag)
        self.activity_box.see("end")
        self.activity_box.config(state="disabled")

    def _clear_log(self):
        self.activity_box.config(state="normal")
        self.activity_box.delete("1.0", "end")
        self.activity_box.config(state="disabled")
        self._activity_log.clear()

    def _refresh_files(self, sub_dir=None):
        if self._is_dragging: return
        if sub_dir is not None:
            self._current_local_dir = sub_dir

        cur_sel = set(
            self.file_tree.item(i, "values")[0]
            for i in self.file_tree.selection()
            if self.file_tree.item(i, "values")
        )

        def _do_refresh():
            base_share = os.path.abspath(cfg["share_path"])
            target_dir = os.path.abspath(os.path.join(base_share, self._current_local_dir)) if self._current_local_dir else base_share
            if not target_dir.startswith(base_share): return

            try: names = os.listdir(target_dir)
            except: self.root.after(0, lambda: self.lbl_files_count.config(text="0")); return

            items = []
            for name in names:
                try:
                    full = os.path.join(target_dir, name)
                    st   = os.stat(full)
                    items.append((name, st, os.path.isdir(full)))
                except: pass

            items.sort(key=lambda x: (not x[2], x[0].lower()))

            def _update_tree():
                tree = self.file_tree
                tree.delete(*tree.get_children())
                if self._current_local_dir:
                    parent_dir = os.path.dirname(self._current_local_dir.replace("\\", "/"))
                    tree.insert("", "end", values=("..", "", "", "DIR"), tags=("__back__", parent_dir))
                for name, st, is_dir in items:
                    sz  = "-" if is_dir else _fmt_size(st.st_size)
                    mod = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                    ext = "DIR" if is_dir else (os.path.splitext(name)[1].lstrip(".").upper() or "FILE")
                    rel = os.path.relpath(os.path.join(target_dir, name), base_share).replace("\\", "/")
                    node = tree.insert("", "end", values=(name, sz, mod, ext), tags=(rel,))
                    if name in cur_sel: tree.selection_add(node)
                self.lbl_files_count.config(text=str(len(items)))

            self.root.after(0, _update_tree)

        threading.Thread(target=_do_refresh, daemon=True).start()

    def _auto_refresh(self):
        if self.running: self._refresh_files()
        recent = (time.time() - self._last_activity_ts) < 10
        interval = 500 if recent else 2000
        self.root.after(interval, self._auto_refresh)

    def _open_file(self, _e=None):
        sel = self.file_tree.selection()
        if not sel: return
        item   = sel[0]
        values = self.file_tree.item(item, "values")
        tags   = self.file_tree.item(item, "tags")
        if not values: return
        ext    = values[3] if len(values) > 3 else ""
        if tags and tags[0] == "__back__":
            self._refresh_files(tags[1]); return
        rel_path  = tags[0]
        full_path = os.path.abspath(os.path.join(cfg["share_path"], rel_path))
        if os.path.isdir(full_path) or ext == "DIR":
            self._refresh_files(rel_path); return
        try: os.startfile(full_path)
        except Exception as e: messagebox.showerror("Erro", str(e))

    def _dialog_add_files(self):
        ps = filedialog.askopenfilenames(title=_T("dlg_select_files"))
        if ps: self._import_paths_list(list(ps))

    def _dialog_add_folder(self):
        f = filedialog.askdirectory(title=_T("dlg_select_folder"))
        if f: self._import_paths_list([f])

    def _delete_file(self):
        sel = self.file_tree.selection()
        if not sel: return
        names = [self.file_tree.item(i, "values")[0] for i in sel]
        if messagebox.askyesno(_T("btn_delete"), _T("dlg_delete_confirm").format(len(names))):
            for n in names:
                p = os.path.join(cfg["share_path"], n)
                try:
                    if os.path.isdir(p): shutil.rmtree(p)
                    else: os.remove(p)
                except: pass
            self._refresh_files()

    def _load_pc_clipboard(self):
        pc = _get_pyperclip()
        if pc: self.clip_box.delete("1.0", "end"); self.clip_box.insert("end", pc.paste())
        else:  messagebox.showwarning(_T("tab_clipboard"), _T("dlg_no_pyperclip"))

    def _copy_clip_to_pc(self):
        text = self.clip_box.get("1.0", "end").strip()
        pc   = _get_pyperclip()
        if pc:
            try: pc.copy(text)
            except: pass
        messagebox.showinfo(_T("tab_clipboard"), _T("dlg_clip_copied"))

    def _send_text_to_phone(self):
        txt = self.quick_text.get("1.0", "end").strip()
        if not txt: return
        fn = "from_pc_%s.txt" % datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(cfg["share_path"], fn), "w", encoding="utf-8") as f:
            f.write(txt)
        self._refresh_files(); self.quick_text.delete("1.0", "end")

    def _save_settings(self):
        try:
            cfg["password"]       = self.pwd_var.get()
            cfg["host"]           = self.host_var.get().strip()
            cfg["port"]           = int(self.port_var.get())
            cfg["notify"]         = self.notify_var.get()
            cfg["clipboard_sync"] = self.clip_var.get()
            cfg.save(); self._update_ip_display()
            messagebox.showinfo(_T("dlg_saved_title"), _T("dlg_saved_msg"))
        except: messagebox.showerror("Error", _T("dlg_invalid_port"))

    def _change_folder(self):
        n = filedialog.askdirectory(initialdir=cfg["share_path"])
        if n: cfg["share_path"] = n; cfg.save(); self.path_lbl.config(text=n); self._refresh_files()

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
            return ip
        except:
            try: return socket.gethostbyname(socket.gethostname())
            except: return "127.0.0.1"

    def _update_ip_display(self):
        rip       = self._get_local_ip()
        conf_host = self.host_var.get().strip()
        disp      = conf_host if conf_host and conf_host != "0.0.0.0" else rip
        self.ip_info.config(text="IP Local: %s\nConnect: http://%s:%s" % (rip, disp, cfg["port"]))
        if self.running: self.ip_lbl.config(text="http://%s:%s" % (disp, cfg["port"]))

    def _on_close(self):
        if self.systray_var.get() == 1: self._hide_to_tray(); return
        self._stop_remote_auto_refresh()
        self._stop_tray_loop()
        self._teardown_win32_drop_targets()
        self._stop_server()
        cfg.save()
        self.root.destroy()


def main():
    try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LinkDrop.Server.Application")
    except: pass
    root = tk.Tk()
    ico_path = resource_path("linkdrop.ico")
    png_path = resource_path("linkdrop.png")
    if os.path.exists(ico_path):
        try: root.iconbitmap(default=ico_path)
        except: pass
    elif os.path.exists(png_path):
        pil = _get_pil()
        if pil:
            try:
                Image, ImageTk = pil
                img = Image.open(png_path); photo = ImageTk.PhotoImage(img)
                root.tk.call("wm", "iconphoto", root._w, "-default", photo)
                root._linkdrop_icon = photo
            except: pass
    root.update()
    app = LinkDropGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
