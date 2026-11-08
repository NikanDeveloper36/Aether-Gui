#!/usr/bin/env python3
"""Aether GUI v2.0.0 — Desktop client matching Aether-GUI (Tauri) design.
Built by Nikan (Nikan.Developer) - NikanDeveloper56.github.io
"""

import sys, os, subprocess, threading, time, json, signal, socket, struct, math, random

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)

ICON_PATH = os.path.join(APP_DIR, "icon.ico")

import customtkinter as ctk

VERSION = "2.1.0"
MAX_AUTO_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]

CONNECT_TIMEOUTS = {
    "turbo": 90, "balanced": 150, "thorough": 330,
    "stealth": 210, "ironclad": 240,
}

# ── Exact Aether-GUI color palette ──
COLORS = {
    "bg":           "#0d0d0f",
    "surface":      "#1a1a1a",
    "surface2":     "#1e1e1e",
    "surface3":     "#242424",
    "surface4":     "#2a2a2a",
    "foreground":   "#f2f2f2",
    "muted":        "#a3a3a3",
    "border":       "#2a2a2a",
    "primary":      "#f2711c",
    "primary_fg":   "#0d0d0f",
    "connected":    "#2dd4bf",
    "connecting":   "#f2711c",
    "error":        "#ef4444",
    "idle":         "#6b7280",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

if os.path.isfile(ICON_PATH):
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("nikan.aether.gui")
    except Exception:
        pass

PROTOCOLS = ["WireGuard", "MASQUE (HTTP/3)", "MASQUE (HTTP/2)", "WARP-in-WARP"]
SCAN_MODES = ["Ironclad", "Thorough", "Stealth", "Balanced", "Turbo"]

STATE_IDLE = "idle"
STATE_LAUNCHING = "launching"
STATE_CONNECTING = "connecting"
STATE_CONNECTED = "connected"
STATE_RECONNECTING = "reconnecting"
STATE_DISCONNECTING = "disconnecting"
STATE_ERROR = "error"


def port_is_live(host, port, timeout=0.3):
    try:
        s = socket.create_connection((host, int(port)), timeout=timeout)
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# ══════════════════════════════════════════════════════════
# Ambient Particle Backdrop
# ══════════════════════════════════════════════════════════
class ParticleBackdrop(ctk.CTkCanvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, highlightthickness=0, bg=COLORS["bg"], **kw)
        self._p = []
        self._id = None
        self._started = False

    def start(self):
        self.after(100, self._init)

    def stop(self):
        if self._id:
            self.after_cancel(self._id)
            self._id = None

    def _init(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            self.after(100, self._init)
            return
        self._p = []
        for _ in range(18):
            self._p.append({
                "x": random.uniform(0, w), "y": random.uniform(0, h),
                "vx": random.uniform(-0.15, 0.15),
                "vy": random.uniform(-0.25, -0.03),
                "r": random.uniform(0.8, 2.2),
                "a": random.uniform(0.04, 0.15),
                "c": random.choice(["#f2711c", "#2dd4bf", "#a3a3a3"]),
            })
        self._started = True
        self._tick()

    def _tick(self):
        if not self._started:
            return
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("all")
        for p in self._p:
            p["x"] += p["vx"]; p["y"] += p["vy"]
            if p["y"] < -10:
                p["y"] = h + 10; p["x"] = random.uniform(0, w)
            if p["x"] < -10: p["x"] = w + 10
            elif p["x"] > w + 10: p["x"] = -10
            c = p["c"]
            dr = int(int(c[1:3], 16) * p["a"])
            dg = int(int(c[3:5], 16) * p["a"])
            db = int(int(c[5:7], 16) * p["a"])
            self.create_oval(p["x"]-p["r"], p["y"]-p["r"], p["x"]+p["r"], p["y"]+p["r"],
                           fill=f"#{dr:02x}{dg:02x}{db:02x}", outline="")
        self._id = self.after(55, self._tick)


# ══════════════════════════════════════════════════════════
# Connect Portal — large circle with breathing, ripple, icons
# ══════════════════════════════════════════════════════════
class ConnectPortal(ctk.CTkCanvas):
    """160px circular button: breathing glow, ripple rings, state icons."""

    SIZE = 160

    def __init__(self, parent, on_click=None, **kw):
        super().__init__(parent, width=self.SIZE, height=self.SIZE,
                         highlightthickness=0, bg=COLORS["bg"], **kw)
        self.cx = self.SIZE // 2
        self.cy = self.SIZE // 2
        self.R = 68          # base radius
        self.on_click = on_click
        self.state = STATE_IDLE
        self._phase = 0.0
        self._speed = 0.06
        self._angle = 0.0
        self._sweep = 0.0
        self._ripples = []   # [{r, alpha, color, speed}]
        self._ripple_cd = 0
        self._glow = 0.3
        self._glow_tgt = 0.3
        self._shake = 0.0
        self._id = None
        self.bind("<Button-1>", lambda e: self._click())

    def set_state(self, s):
        if s == self.state:
            return
        self.state = s
        if s in (STATE_LAUNCHING, STATE_CONNECTING, STATE_RECONNECTING):
            self._speed = 0.12; self._glow_tgt = 0.8; self._ripple(COLORS["connecting"])
        elif s == STATE_CONNECTED:
            self._speed = 0.05; self._glow_tgt = 1.0
            self._ripple(COLORS["connected"]); self._ripple(COLORS["connected"])
        elif s == STATE_ERROR:
            self._speed = 0.0; self._glow_tgt = 0.6
            self._shake = 12.0; self._ripple(COLORS["error"])
        elif s == STATE_DISCONNECTING:
            self._speed = 0.08; self._glow_tgt = 0.4
        else:
            self._speed = 0.06; self._glow_tgt = 0.3

    def _ripple(self, c):
        self._ripples.append({"r": self.R, "a": 0.55, "c": c, "s": 1.8})

    def _click(self):
        if self.on_click:
            self.on_click()
            self._ripple(COLORS["primary"])

    def start(self):
        self._tick()

    def stop(self):
        if self._id:
            self.after_cancel(self._id); self._id = None

    def _tick(self):
        self._phase += self._speed
        self._angle = (self._angle + 2.0) % 360

        if self.state in (STATE_LAUNCHING, STATE_CONNECTING, STATE_RECONNECTING):
            self._sweep = min(self._sweep + 5, 270)
        elif self.state == STATE_CONNECTED:
            self._sweep = 270
        else:
            self._sweep = max(self._sweep - 4, 0)

        self._glow += (self._glow_tgt - self._glow) * 0.08
        if abs(self._shake) > 0.3:
            self._shake *= 0.92
        else:
            self._shake = 0

        self._ripples = [r for r in (r.__setitem__("r", r["r"]+r["s"]) or r.__setitem__("a", r["a"]-0.012) or r for r in self._ripples) if r["a"] > 0.01]

        if self.state in (STATE_LAUNCHING, STATE_CONNECTING, STATE_RECONNECTING):
            self._ripple_cd -= 1
            if self._ripple_cd <= 0:
                self._ripple(COLORS["connecting"]); self._ripple_cd = random.randint(15, 30)

        self.draw()
        self._id = self.after(33, self._tick)

    def draw(self):
        self.delete("all")
        cx = self.cx + self._shake
        cy = self.cy
        breath = 1.0 + 0.015 * math.sin(self._phase)
        R = int(self.R * breath)

        # ripples
        for rr in self._ripples:
            rv = int(int(rr["c"][1:3],16) * rr["a"])
            gv = int(int(rr["c"][3:5],16) * rr["a"])
            bv = int(int(rr["c"][5:7],16) * rr["a"])
            self.create_oval(cx-rr["r"], cy-rr["r"], cx+rr["r"], cy+rr["r"],
                           outline=f"#{min(rv,255):02x}{min(gv,255):02x}{min(bv,255):02x}", width=2)

        # glow halo
        gc = {STATE_CONNECTED: COLORS["connected"], STATE_LAUNCHING: COLORS["connecting"],
              STATE_CONNECTING: COLORS["connecting"], STATE_RECONNECTING: COLORS["connecting"],
              STATE_ERROR: COLORS["error"]}.get(self.state, COLORS["idle"])
        for i in range(5, 0, -1):
            gr = R + i * 7
            b = self._glow * (1.0 - i * 0.18)
            b = max(0, min(1, b))
            rv = int(int(gc[1:3],16) * b); gv = int(int(gc[3:5],16) * b); bv = int(int(gc[5:7],16) * b)
            self.create_oval(cx-gr, cy-gr, cx+gr, cy+gr, outline=f"#{rv:02x}{gv:02x}{bv:02x}", width=2)

        # outer ring
        self.create_oval(cx-R, cy-R, cx+R, cy+R, outline="#222222", width=2)

        # rotating dots
        rad = math.radians(self._angle)
        dx = cx + R * math.cos(rad); dy = cy + R * math.sin(rad)
        self.create_oval(dx-3, dy-3, dx+3, dy+3, fill=COLORS["primary"], outline="")
        rad2 = math.radians(self._angle + 180)
        dx2 = cx + R * math.cos(rad2); dy2 = cy + R * math.sin(rad2)
        self.create_oval(dx2-2, dy2-2, dx2+2, dy2+2, fill="#fb923c", outline="")

        # inner circle
        ir = R - 22
        self.create_oval(cx-ir, cy-ir, cx+ir, cy+ir, fill="#111113", outline="#282828", width=2)

        # center icon
        if self.state == STATE_IDLE:
            pr = 20
            self.create_arc(cx-pr, cy-pr, cx+pr, cy+pr, start=30, extent=300,
                          outline=COLORS["idle"], width=3, style="arc")
            self.create_line(cx, cy-pr-2, cx, cy-pr+12, fill=COLORS["idle"], width=3)
        elif self.state in (STATE_LAUNCHING, STATE_CONNECTING, STATE_RECONNECTING):
            self.create_arc(cx-22, cy-22, cx+22, cy+22, start=int(self._angle),
                          extent=int(self._sweep), outline=COLORS["primary"], width=4, style="arc")
        elif self.state == STATE_CONNECTED:
            self.create_line(cx-14, cy+2, cx-4, cy+12, fill=COLORS["connected"], width=4, capstyle="round")
            self.create_line(cx-4, cy+12, cx+16, cy-10, fill=COLORS["connected"], width=4, capstyle="round")
        elif self.state == STATE_ERROR:
            self.create_line(cx-10, cy-10, cx+10, cy+10, fill=COLORS["error"], width=4, capstyle="round")
            self.create_line(cx+10, cy-10, cx-10, cy+10, fill=COLORS["error"], width=4, capstyle="round")


# ══════════════════════════════════════════════════════════
# Progress Bar (indeterminate sweep)
# ══════════════════════════════════════════════════════════
class ScanProgressBar(ctk.CTkCanvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, height=4, highlightthickness=0, bg=COLORS["bg"],
                        **kw)
        self._x = -40
        self._w = 160
        self._running = False
        self._id = None

    def start(self):
        self._running = True; self._x = -40; self._tick()

    def stop(self):
        self._running = False
        if self._id:
            self.after_cancel(self._id); self._id = None
        self.delete("all")

    def _tick(self):
        if not self._running:
            return
        self.delete("all")
        w = self.winfo_width()
        if w < 10:
            self._id = self.after(30, self._tick); return
        # background track
        self.create_rectangle(0, 0, w, 4, fill=COLORS["surface2"], outline="")
        # sweep bar
        self._x += 4
        if self._x > w + 40:
            self._x = -40
        bw = 50
        self.create_rectangle(self._x, 0, self._x + bw, 4, fill=COLORS["connecting"], outline="")
        self._id = self.after(25, self._tick)


# ══════════════════════════════════════════════════════════
# Main Application
# ══════════════════════════════════════════════════════════
class AetherGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Aether")
        self.geometry("480x640")
        self.minsize(400, 550)
        self.configure(fg_color=COLORS["bg"])

        if os.path.isfile(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except Exception:
                pass

        self._conn_state = STATE_IDLE
        self.process = None
        self.connect_time = 0
        self.timer_id = None
        self.retry_count = 0
        self.user_requested_stop = False
        self.monitor_thread = None
        self._pulse_id = None
        self._adv_open = False
        self._adv_h = 0
        self._adv_target_h = 0
        self._adv_id = None
        self._adv_content = None

        self._build_ui()
        self._animate_entry()
        self.portal.start()
        self.particles.start()

    # ── UI ──────────────────────────────────────────────
    def _build_ui(self):
        # Particles backdrop
        self.particles = ParticleBackdrop(self)
        self.particles.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Main centered container
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True)

        # ── Top spacer + logo ──
        top = ctk.CTkFrame(self.main, fg_color="transparent")
        top.pack(fill="x", pady=(24, 0))
        self._logo_label(top)

        # ── Center area: button + status ──
        center = ctk.CTkFrame(self.main, fg_color="transparent")
        center.pack(expand=True, fill="both")

        self.portal = ConnectPortal(center, on_click=self._on_connect_click)
        self.portal.pack(pady=(20, 12))

        # Status text (primary)
        self.status_label = ctk.CTkLabel(center, text="Disconnected",
                                          font=("Inter", 16, "bold"),
                                          text_color=COLORS["foreground"])
        self.status_label.pack()

        # Secondary status
        self.secondary_label = ctk.CTkLabel(center, text="Click to connect",
                                             font=("Inter", 11),
                                             text_color=COLORS["muted"])
        self.secondary_label.pack(pady=(2, 4))

        # Progress bar (hidden by default)
        self.progress = ScanProgressBar(center, width=160)
        # Don't pack yet

        # ── Advanced Panel (collapsible) ──
        self._build_advanced()

    def _logo_label(self, parent):
        """Show app logo + version at top."""
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack()
        # Try to load logo image
        logo_path = os.path.join(APP_DIR, "icon-64.png")
        if not os.path.isfile(logo_path):
            logo_path = os.path.join(APP_DIR, "icon-128.png")
        if os.path.isfile(logo_path):
            self._logo_img = ctk.CTkImage(light_image=None, dark_image=None, size=(48, 48))
            from PIL import Image as PILImage
            pil = PILImage.open(logo_path).resize((48, 48), PILImage.LANCZOS)
            self._logo_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(48, 48))
            ctk.CTkLabel(f, image=self._logo_img, text="").pack(side="left", padx=(0, 8))
        ctk.CTkLabel(f, text="AETHER", font=("Inter", 20, "bold"),
                      text_color=COLORS["primary"]).pack(side="left")
        ctk.CTkLabel(f, text=f" v{VERSION}", font=("Inter", 12),
                      text_color=COLORS["muted"]).pack(side="left", pady=(4, 0))

    def _build_advanced(self):
        """Collapsible advanced panel at bottom."""
        adv_outer = ctk.CTkFrame(self.main, fg_color="transparent")
        adv_outer.pack(fill="x", side="bottom", pady=(0, 8))

        # Trigger button
        self._adv_trigger = ctk.CTkButton(adv_outer, text="⚙  Advanced",
                                           font=("Inter", 11), height=28,
                                           fg_color="transparent", hover_color=COLORS["surface2"],
                                           text_color=COLORS["muted"],
                                           command=self._toggle_advanced)
        self._adv_trigger.pack()

        # Content frame (animated height)
        self._adv_clip = ctk.CTkFrame(adv_outer, fg_color="transparent", height=0)
        self._adv_clip.pack(fill="x")
        self._adv_clip.pack_propagate(False)

        self._adv_content = ctk.CTkFrame(self._adv_clip, fg_color=COLORS["surface"],
                                          corner_radius=12)

        # Protocol
        row1 = ctk.CTkFrame(self._adv_content, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(row1, text="Protocol", font=("Inter", 11),
                      text_color=COLORS["muted"]).pack(side="left")
        self.protocol_var = ctk.StringVar(value="WireGuard")
        ctk.CTkOptionMenu(row1, variable=self.protocol_var, values=PROTOCOLS,
                           command=self._on_protocol_change,
                           width=160, corner_radius=8, fg_color=COLORS["surface2"]).pack(side="right")

        # Scan Mode
        row2 = ctk.CTkFrame(self._adv_content, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row2, text="Scan Mode", font=("Inter", 11),
                      text_color=COLORS["muted"]).pack(side="left")
        self.scan_var = ctk.StringVar(value="Ironclad")
        ctk.CTkOptionMenu(row2, variable=self.scan_var, values=SCAN_MODES,
                           width=120, corner_radius=8, fg_color=COLORS["surface2"]).pack(side="right")

        # IP Version
        row3 = ctk.CTkFrame(self._adv_content, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row3, text="IP Version", font=("Inter", 11),
                      text_color=COLORS["muted"]).pack(side="left")
        self.ip_var = ctk.StringVar(value="Dual")
        ctk.CTkOptionMenu(row3, variable=self.ip_var, values=["IPv4", "IPv6", "Dual"],
                           width=80, corner_radius=8, fg_color=COLORS["surface2"]).pack(side="right")

        # Separator
        sep = ctk.CTkFrame(self._adv_content, fg_color="transparent", height=16)
        sep.pack(fill="x")
        ctk.CTkLabel(sep, text="─  LOGS  ─", font=("Inter", 8),
                      text_color=COLORS["muted"]).pack()

        # Log area
        self.log_text = ctk.CTkTextbox(self._adv_content, font=("Consolas", 10),
                                        fg_color=COLORS["surface2"], text_color=COLORS["muted"],
                                        corner_radius=8, height=140,
                                        border_width=0)
        self.log_text.pack(fill="x", padx=12, pady=(0, 12))
        self.log_text.configure(state="disabled")

        self._adv_content.pack(fill="x", padx=12)

    def _toggle_advanced(self):
        if self._adv_open:
            self._adv_target_h = 0
            self._adv_trigger.configure(text="⚙  Advanced")
        else:
            self._adv_target_h = 420
            self._adv_trigger.configure(text="⚙  Advanced ▲")
        self._adv_open = not self._adv_open
        self._animate_adv()

    def _animate_adv(self):
        diff = self._adv_target_h - self._adv_h
        if abs(diff) < 4:
            self._adv_h = self._adv_target_h
        else:
            self._adv_h += int(diff * 0.25)
        self._adv_clip.configure(height=max(1, self._adv_h))
        if abs(self._adv_target_h - self._adv_h) > 2:
            self._adv_id = self.after(16, self._animate_adv)

    # ── State Machine ───────────────────────────────────
    def _set_state(self, new_state, info=""):
        self._conn_state = new_state
        self.portal.set_state(new_state)

        if new_state == STATE_IDLE:
            self.status_label.configure(text="Disconnected", text_color=COLORS["foreground"])
            self.secondary_label.configure(text="Click to connect")
            self.progress.stop()
            self.progress.pack_forget()
            self._stop_timer()

        elif new_state == STATE_LAUNCHING:
            self.status_label.configure(text="Starting Aether…", text_color=COLORS["foreground"])
            self.secondary_label.configure(text="Answering setup prompts")
            self.progress.pack(pady=(0, 4))
            self.progress.start()

        elif new_state == STATE_CONNECTING:
            self.status_label.configure(text="Finding a route…", text_color=COLORS["foreground"])
            self.secondary_label.configure(text=f"Scanning ({self.scan_var.get()})…")

        elif new_state == STATE_CONNECTED:
            self.status_label.configure(text="Connected", text_color=COLORS["foreground"])
            self.progress.stop()
            self.progress.pack_forget()
            self._start_timer()
            threading.Thread(target=self._fetch_tunnel_ip, daemon=True).start()

        elif new_state == STATE_RECONNECTING:
            self.status_label.configure(text="Reconnecting…", text_color=COLORS["foreground"])
            self.secondary_label.configure(text=f"Attempt {info}/{MAX_AUTO_RETRIES}")

        elif new_state == STATE_DISCONNECTING:
            self.status_label.configure(text="Disconnecting…", text_color=COLORS["foreground"])
            self.secondary_label.configure(text="")
            self.progress.stop()

        elif new_state == STATE_ERROR:
            self.status_label.configure(text="Connection failed", text_color=COLORS["foreground"])
            self.secondary_label.configure(text=info or "Unknown error")
            self.progress.stop()
            self.progress.pack_forget()
            self._stop_timer()

    # ── Connect Logic ───────────────────────────────────
    def _on_connect_click(self):
        if self._conn_state in (STATE_IDLE, STATE_ERROR):
            self._start_connect()
        elif self._conn_state in (STATE_LAUNCHING, STATE_CONNECTING, STATE_CONNECTED, STATE_RECONNECTING):
            self._request_disconnect()

    def _find_binary(self):
        for name in ("aether.exe", "aether"):
            for d in (APP_DIR, os.path.join(APP_DIR, "..")):
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    return p
        return None

    def _on_protocol_change(self, choice):
        pass  # No fragment toggle needed in minimal layout

    def _build_cmd(self, binary):
        proto = self.protocol_var.get()
        scan = self.scan_var.get().lower()
        cmd = [binary, "--bind", "127.0.0.1:1819", "--scan", scan]

        if "WireGuard" in proto:
            cmd.append("--wg")
        elif "WARP-in-WARP" in proto:
            cmd.append("--gool")
        else:
            cmd.append("--masque")
            if "HTTP/2" in proto:
                cmd.append("--h2")

        cmd.append("--quick-reconnect")

        ip = self.ip_var.get()
        if ip == "IPv4": cmd.append("-4")
        elif ip == "IPv6": cmd.append("-6")

        return cmd

    def _start_connect(self):
        binary = self._find_binary()
        if not binary:
            self._set_state(STATE_ERROR, "Binary not found")
            self._log("ERROR: aether binary not found.")
            return

        cmd = self._build_cmd(binary)
        self.user_requested_stop = False
        self.retry_count = 0
        self._set_state(STATE_LAUNCHING)
        self._log(f"CMD: {' '.join(cmd)}")

        if port_is_live("127.0.0.1", 1819):
            self._set_state(STATE_ERROR, "Port 1819 in use")
            return

        try:
            cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                              stderr=subprocess.STDOUT, text=True,
                                              creationflags=cf)
        except Exception as e:
            self._set_state(STATE_ERROR, str(e)); return

        threading.Thread(target=self._read_logs, daemon=True).start()
        self.monitor_thread = threading.Thread(target=self._monitor_connect,
                                                args=(cmd, "1819"), daemon=True)
        self.monitor_thread.start()

    def _read_logs(self):
        try:
            for line in self.process.stdout:
                self._log(line.rstrip())
        except Exception:
            pass

    def _monitor_connect(self, cmd, port):
        scan = self.scan_var.get().lower()
        timeout = CONNECT_TIMEOUTS.get(scan, 150)
        deadline = time.time() + timeout
        announced = False

        while True:
            time.sleep(0.4)
            if self.user_requested_stop:
                return
            if self.process and self.process.poll() is not None:
                rc = self.process.returncode
                self._handle_failure(cmd, port, f"Exit code {rc}"); return

            if not announced and time.time() > deadline - timeout + 3:
                self.after(0, lambda: self._set_state(STATE_CONNECTING))
                announced = True

            if port_is_live("127.0.0.1", port):
                self._log(f"SOCKS5 port {port} live — connected!")
                self.after(0, lambda: self._set_state(STATE_CONNECTED))
                self.retry_count = 0
                self._monitor_connected(cmd, port); return

            if time.time() >= deadline:
                if self.process:
                    try: self.process.terminate()
                    except: pass
                self._handle_failure(cmd, port, f"Timeout ({timeout}s)"); return

    def _fetch_tunnel_ip(self):
        port = "1819"
        for attempt in range(3):
            if self.user_requested_stop or self._conn_state != STATE_CONNECTED:
                return
            try:
                info = self._socks5_geo(port)
                if info:
                    ip = info.get("ip", "?")
                    country = info.get("country", "?")
                    self.after(0, lambda: self.secondary_label.configure(
                        text=f"{ip} · {country}"))
                    return
            except Exception as e:
                time.sleep(2)

    def _socks5_geo(self, port, timeout=10):
        host = "ip-api.com"
        hb = host.encode()
        sock = socket.create_connection(("127.0.0.1", int(port)), timeout=timeout)
        sock.settimeout(timeout)
        try:
            sock.sendall(b"\x05\x01\x00")
            if sock.recv(2) != b"\x05\x00":
                raise Exception("handshake")
            sock.sendall(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + struct.pack(">H", 80))
            r = sock.recv(10)
            if len(r) < 2 or r[1] != 0:
                raise Exception("connect")
            sock.sendall(b"GET /json HTTP/1.1\r\nHost: ip-api.com\r\nConnection: close\r\n\r\n")
            data = b""
            while True:
                c = sock.recv(4096)
                if not c: break
                data += c
                if len(data) > 65536: break
            text = data.decode(errors="replace")
            if "\r\n\r\n" in text:
                body = text.split("\r\n\r\n", 1)[1].strip()
                for end in ["\r\n0", "\r\n\r\n"]:
                    if end in body: body = body[:body.index(end)]
                return json.loads(body)
            return None
        finally:
            sock.close()

    def _monitor_connected(self, cmd, port):
        while True:
            time.sleep(0.5)
            if self.user_requested_stop: return
            if self.process and self.process.poll() is not None:
                self._handle_failure(cmd, port, "Connection lost"); return

    def _handle_failure(self, cmd, port, msg):
        if self.user_requested_stop:
            self.after(0, lambda: self._set_state(STATE_IDLE)); return
        self.retry_count += 1
        if self.retry_count > MAX_AUTO_RETRIES:
            self.after(0, lambda: self._set_state(STATE_ERROR, f"{msg} (gave up)")); return
        attempt = self.retry_count
        self.after(0, lambda a=attempt: self._set_state(STATE_RECONNECTING, a))

        def retry():
            time.sleep(RETRY_BACKOFF[attempt-1])
            if self.user_requested_stop: return
            self.after(0, lambda: self._set_state(STATE_LAUNCHING))
            try:
                cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                                  stderr=subprocess.STDOUT, text=True,
                                                  creationflags=cf)
            except Exception as e:
                self.after(0, lambda: self._set_state(STATE_ERROR, str(e))); return
            threading.Thread(target=self._read_logs, daemon=True).start()
            threading.Thread(target=self._monitor_connect, args=(cmd, port), daemon=True).start()

        threading.Thread(target=retry, daemon=True).start()

    def _request_disconnect(self):
        self.user_requested_stop = True
        self._set_state(STATE_DISCONNECTING)
        if self.process:
            try:
                self.process.terminate() if sys.platform == "win32" else self.process.send_signal(signal.SIGTERM)
            except: pass

        def wait():
            t = time.time()
            while time.time() - t < 3:
                if self.process and self.process.poll() is not None: break
                time.sleep(0.2)
            if self.process and self.process.poll() is None:
                try: self.process.kill()
                except: pass
            self.process = None
            self.after(0, lambda: self._set_state(STATE_IDLE))

        threading.Thread(target=wait, daemon=True).start()

    # ── Timer ───────────────────────────────────────────
    def _start_timer(self):
        self.connect_time = int(time.time())
        self._tick_timer()

    def _tick_timer(self):
        if self._conn_state != STATE_CONNECTED: return
        e = int(time.time()) - self.connect_time
        h, m, s = e // 3600, (e % 3600) // 60, e % 60
        self.secondary_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.timer_id = self.after(1000, self._tick_timer)

    def _stop_timer(self):
        if self.timer_id:
            self.after_cancel(self.timer_id); self.timer_id = None

    # ── Logs ────────────────────────────────────────────
    def _log(self, msg):
        def w():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        if threading.current_thread() is threading.main_thread(): w()
        else: self.after(0, w)

    # ── Entry Animation ─────────────────────────────────
    def _animate_entry(self):
        self.attributes("-alpha", 0.0)
        self._fade_n = 0
        def f():
            self._fade_n += 1
            a = min(1.0, self._fade_n / 15)
            self.attributes("-alpha", a)
            if a < 1.0: self.after(20, f)
        f()

    def on_close(self):
        self.user_requested_stop = True
        self.portal.stop()
        self.particles.stop()
        self.progress.stop()
        if self._pulse_id:
            self.after_cancel(self._pulse_id)
        if self.process:
            try: self.process.kill()
            except: pass
        self.destroy()


if __name__ == "__main__":
    app = AetherGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
