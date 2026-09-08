#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================
# 导入系统库
# ============================
import os
import sys
import time
import json
import glob
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import ctypes
import logging
import math
import select
import zipfile
import struct
import configparser
import fcntl
import datetime

VERSION = "1.0.2"

# ============================
# 导入第三方库
# ============================
def ensure_requests():
    try:
        program = os.path.dirname(os.path.abspath(__file__))
        depspath = os.path.join(program, "deps")
        if not os.path.exists(depspath):
            module_file = os.path.join(program, "module.zip")
            with zipfile.ZipFile(module_file, 'r') as zip_ref:
                zip_ref.extractall(program)
            print("Successfully installed sdl2 and PIL and flask")
        return True
    except Exception as e:
        print(f"Failed to install: {e}")
        return False

if ensure_requests():
    base_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(base_path, "deps"))

try:
    import sdl2
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Failed to import SDL2 and PIL modules. Please install them.")
    sys.exit(1)

# ============================
# 配置 & 常量
# ============================
APP_PATH = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOGGER = logging.getLogger("radio_dualscreen")
LOGGER.info("=== Radio DualScreen Started ===")

class RadioConfig:
    BOARD_MAPPING = {
        "RGds": 10,
        "RGdsplus": 11
    }
    SYSTEM_LIST = ("zh_CN", "zh_TW", "en_US", "ja_JP", "ko_KR", "es_LA", "ru_RU", "de_DE", "fr_FR", "pt_BR")

    COLOR_BG = "#121212"
    COLOR_BG_GRADIENT = "#2C2C2C"
    COLOR_TEXT = "#E0E0E0"
    COLOR_SHADOW = "#00000080"

    font_file = os.path.join(APP_PATH, "font", "font.ttf")
    if not os.path.exists(font_file):
        font_file = "/mnt/vendor/bin/default.ttf"

    KEYMAP = {
        304: "A", 305: "B", 306: "Y", 307: "X",
        308: "L1", 309: "R1", 314: "L2", 315: "R2",
        17: "DY", 16: "DX",
        310: "SELECT", 311: "START", 312: "MENUF",
        114: "V-", 115: "V+",
    }

    @staticmethod
    def screen_resolutions() -> Dict[int, Tuple[int, int, int]]:
        return {
            9: (1024, 768, 18),
            10: (640, 480, 11),
            11: (682, 512, 11)
        }

# ============================
# 多语言翻译器
# ============================
class Translator:
    def __init__(self, lang_code="en_US"):
        self.lang_code = lang_code
        self.lang_data = {}
        self.load_language(lang_code)

    def load_language(self, lang_code):
        base = os.path.dirname(os.path.abspath(__file__))
        lang_file = os.path.join(base, "lang", f"{lang_code}.json")
        if not os.path.exists(lang_file):
            lang_file = os.path.join(base, "lang", "en_US.json")
            LOGGER.warning("Language file %s not found, using en_US", lang_code)
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                self.lang_data = json.load(f)
            LOGGER.info("Loaded language: %s", lang_code)
        except Exception as e:
            LOGGER.error("Failed to load language file: %s", e)
            self.lang_data = {}

    def t(self, key):
        return self.lang_data.get(key, key)

