# Kindle MTA Live Subway Sign (`kindle-mta`)

A lightweight, native Python 3.11 live NYC MTA subway arrival board built for a jailbroken **Kindle Paperwhite 5 (11th Gen, `M2L3EKX)** running firmware `5.19.x`. It renders directly to the e-ink framebuffer (`eips`) using a pure-Python `ctypes` FreeType wrapper-no browser, X11 server, or heavy image libraries required.

---

## Features

- **Real-Time GTFS-RT Arrivals:** Fetches and parses live MTA protobuf feeds (`nyct/gtfs-*`) once per refresh cycle, displaying the next three arriving trains in minutes (`4+14,26`).
- **E-Ink Optimized Rendering:**
  - Static base layout (line bullets, direction headers, divider) drawn once on startup or config change.
  - Partial framebuffer blits (`eips -g`) for arrival minutes and the `Updated HH:mm PM • XX%` status footer.
  - Automatic hourly full-screen refresh (`eips -f`) to clear e-ink ghosting.
  - Clock-aligned 60-second sleep cadence so timestamps never drift or skip a minute.
- **Zoero-Dependency Font Rendering (`ft_font.py`):** Binds directly to the Kindle's native `/usr/lib/libfreetype.so.6` via `ctypes` with in-memory font caching.
- **Touch Exit & Kindle UI Restoration:** Listens on `/dev/input/event1` for taps on the `<Back` button, re-enables the screensaver, and restarts `pillow` and `framework` to return cleanly to the Kindle Library.
- **180° / 270° Landscape Rotation:** Supports rotated mounting orientations via `KINDLE_ROTATION` with automatic touch and patch coordinate mirroring.
- **Custom Library Cover:** Includes a `400x600` G-train cover thumbnail (`thumbnail_subway_sign.png`) linked to `Subway Sign.sh` in `/var/local/cc.db`.

---

## Hardware & Kindle Prerequisites

- **Device:** Kindle Paperwhite 5 (`M2L3EK`), `1236x1648` portrait framebuffer, firmware `5.19.x`
- **Jailbreak & Tools:** Jailbroken with KUAL, USBNetwork (SSH over Wi-Fi/USB), and Python 3.11 installed at `/mnt/us/python3/bin/python3`
- **Vendored Python Libraries (`/mnt/us/subway-sign/libs`):** Pure-Python `protobuf` and `gtfs-realtime-bindings` (excluded from Git via `.gitignore`; `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` is set automatically)

---

## Repository Structure

- `deploy.sh` - Syntax-checks, pushes files via scp, and restarts the sign
- `kindle-deployed/native_sign.py` - Main GTFS-RT fetcher, e-ink renderer, and touch listener
m `kindle-deployed/ft_font.py` - Ctypes wrapper around `/usr/lib/libfreetype.so.6`
- `kindle-deployed/config.json` - Station, line, direction labels, and theme configuration
- `kindle-deployed/DejaVuSans-Bold.ttf` - Font used for bullets, headers, and arrival minutes
- `"kindle-deployed/Subway Sign.sh"` - Kindle Documents launcher script
- `"kindle-deployed/thumbnail_subway_sign.png"` - 400x600 Library grid cover image

---

## Configuration (`config.json`)

Edit `kindle-deployed/config.json` to customize the two displayed rows or switch between light and dark themes. `native_sign.py` watches `config.json` modification times and redraws the static base automatically when updated.

- `theme` - `white` (black ink on white background) or `black` (white ink on black background)
- `row1` / `row2` - Top and bottom arrival rows
- `line` - MTA route letter/number (`G`, `A`, `C`, `E`, `B`, `D`l `F`, `M`, `J`, `Z`, `L`, `N`, `Q`, `R`, `W`, `1`- `7`)
- `stop_id` - GTFS stop ID including direction suffix (`N` = Northbound/Queens-bound, `S` = Southbound/Brooklyn-bound; e.g., `G33N` / `G33S` for Bedford-Nostrand Avs)
- `label` - Destination text rendered beside the line bullet

---

## Deployment Workflow (`deploy.sh`)

From your WSL environment, run `./deploy.sh` to validate Python syntax, sync updated files to the Kindle over SSH, and restart the background process:

1. Runs `python3 -m py_compile` locally on `native_sign.py` and `ft_font.py` so broken code is never pushed.
2. Copies updated scripts and `config.json` to `/mnt/us/subway-sign/` and `Subway Sign.sh` to `/mnt/us/documents/`.
3. Restarts `native_sign.py` cleanly on the Kindle and tails `/tmp/sign.log` to verify startup.

### Attaching the Library Cover Thumbnail (One-Time Setup)

Copy `thumbnail_subway_sign.png` to `/mnt/us/system/thumbnails/thumbnail_subway_sign.png` and update `p_thumbnail` in `/var/local/cc.db` for the `Subway Sign.sh` entry, then run `initctl restart framework`.
