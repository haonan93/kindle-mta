#!/mnt/us/python3/bin/python3
import datetime
import glob
import json
import os
import ssl
import struct
import subprocess
import sys
import threading
import time
import urllib.request

# Use pure-Python protobuf parser so no C extensions are required on Kindle ARM
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

BASE_DIR = "/mnt/us/subway-sign"
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "libs"))

import ft_font
ft_font.install()

from PIL import Image, ImageDraw, ImageFont
from google.transit import gtfs_realtime_pb2

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
FONT_PATH = os.path.join(BASE_DIR, "DejaVuSans-Bold.ttf")
KINDLE_ROTATION = int(os.getenv("KINDLE_ROTATION", "270"))

MTA_FEEDS = {
    "G": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g",
    "A": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",
    "C": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",
    "E": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",
    "B": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
    "D": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
    "F": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
    "M": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
    "J": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz",
    "Z": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz",
    "L": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l",
    "N": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "Q": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "R": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "W": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "1": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "2": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "3": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "4": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "5": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "6": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "7": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
}

_FONT_CACHE = {}
_FEED_MSG = gtfs_realtime_pb2.FeedMessage()
_SSL_CTX = ssl._create_unverified_context()


def get_font(size):
    font = _FONT_CACHE.get(size)
    if font is None:
        font = ImageFont.truetype(FONT_PATH, size)
        _FONT_CACHE[size] = font
    return font


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def get_colors(theme):
    if str(theme).lower() == "black":
        return 0, 255
    return 255, 0


def get_battery_percent():
    for path in glob.glob("/sys/class/power_supply/*/capacity"):
        try:
            with open(path, "r") as f:
                val = f.read().strip()
            if val.isdigit():
                return f"{val}%"
        except OSError:
            pass
    try:
        out = subprocess.check_output(["gasgauge-info", "-s"], text=True).strip()
        return out if "%" in out else f"{out}%"
    except Exception:
        return ""


