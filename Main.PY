import os
import ctypes
import time
from ctypes import wintypes
from pathlib import Path

import pygame

# Optional libraries (the program still starts without them)
#   pip install python-vlc pillow
# python-vlc also needs the real VLC app installed (64-bit, same as Python).
try:
    import vlc
    HAVE_VLC = True
except Exception:
    vlc = None
    HAVE_VLC = False

try:
    from PIL import Image, ImageSequence
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

# ---------------- Settings ----------------
ROOT_PATH = "C:/"
WINDOW_SIZE = (1100, 650)
TREE_W = 320
ROW_H = 24
INDENT = 22
HEADER_H = 90
LOGO_FILE = "logo.png"
LOGO_HEIGHT = 70
ICON = 16
CONTROLS_H = 84

BG = (255, 255, 255)
LINE = (200, 200, 210)
TEXT = (0, 0, 0)
HOVER = (128, 128, 128)
SELECT = (60, 80, 140)
GRAY = (110, 110, 120)
PANEL_BG = (240, 240, 245)
BTN = (225, 225, 232)
BTN_HOVER = (205, 205, 215)
ACCENT = (0, 120, 215)
TRACK = (200, 200, 210)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".ico", ".tiff"}
GIF_EXTS = {".gif"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".wma"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".m4v"}
MEDIA_EXTS = IMAGE_EXTS | GIF_EXTS | AUDIO_EXTS | VIDEO_EXTS

# ---------------- Windows icon extraction + window helpers ----------------
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    shell32 = ctypes.windll.shell32
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    class SHFILEINFOW(ctypes.Structure):
        _fields_ = [
            ("hIcon", ctypes.c_void_p),
            ("iIcon", ctypes.c_int),
            ("dwAttributes", wintypes.DWORD),
            ("szDisplayName", wintypes.WCHAR * 260),
            ("szTypeName", wintypes.WCHAR * 80),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    shell32.SHGetFileInfoW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFOW),
        wintypes.UINT, wintypes.UINT,
    ]
    shell32.SHGetFileInfoW.restype = ctypes.c_void_p
    user32.GetDC.restype = ctypes.c_void_p
    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.DestroyIcon.argtypes = [ctypes.c_void_p]
    user32.DrawIconEx.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
    ]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateDIBSection.restype = ctypes.c_void_p
    gdi32.CreateDIBSection.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, wintypes.DWORD,
    ]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

    # child-window helpers (used to show video inside the pygame window)
    user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_int
    user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    user32.SetWindowLongW.restype = ctypes.c_int
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ]
    user32.CreateWindowExW.restype = ctypes.c_void_p
    user32.MoveWindow.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.BOOL,
    ]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.EnableWindow.argtypes = [ctypes.c_void_p, wintypes.BOOL]
    user32.DestroyWindow.argtypes = [ctypes.c_void_p]

SHGFI_ICON = 0x100
SHGFI_SMALLICON = 0x1
SHGFI_USEFILEATTRIBUTES = 0x10
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_ATTRIBUTE_DIRECTORY = 0x10


