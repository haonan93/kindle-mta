# Re-Kindle NYC Subway Wall Sign (Kindle Paperwhite 5 / M2L3EK)

## Overview
A sideways (landscape `1648x1236`) Kindle Paperwhite 5 (`M2L3EK`) e-ink wall/window sign inspired by RideOnTime LED boards. Designed for across-the-room legibility with `235pt` arrival countdowns, `180pt` direction headers, `396px` diameter line bullets, a clear `40pt` top-right `Updated HH:MM` indicator, and switchable White (light) or Black (dark) themes.

## Key Architecture
- `server.py`: HTTP server (using `gtfs-realtime-bindings` and `Pillow`) that fetches live MTA GTFS-Realtime protobuf feeds, serves a mobile-friendly `/admin` UI with theme + rotation preview buttons, serves a `/kiosk` full-screen browser test page, and renders `1236x1648` rotated PNGs for Kindle `eips` (`/base.png`, `/row1.png`, `/row2.png`, `/updated.png`).
- `config.json`: Stores active `theme` (`"white"` or `"black"`), train line, direction header, and MTA Stop ID for Row 1 and Row 2. Defaulted to Bedford-Nostrand Avs (`G33N` Queens-bound and `G33S` Brooklyn-bound).
- `extensions/dashboard/run.sh`: Client loop for jailbroken Kindle (`M2L3EK`) when running `server.py` on a host PC/Pi. Checks `/version` every 60s; flashes `/base.png` only when config/theme changes, and performs flash-free partial `eips` updates for `/row1.png`, `/row2.png`, and `/updated.png` every minute.
- `kindle-native/native_sign.py`: Self-contained standalone Python script that runs directly on a jailbroken Kindle (`M2L3EK`) with Python 3 installed—supports `"theme": "white" | "black"` and partial `Updated HH:MM` refreshes.

## Development & Run Commands
- Install dependencies: `pip install -r requirements.txt`
- Start server: `python3 server.py` (or `KINDLE_ROTATION=270 python3 server.py`)
- Open Local Admin UI: `http://localhost:8080/admin`
- Preview rotated/themed sign: `http://localhost:8080/preview.png?rotate=90&theme=black`