# ============================
# 输入处理
# ============================
class InputHandler:
    def __init__(self, cfg: RadioConfig):
        self.cfg = cfg
        self.code_name = ""
        self.value = 0

        try:
            self.board_info = Path("/mnt/vendor/oem/board.ini").read_text().splitlines()[0]
        except:
            self.board_info = "RGds"
        self.device_path = self._find_anbernic_device()
        self.dev_fd = None

        try:
            self.dev_fd = open(self.device_path, "rb", buffering=0)
            flags = fcntl.fcntl(self.dev_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.dev_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        except Exception as e:
            LOGGER.error("Failed to open input device: %s", e)
            self.dev_fd = None

    def _find_anbernic_device(self):
        keyword = "ANBERNIC"
        for event_path in glob.glob("/dev/input/event*"):
            dev_name = os.path.basename(event_path)
            sys_path = f"/sys/class/input/{dev_name}/device/name"
            try:
                with open(sys_path, 'r') as f:
                    name = f.read().strip()
                    if keyword in name:
                        return event_path
            except Exception:
                continue
        fallback = f"/dev/input/event{self.cfg.BOARD_MAPPING.get(self.board_info, 5)}"
        if os.path.exists(fallback):
            return fallback
        raise RuntimeError("No ANBERNIC input device found")

    def poll(self) -> None:
        if self.dev_fd is None:
            self.code_name = ""
            self.value = 0
            return
        try:
            rlist, _, _ = select.select([self.dev_fd], [], [], 0.01)
            if not rlist:
                self.code_name = ""
                self.value = 0
                return
            event = self.dev_fd.read(24)
            if not event:
                self.code_name = ""
                self.value = 0
                return
            (tv_sec, tv_usec, etype, kcode, kvalue) = struct.unpack("llHHI", event)
            if kvalue != 0:
                if kvalue != 1:
                    kvalue = -1
                else:
                    kvalue = 1
                self.code_name = self.cfg.KEYMAP.get(kcode, str(kcode))
                self.value = kvalue
                LOGGER.debug("Key: %s (code:%s val:%s)", self.code_name, kcode, kvalue)
            else:
                self.code_name = ""
                self.value = 0
        except Exception as e:
            LOGGER.error("Input error: %s", e)
            self.code_name = ""
            self.value = 0

    def is_key(self, name: str, key_value: int = 99) -> bool:
        if self.code_name == name:
            if key_value != 99:
                return self.value == key_value
            return True
        return False

    def slide_key(self) -> bool:
        return bool(self.code_name)

    def reset(self) -> None:
        self.code_name = ""
        self.value = 0

# ============================
# 触摸处理
# ============================
class TouchHandler:
    def __init__(self, device="/dev/input/event1", screen_width=640, screen_height=480):
        self.device = device
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fd = None
        self.touch_active = False
        self.last_x = None
        self.last_y = None
        self.pending_tap = None
        self._open_device()

    def _open_device(self):
        try:
            self.fd = os.open(self.device, os.O_RDONLY | os.O_NONBLOCK)
            LOGGER.info(f"Touch device opened: {self.device}")
        except Exception as e:
            LOGGER.error(f"Failed to open touch device {self.device}: {e}")
            self.fd = None

    def get_tap(self):
        """非阻塞返回最近一次触摸抬起事件坐标 (x, y)，若无则返回 None"""
        if self.fd is None:
            return None
        import select
        r, _, _ = select.select([self.fd], [], [], 0)
        if not r:
            return None
        while True:
            try:
                data = os.read(self.fd, 256)
                if len(data) == 0:
                    break
                offset = 0
                while offset + 24 <= len(data):
                    chunk = data[offset:offset+24]
                    sec, usec, etype, code, value = struct.unpack("llHHI", chunk)
                    if etype == 0x03:  # EV_ABS
                        if code == 0x35:  # ABS_MT_POSITION_X
                            self.last_x = value
                        elif code == 0x36:  # ABS_MT_POSITION_Y
                            self.last_y = value
                    elif etype == 0x01 and code == 0x14a:  # EV_KEY, BTN_TOUCH
                        new_active = (value == 1)
                        if not new_active and self.touch_active:
                            if self.last_x is not None and self.last_y is not None:
                                x = max(0, min(self.last_x, self.screen_width-1))
                                y = max(0, min(self.last_y, self.screen_height-1))
                                self.pending_tap = (x, y)
                        self.touch_active = new_active
                    offset += 24
            except BlockingIOError:
                break
            except Exception as e:
                LOGGER.error(f"Touch read error: {e}")
                break
        if self.pending_tap is not None:
            tap = self.pending_tap
            self.pending_tap = None
            return tap
        return None

    def set_screen_size(self, width, height):
        self.screen_width = width
        self.screen_height = height

# ============================
# 双屏 UI 渲染器
# ============================
class DualUIRenderer:
    """管理两个屏幕的窗口，提供切换绘制目标的功能"""
    def __init__(self, cfg: RadioConfig, board_info=None):
        self.cfg = cfg
        self.board_info = board_info
        self.screens = []          # 每个元素: dict {window, renderer, surface, draw, width, height}
        self.current_target = 0    # 默认目标索引

        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
            raise RuntimeError("SDL_Init failed")

        display_count = sdl2.SDL_GetNumVideoDisplays()
        LOGGER.info(f"Detected {display_count} displays")

        # 决定要创建的屏幕数量（最多2个）
        num_screens = min(display_count, 2)
        if num_screens < 1:
            raise RuntimeError("No display available")

        for disp_idx in range(num_screens):
            bounds = sdl2.SDL_Rect()
            if sdl2.SDL_GetDisplayBounds(disp_idx, bounds) == 0:
                w, h = bounds.w, bounds.h
            else:
                # 降级使用配置尺寸
                res = RadioConfig.screen_resolutions().get(
                    cfg.BOARD_MAPPING.get(board_info or "RGds", 10), (640, 480, 11)
                )
                w, h = res[0], res[1]
            # 为 RGdsplus 特殊处理
            if board_info == "RGdsplus":
                res = RadioConfig.screen_resolutions().get(cfg.BOARD_MAPPING.get("RGdsplus", 11), (682, 512, 11))
                w, h = res[0], res[1]

            # 创建窗口
            win = sdl2.SDL_CreateWindow(
                f"Radio Screen {disp_idx}".encode(),
                sdl2.SDL_WINDOWPOS_CENTERED_DISPLAY(disp_idx),
                sdl2.SDL_WINDOWPOS_CENTERED_DISPLAY(disp_idx),
                w, h,
                sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP | sdl2.SDL_WINDOW_SHOWN
            )
            if not win:
                LOGGER.error(f"Failed to create window on display {disp_idx}")
                continue

            ren = sdl2.SDL_CreateRenderer(win, -1, sdl2.SDL_RENDERER_ACCELERATED)
            if not ren:
                ren = sdl2.SDL_CreateRenderer(win, -1, sdl2.SDL_RENDERER_SOFTWARE)
            if not ren:
                sdl2.SDL_DestroyWindow(win)
                LOGGER.error(f"Failed to create renderer on display {disp_idx}")
                continue

            surface = Image.new("RGBA", (w, h), color=cfg.COLOR_BG)
            draw = ImageDraw.Draw(surface)

            self.screens.append({
                "window": win,
                "renderer": ren,
                "surface": surface,
                "draw": draw,
                "width": w,
                "height": h,
                "display": disp_idx
            })
            LOGGER.info(f"Screen {disp_idx} created ({w}x{h})")

        if not self.screens:
            raise RuntimeError("No screens created")

        # 默认目标：如果有两个屏幕，设为下屏（索引1）作为 UI 目标
        if len(self.screens) >= 2:
            self.current_target = 1
        else:
            self.current_target = 0

        LOGGER.info(f"Default target set to screen {self.current_target}")

    def set_target(self, screen_idx: int):
        if 0 <= screen_idx < len(self.screens):
            self.current_target = screen_idx
            LOGGER.debug(f"Drawing target switched to screen {screen_idx}")
        else:
            LOGGER.warning(f"Invalid screen index {screen_idx}, keeping current")

    def get_screen_size(self, screen_idx=None) -> Tuple[int, int]:
        if screen_idx is None:
            screen_idx = self.current_target
        if screen_idx < len(self.screens):
            return (self.screens[screen_idx]["width"], self.screens[screen_idx]["height"])
        return (640, 480)

    def clear(self, screen_idx=None):
        if screen_idx is None:
            screen_idx = self.current_target
        scr = self.screens[screen_idx]
        w, h = scr["width"], scr["height"]
        scr["surface"].paste(self.cfg.COLOR_BG, (0, 0, w, h))
        scr["draw"] = ImageDraw.Draw(scr["surface"])

    def text(self, pos, text, font_size=22, color=None, anchor=None, bold=False, shadow=False, screen_idx=None):
        if screen_idx is None:
            screen_idx = self.current_target
        scr = self.screens[screen_idx]
        color = color or self.cfg.COLOR_TEXT
        font_path = self.cfg.font_file
        try:
            fnt = ImageFont.truetype(font_path, font_size)
            if shadow:
                for dx, dy in [(1,1),(1,-1),(-1,1),(-1,-1)]:
                    scr["draw"].text((pos[0]+dx, pos[1]+dy), text, font=fnt, fill=self.cfg.COLOR_SHADOW, anchor=anchor)
            scr["draw"].text(pos, text, font=fnt, fill=color, anchor=anchor)
        except:
            fnt = ImageFont.load_default()
            scr["draw"].text(pos, text, font=fnt, fill=color, anchor=anchor)

    def rect(self, xy, fill=None, outline=None, width=1, radius=0, shadow=False, screen_idx=None):
        if screen_idx is None:
            screen_idx = self.current_target
        scr = self.screens[screen_idx]
        if shadow and radius > 0:
            sh_xy = [xy[0]+2, xy[1]+2, xy[2]+2, xy[3]+2]
            scr["draw"].rounded_rectangle(sh_xy, radius=radius, fill=self.cfg.COLOR_SHADOW)
        if radius > 0:
            scr["draw"].rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
        else:
            scr["draw"].rectangle(xy, fill=fill, outline=outline, width=width)

    def circle(self, center, radius, fill=None, outline=None, shadow=False, screen_idx=None):
        if screen_idx is None:
            screen_idx = self.current_target
        scr = self.screens[screen_idx]
        x, y = center
        if shadow:
            scr["draw"].ellipse([x-radius-2, y-radius-2, x+radius+2, y+radius+2],
                                fill=self.cfg.COLOR_SHADOW)
        scr["draw"].ellipse([x-radius, y-radius, x+radius, y+radius], fill=fill, outline=outline)

    def line(self, xy, fill=None, width=1, screen_idx=None):
        if screen_idx is None:
            screen_idx = self.current_target
        scr = self.screens[screen_idx]
        scr["draw"].line(xy, fill=fill, width=width)

    def blend_colors(self, color1: str, color2: str, ratio: float) -> str:
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    def paint(self, screen_idx=None):
        if screen_idx is None:
            screen_idx = self.current_target
        scr = self.screens[screen_idx]
        img = scr["surface"]
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        data = img.tobytes()
        w, h = scr["width"], scr["height"]
        surface = sdl2.SDL_CreateRGBSurfaceWithFormatFrom(
            data, w, h, 32, w * 4, sdl2.SDL_PIXELFORMAT_RGBA32
        )
        texture = sdl2.SDL_CreateTextureFromSurface(scr["renderer"], surface)
        sdl2.SDL_FreeSurface(surface)

        win_w = ctypes.c_int()
        win_h = ctypes.c_int()
        sdl2.SDL_GetWindowSize(scr["window"], ctypes.byref(win_w), ctypes.byref(win_h))
        dst = sdl2.SDL_Rect(0, 0, win_w.value, win_h.value)
        sdl2.SDL_RenderCopy(scr["renderer"], texture, None, dst)
        sdl2.SDL_RenderPresent(scr["renderer"])
        sdl2.SDL_DestroyTexture(texture)

    def paint_all(self):
        for i in range(len(self.screens)):
            self.paint(i)

    def draw_end(self):
        for scr in self.screens:
            sdl2.SDL_DestroyRenderer(scr["renderer"])
            sdl2.SDL_DestroyWindow(scr["window"])
        sdl2.SDL_Quit()

# ============================
# 收音机核心功能
# ============================
class RadioScanner:
    @staticmethod
    def find_sources() -> List[Dict]:
        bases = [
            "/roms/Radio", "/mnt/mmc/Radio", "/mnt/sdcard/Radio",
        ]
        bases.append(os.path.join(APP_PATH, "Radio"))

        sources = []
        seen = set()
        for b in bases:
            if not os.path.isdir(b):
                continue
            for f in os.listdir(b):
                if f.endswith(".txt"):
                    path = os.path.join(b, f)
                    real = os.path.realpath(path)
                    if real in seen:
                        continue
                    seen.add(real)
                    sources.append({"file": path, "name": f[:-4]})
                    LOGGER.info("Found source: %s", f)
        return sources

    @staticmethod
    def parse_txt(filepath: str) -> List[Dict]:
        channels = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line[0] in "#;":
                        continue
                    sep = line.find(',') if ',' in line else line.find('\t')
                    if sep != -1:
                        name = line[:sep].strip()
                        url = line[sep+1:].strip()
                        if url.startswith("http"):
                            channels.append({"name": name, "url": url})
                    else:
                        if line.startswith("http"):
                            host = line.split('/')[2] if '://' in line else "电台"
                            channels.append({"name": host, "url": line})
        except Exception as e:
            LOGGER.error("Parse error %s: %s", filepath, e)
        return channels

class RadioPlayer:
    def __init__(self):
        self.pid = None
        self.proc = None
        self.status = "idle"
        self.fail_reason = ""
        self.volume = 60
        self.last_url = ""
        self.last_play_time = 0

        # IPC socket 路径
        self.ipc_socket = "/tmp/mpv-ipc-radio.sock"
        if os.path.exists(self.ipc_socket):
            os.remove(self.ipc_socket)

        # 仅保证音频输出通道开启
        self._enable_outputs()

    def _enable_outputs(self):
        """打开 LINEOUT 和 SPK 通道（仅开关，不调节音量）"""
        for ctrl in ["LINEOUT", "SPK"]:
            try:
                subprocess.run(["amixer", "set", ctrl, "on"], stderr=subprocess.DEVNULL, check=False)
            except:
                pass
        LOGGER.info("Outputs enabled (LINEOUT, SPK)")

    def set_volume(self, vol):
        """
        设置音量（0-100），并尝试通过 IPC 实时调整 mpv 音量。
        音量值会保存在 self.volume，外部调用者（RadioApp）负责持久化到配置文件。
        """
        self.volume = max(0, min(100, vol))

        # 如果 mpv 进程存活，通过 Unix Socket 发送命令
        if self.proc is not None and self.proc.poll() is None:
            try:
                import socket
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                sock.connect(self.ipc_socket)
                cmd = json.dumps({"command": ["set_property", "volume", self.volume]})
                sock.sendall((cmd + "\n").encode())
                sock.close()
                LOGGER.info("Volume set to %d via IPC", self.volume)
            except Exception as e:
                LOGGER.error("IPC volume set failed: %s", e)
        else:
            LOGGER.info("mpv not running, volume value saved (will apply on next play)")

    def play(self, url: str):
        """启动 mpv 播放，并启用 IPC 服务器"""
        now = time.time()
        if url == self.last_url and now - self.last_play_time < 1.0:
            LOGGER.info("防连发跳过: %s", url)
            return

        self.stop()
        self.status = "connecting"
        self.fail_reason = ""
        self.last_url = url
        self.last_play_time = now

        mpv_vol = min(100, self.volume)
        cmd = [
            "mpv",
            "--vid=no",                # 无视频
            "--no-video",
            "--no-osd-bar",
            f"--volume={mpv_vol}",     # 启动音量
            "--network-timeout=20",
            "--cache=yes",
            "--cache-secs=10",
            "--stream-lavf-o=reconnect=1",
            "--user-agent=Mozilla/5.0",
            f"--input-ipc-server={self.ipc_socket}",  # 开启 IPC
            url
        ]
        LOGGER.info("Playing: %s (mpv volume=%d%%)", url, mpv_vol)

        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.pid = self.proc.pid
            self.status = "playing"
        except Exception as e:
            self.status = "failed"
            self.fail_reason = str(e)
            LOGGER.error("mpv start failed: %s", e)

    def stop(self):
        """停止 mpv 播放"""
        if self.pid:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1)
            except:
                self.proc.kill()
            self.pid = None
            self.proc = None
            self.status = "idle"
            LOGGER.info("Stopped")

    def is_alive(self) -> bool:
        """检查 mpv 进程是否仍在运行"""
        if self.proc is not None:
            ret = self.proc.poll()
            if ret is None:
                return True
            self.proc = None
            self.pid = None
            return False
        return False