def _draw_on_fill(hicon, size, fill_byte):
    """Draw an HICON onto a 32-bit DIB prefilled with one byte value; return BGRA bytes."""
    hdc = user32.GetDC(None)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = size
    bmi.biHeight = -size  # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bits = ctypes.c_void_p()
    hbm = gdi32.CreateDIBSection(memdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    old = gdi32.SelectObject(memdc, hbm)
    ctypes.memset(bits, fill_byte, size * size * 4)
    user32.DrawIconEx(memdc, 0, 0, hicon, size, size, 0, None, 3)  # DI_NORMAL
    data = ctypes.string_at(bits, size * size * 4)
    gdi32.SelectObject(memdc, old)
    gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(None, hdc)
    return data


def _hicon_to_surface(hicon, size):
    """Render on black and on white, then work out the per-pixel alpha."""
    black = _draw_on_fill(hicon, size, 0x00)
    white = _draw_on_fill(hicon, size, 0xFF)
    out = bytearray(size * size * 4)
    for i in range(0, size * size * 4, 4):
        diffs = [white[i + c] - black[i + c] for c in range(3)]
        a = 255 - sum(diffs) // 3
        a = max(0, min(255, a))
        if a == 0:
            continue
        # BGRA -> RGBA, un-premultiply
        for c, src in enumerate((2, 1, 0)):
            out[i + c] = min(255, black[i + src] * 255 // a)
        out[i + 3] = a
    return pygame.image.frombuffer(bytes(out), (size, size), "RGBA").convert_alpha()


def _fallback_icon(is_dir):
    s = pygame.Surface((ICON, ICON), pygame.SRCALPHA)
    color = (240, 200, 60) if is_dir else (200, 200, 210)
    pygame.draw.rect(s, color, (1, 3, ICON - 2, ICON - 5), border_radius=2)
    return s


_icon_cache = {}


def get_icon(path, is_dir):
    key = "<dir>" if is_dir else path.suffix.lower()
    if key in _icon_cache:
        return _icon_cache[key]

    surf = None
    if IS_WINDOWS:
        try:
            info = SHFILEINFOW()
            fake_name = "folder" if is_dir else "file" + key
            attrs = FILE_ATTRIBUTE_DIRECTORY if is_dir else FILE_ATTRIBUTE_NORMAL
            shell32.SHGetFileInfoW(
                fake_name, attrs, ctypes.byref(info), ctypes.sizeof(info),
                SHGFI_ICON | SHGFI_SMALLICON | SHGFI_USEFILEATTRIBUTES,
            )
            if info.hIcon:
                surf = _hicon_to_surface(info.hIcon, ICON)
                user32.DestroyIcon(info.hIcon)
        except Exception:
            surf = None
    if surf is None:
        surf = _fallback_icon(is_dir)
    _icon_cache[key] = surf
    return surf


# ---------------- Tree nodes ----------------
class Node:
    def __init__(self, path, is_dir, name=None):
        self.path = path
        self.is_dir = is_dir
        self.name = name or path.name or str(path)
        self.expanded = False
        self.children = None

    def load(self, show_all):
        if self.children is not None:
            return
        kids = []
        try:
            for entry in os.scandir(self.path):
                try:
                    p = Path(entry.path)
                    if entry.is_dir():
                        kids.append(Node(p, True))
                    else:
                        kids.append(Node(p, False))
                except OSError:
                    continue
        except (PermissionError, FileNotFoundError, OSError):
            pass
        kids.sort(key=lambda n: (not n.is_dir, n.name.lower()))
        self.children = kids

    def visible_children(self, show_all):
        if self.children is None:
            self.load(show_all)
        if show_all:
            return self.children
        return [
            k for k in self.children
            if k.is_dir or k.path.suffix.lower() in MEDIA_EXTS
        ]


def build_rows(node, depth, parent_idx, rows, last_child, show_all):
    idx = len(rows)
    rows.append((node, depth, parent_idx))
    if parent_idx is not None:
        last_child[parent_idx] = idx
    if node.is_dir and node.expanded:
        for k in node.visible_children(show_all):
            build_rows(k, depth + 1, idx, rows, last_child, show_all)


# ---------------- Drawing helpers ----------------
def draw_windows_logo(surface, x, y, size=44):
    gap = 3
    sq = (size - gap) // 2
    blue = (0, 140, 240)
    for dx in (0, sq + gap):
        for dy in (0, sq + gap):
            pygame.draw.rect(surface, blue, (x + dx, y + dy, sq, sq))


def open_file(path):
    try:
        os.startfile(str(path))  # opens with the Windows default app
    except AttributeError:
        import subprocess
        subprocess.Popen(["xdg-open", str(path)])
    except OSError as e:
        print("Could not open:", path, e)


def fmt_time(ms):
    s = max(0, int(ms // 1000))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fit_text(font, text, max_w):
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + "...")[0] > max_w:
        text = text[:-1]
    return text + "..."


def draw_note(surface, cx, cy, color):
    pygame.draw.ellipse(surface, color, (cx - 30, cy + 10, 36, 26))
    pygame.draw.line(surface, color, (cx + 4, cy + 22), (cx + 4, cy - 40), 5)
    pygame.draw.polygon(surface, color, [
        (cx + 4, cy - 40), (cx + 34, cy - 26), (cx + 34, cy - 14), (cx + 4, cy - 28)])


def draw_slider(surface, rect, frac, enabled=True):
    pygame.draw.rect(surface, TRACK, rect, border_radius=4)
    if enabled:
        fill = rect.copy()
        fill.width = int(rect.width * max(0.0, min(1.0, frac)))
        pygame.draw.rect(surface, ACCENT, fill, border_radius=4)
        kx = rect.x + int(rect.width * max(0.0, min(1.0, frac)))
        pygame.draw.circle(surface, ACCENT, (kx, rect.centery), 8)


# ---------------- Video child window (so video plays INSIDE our window) ----------------
class VideoWindow:
    def __init__(self):
        self.hwnd = None
        self.visible = False
        self.rect = None
        if not IS_WINDOWS:
            return
        try:
            parent = pygame.display.get_wm_info()["window"]
            style = user32.GetWindowLongW(parent, -16)  # GWL_STYLE
            user32.SetWindowLongW(parent, -16, style | 0x02000000)  # WS_CLIPCHILDREN
            WS_CHILD = 0x40000000
            SS_BLACKRECT = 0x4
            self.hwnd = user32.CreateWindowExW(
                0, "STATIC", None, WS_CHILD | SS_BLACKRECT,
                0, 0, 10, 10, parent, None, None, None)
            if self.hwnd:
                user32.EnableWindow(self.hwnd, False)  # keep keyboard focus on pygame
        except Exception as e:
            print("Could not create video area:", e)
            self.hwnd = None

    def place(self, rect):
        if not self.hwnd:
            return
        key = (rect.x, rect.y, rect.w, rect.h)
        if key != self.rect:
            user32.MoveWindow(self.hwnd, rect.x, rect.y, rect.w, rect.h, True)
            self.rect = key

    def show(self, flag):
        if not self.hwnd or flag == self.visible:
            return
        user32.ShowWindow(self.hwnd, 5 if flag else 0)  # SW_SHOW / SW_HIDE
        self.visible = flag

    def destroy(self):
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None


# ---------------- Media player ----------------
class MediaPlayer:
    def __init__(self, video_window):
        self.vw = video_window
        self.kind = None          # None, "image", "gif", "audio", "video"
        self.path = None
        self.volume = 70
        self.error = ""
        self.paused = False
        self.ended = False
        self.backend = None       # "vlc" or "mixer" for audio/video

        self.image = None
        self._scaled = None       # (key, surface)
        self.frames, self.durations = [], []
        self.frame_idx, self.frame_t = 0, 0.0

        self.vlc_player = None
        self.instance = None
        self._vol_pending = False
        if HAVE_VLC:
            try:
                self.instance = vlc.Instance("--no-video-title-show", "--quiet")
                self.vlc_player = self.instance.media_player_new()
                self.vlc_player.video_set_mouse_input(False)
                self.vlc_player.video_set_key_input(False)
            except Exception as e:
                print("VLC could not start:", e)
                self.vlc_player = None

    # ---- loading ----
    def stop(self):
        if self.vlc_player:
            try:
                self.vlc_player.stop()
            except Exception:
                pass
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        self.vw.show(False)
        self.kind = None
        self.path = None
        self.image = None
        self._scaled = None
        self.frames, self.durations = [], []
        self.paused = False
        self.ended = False
        self.backend = None

    def load(self, path):
        self.stop()
        self.error = ""
        self.path = path
        ext = path.suffix.lower()
        try:
            if ext in IMAGE_EXTS:
                self.image = self._load_surface(path)
                self.kind = "image"
            elif ext in GIF_EXTS:
                self._load_gif(path)
            elif ext in AUDIO_EXTS:
                self._play_audio(path)
            elif ext in VIDEO_EXTS:
                self._play_video(path)
        except Exception as e:
            self.error = f"Could not play this file ({e})"
            self.kind = None

    def _load_surface(self, path):
        try:
            return pygame.image.load(str(path)).convert_alpha()
        except pygame.error:
            if not HAVE_PIL:
                raise
            im = Image.open(str(path)).convert("RGBA")
            return pygame.image.frombuffer(im.tobytes(), im.size, "RGBA").convert_alpha()

    def _load_gif(self, path):
        if not HAVE_PIL:
            self.image = self._load_surface(path)
            self.kind = "image"
            self.error = "Install Pillow (pip install pillow) to animate GIFs."
            return
        im = Image.open(str(path))
        for i, fr in enumerate(ImageSequence.Iterator(im)):
            if i >= 300:
                break
            rgba = fr.convert("RGBA")
            if rgba.width > 960:
                rgba = rgba.resize((960, max(1, int(rgba.height * 960 / rgba.width))))
            surf = pygame.image.frombuffer(rgba.tobytes(), rgba.size, "RGBA").convert_alpha()
            self.frames.append(surf)
            self.durations.append(max(20, int(fr.info.get("duration", 100))))
        self.frame_idx, self.frame_t = 0, time.time()
        self.kind = "gif"

    def _play_audio(self, path):
        if self.vlc_player:
            self._start_vlc(path, video=False)
            self.kind = "audio"
            self.backend = "vlc"
        else:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.volume / 100)
            pygame.mixer.music.play()
            self.kind = "audio"
            self.backend = "mixer"

    def _play_video(self, path):
        if not (self.vlc_player and self.vw.hwnd):
            self.error = ("Video needs VLC: install VLC (64-bit) and run  pip install python-vlc.  "
                          "Press O to open it in your default player instead.")
            return
        self._start_vlc(path, video=True)
        self.kind = "video"
        self.backend = "vlc"
        self.vw.show(True)

    def _start_vlc(self, path, video):
        media = self.instance.media_new(str(path))
        self.vlc_player.set_media(media)
        if video:
            self.vlc_player.set_hwnd(self.vw.hwnd)
        self.vlc_player.play()
        self.vlc_player.audio_set_volume(self.volume)
        self._vol_pending = True

    # ---- controls ----
    def is_playing(self):
        if self.kind == "gif":
            return not self.paused
        if self.backend == "vlc":
            return bool(self.vlc_player.is_playing())
        if self.backend == "mixer":
            return pygame.mixer.music.get_busy() and not self.paused
        return False

    def can_play_pause(self):
        return self.kind in ("gif", "audio", "video")

    def toggle_pause(self):
        if self.kind == "gif":
            self.paused = not self.paused
            self.frame_t = time.time()
        elif self.backend == "vlc":
            st = self.vlc_player.get_state()
            if st in (vlc.State.Ended, vlc.State.Stopped):
                self.vlc_player.stop()
                self.vlc_player.play()
                self.paused = False
                self.ended = False
                self._vol_pending = True
            elif self.vlc_player.is_playing():
                self.vlc_player.set_pause(1)
                self.paused = True
            else:
                self.vlc_player.set_pause(0)
                self.paused = False
        elif self.backend == "mixer":
            if self.ended:
                pygame.mixer.music.play()
                self.ended = False
                self.paused = False
            elif self.paused:
                pygame.mixer.music.unpause()
                self.paused = False
            else:
                pygame.mixer.music.pause()
                self.paused = True

    def length_ms(self):
        if self.backend == "vlc":
            return max(0, self.vlc_player.get_length())
        return 0

    def position_ms(self):
        if self.backend == "vlc":
            return max(0, self.vlc_player.get_time())
        if self.backend == "mixer":
            return max(0, pygame.mixer.music.get_pos())
        return 0

    def can_seek(self):
        return self.backend == "vlc" and self.length_ms() > 0

    def seek_frac(self, frac):
        if not self.can_seek():
            return
        frac = max(0.0, min(0.999, frac))
        if self.vlc_player.get_state() in (vlc.State.Ended, vlc.State.Stopped):
            self.vlc_player.stop()
            self.vlc_player.play()
            self.ended = False
        self.vlc_player.set_time(int(self.length_ms() * frac))

    def seek_rel(self, seconds):
        if not self.can_seek():
            return
        t = self.position_ms() + int(seconds * 1000)
        self.vlc_player.set_time(max(0, min(self.length_ms() - 500, t)))

    def set_volume(self, v):
        self.volume = max(0, min(100, int(v)))
        if self.vlc_player:
            self.vlc_player.audio_set_volume(self.volume)
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.set_volume(self.volume / 100)
        except Exception:
            pass

    # ---- per-frame ----
    def update(self):
        if self.kind == "gif" and self.frames and not self.paused:
            now = time.time()
            if now - self.frame_t >= self.durations[self.frame_idx] / 1000:
                self.frame_idx = (self.frame_idx + 1) % len(self.frames)
                self.frame_t = now
        elif self.backend == "vlc":
            st = self.vlc_player.get_state()
            if self._vol_pending and st == vlc.State.Playing:
                self.vlc_player.audio_set_volume(self.volume)
                self._vol_pending = False
            if st == vlc.State.Ended:
                self.ended = True
            elif st == vlc.State.Error:
                self.error = "VLC could not play this file."
                self.stop()
        elif self.backend == "mixer":
            if not self.paused and not pygame.mixer.music.get_busy():
                self.ended = True

    def _fit(self, surf, rect, smooth):
        sw, sh = surf.get_size()
        scale = min(rect.w / sw, rect.h / sh)
        size = (max(1, int(sw * scale)), max(1, int(sh * scale)))
        if smooth:
            key = (id(surf), size)
            if not self._scaled or self._scaled[0] != key:
                self._scaled = (key, pygame.transform.smoothscale(surf, size))
            return self._scaled[1]
        return pygame.transform.scale(surf, size)

    def draw(self, surface, rect, font, big_font):
        if self.kind == "video":
            return  # the video child window covers this area
        pygame.draw.rect(surface, PANEL_BG, rect)
        pygame.draw.rect(surface, LINE, rect, 1)
        if self.kind == "image" and self.image:
            img = self._fit(self.image, rect.inflate(-10, -10), True)
            surface.blit(img, img.get_rect(center=rect.center))
        elif self.kind == "gif" and self.frames:
            img = self._fit(self.frames[self.frame_idx], rect.inflate(-10, -10), False)
            surface.blit(img, img.get_rect(center=rect.center))
        elif self.kind == "audio":
            draw_note(surface, rect.centerx, rect.centery - 20, ACCENT)
            name = fit_text(big_font, self.path.name, rect.w - 40)
            t = big_font.render(name, True, TEXT)
            surface.blit(t, t.get_rect(center=(rect.centerx, rect.centery + 70)))
        else:
            msg = self.error or "Double-click a video, song or picture to play it here"
            color = (180, 40, 40) if self.error else GRAY
            words, lines, cur = msg.split(" "), [], ""
            for wd in words:
                test = (cur + " " + wd).strip()
                if font.size(test)[0] > rect.w - 60 and cur:
                    lines.append(cur)
                    cur = wd
                else:
                    cur = test
            lines.append(cur)
            y = rect.centery - len(lines) * 12
            for ln in lines:
                t = font.render(ln, True, color)
                surface.blit(t, t.get_rect(center=(rect.centerx, y)))
                y += 24
        if self.error and self.kind in ("image", "gif"):
            t = font.render(self.error, True, (180, 40, 40))
            surface.blit(t, (rect.x + 10, rect.bottom - 28))

    def shutdown(self):
        self.stop()
        if self.vlc_player:
            try:
                self.vlc_player.release()
                self.instance.release()
            except Exception:
                pass


# ---------------- Main ----------------
def main():
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption("Toothless OS Media Center")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("segoeui", 16)
    big_font = pygame.font.SysFont("segoeui", 36)
    mid_font = pygame.font.SysFont("segoeui", 22)
    small_font = pygame.font.SysFont("segoeui", 13)

    # Load your logo (looks for logo.png next to this script)
    logo = None
    logo_path = Path(__file__).parent / LOGO_FILE
    try:
        logo = pygame.image.load(str(logo_path)).convert_alpha()
        ratio = LOGO_HEIGHT / logo.get_height()
        logo = pygame.transform.smoothscale(
            logo, (int(logo.get_width() * ratio), LOGO_HEIGHT)
        )
    except (pygame.error, FileNotFoundError):
        print("Could not load", logo_path)

    logo_w = logo.get_width() + 20 if logo else 0

    video_window = VideoWindow()
    player = MediaPlayer(video_window)
    if not HAVE_VLC:
        print("python-vlc not found: video won't play inside the window. "
              "Run: pip install python-vlc  (and install VLC)")

    show_all = False
    root = Node(Path(ROOT_PATH), True, name="C:/")
    root.expanded = True

    scroll = 0
    selected = None
    last_click = (None, 0.0)
    drag_seek = False
    drag_vol = False

    running = True
    while running:
        rows, last_child = [], {}
        build_rows(root, 0, None, rows, last_child, show_all)

        w, h = screen.get_size()
        tree_rect = pygame.Rect(0, HEADER_H, TREE_W, h - HEADER_H)
        panel = pygame.Rect(TREE_W, HEADER_H, max(50, w - TREE_W), h - HEADER_H)
        ctrl = pygame.Rect(panel.x, panel.bottom - CONTROLS_H, panel.w, CONTROLS_H)
        view = pygame.Rect(panel.x + 10, panel.y + 10, panel.w - 20,
                           max(40, panel.h - CONTROLS_H - 20))

        seek_rect = pygame.Rect(ctrl.x + 70, ctrl.y + 14, max(20, ctrl.w - 140), 8)
        play_btn = pygame.Rect(ctrl.x + 16, ctrl.y + 38, 34, 34)
        stop_btn = pygame.Rect(ctrl.x + 58, ctrl.y + 38, 34, 34)
        vol_rect = pygame.Rect(ctrl.right - 170, ctrl.y + 51, 120, 8)

        max_scroll = max(0, len(rows) * ROW_H + 10 - tree_rect.height)
        scroll = max(0, min(scroll, max_scroll))

        def seek_from_mouse(mx):
            player.seek_frac((mx - seek_rect.x) / seek_rect.w)

        def vol_from_mouse(mx):
            player.set_volume(100 * (mx - vol_rect.x) / vol_rect.w)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEWHEEL:
                if panel.collidepoint(pygame.mouse.get_pos()):
                    player.set_volume(player.volume + event.y * 5)
                else:
                    scroll = max(0, min(scroll - event.y * ROW_H * 2, max_scroll))

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f:
                    show_all = not show_all
                    scroll = 0
                elif event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    player.toggle_pause()
                elif event.key == pygame.K_s:
                    player.stop()
                elif event.key == pygame.K_LEFT:
                    player.seek_rel(-5)
                elif event.key == pygame.K_RIGHT:
                    player.seek_rel(5)
                elif event.key == pygame.K_UP:
                    player.set_volume(player.volume + 5)
                elif event.key == pygame.K_DOWN:
                    player.set_volume(player.volume - 5)
                elif event.key == pygame.K_o and selected and not selected.is_dir:
                    open_file(selected.path)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if play_btn.collidepoint(mx, my):
                    player.toggle_pause()
                elif stop_btn.collidepoint(mx, my):
                    player.stop()
                elif seek_rect.inflate(0, 20).collidepoint(mx, my) and player.can_seek():
                    drag_seek = True
                    seek_from_mouse(mx)
                elif vol_rect.inflate(16, 20).collidepoint(mx, my):
                    drag_vol = True
                    vol_from_mouse(mx)
                elif tree_rect.collidepoint(mx, my):
                    i = (my - tree_rect.top + scroll) // ROW_H
                    if 0 <= i < len(rows):
                        node = rows[i][0]
                        selected = node
                        now = time.time()
                        double = last_click[0] is node and now - last_click[1] < 0.4
                        last_click = (node, now)
                        if node.is_dir:
                            node.expanded = not node.expanded
                        elif double:
                            if node.path.suffix.lower() in MEDIA_EXTS:
                                player.load(node.path)
                            else:
                                open_file(node.path)

            elif event.type == pygame.MOUSEMOTION:
                if drag_seek:
                    seek_from_mouse(event.pos[0])
                if drag_vol:
                    vol_from_mouse(event.pos[0])

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                drag_seek = False
                drag_vol = False

        player.update()

        # keep the video area in sync with the layout
        if player.kind == "video":
            video_window.place(view)
            video_window.show(True)
        else:
            video_window.show(False)

        # ---- draw ----
        screen.fill(BG)

        # header (matches your sketch: Windows logo + "C:/")
        if logo:
            screen.blit(logo, (10, 8))
        draw_windows_logo(screen, 20 + logo_w, 12)
        label = big_font.render("C:/", True, TEXT)
        screen.blit(label, (78 + logo_w, 12))
        hint = small_font.render(
            "Click folder = open/close  |  Double-click = play  |  Space = pause  |  "
            "Arrows = seek/volume  |  F = all files  |  O = open externally",
            True, (150, 150, 170),
        )
        screen.blit(hint, (20 + logo_w, HEADER_H - 22))

        # ---- tree (left) ----
        screen.set_clip(tree_rect)
        mouse = pygame.mouse.get_pos()
        base_x = 20

        def row_y(i):
            return tree_rect.top + i * ROW_H - scroll

        for i, (node, depth, parent_idx) in enumerate(rows):
            if node.is_dir and node.expanded and i in last_child:
                x = base_x + depth * INDENT + ICON // 2
                pygame.draw.line(
                    screen, LINE,
                    (x, row_y(i) + ROW_H - 4),
                    (x, row_y(last_child[i]) + ROW_H // 2), 1,
                )
            if parent_idx is not None:
                px = base_x + (depth - 1) * INDENT + ICON // 2
                cy = row_y(i) + ROW_H // 2
                pygame.draw.line(screen, LINE, (px, cy), (base_x + depth * INDENT - 3, cy), 1)

        for i, (node, depth, parent_idx) in enumerate(rows):
            y = row_y(i)
            if y + ROW_H < tree_rect.top or y > tree_rect.bottom:
                continue
            row_rect = pygame.Rect(0, y, TREE_W, ROW_H)
            if node is selected:
                pygame.draw.rect(screen, SELECT, row_rect)
            elif row_rect.collidepoint(mouse) and tree_rect.collidepoint(mouse):
                pygame.draw.rect(screen, HOVER, row_rect)

            x = base_x + depth * INDENT
            screen.blit(get_icon(node.path, node.is_dir), (x, y + (ROW_H - ICON) // 2))
            txt = font.render(node.name, True, TEXT)
            screen.blit(txt, (x + ICON + 6, y + (ROW_H - txt.get_height()) // 2))

        screen.set_clip(None)
        pygame.draw.line(screen, LINE, (TREE_W, HEADER_H), (TREE_W, h), 1)

        # ---- player (right) ----
        player.draw(screen, view, font, mid_font)

        # controls bar
        pygame.draw.rect(screen, BG, ctrl)
        timed = player.kind in ("audio", "video")
        seekable = player.can_seek()
        pos, length = player.position_ms(), player.length_ms()
        frac = (pos / length) if length > 0 else 0
        if timed:
            screen.blit(small_font.render(fmt_time(pos), True, GRAY), (ctrl.x + 16, ctrl.y + 9))
            end_txt = fmt_time(length) if length > 0 else "--:--"
            screen.blit(small_font.render(end_txt, True, GRAY), (ctrl.right - 56, ctrl.y + 9))
        draw_slider(screen, seek_rect, frac, enabled=timed and seekable)

        for rect in (play_btn, stop_btn):
            hot = rect.collidepoint(mouse)
            pygame.draw.rect(screen, BTN_HOVER if hot else BTN, rect, border_radius=6)
        cx, cy = play_btn.center
        if player.can_play_pause() and player.is_playing():
            pygame.draw.rect(screen, TEXT, (cx - 7, cy - 8, 5, 16))
            pygame.draw.rect(screen, TEXT, (cx + 2, cy - 8, 5, 16))
        else:
            pygame.draw.polygon(screen, TEXT, [(cx - 5, cy - 8), (cx - 5, cy + 8), (cx + 8, cy)])
        pygame.draw.rect(screen, TEXT, (stop_btn.centerx - 7, stop_btn.centery - 7, 14, 14))

        # now playing
        title_x = stop_btn.right + 16
        title_w = vol_rect.x - 50 - title_x
        if player.path and title_w > 40:
            name = fit_text(font, player.path.name, title_w)
            screen.blit(font.render(name, True, TEXT), (title_x, ctrl.y + 46))

        # volume
        screen.blit(small_font.render("Vol", True, GRAY), (vol_rect.x - 32, ctrl.y + 47))
        draw_slider(screen, vol_rect, player.volume / 100)
        screen.blit(small_font.render(f"{player.volume}%", True, GRAY),
                    (vol_rect.right + 14, ctrl.y + 47))

        pygame.display.flip()
        clock.tick(60)

    player.shutdown()
    video_window.destroy()
    pygame.quit()


if __name__ == "__main__":
    main()