def fetch_all_arrivals(row_specs):
    feeds_to_stops = {}
    for line_letter, stop_id in row_specs:
        url = MTA_FEEDS.get(line_letter.upper(), MTA_FEEDS["G"])
        feeds_to_stops.setdefault(url, set()).add(stop_id)

    now = time.time()
    arrivals_by_stop = {stop_id: set() for _, stop_id in row_specs}

    for feed_url, target_stops in feeds_to_stops.items():
        req = urllib.request.Request(feed_url, headers={"User-Agent": "kindle-native-mta/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as res:
            _FEED_MSG.Clear()
            _FEED_MSG.ParseFromString(res.read())

        for entity in _FEED_MSG.entity:
            if not entity.HasField("trip_update"):
                continue
            for stu in entity.trip_update.stop_time_update:
                if stu.stop_id in target_stops:
                    t = stu.arrival.time or stu.departure.time
                    if t and t >= now:
                        arrivals_by_stop[stu.stop_id].add(int((t - now) // 60))

    return {stop_id: sorted(mins)[:3] for stop_id, mins in arrivals_by_stop.items()}


def _blit_rotated(img, out_path, x_pos, y_pos, full_refresh=False):
    if KINDLE_ROTATION in (90, 180, 270):
        img = img.rotate(KINDLE_ROTATION, expand=True)
    img.save(out_path, format="PNG")
    if KINDLE_ROTATION in (180, 270):
        x_pos = max(0, 1236 - x_pos - img.width)
        y_pos = max(0, 1648 - y_pos - img.height)
    cmd = ["eips", "-f", "-g", out_path] if full_refresh else ["eips", "-g", out_path, "-x", str(x_pos), "-y", str(y_pos)]
    subprocess.run(cmd, check=False)


def draw_static_base(cfg):
    theme = cfg.get("theme", "white")
    bg, fg = get_colors(theme)
    img = Image.new("L", (1648, 1236), color=bg)
    draw = ImageDraw.Draw(img)
    f_bullet = get_font(305)
    f_dir = get_font(180)

    for cy, ty, row_key in [(340, 72, "row1"), (936, 670, "row2")]:
        letter = cfg[row_key]["line"]
        draw.ellipse([236 - 198, cy - 198, 236 + 198, cy + 198], fill=fg)
        tb = draw.textbbox((0, 0), letter, font=f_bullet)
        draw.text(
            (236 - (tb[2] - tb[0]) / 2 - tb[0], cy - (tb[3] - tb[1]) / 2 - tb[1]),
            letter,
            fill=bg,
            font=f_bullet,
        )
        draw.text((485, ty), cfg[row_key]["label"], fill=fg, font=f_dir)

    for x in range(40, 1608, 40):
        draw.ellipse([x - 8, 628 - 8, x + 8, 628 + 8], fill=fg)

    _blit_rotated(img, "/tmp/base.png", 0, 0, full_refresh=True)
    draw_back_button(theme=theme)


def draw_minutes_patch(minutes_list, out_path, x_pos, y_pos, theme="white"):
    bg, fg = get_colors(theme)
    img = Image.new("L", (1130, 300), color=bg)
    draw = ImageDraw.Draw(img)
    text = ",".join(str(m) for m in minutes_list) if minutes_list else "--"
    draw.text((0, 150), text, fill=fg, font=get_font(207), anchor="lm")
    _blit_rotated(img, out_path, x_pos, y_pos)


def draw_updated_patch(out_path, x_pos, y_pos, theme="white"):
    bg = 255 if theme == "white" else 0
    fg = 90 if theme == "white" else 180
    img = Image.new("L", (640, 64), color=bg)
    draw = ImageDraw.Draw(img)
    ts = datetime.datetime.now().strftime("%-I:%M %p")
    bat = get_battery_percent()
    label = f"Updated {ts}  •  {bat}" if bat else f"Updated {ts}"
    draw.text((10, 32), label, fill=fg, font=get_font(38), anchor="lm")
    _blit_rotated(img, out_path, x_pos, y_pos)


def draw_back_button(theme="white"):
    bg, fg = get_colors(theme)
    img = Image.new("L", (170, 56), color=bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, 167, 53], outline=fg, width=3)
    draw.text((85, 28), "< Back", fill=fg, font=get_font(26), anchor="mm")
    _blit_rotated(img, "/tmp/back_btn.png", 25, 25)


def _exit_to_kindle():
    subprocess.run(["lipc-set-prop", "com.lab126.powerd", "preventScreenSaver", "0"], check=False)
    subprocess.run(["initctl", "start", "pillow"], check=False)
    subprocess.run(["initctl", "stop", "framework"], check=False)
    time.sleep(1)
    subprocess.run(["initctl", "start", "framework"], check=False)
    os._exit(0)


def _watch_touch_exit(dev="/dev/input/event1"):
    time.sleep(3)
    print("Listening for touch on:", dev, flush=True)
    cur_x, cur_y = -1, -1
    try:
        with open(dev, "rb") as f:
            while True:
                data = f.read(16)
                if len(data) < 16:
                    break
                _, _, ev_type, ev_code, ev_val = struct.unpack("IIHHi", data)
                if ev_type == 3 and ev_code in (0, 53):
                    cur_x = ev_val
                elif ev_type == 3 and ev_code in (1, 54):
                    cur_y = ev_val
                elif (ev_type == 3 and ev_code == 57 and ev_val == -1) or (ev_type == 1 and ev_code == 330 and ev_val == 0):
                    in_tl = (0 <= cur_x <= 450 and 0 <= cur_y <= 450)
                    in_br = (cur_x >= 800 and cur_y >= 1200)
                    if in_tl or in_br:
                        print("Back button tapped! Restoring Kindle UI...", flush=True)
                        _exit_to_kindle()
    except Exception as e:
        print("Touch watcher error:", e, flush=True)


def main_loop():
    subprocess.run(["initctl", "stop", "framework"], check=False)
    subprocess.run(["initctl", "stop", "pillow"], check=False)
    subprocess.run(["lipc-set-prop", "com.lab126.powerd", "deferSuspend", "9999999"], check=False)
    subprocess.run(["eips", "-c"], check=False)
    subprocess.run(["eips", "-c"], check=False)
    subprocess.run(["lipc-set-prop", "com.lab126.powerd", "preventScreenSaver", "1"], check=False)
    subprocess.run(["lipc-set-prop", "com.lab126.powerd", "flIntensity", "0"], check=False)

    threading.Thread(target=_watch_touch_exit, daemon=True).start()
    last_mtime = None
    last_r1 = None
    last_r2 = None
    ticks = 0

    while True:
        try:
            cfg = load_config()
            theme = cfg.get("theme", "white")
            cur_mtime = os.path.getmtime(CONFIG_PATH)

            if cur_mtime != last_mtime or ticks >= 60:
                draw_static_base(cfg)
                last_mtime = cur_mtime
                last_r1 = None
                last_r2 = None
                ticks = 0

            row1_spec = (cfg["row1"]["line"], cfg["row1"]["stop_id"])
            row2_spec = (cfg["row2"]["line"], cfg["row2"]["stop_id"])
            arrivals = fetch_all_arrivals([row1_spec, row2_spec])

            r1 = arrivals[row1_spec[1]]
            if r1 != last_r1:
                draw_minutes_patch(r1, "/tmp/row1.png", 290, 53, theme=theme)
                last_r1 = r1

            r2 = arrivals[row2_spec[1]]
            if r2 != last_r2:
                draw_minutes_patch(r2, "/tmp/row2.png", 885, 53, theme=theme)
                last_r2 = r2

            draw_updated_patch("/tmp/updated.png", 1130, 50, theme=theme)
            ticks += 1
        except Exception as e:
            print("Update error:", e, flush=True)

        time.sleep(max(5.0, 60.0 - (time.time() % 60.0)))


if __name__ == "__main__":
    main_loop()