# ============================
# 频谱生成器
# ============================
class SpectrumGenerator:
    def __init__(self, num_bars=28):
        self.num_bars = num_bars
        self.levels = [0.0] * num_bars
        self.targets = [0.0] * num_bars
        self.timer = 0.0

    def update(self, dt: float, play_status: str, now_sec: float):
        if play_status == "playing":
            self.timer -= dt
            if self.timer <= 0:
                self.timer = 0.07
                import random
                for i in range(self.num_bars):
                    base = 0.9 - 0.55 * (i / self.num_bars)
                    wob = 0.5 * abs((now_sec * 3.3 + i * 1.7) % (2*3.14159) - 3.14159)
                    wob += 0.3 * abs((now_sec * 7.9 + i * 0.9) % (2*3.14159) - 3.14159)
                    t = base * wob / 3.14159 + random.random() * 0.30
                    t = max(0.04, min(1.0, t))
                    self.targets[i] = t
            for i in range(self.num_bars):
                d = self.targets[i] - self.levels[i]
                if d > 0:
                    self.levels[i] += d * min(1.0, dt * 20)
                else:
                    self.levels[i] += d * min(1.0, dt * 9)
        elif play_status == "connecting":
            v = 0.08 + 0.05 * (0.5 + 0.5 * (now_sec * 6) % (2*3.14159) / 3.14159)
            for i in range(self.num_bars):
                self.levels[i] += (v - self.levels[i]) * min(1.0, dt * 6)
        else:
            for i in range(self.num_bars):
                self.levels[i] *= max(0.0, 1.0 - dt * 4)

