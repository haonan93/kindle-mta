# Re-Kindle NYC Subway Sign (Kindle Paperwhite 5 `M2L3EK` Edition)

Turn a jailbroken **Kindle Paperwhite 5 (`M2L3EK`, `1236×1648`)** into a sideways (landscape `1648×1236`) wall or window NYC subway countdown sign. Optimized for across-the-room readability with **minute-only partial e-ink updates** (`eips`), a clear top-right **`Updated HH:MM`** timestamp, and switchable **White / Black** background themes.

## Features
- **White & Black Background Themes:** Toggle between crisp e-ink **White** (lowest ghosting) and high-contrast **Black** (RideOnTime LED look) in `/admin` or via `?theme=white|black`.
- **Top-Right Last Updated Timestamp:** Easy-to-read `40pt` `Updated HH:MM` indicator in the top-right corner (`Updated 6:00 PM` / 12-hour format) that updates via a `460×64` partial patch every 60 seconds so you always know the feed is live.
- **Native Paperwhite 5 (`M2L3EK`) Resolution:** `1648×1236` landscape rendering with `235pt` unclipped countdown minutes, `180pt` direction headers, and `396px` subway line bullets.
- **Rotation Support (`0°`, `90°`, `180°`, `270°`):** Preview any rotation angle via `/preview.png?rotate=90` or toggle directly inside `/admin`, and flip the Kindle framebuffer orientation with `KINDLE_ROTATION=270`.
- **Partial E-Ink Refresh (`eips`):** Static elements (train bullets, direction labels, dotted divider) are drawn once. Every 60 seconds, only the countdown boxes and top-right timestamp are stamped onto the screen.

## Quick Start (Local Server)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 server.py
```

Open **`http://localhost:8080/admin`** in your browser to configure stops, toggle White/Black theme, and preview the sign.

## Mode 1: Host Server + Thin Kindle Client (`M2L3EK`)

1. Copy `extensions/dashboard/run.sh` to your Kindle (`/mnt/us/extensions/dashboard/run.sh`).
2. Edit `SERVER="http://YOUR_SERVER_IP:8080"` inside `run.sh` to match your computer or Raspberry Pi's local IP address.
3. Make executable and launch over SSH:
   ```sh
   chmod +x /mnt/us/extensions/dashboard/run.sh
   nohup /mnt/us/extensions/dashboard/run.sh >/tmp/sign.log 2>&1 &
   ```

## Mode 2: Standalone Native on Kindle (`M2L3EK`)

1. Install Python 3 on your jailbroken Kindle via MRPI (`/mnt/us/python3/bin/python3`).
2. Copy `kindle-native/native_sign.py`, `config.json`, `DejaVuSans-Bold.ttf`, and the pure-Python `google/` protobuf folder (into `libs/`) to `/mnt/us/subway-sign/`.
3. Launch directly on the Kindle:
   ```sh
   nohup /mnt/us/python3/bin/python3 /mnt/us/subway-sign/native_sign.py >/tmp/sign.log 2>&1 &
   ```
