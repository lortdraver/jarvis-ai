import math
import time
from collections import deque

import numpy as np
import pygame

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

try:
    import win32api
    import win32con
    import win32gui
except ImportError:
    win32api = None
    win32con = None
    win32gui = None


class JarvisUI:
    def __init__(self):
        pygame.init()

        display = pygame.display.Info()
        self.screen_w = display.current_w
        self.screen_h = display.current_h
        self.width = 430
        self.height = min(780, self.screen_h - 80)
        self.tab_width = 28
        self.margin = 18

        self.open_x = self.screen_w - self.width - self.margin
        self.closed_x = self.screen_w - self.tab_width
        self.pos_x = self.closed_x
        self.pos_y = max(24, (self.screen_h - self.height) // 2)

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.NOFRAME)
        pygame.display.set_caption("JARVIS Interface")

        self.hwnd = pygame.display.get_wm_info().get("window")
        self.always_on_top = True
        self._configure_window()

        self.panel_open = False
        self.slide = 0.0
        self.target_slide = 0.0
        self.boot_start = time.time()
        self.running = True

        self.bg_key = (1, 1, 1)
        self.navy = (5, 12, 22)
        self.panel = (7, 20, 34, 205)
        self.card = (10, 32, 50, 128)
        self.cyan = (0, 225, 255)
        self.blue = (45, 124, 255)
        self.teal = (0, 255, 188)
        self.white = (226, 247, 255)
        self.muted = (116, 174, 190)
        self.warning = (255, 190, 76)

        self.font_xs = pygame.font.SysFont("Consolas", 12)
        self.font_sm = pygame.font.SysFont("Consolas", 14)
        self.font_md = pygame.font.SysFont("Consolas", 16, bold=True)
        self.font_lg = pygame.font.SysFont("Agency FB", 28, bold=True)
        self.font_xl = pygame.font.SysFont("Agency FB", 42, bold=True)

        self.status = "LISTENING"
        self.status_text = "JARVIS ONLINE"
        self.current_phrase = "Awaiting command..."
        self.voice_level = 0.0
        self.voice_history = deque([0.0] * 54, maxlen=54)
        self.dialog = deque(maxlen=8)
        self.notifications = deque(maxlen=5)

        self.last_net_time = time.time()
        self.last_net_total = self._net_total()
        self.net_speed = 0.0

        self.dialog.append(("SYSTEM", "Neural voice interface initialized."))
        self.notify("Boot sequence started", "SYSTEM")

    def _configure_window(self):
        if not (self.hwnd and win32gui and win32con and win32api):
            return

        style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            self.hwnd,
            win32con.GWL_EXSTYLE,
            style | win32con.WS_EX_LAYERED,
        )
        win32gui.SetLayeredWindowAttributes(
            self.hwnd,
            win32api.RGB(1, 1, 1),
            0,
            win32con.LWA_COLORKEY,
        )
        self._move_window()

    def _move_window(self):
        if not (self.hwnd and win32gui and win32con):
            return

        top_flag = win32con.HWND_TOPMOST if self.always_on_top else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(
            self.hwnd,
            top_flag,
            int(self.pos_x),
            int(self.pos_y),
            0,
            0,
            win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )

    def set_state(self, state_type, text=""):
        state_map = {
            "listen": "LISTENING",
            "idle": "LISTENING",
            "think": "THINKING",
            "speak": "SPEAKING",
            "shazam": "EXECUTING",
            "error": "ERROR",
            "status": "SYSTEM",
        }
        self.status = state_map.get(str(state_type).lower(), str(state_type).upper())

        if text:
            self.current_phrase = str(text)
            speaker = "JARVIS" if self.status in {"SPEAKING", "SYSTEM", "ERROR"} else "INPUT"
            self.dialog.append((speaker, self.current_phrase))
            if self.status in {"THINKING", "EXECUTING", "ERROR"}:
                self.notify(self.current_phrase, self.status)

    def update_volume(self, audio_data):
        try:
            rms = float(np.sqrt(np.mean(audio_data**2)))
            self.voice_level = max(0.0, min(1.0, rms * 16))
        except Exception:
            self.voice_level = 0.0
        self.voice_history.append(self.voice_level)

    def notify(self, text, title="JARVIS"):
        self.notifications.appendleft(
            {
                "title": str(title)[:18],
                "text": str(text)[:64],
                "created": time.time(),
            }
        )

    def _net_total(self):
        if psutil is None:
            return 0
        counters = psutil.net_io_counters()
        return counters.bytes_sent + counters.bytes_recv

    def _update_monitor(self):
        now = time.time()
        if psutil is None:
            return "--", "--", "--"

        cpu = int(psutil.cpu_percent(interval=None))
        ram = int(psutil.virtual_memory().percent)
        total = self._net_total()
        elapsed = max(0.1, now - self.last_net_time)
        self.net_speed = max(0.0, (total - self.last_net_total) / elapsed)
        self.last_net_total = total
        self.last_net_time = now
        net = f"{self.net_speed / 1024:.0f} KB/s"
        return f"{cpu}%", f"{ram}%", net

    def _status_color(self):
        return {
            "LISTENING": self.cyan,
            "THINKING": self.blue,
            "SPEAKING": self.teal,
            "EXECUTING": self.warning,
            "ERROR": (255, 92, 92),
        }.get(self.status, self.cyan)

    def _draw_text(self, text, font, color, x, y, max_width=None):
        text = str(text)
        if max_width is None:
            self.screen.blit(font.render(text, True, color), (x, y))
            return y + font.get_height()

        words = text.split()
        line = ""
        cursor_y = y
        for word in words:
            test = f"{line} {word}".strip()
            if font.size(test)[0] <= max_width:
                line = test
                continue
            if line:
                self.screen.blit(font.render(line, True, color), (x, cursor_y))
                cursor_y += font.get_height() + 3
            line = word
        if line:
            self.screen.blit(font.render(line, True, color), (x, cursor_y))
            cursor_y += font.get_height() + 3
        return cursor_y

    def _alpha_rect(self, rect, color, radius=8, border=None):
        surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(surface, color, surface.get_rect(), border_radius=radius)
        if border:
            pygame.draw.rect(
                surface,
                border,
                surface.get_rect(),
                width=1,
                border_radius=radius,
            )
        self.screen.blit(surface, rect.topleft)

    def _glow_rect(self, rect, color):
        for i, alpha in enumerate((26, 18, 10)):
            inflated = rect.inflate(8 + i * 12, 8 + i * 12)
            surface = pygame.Surface((inflated.width, inflated.height), pygame.SRCALPHA)
            pygame.draw.rect(
                surface,
                (*color, alpha),
                surface.get_rect(),
                width=1,
                border_radius=8,
            )
            self.screen.blit(surface, inflated.topleft)

    def _draw_boot(self, now):
        elapsed = now - self.boot_start
        if elapsed > 3.2:
            return

        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((2, 8, 15, int(max(0, 190 - elapsed * 55))))
        self.screen.blit(overlay, (0, 0))

        progress = min(1.0, elapsed / 3.0)
        title = self.font_xl.render("JARVIS", True, self.cyan)
        self.screen.blit(title, (34, self.height // 2 - 62))
        self._draw_text("STARK INDUSTRIES NEURAL HUD", self.font_sm, self.muted, 36, self.height // 2 - 18)

        bar = pygame.Rect(36, self.height // 2 + 18, self.width - 72, 6)
        pygame.draw.rect(self.screen, (12, 42, 58), bar, border_radius=3)
        pygame.draw.rect(
            self.screen,
            self.cyan,
            (bar.x, bar.y, int(bar.width * progress), bar.height),
            border_radius=3,
        )
        self._draw_text(f"BOOT {int(progress * 100):03d}%", self.font_xs, self.white, 36, bar.y + 16)

    def _draw_tab(self):
        tab_rect = pygame.Rect(0, self.height // 2 - 58, self.tab_width, 116)
        hover = tab_rect.collidepoint(pygame.mouse.get_pos())
        color = self.teal if hover else self.cyan
        self._alpha_rect(tab_rect, (4, 26, 42, 220), radius=6, border=(*color, 180))
        self._glow_rect(tab_rect, color)
        label = "OPEN" if not self.panel_open else "CLOSE"
        for i, ch in enumerate(label):
            surf = self.font_xs.render(ch, True, color)
            self.screen.blit(surf, (8, tab_rect.y + 16 + i * 15))

    def _draw_orb(self, now):
        cx, cy = self.width // 2, 154
        level = self.voice_level
        base = 54 + level * 20
        status_color = self._status_color()

        for radius, alpha in ((base + 30, 26), (base + 18, 38), (base + 6, 58)):
            surface = pygame.Surface((self.width, 240), pygame.SRCALPHA)
            pygame.draw.circle(surface, (*status_color, alpha), (cx, cy), int(radius), width=2)
            self.screen.blit(surface, (0, 0))

        for i in range(3):
            phase = now * (0.9 + i * 0.22) + i * 1.7
            radius_x = base + 15 + i * 11
            radius_y = base * (0.34 + i * 0.08)
            rect = pygame.Rect(0, 0, radius_x * 2, radius_y * 2)
            rect.center = (cx, cy)
            start = phase % (math.pi * 2)
            end = start + math.pi * 1.55
            pygame.draw.arc(self.screen, status_color, rect, start, end, 2)

        pygame.draw.circle(self.screen, (4, 26, 42), (cx, cy), int(base * 0.62))
        pygame.draw.circle(self.screen, status_color, (cx, cy), int(base * 0.48), width=2)
        pygame.draw.circle(self.screen, self.white, (cx - 12, cy - 15), 4)

    def _draw_waveform(self):
        rect = pygame.Rect(34, 256, self.width - 68, 64)
        self._alpha_rect(rect, (4, 18, 28, 118), radius=8, border=(*self.cyan, 72))
        mid = rect.centery
        step = rect.width / max(1, len(self.voice_history) - 1)
        points = []
        for index, value in enumerate(self.voice_history):
            x = rect.x + index * step
            y = mid - (value * 28 + 3 * math.sin(index * 0.8 + time.time() * 5))
            points.append((x, y))
        if len(points) > 1:
            pygame.draw.lines(self.screen, self.teal, False, points, 2)
            mirror = [(x, mid + (mid - y)) for x, y in points]
            pygame.draw.lines(self.screen, self.blue, False, mirror, 1)

    def _draw_header(self):
        self._draw_text("JARVIS", self.font_xl, self.cyan, 34, 28)
        self._draw_text("// STARK INDUSTRIES", self.font_sm, self.muted, 156, 48)

        pin_rect = pygame.Rect(self.width - 74, 30, 42, 24)
        pin_color = self.teal if self.always_on_top else self.muted
        self._alpha_rect(pin_rect, (6, 26, 42, 130), radius=6, border=(*pin_color, 150))
        self._draw_text("PIN", self.font_xs, pin_color, pin_rect.x + 10, pin_rect.y + 5)

    def _draw_status(self):
        color = self._status_color()
        status_rect = pygame.Rect(34, 218, self.width - 68, 28)
        self._alpha_rect(status_rect, (7, 25, 39, 155), radius=8, border=(*color, 120))
        pygame.draw.circle(self.screen, color, (status_rect.x + 17, status_rect.centery), 5)
        self._draw_text(self.status, self.font_md, color, status_rect.x + 32, status_rect.y + 5)
        self._draw_text("VOICE LINK ACTIVE", self.font_xs, self.muted, status_rect.right - 132, status_rect.y + 7)

    def _draw_dialog(self):
        rect = pygame.Rect(34, 338, self.width - 68, 214)
        self._alpha_rect(rect, self.card, radius=8, border=(*self.cyan, 64))
        self._draw_text("DIALOG STREAM", self.font_md, self.white, rect.x + 16, rect.y + 12)

        y = rect.y + 42
        for speaker, message in list(self.dialog)[-5:]:
            color = self.teal if speaker == "JARVIS" else self.blue if speaker == "INPUT" else self.muted
            self._draw_text(speaker, self.font_xs, color, rect.x + 16, y)
            y = self._draw_text(message, self.font_sm, self.white, rect.x + 84, y - 1, rect.width - 104)
            y += 8

    def _draw_monitor(self):
        cpu, ram, net = self._update_monitor()
        rect = pygame.Rect(34, 570, self.width - 68, 92)
        self._alpha_rect(rect, self.card, radius=8, border=(*self.blue, 66))
        self._draw_text("SYSTEM MONITOR", self.font_md, self.white, rect.x + 16, rect.y + 12)

        items = (("CPU", cpu), ("RAM", ram), ("NET", net))
        card_w = (rect.width - 48) // 3
        for index, (label, value) in enumerate(items):
            x = rect.x + 16 + index * (card_w + 8)
            sub = pygame.Rect(x, rect.y + 42, card_w, 34)
            self._alpha_rect(sub, (0, 26, 42, 120), radius=6, border=(*self.teal, 70))
            self._draw_text(label, self.font_xs, self.muted, sub.x + 8, sub.y + 5)
            self._draw_text(value, self.font_sm, self.cyan, sub.x + 8, sub.y + 18)

    def _draw_notifications(self):
        now = time.time()
        y = self.height - 92
        for note in list(self.notifications):
            age = now - note["created"]
            if age > 4.2:
                continue
            alpha = int(min(1.0, age / 0.25, (4.2 - age) / 0.45) * 190)
            rect = pygame.Rect(34, y, self.width - 68, 54)
            self._alpha_rect(rect, (5, 30, 44, alpha), radius=8, border=(*self.cyan, min(150, alpha)))
            self._draw_text(note["title"], self.font_xs, self.cyan, rect.x + 14, rect.y + 8)
            self._draw_text(note["text"], self.font_sm, self.white, rect.x + 14, rect.y + 24, rect.width - 28)
            y -= 62

    def draw(self):
        now = time.time()
        self.slide += (self.target_slide - self.slide) * 0.18
        self.pos_x = self.closed_x + (self.open_x - self.closed_x) * self.slide
        self._move_window()

        self.screen.fill(self.bg_key)

        panel_rect = pygame.Rect(self.tab_width, 0, self.width - self.tab_width, self.height)
        self._glow_rect(panel_rect.inflate(-8, -8), self.cyan)
        self._alpha_rect(panel_rect, self.panel, radius=8, border=(*self.cyan, 120))

        for y in range(82, self.height, 72):
            pygame.draw.line(self.screen, (0, 96, 128), (self.tab_width + 20, y), (self.width - 24, y), 1)

        self._draw_header()
        self._draw_orb(now)
        self._draw_status()
        self._draw_waveform()
        self._draw_dialog()
        self._draw_monitor()
        self._draw_notifications()
        self._draw_boot(now)
        self._draw_tab()

        pygame.display.flip()

    def _handle_click(self, pos):
        tab_rect = pygame.Rect(0, self.height // 2 - 58, self.tab_width, 116)
        pin_rect = pygame.Rect(self.width - 74, 30, 42, 24)

        if tab_rect.collidepoint(pos):
            self.panel_open = not self.panel_open
            self.target_slide = 1.0 if self.panel_open else 0.0
            self.notify("Panel opened" if self.panel_open else "Panel closed", "HUD")
            return

        if pin_rect.collidepoint(pos):
            self.always_on_top = not self.always_on_top
            self.notify("Always on top enabled" if self.always_on_top else "Always on top disabled", "HUD")
            self._move_window()

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.panel_open = False
                        self.target_slide = 0.0
                    elif event.key == pygame.K_SPACE:
                        self.panel_open = not self.panel_open
                        self.target_slide = 1.0 if self.panel_open else 0.0
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            self.draw()
            clock.tick(60)