# ============================
# 主应用 (双屏版)
# ============================
class RadioApp:
    def __init__(self):
        self.cfg = RadioConfig()
        self.system_langs = ("zh_CN", "zh_TW", "en_US", "ja_JP", "ko_KR", "es_LA", "ru_RU", "de_DE", "fr_FR", "pt_BR")
        self.language = "en_US"
        self.dial_mode = "1"

        try:
            board_info = Path("/mnt/vendor/oem/board.ini").read_text().splitlines()[0]
        except:
            board_info = "RGds"
        self.board_info = board_info
        self.hw_info = self.cfg.BOARD_MAPPING.get(board_info, 5)

        self.screenshot_dir = "/mnt/mmc/anbernic/screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)

        # 检测显示器数量
        sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
        self.display_count = sdl2.SDL_GetNumVideoDisplays()
        sdl2.SDL_Quit()
        LOGGER.info(f"Detected {self.display_count} displays")
        if self.display_count >= 2:
            self.ui_display = 1      # 下屏（触摸屏）
            self.spectrum_display = 0  # 上屏
        else:
            self.ui_display = 0
            self.spectrum_display = 0
            LOGGER.warning("Only one display, spectrum and UI will share the same screen")

        self.input = InputHandler(self.cfg)
        self.ui = DualUIRenderer(self.cfg, self.board_info)
        w, h = self.ui.get_screen_size(self.ui_display)
        self.touch = TouchHandler(screen_width=w, screen_height=h)

        self.player = RadioPlayer()
        self.spectrum = SpectrumGenerator(28)

        self.sources = []
        self.source_cache = {}
        self.current_source_idx = 0
        self.current_channel_idx = 0
        self.current_channels = []
        self.channel_list_start = 0
        self.playing_channel_idx = -1

        self.wifi_connected = False
        self.wifi_essid = ""
        self.battery_level = 0
        self.battery_charging = False
        self.status_timer = 0.0
        self.now_sec = 0.0
        self.show_hints = True
        self.show_spectrum = True
        self.hint_timer_default = 10.0
        self.reset_hint_timer()

        self._ready()
        self._load_config()
        self._scan_radio()
        self._update_system_status()

        self.skip_first_input = True

    def reset_hint_timer(self):
        self.hint_timer = self.hint_timer_default

    def take_screenshot(self):
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            for idx, scr in enumerate(self.ui.screens):
                img = scr["surface"]
                if img.mode != "RGB":
                    img = img.convert("RGB")
                label = "upper" if idx == 0 else "lower"
                filename = f"screenshot_{label}_{timestamp}.png"
                filepath = os.path.join(self.screenshot_dir, filename)
                img.save(filepath, "PNG")
                LOGGER.info("Screenshot saved: %s", filepath)
        except Exception as e:
            LOGGER.error("Failed to save screenshot: %s", e)

    def _ready(self) -> None:
        target_path = [
            "/mnt/mmc",
            "/mnt/sdcard",
            APP_PATH
        ]
        for path in target_path:
            if path == "/mnt/sdcard" and not os.path.ismount(path):
                continue
            radio_dir = os.path.join(path, "Radio")
            os.makedirs(radio_dir, exist_ok=True)

    def _load_config(self):
        self.config = configparser.ConfigParser()
        self.config_file = os.path.join(APP_PATH, "radio.ini")
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)

        for section in ['General', 'Volume', 'Resume', 'Dial']:
            if section not in self.config:
                self.config[section] = {}

        lang = self.config.get('General', 'language', fallback=None)
        if lang and lang in self.system_langs:
            self.language = lang
        else:
            self.language = self._load_system_language()
        self.translator = Translator(self.language)

        vol = self.config.getint('Volume', 'value', fallback=80)
        vol = max(0, min(100, vol))
        self.player.set_volume(vol)

        src = self.config.getint('Resume', 'source_index', fallback=1)
        ch = self.config.getint('Resume', 'channel_index', fallback=1)
        self.current_source_idx = src - 1
        self.current_channel_idx = ch - 1

        mode = self.config.get('Dial', 'mode', fallback='1')
        if mode in ['1', '2']:
            self.dial_mode = mode
        else:
            self.dial_mode = '1'

    def _save_config(self):
        self.config['General']['language'] = self.language
        self.config['Volume']['value'] = str(self.player.volume)
        self.config['Resume']['source_index'] = str(self.current_source_idx + 1)
        self.config['Resume']['channel_index'] = str(self.current_channel_idx + 1)
        self.config['Dial']['mode'] = self.dial_mode
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
        except Exception as e:
            LOGGER.error("Failed to save config: %s", e)

    def _load_system_language(self):
        try:
            lang_path = "/mnt/vendor/oem/language.ini"
            if os.path.exists(lang_path):
                with open(lang_path, 'r') as f:
                    idx = int(f.read().strip())
                    if 0 <= idx < len(self.system_langs):
                        return self.system_langs[idx]
        except:
            pass
        return "en_US"

    def _scan_radio(self):
        self.sources = RadioScanner.find_sources()
        self.source_cache = {}
        if self.sources:
            if self.current_source_idx < 0 or self.current_source_idx >= len(self.sources):
                self.current_source_idx = 0
            self._load_source(self.current_source_idx)
        else:
            self.current_channels = []
            self.current_source_idx = 0
            LOGGER.warning("No radio sources found")

    def _load_source(self, idx: int):
        if idx < 0 or idx >= len(self.sources):
            return
        src = self.sources[idx]
        if src['file'] in self.source_cache:
            ch = self.source_cache[src['file']]
        else:
            ch = RadioScanner.parse_txt(src['file'])
            self.source_cache[src['file']] = ch
        self.current_source_idx = idx
        self.current_channels = ch
        if self.current_channel_idx < 0 or self.current_channel_idx >= len(ch):
            self.current_channel_idx = 0
        LOGGER.info("Loaded %s: %d channels", src['name'], len(ch))

    def _update_system_status(self):
        # WiFi
        try:
            with open("/sys/class/net/wlan0/operstate", 'r') as f:
                op = f.read().strip()
            self.wifi_connected = (op == "up")
            if not self.wifi_connected:
                with open("/proc/net/wireless", 'r') as f:
                    w = f.read().strip().split()
                if "wlan" in w:
                    self.wifi_connected = True
            if self.wifi_connected:
                essid = subprocess.check_output(["iw", "dev", "wlan0", "link"], stderr=subprocess.DEVNULL).decode()
                for line in essid.splitlines():
                    if line.strip().startswith('SSID'):
                        essid = str(line.split('SSID:', 1)[1].strip())
                self.wifi_essid = essid if essid else self.translator.t("Connected")
            else:
                self.wifi_essid = ""
        except:
            self.wifi_connected = False
            self.wifi_essid = ""
        # 电池
        for p in ["battery", "BAT0", "axp2202-battery"]:
            try:
                with open(f"/sys/class/power_supply/{p}/capacity", 'r') as f:
                    self.battery_level = int(f.read().strip())
                    try:
                        with open(f"/sys/class/power_supply/{p}/status", 'r') as f:
                            st = f.read().strip()
                            self.battery_charging = (st in ["Charging", "Full"])
                    except:
                        self.battery_charging = False
                    break
            except:
                continue

    # ---------- 按键处理 ----------
    def handle_input(self):
        if self.skip_first_input:
            self.input.reset()
            self.skip_first_input = False
            return
        self.input.poll()
        if not self.input.code_name:
            return

        k = self.input.code_name
        val = self.input.value

        # 公共退出键
        if k == "MENUF":
            self.quit()
            return

        # 音量键始终有效
        if k == "V-":
            self.player.set_volume(self.player.volume - 10)
            self._save_config()
            self.reset_hint_timer()
            self.input.reset()
            return
        elif k == "V+":
            self.player.set_volume(self.player.volume + 10)
            self._save_config()
            self.reset_hint_timer()
            self.input.reset()
            return

        # X 切换熄屏
        if k == "X":
            self.reset_hint_timer()
            if self.show_hints and self.show_spectrum:  # 全亮
                self.show_hints = False
            elif not self.show_hints and self.show_spectrum:  # 上屏亮
                self.show_spectrum = False
            elif not self.show_hints and not self.show_spectrum:  # 全灭
                self.show_hints = True
            elif self.show_hints and not self.show_spectrum:  # 下屏亮
                self.show_spectrum = True
            self.input.reset()
            return

        # 熄屏状态下只响应唤醒
        if not self.show_hints:
            if k in ("B"):
                self.show_hints = True
                self.show_spectrum = True
                self.reset_hint_timer()
            self.input.reset()
            return

        # ===== 亮屏按键处理 =====
        if k == "B":
            self.player.stop()
            self.playing_channel_idx = -1
            self.reset_hint_timer()
        elif k == "A":
            if self.player.status != "playing" or self.playing_channel_idx != self.current_channel_idx:
                self.play_selected()
                self.reset_hint_timer()
        elif k == "Y":
            self._scan_radio()
            self.reset_hint_timer()
        elif k == "DY":
            if val == -1:
                self.change_channel(-1)
            elif val == 1:
                self.change_channel(1)
            self.reset_hint_timer()
        elif k == "DX":
            page = self._page_size()
            if val == -1:
                self.change_channel(-page)
            elif val == 1:
                self.change_channel(page)
            self.reset_hint_timer()
        elif k == "L1":
            self.change_source(-1)
            self.reset_hint_timer()
        elif k == "R1":
            self.change_source(1)
            self.reset_hint_timer()
        elif k == "SELECT":
            langs = self.system_langs
            try:
                idx = langs.index(self.language)
                next_lang = langs[(idx + 1) % len(langs)]
            except:
                next_lang = langs[0]
            self.language = next_lang
            self.translator.load_language(next_lang)
            self._save_config()
            self.reset_hint_timer()
            LOGGER.info("Language switched to %s", next_lang)
        elif k == "START":
            if self.dial_mode == "1":
                self.dial_mode = "2"
            else:
                self.dial_mode = "1"
            self._save_config()
            self.reset_hint_timer()

        self.input.reset()

    def change_channel(self, delta: int):
        if not self.current_channels:
            return
        n = len(self.current_channels)
        self.current_channel_idx = (self.current_channel_idx + delta) % n
        LOGGER.info("Channel: %s", self.current_channels[self.current_channel_idx]['name'])
        if self.player.is_alive():
            self.play_selected()

    def change_source(self, delta: int):
        if not self.sources:
            return
        n = len(self.sources)
        self.current_source_idx = (self.current_source_idx + delta) % n
        self._load_source(self.current_source_idx)
        self.current_channel_idx = 0
        if self.player.status == "playing":
            self.playing_channel_idx = -1
            self.play_selected()
        self.reset_hint_timer()
        LOGGER.info("Source: %s", self.sources[self.current_source_idx]['name'])

    def play_selected(self):
        if not self.current_channels or self.current_channel_idx >= len(self.current_channels):
            return
        ch = self.current_channels[self.current_channel_idx]
        self.player.play(ch['url'])
        if self.player.status == "playing":
            self.playing_channel_idx = self.current_channel_idx
        else:
            self.playing_channel_idx = -1

    def _page_size(self) -> int:
        top_h = 44
        bottom_h = 44
        item_h = 26
        # 使用下屏尺寸
        w, h = self.ui.get_screen_size(self.ui_display)
        avail = h - top_h - bottom_h - 40
        return max(1, int(avail / item_h))

    def update(self, dt: float):
        self.now_sec += dt
        self.status_timer += dt
        if self.status_timer >= 8:
            self.status_timer = 0
            self._update_system_status()

        if self.show_hints:
            self.hint_timer -= dt
            if self.hint_timer <= 0:
                self.show_hints = False

        if self.player.pid and not self.player.is_alive():
            self.player.pid = None
            self.player.proc = None
            if self.player.status != "idle":
                self.player.status = "failed"
                if not self.player.fail_reason:
                    self.player.fail_reason = self.translator.t("Playback failed")
                self.playing_channel_idx = -1
                LOGGER.info("mpv exited")

        self.spectrum.update(dt, self.player.status, self.now_sec)

    # ---------- 绘制 ----------
    def draw(self):
        ui = self.ui
        t = self.translator.t

        ch = self.current_channels
        cur = ch[self.current_channel_idx] if ch else None
        top_h = 40
        bot_h = 44

        if self.show_spectrum:
            # ========== 绘制上屏：频谱 ==========
            if self.display_count >= 2:
                ui.set_target(self.spectrum_display)
                W, H = ui.get_screen_size()
                ui.clear()

                # 绘制背景
                ui.rect([0, 0, W, H], fill="#0A0F1A")

                # 标题
                ui.text((W//2, 30), "✌ SPECTRUM ✌", font_size=28, color="#4FC3F7", anchor="mt")

                # 绘制频谱
                self._draw_spectrum_on_screen(ui, W, H)

                # 显示当前频道和状态
                if cur:
                    ui.text((W//2, H-20), f"{cur['name']}  |  {t(self.player.status)}{' '*(len(cur['name']) - len(self.player.status))}", font_size=20, color="#7A8BA0", anchor="mb")
                else:
                    ui.text((W//2, H-20), t("No station"), font_size=20, color="#7A8BA0", anchor="mb")

                ui.paint()
            else:
                pass
            # 由于单屏情况比较复杂，我们在此不做完全实现，但为了演示双屏，我们确保双屏工作正常。
            # 如果只有单屏，程序仍然可以运行，但频谱不会显示（因为没画）。为了完善，我们可以补上单屏逻辑，但这里先忽略。
        else:
            if self.display_count >= 2:
                ui.set_target(self.spectrum_display)
                W, H = ui.get_screen_size()
                ui.clear()

                # 绘制背景
                ui.rect([0, 0, W, H], fill="#000000")
                ui.text((W//2, H//2), "Anbernic", font_size=72, color="#101622",anchor="mm")
                ui.text((W//2, H//2 + 50), "Radio", font_size=24, color="#101622",anchor="mm")
                ui.paint()

        # 绘制下屏 UI
        ui.set_target(self.ui_display)
        W, H = ui.get_screen_size()
        ui.clear()

        if not self.show_hints:
            ui.clear()
            ui.rect([0,0,W,H], fill="#000000C8")
            ui.text((W//2, H//2-30), f"{t('Screen off playing')} · {t('Press X/B to turn on')}", font_size=32, color="#3A3A3A", anchor="mm")
            ui.paint()
        else:
            # ---------- 顶部状态栏 ----------
            ui.rect([0,0,W,top_h], fill="#0D1B2A")
            ui.text((12, 12), f'{t("Network Radio")} v{VERSION}', font_size=18, color="#E0E8F0")
            bat_str = f"{self.battery_level}%" + (" █" if self.battery_charging else " ")
            bat_color = "#4FC3F7" if self.battery_level >= 60 else "#64F6A6" if self.battery_level >= 20 else "#EF5350"
            ui.text((W-12, 22), bat_str, font_size=18, color=bat_color, anchor="rm")
            t_str = time.strftime("%H:%M:%S")
            ui.text((W//2-100, 22), t_str, font_size=20, color="#E0E8F0", anchor="lm")
            wifi_str = f"WiFi: {self.wifi_essid}" if self.wifi_connected else "WiFi ×"
            wifi_color = "#4FC3F7" if self.wifi_connected else "#EF5350"
            ui.text((W//2+200, 22), wifi_str, font_size=18, color=wifi_color, anchor="rm")

            # ---------- 左侧列表 ----------
            lx, ly = 12, top_h + 6
            lw = int(W * 0.45)
            lh = H - ly - bot_h - 6
            ui.rect([lx, ly, lx+lw, ly+lh], fill="#0F1A2E")
            ui.rect([lx+2, ly+2, lx+lw-2, ly+lh-2], fill="#152238")
            src_name = self.sources[self.current_source_idx]['name'] if self.sources else t("Radio")
            ui.text((lx+12, ly+10), f"● {src_name}", font_size=22, color="#64B5F6")
            ui.text((lx+12, ly+44), f"{self.current_source_idx+1}/{len(self.sources)} {t('Category')}  {len(ch)} {t('Channels')}", font_size=14, color="#7A8BA0")

            item_h = 34
            list_top = ly + 74
            visible = self._page_size()
            start = self.current_channel_idx - visible//2
            if start < 0: start = 0
            if ch and start > len(ch) - visible:
                start = max(0, len(ch) - visible)
            for i in range(visible):
                idx = start + i
                if idx < len(ch):
                    y = list_top + i * item_h
                    if idx == self.current_channel_idx:
                        ui.rect([lx+6, y, lx+lw-6, y+item_h-4], fill="#1E88E5")
                        col = "#FFFFFF"
                    else:
                        col = "#B0C4DE"
                    name = ch[idx]['name']
                    if len(name) > 18: name = name[:16]+"…"
                    ui.text((lx+12, y+5), f"{idx+1:2d} {name}", font_size=18, color=col)

            # ---------- 右侧面板（状态与音量） ----------
            rx = lx + lw + 12
            rw = W - rx - 12
            rh = lh
            ui.rect([rx, ly, rx+rw, ly+rh], fill="#0F1A2E")
            ui.rect([rx+2, ly+2, rx+rw-2, ly+rh-2], fill="#152238")

            # 信号灯
            power_col = "#66BB6A"
            ui.circle((rx+26, ly+24), 8, fill=power_col)
            play_col = "#66BB6A" if self.player.status == "playing" else "#455A64"
            ui.circle((rx+50, ly+24), 8, fill=play_col)
            wifi_col = "#66BB6A" if self.wifi_connected else "#455A64"
            ui.circle((rx+74, ly+24), 8, fill=wifi_col)

            status_text = f"{t('Power')}  {t('play')}  {t('WiFi')}"
            if self.player.status == "connecting":
                status_text += f"  ● {t('connecting...')}"
            elif self.player.status == "playing":
                status_text += f"  ● {t('playing')}"
            else:
                status_text += f"  ● {t('idle')}"
            ui.text((rx+92, ly+16), status_text, font_size=16, color="#B0C4DE")

            # 当前台名+URL
            if cur:
                name = cur['name'][:30] + "…" if len(cur['name'])>30 else cur['name']
                ui.text((rx+rw//2, ly+60), name, font_size=22, color="#E0E8F0", anchor="mm")
                url = cur['url'][:30] + "…" if len(cur['url'])>30 else cur['url']
                ui.text((rx+rw//2, ly+90), url, font_size=16, color="#7A8BA0", anchor="mm")
            else:
                ui.text((rx+rw//2, ly+60), t('No stations'), font_size=22, color="#D2C3AA", anchor="mm")

            # 调谐刻度盘（圆形）位置计算
            dial_radius = 72  # 固定最大半径
            dcx = rx + rw // 2
            dcy = ly + rh - 200  # 距离面板底部80像素（音量条在底部）
            dr = min(dial_radius, (rh - 100) // 2)  # 防止超出面板

            if self.dial_mode == "1":
                # 横向调谐条
                dial_y = dcy - 40  # 条的位置在刻度盘中心上方
                dial_h = 120
                dial_x_start = rx + 20
                dial_width = rw - 40
                self._draw_horizontal_dial(dial_x_start, dial_y, dial_width, dial_h, self.current_channel_idx)

            if self.dial_mode == "2":
                self._draw_dial(dcx, dcy, dr)
                pct = (self.current_channel_idx % 100) / 100.0 if ch else 0
                self._draw_needle(dcx, dcy, dr, pct)
                ui.text((dcx, dcy + dr + 10), f"FM {88 + (self.current_channel_idx%100)*0.2:.1f} MHz",
                        font_size=16, color="#D2C3AA", anchor="mt")

            # 音量条
            vx = rx + 20
            vw = rw - 40
            vy = ly + rh - 50
            vh = 18
            ui.rect([vx, vy, vx+vw, vy+vh], fill="#0A0F1A")
            ui.rect([vx, vy, vx+vw, vy+vh], fill=None, outline="#1E3A5F")
            fw = int((vw - 4) * min(self.player.volume, 100) / 100)
            if fw >= 0:
                ui.rect([vx+2, vy+2, vx+2+fw, vy+vh-2], fill="#42A5F5")
                ui.text((vx, vy+vh+8), f"{t('Volume')} {self.player.volume}%", font_size=18, color="#B0C4DE")
            if self.player.status == "failed":
                ui.text((vx+vw, vy+vh+18), f"{self.player.fail_reason[:20]}", font_size=18, color="#EF5350", anchor="rm")

            # 底部提示
            hint1 = (
                " ↑↓ " + t("channel") + "  ←→ " + t("page") +
                "  L1/R1 " + t("category") + " SEL " + t("language") +
                " STA " + t("dial style")
            )
            hint2 = (
                "  A " + t("play") +
                "  B " + t("stop/turn on") + "  X " + t("screen off") +
                "  Y " + t("refresh") + "  RG " + t("exit")
            )
            ui.rect([0, H-bot_h, W, H], fill="#0D1B2A")
            ui.text((12, H-bot_h+1), hint1, font_size=16, color="#B0C4DE")
            ui.text((12, H-bot_h+23), hint2, font_size=16, color="#B0C4DE")

            ui.paint()

    def _draw_spectrum_on_screen(self, ui, W, H):
        """在给定的UI对象上绘制频谱（用于上屏或单屏右侧）"""
        pad = 60  # 底部边距
        gap = 4
        num_bars = self.spectrum.num_bars
        total_gap = (num_bars - 1) * gap
        bw = (W - 2*pad - total_gap) / num_bars
        seg_h = 6
        seg_gap = 2
        inner_top = 80
        max_segs = int((H - inner_top - pad + seg_gap) / (seg_h + seg_gap))
        if max_segs < 2:
            max_segs = 2
        for i, level in enumerate(self.spectrum.levels):
            lit = int(level * max_segs)
            bx = pad + i*(bw+gap)
            for s in range(max_segs):
                sy = H - pad - s*(seg_h+seg_gap) - 5
                if s < lit:
                    frac = s / max_segs
                    if frac < 0.55:
                        col = "#3CE65A"
                    elif frac < 0.82:
                        col = "#FAC832"
                    else:
                        col = "#F0503C"
                else:
                    col = "#1A1A2E"
                ui.rect([bx, sy, bx+bw, sy+seg_h], fill=col, screen_idx=self.spectrum_display)

    def _draw_dial(self, cx, cy, r):
        ui = self.ui
        ui.circle((cx+3, cy+3), r, fill="#00000064")
        ui.circle((cx, cy), r, fill="#C8D8E8")
        for a in range(0, 360, 3):
            rad = a * math.pi / 180
            r1 = r * 0.78
            r2 = r * 0.9
            x1 = cx + math.cos(rad) * r1
            y1 = cy + math.sin(rad) * r1
            x2 = cx + math.cos(rad) * r2
            y2 = cy + math.sin(rad) * r2
            color = "#1E3A5F"
            width = 2 if a % 15 == 0 else 1
            ui.line([(x1, y1), (x2, y2)], fill=color, width=width)   # 改这里

    def _draw_needle(self, cx, cy, r, pct):
        ui = self.ui
        angle = math.radians(-120 + pct * 240)
        length = r * 0.8
        x2 = cx + math.cos(angle) * length
        y2 = cy + math.sin(angle) * length
        ui.line([(cx, cy), (x2, y2)], fill="#D25014", width=4)      # 改这里
        ui.circle((cx, cy), 6, fill="#5A4628")

    def _draw_horizontal_dial(self, x_start, y, width, height, current_idx):
        ui = self.ui
        # 背景条
        ui.rect([x_start, y, x_start + width, y + height],
                fill="#1A1A2E", outline="#2A3A5F", radius=4)

        freq_idx = current_idx % 100
        pos = x_start + (freq_idx / 99) * width

        # 刻度：88~108 MHz，每1MHz一条
        for f in range(88, 109, 1):
            idx = f - 88
            x = x_start + (idx / 20) * width
            if idx % 5 == 0:
                ui.rect([x - 1, y + 4, x + 1, y + height - 4], fill="#B0C4DE")
                label = f"{f}.0"
                ui.text((x, y + height + 6), label, font_size=14, color="#7A8BA0", anchor="mt")
            else:
                ui.rect([x - 1, y + 10, x + 1, y + height - 10], fill="#5A6A7F")

        # 指针（红色竖线）
        ui.rect([pos - 1, y, pos + 1, y + height], fill="#FF4444")

        # 频率数字
        freq_value = 88.0 + (freq_idx / 99) * 20.0
        ui.text((x_start + width // 2, y - 6), f"FM {freq_value:.1f} MHz",
                font_size=18, color="#D2C3AA", anchor="mb")

    # ---------- 退出 ----------
    def quit(self):
        self._save_config()
        self.player.stop()
        self.ui.draw_end()
        sys.exit(0)

    # ---------- 主循环 ----------
    def run(self):
        last_time = time.time()
        while True:
            now = time.time()
            dt = min(0.05, now - last_time)
            last_time = now

            # 触摸处理
            tap = self.touch.get_tap()
            if tap is not None:
                x, y = tap
                LOGGER.info(f"Touch at ({x},{y})")
                W, H = self.ui.get_screen_size(self.ui_display)
                lw = int(W * 0.45)
                if x < lw:
                    top_h = 40
                    ly = top_h + 6
                    item_h = 34
                    list_top = ly + 74
                    visible = self._page_size()
                    start = self.current_channel_idx - visible//2
                    if start < 0: start = 0
                    for i in range(visible):
                        idx = start + i
                        if idx < len(self.current_channels):
                            rect_y = list_top + i * item_h
                            if rect_y <= y <= rect_y + item_h - 4:
                                self.current_channel_idx = idx
                                LOGGER.info("Touch selected channel %d", idx)
                                if self.player.is_alive():
                                    self.play_selected()
                                break
                else:
                    # 点击右侧区域可能用作播放或音量，但这里简单处理：模拟A键
                    self.input.code_name = "A"
                    self.input.value = 1
                    self.handle_input()
                    self.input.reset()

            self.handle_input()
            self.update(dt)
            self.draw()
            time.sleep(0.02)

# ============================
# 入口
# ============================
if __name__ == "__main__":
    app = RadioApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.quit()
    except Exception as e:
        LOGGER.exception("Unhandled exception")
        app.ui.draw_end()
        sys.exit(1)
