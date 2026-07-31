import sys
import ctypes
import winreg
import subprocess
import customtkinter as ctk

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# ---------- Палитра ----------
BG = "#0b0c10"
CARD = "#15171d"
CARD_BORDER = "#22252e"
ACCENT = "#7c5cff"       # фиолетовый акцент — используется вместо "зелёное = хорошо"
ACCENT_HOVER = "#6a4de0"
TEXT_MAIN = "#f4f4f6"
TEXT_DIM = "#8b8d98"
GREEN = "#22c55e"
RED = "#ef4444"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def check_registry_ttl():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
            0,
            winreg.KEY_READ,
        )
        value, _ = winreg.QueryValueEx(key, "DefaultTTL")
        winreg.CloseKey(key)
        return value == 65
    except FileNotFoundError:
        return False
    except Exception:
        return False


def list_interfaces():
    """Получаем реальные имена сетевых интерфейсов через netsh, чтобы не хардкодить."""
    try:
        res = subprocess.run(
            'netsh interface ipv4 show interfaces',
            shell=True, capture_output=True
        )
        # Кодировка консоли Windows зависит от локали/настроек системы:
        # чаще всего CP866, иногда CP1251, на новых системах с "Beta UTF-8" — UTF-8.
        # Пробуем по очереди и берём первую, которая раскодировалась без ошибок.
        raw = None
        for enc in ("cp866", "cp1251", "utf-8"):
            try:
                raw = res.stdout.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if raw is None:
            raw = res.stdout.decode("utf-8", errors="replace")

        names = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].isdigit():
                name = " ".join(parts[4:])
                if name.lower() not in ("loopback pseudo-interface 1",):
                    names.append(name)
        return names or ["Wi-Fi"]
    except Exception:
        return ["Wi-Fi"]


def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.returncode == 0, res.stderr.strip()
    except Exception as e:
        return False, str(e)


class BypassApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Freehop")
        self.geometry("400x520")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.font_title = ("Segoe UI Semibold", 17)
        self.font_body = ("Segoe UI", 13)
        self.font_small = ("Segoe UI", 11)
        self.font_log = ("Cascadia Mono", 10)

        self.interfaces = list_interfaces()

        self._build_header()
        self._build_status_card()
        self._build_interface_picker()
        self._build_ttl_picker()
        self._build_toggle()
        self._build_log()

        self.check_initial_state()

    # ---------- UI blocks ----------

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(padx=20, pady=(22, 10), fill="x")

        ctk.CTkLabel(
            header, text="Hotspot Bypass", font=self.font_title, text_color=TEXT_MAIN
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Обход снижения скорости раздачи",
            font=self.font_small,
            text_color=TEXT_DIM,
        ).pack(anchor="w", pady=(2, 0))

    def _build_status_card(self):
        self.status_card = ctk.CTkFrame(
            self, fg_color=CARD, corner_radius=14, border_width=1, border_color=CARD_BORDER
        )
        self.status_card.pack(padx=20, pady=10, fill="x")

        inner = ctk.CTkFrame(self.status_card, fg_color="transparent")
        inner.pack(padx=16, pady=14, fill="x")

        self.dot = ctk.CTkLabel(inner, text="●", font=("Arial", 16), text_color=RED)
        self.dot.pack(side="left", padx=(0, 10))

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)

        self.status_text = ctk.CTkLabel(
            text_col, text="Обход выключен", font=self.font_body, text_color=TEXT_MAIN, anchor="w"
        )
        self.status_text.pack(anchor="w")

        self.status_sub = ctk.CTkLabel(
            text_col, text="TTL не изменён", font=self.font_small, text_color=TEXT_DIM, anchor="w"
        )
        self.status_sub.pack(anchor="w")

    def _build_interface_picker(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(padx=20, pady=(4, 4), fill="x")

        ctk.CTkLabel(
            wrap, text="СЕТЕВОЙ ИНТЕРФЕЙС", font=("Segoe UI", 10, "bold"), text_color=TEXT_DIM
        ).pack(anchor="w", pady=(0, 6))

        self.iface_var = ctk.StringVar(value=self.interfaces[0])
        self.iface_menu = ctk.CTkOptionMenu(
            wrap,
            values=self.interfaces,
            variable=self.iface_var,
            fg_color=CARD,
            button_color=CARD_BORDER,
            button_hover_color="#2a2d38",
            text_color=TEXT_MAIN,
            corner_radius=10,
            height=38,
        )
        self.iface_menu.pack(fill="x")

    def _build_ttl_picker(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(padx=20, pady=(10, 4), fill="x")

        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x")

        ctk.CTkLabel(
            row, text="TTL", font=("Segoe UI", 10, "bold"), text_color=TEXT_DIM
        ).pack(anchor="w", pady=(0, 6))

        # 65 — самое частое значение (телефон обычно ставит 64, роутер после NAT съедает 1 хоп).
        # Если оператор детектит иначе, можно попробовать 63/62 — иногда помогает при двойном NAT.
        self.ttl_var = ctk.StringVar(value="65")
        self.ttl_menu = ctk.CTkOptionMenu(
            row,
            values=["65", "64", "63", "62"],
            variable=self.ttl_var,
            fg_color=CARD,
            button_color=CARD_BORDER,
            button_hover_color="#2a2d38",
            text_color=TEXT_MAIN,
            corner_radius=10,
            height=34,
            width=110,
        )
        self.ttl_menu.pack(anchor="w")

        ctk.CTkLabel(
            wrap,
            text="Если 65 не помогает — попробуй 64 или 63",
            font=self.font_small,
            text_color=TEXT_DIM,
        ).pack(anchor="w", pady=(4, 0))

    def _build_toggle(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(padx=20, pady=(14, 4), fill="x")

        row = ctk.CTkFrame(wrap, fg_color=CARD, corner_radius=14, border_width=1, border_color=CARD_BORDER)
        row.pack(fill="x")

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(padx=16, pady=14, fill="x")

        ctk.CTkLabel(
            inner, text="Включить обход", font=self.font_body, text_color=TEXT_MAIN
        ).pack(side="left")

        self.switch_var = ctk.BooleanVar(value=False)
        self.switch = ctk.CTkSwitch(
            inner,
            text="",
            variable=self.switch_var,
            command=self.on_toggle,
            progress_color=ACCENT,
            button_color="#e4e4e7",
            button_hover_color="#ffffff",
            width=44,
        )
        self.switch.pack(side="right")

        self.help_btn = ctk.CTkButton(
            wrap,
            text="Скорость не увеличилась?",
            font=self.font_small,
            height=26,
            corner_radius=8,
            fg_color="transparent",
            hover_color=CARD,
            text_color=TEXT_DIM,
            command=self.show_help_popup,
        )
        self.help_btn.pack(pady=(6, 0))

    def _build_log(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(padx=20, pady=(14, 20), fill="both", expand=True)

        ctk.CTkLabel(
            wrap, text="ЖУРНАЛ", font=("Segoe UI", 10, "bold"), text_color=TEXT_DIM
        ).pack(anchor="w", pady=(0, 6))

        self.log_frame = ctk.CTkFrame(
            wrap, fg_color=CARD, corner_radius=12, border_width=1, border_color=CARD_BORDER
        )
        self.log_frame.pack(fill="both", expand=True)

        self.log_box = ctk.CTkTextbox(
            self.log_frame,
            font=self.font_log,
            fg_color="transparent",
            text_color="#a1a1aa",
            activate_scrollbars=True,
        )
        self.log_box.pack(padx=10, pady=8, fill="both", expand=True)
        self.log_box.configure(state="disabled")

    # ---------- Logic ----------

    def show_help_popup(self):
        # Не открываем второе окно, если оно уже открыто
        if getattr(self, "_help_win", None) is not None and self._help_win.winfo_exists():
            self._help_win.lift()
            return

        win = ctk.CTkToplevel(self)
        self._help_win = win
        win.title("Совет")
        win.geometry("300x200")
        win.resizable(False, False)
        win.configure(fg_color=CARD)
        win.attributes("-topmost", True)
        win.grab_set()  # модальное окно поверх основного

        # Заголовок с крестиком
        header = ctk.CTkFrame(win, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 0))

        ctk.CTkLabel(
            header, text="Скорость не растёт?", font=self.font_body, text_color=TEXT_MAIN
        ).pack(side="left")

        close_btn = ctk.CTkButton(
            header,
            text="✕",
            width=26,
            height=26,
            corner_radius=8,
            fg_color="transparent",
            hover_color="#2a2d38",
            text_color=TEXT_DIM,
            command=win.destroy,
        )
        close_btn.pack(side="right")

        # Текст совета
        ctk.CTkLabel(
            win,
            text=(
                "Попробуйте:\n\n"
                "1. Включить раздачу в диапазоне 5 ГГц "
                "(в настройках точки доступа на телефоне)\n\n"
                "2. Перезагрузить компьютер"
            ),
            font=self.font_small,
            text_color="#c4c6d0",
            justify="left",
            wraplength=260,
        ).pack(padx=14, pady=(10, 14), anchor="w")

        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def add_log(self, text, ok=None):
        prefix = "› "
        if ok is True:
            prefix = "✓ "
        elif ok is False:
            prefix = "✗ "
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{prefix}{text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_state_ui(self, enabled: bool):
        if enabled:
            ttl = self.ttl_var.get() if hasattr(self, "ttl_var") else "65"
            self.dot.configure(text_color=GREEN)
            self.status_text.configure(text="Обход включен")
            self.status_sub.configure(text=f"TTL = {ttl}, MTU снижен")
        else:
            self.dot.configure(text_color=RED)
            self.status_text.configure(text="Обход выключен")
            self.status_sub.configure(text="TTL не изменён")
        self.switch_var.set(enabled)

    def check_initial_state(self):
        enabled = check_registry_ttl()
        self.set_state_ui(enabled)
        if enabled:
            self.add_log("Найден DefaultTTL в реестре — обход уже активен", ok=True)
        else:
            self.add_log("DefaultTTL отсутствует — заводской режим", ok=None)

    def on_toggle(self):
        if self.switch_var.get():
            self.enable()
        else:
            self.disable()

    def enable(self):
        iface = self.iface_var.get()
        ttl = self.ttl_var.get()
        self.add_log(f"Включаем обход (TTL={ttl})…")

        ok1, err1 = run_cmd(
            'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters" '
            f'/v DefaultTTL /t REG_DWORD /d {ttl} /f'
        )
        run_cmd(f"netsh int ipv4 set global defaultcurhoplimit={ttl}")
        run_cmd(f"netsh int ipv6 set global defaultcurhoplimit={ttl}")
        self.add_log(f"TTL установлен в реестре ({ttl})", ok=ok1)
        if not ok1 and err1:
            self.add_log(f"Ошибка: {err1}", ok=False)

        ok2, err2 = run_cmd(
            f'netsh interface ipv4 set subinterface "{iface}" mtu=1380 store=persistent'
        )
        run_cmd("ipconfig /flushdns")
        self.add_log(f"MTU снижен до 1380 на «{iface}»", ok=ok2)
        if not ok2 and err2:
            self.add_log(f"Ошибка: {err2}", ok=False)

        self.set_state_ui(True)
        self.add_log("Готово. Переподключи Wi-Fi и проверь скорость.")

        if not (ok1 and ok2):
            self.add_log(
                "Часть команд не выполнилась — проверь права администратора.", ok=False
            )
        else:
            self.add_log(
                "Если скорость всё равно режется — оператор, вероятно, "
                "детектит не по TTL, а по DPI. Этот способ тогда не поможет.",
                ok=None,
            )

    def disable(self):
        iface = self.iface_var.get()
        self.add_log("Сбрасываем настройки…")

        ok1, _ = run_cmd(
            'reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters" '
            '/v DefaultTTL /f'
        )
        self.add_log("Ключ DefaultTTL удалён из реестра", ok=ok1)

        run_cmd("netsh int ipv4 set global defaultcurhoplimit=64")
        run_cmd("netsh int ipv6 set global defaultcurhoplimit=64")
        ok2, _ = run_cmd(
            f'netsh interface ipv4 set subinterface "{iface}" mtu=1500 store=persistent'
        )
        self.add_log(f"MTU возвращён на 1500 на «{iface}»", ok=ok2)

        self.set_state_ui(False)
        self.add_log("Настройки полностью сброшены.")


if __name__ == "__main__":
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    else:
        app = BypassApp()
        app.mainloop()