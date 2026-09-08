# Anbernic Dual-Screen Internet Radio

![Version](https://img.shields.io/badge/version-1.0.2-blue.svg)
![Platform](https://img.shields.io/b/platform-Anbernic%20Dual%20Screen-green.svg)
![License](https://img.shields.io/b/license-MIT-yellow.svg)

A dedicated internet radio player for Anbernic dual-screen handhelds (e.g., RGds, RGdsplus series). Utilizes the dual‑screen hardware to its full potential: the upper screen displays a dynamic spectrum, while the lower screen provides complete browsing, control, and status information, delivering an immersive listening experience.

## ✨ Features

- 🖥️ **Native Dual‑Screen Support** – Upper screen shows a vibrant spectrum (or standby logo), lower screen hosts the full interface, completely independent.
- 🎛️ **Two Tuning Modes** – Choose between **horizontal frequency bar** and **circular dial** for channel selection.
- 📡 **Rich Station Management** – Supports multiple `.txt` playlist files (name,URL) with quick category switching via L1/R1.
- 🔊 **Real‑time Volume Control** – Hardware volume keys adjust volume and automatically save the setting.
- 🌐 **Multi‑language UI** – Built‑in 10 languages (including Simplified/Traditional Chinese, English, Japanese, etc.), switch instantly with SELECT.
- 📶 **System Status Display** – Shows Wi‑Fi connectivity, battery level, and charging status in real time.
- 💾 **Resume Playback** – Automatically remembers the last played category and channel, restoring on next launch.
- ⚡ **Lightweight & Efficient** – Built with SDL2 and Pillow for graphics, mpv for audio decoding, low resource usage.

## 📸 Screenshots

<img width="682" height="512" alt="screenshot_upper_20260908_093436" src="https://github.com/user-attachments/assets/6773adee-25ce-4070-bc22-85e548bb1bf8" />
<img width="682" height="512" alt="screenshot_lower_20260908_093436" src="https://github.com/user-attachments/assets/ac8ab3be-9054-4fdc-a7c0-a19bfb9e5bf8" />

## 📦 Installation

### Hardware Requirements
- Anbernic dual‑screen device (RGds, RGdsplus, etc., with two independent displays).
- Wi‑Fi connection (required for streaming internet radio).

### Software Dependencies
- Python 3.7+
- mpv player (must be installed and in PATH)
- SDL2 library
- Python packages: `sdl2`, `Pillow`, `requests` (auto‑installed to the `deps` directory on first run).

### Installation Steps
1. **Download the package** – Copy all files to any directory on your device (e.g., `/mnt/sdcard/RadioApp`).
2. **Prepare station lists** – Place your `.txt` station files inside a `Radio` folder. Each line should be `StationName,URL` (comments start with `#`). The program scans the following paths:
   - `/roms/Radio`
   - `/mnt/mmc/Radio`
   - `/mnt/sdcard/Radio`
   - `./Radio` (application directory)
3. **Font file (optional)** – Place a Chinese‑capable font as `font/font.ttf`; otherwise, the system default is used (may display garbled Chinese).
4. **Run** – Execute `python3 radio.py`. The program will auto‑detect the number of displays and start with the upper screen for spectrum and the lower screen for UI.

> **Note**: On first launch, the program extracts `module.zip` to `deps` to install dependencies automatically. Ensure write permissions.

## 🎮 Usage

### Key Mapping
| Key          | Function                                                                                  |
| ------------ | ----------------------------------------------------------------------------------------- |
| **A**        | Play the currently selected station                                                       |
| **B**        | Stop playback / Wake up screen (when in screen‑off mode)                                  |
| **X**        | Cycle screen display modes: <br> (All on → Upper only → All off → Lower only)            |
| **Y**        | Refresh station list (rescan all `Radio` directories)                                     |
| **L1 / R1**  | Switch station category (previous / next)                                                 |
| **↑ / ↓**    | Switch channel (previous / next)                                                          |
| **← / →**    | Switch channel (page up / down, jumps one screenful)                                      |
| **VOL+ / VOL-** | Increase / decrease volume (step 10%)                                                   |
| **SELECT**   | Cycle interface language                                                                  |
| **START**    | Toggle tuning mode (horizontal frequency bar ↔ circular dial)                             |
| **MENUF**    | Exit the application                                                                      |

### Interface Layout
- **Upper Screen (Spectrum)**:
  - Dynamic bar spectrum with color changes based on signal intensity.
  - Bottom shows current station name and playback status.
  - When turned off, displays a black background with Anbernic logo.
- **Lower Screen (Control)**:
  - **Top status bar**: Version, Wi‑Fi status, battery level/charging, current time.
  - **Left list**: Current category name, category index, total channels, and a scrollable list of stations (current selection highlighted).
  - **Right panel**:
    - Status indicators (Power, Play, Wi‑Fi)
    - Current station name and URL
    - Tuning control (horizontal bar or circular dial showing frequency 88–108 MHz)
    - Volume progress bar
  - **Bottom hint bar**: Short descriptions of all key functions.

## ⚙️ Configuration

The program generates `radio.ini` in its running directory to save user preferences.

```ini
[General]
language = en_US           ; Current language code (see lang directory)
[Volume]
value = 80                 ; Volume value (0-100)
[Resume]
source_index = 1           ; Last played category index (1‑based)
channel_index = 5          ; Last played channel index (1‑based)
[Dial]
mode = 1                   ; Tuning mode: 1=horizontal bar, 2=circular dial
```

### Custom Languages
Place JSON files named with language codes (e.g., `zh_CN.json`) inside the `lang` folder, containing key‑value pairs. The program loads them automatically.

### Station List Format
Files with `.txt` extension, each line a station in the format `Name,URL` (comma or Tab separated). Empty lines and lines starting with `#` or `;` are ignored.

Example:
```
# My Favorites
China National Radio,http://example.com/radio1.mp3
Music FM,http://example.com/radio2.m3u8
```

## 🛠️ Development & Building

### Manual Dependency Installation
If automatic installation fails, install manually:
```bash
pip install sdl2 Pillow
```
Ensure mpv and SDL2 runtime libraries are installed on the system.

### Debugging
Logs are written to `radio_dualscreen.log` for troubleshooting.

### Extending
- Spectrum effects can be tuned in the `SpectrumGenerator` class.
- Touch handling is in `TouchHandler` – adapt to different touch devices as needed.

## 📄 License

This project is licensed under the [MIT License](LICENSE) – you are free to use, modify, and distribute it.

## 🤝 Contributing

Issues and Pull Requests are welcome to improve the dual‑screen experience or add new features.

---

**Enjoy your listening!** 🎵
