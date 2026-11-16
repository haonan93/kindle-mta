import os, time, subprocess, threading, struct, glob
import threading, struct, glob
import glob as _glob

def get_battery_percent():
    for path in _glob.glob("/sys/class/power_supply/*/capacity"):
        try:
            val = open(path).read().strip()
            if val.isdigit():
                return f"{val}%"
        except Exception:
            pass
    try:
        out = subprocess.check_output(["gasgauge-info", "-s"], text=True).strip()
        return out if "%" in out else f"{out}%"
    except Exception:
        return ""

import sys, ssl
ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, "/mnt/us/subway-sign")
import ft_font
ft_font.install()
from PIL import ImageFont
#!/mnt/us/python3/bin/python3
import os
import sys
import json
import time
import datetime
import subprocess
import urllib.request

# Use pure-Python protobuf parser so no C extensions are required on Kindle ARM
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
sys.path.insert(0, "/mnt/us/subway-sign/libs")

from google.transit import gtfs_realtime_pb2
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = "/mnt/us/subway-sign"
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

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def get_colors(theme):
    if str(theme).lower() == "black":
        return 0, 255  # bg=black, fg=white
    return 255, 0      # bg=white, fg=black

def fetch_arrivals(line_letter, stop_id):
    feed_url = MTA_FEEDS.get(line_letter.upper(), MTA_FEEDS["G"])
    feed = gtfs_realtime_pb2.FeedMessage()
    req = urllib.request.Request(feed_url, headers={"User-Agent": "kindle-native-mta/1.0"})
    with urllib.request.urlopen(req, timeout=10) as res:
        feed.ParseFromString(res.read())

    now = time.time()
    mins = []
    for entity in feed.entity:
        if entity.HasField("trip_update"):
            for stu in entity.trip_update.stop_time_update:
                if stu.stop_id == stop_id:
                    t = stu.arrival.time or stu.departure.time
                    if t and t >= now:
                        mins.append(int((t - now) // 60))
    return sorted(list(set(mins)))[:3]

def draw_static_base(cfg):
    bg, fg = get_colors(cfg.get("theme", "white"))
    img = Image.new("L", (1648, 1236), color=bg)
    draw = ImageDraw.Draw(img)
    f_bullet = ImageFont.truetype(FONT_PATH, 305)
    f_dir = ImageFont.truetype(FONT_PATH, 180)

    for cy, ty, row_key in [(340, 72, "row1"), (936, 670, "row2")]:
        letter = cfg[row_key]["line"]
        draw.ellipse([236 - 198, cy - 198, 236 + 198, cy + 198], fill=fg)
        tb = draw.textbbox((0, 0), letter, font=f_bullet)
        draw.text((236 - (tb[2] - tb[0]) / 2 - tb[0], cy - (tb[3] - tb[1]) / 2 - tb[1]), letter, fill=bg, font=f_bullet)
        draw.text((485, ty), cfg[row_key]["label"], fill=fg, font=f_dir)

    for x in range(40, 1608, 40):
        draw.ellipse([x - 8, 628 - 8, x + 8, 628 + 8], fill=fg)

    if KINDLE_ROTATION in (90, 180, 270):
        img = img.rotate(KINDLE_ROTATION, expand=True)
    img.save("/tmp/base.png", format="PNG")
    subprocess.run(["eips", "-f", "-g", "/tmp/base.png"])

def draw_minutes_patch(minutes_list, out_path, x_pos, y_pos, theme="white"):
    bg, fg = get_colors(theme)
    img = Image.new("L", (1130, 300), color=bg)
    draw = ImageDraw.Draw(img)
    f_times = ImageFont.truetype(FONT_PATH, 207)
    text = ",".join(str(m) for m in minutes_list) if minutes_list else "--"
    draw.text((0, 150), text, fill=fg, font=f_times, anchor="lm")

    if KINDLE_ROTATION in (90, 180, 270):
        img = img.rotate(KINDLE_ROTATION, expand=True)
    img.convert("L").save(out_path, format="PNG")
    if KINDLE_ROTATION == 270:
        x_pos = max(0, 1236 - x_pos - img.width)
        y_pos = max(0, 1648 - y_pos - img.height)
    subprocess.run(["eips", "-g", out_path, "-x", str(x_pos), "-y", str(y_pos)])

def draw_updated_patch(out_path, x_pos, y_pos, theme="white"):
    bg = 255 if theme == "white" else 0
    fg = 90 if theme == "white" else 180
    img = Image.new("L", (640, 64), bg)
    d = ImageDraw.Draw(img)
    font_path = "/mnt/us/subway-sign/DejaVuSans.ttf"
    if not os.path.exists(font_path):
        font_path = "/mnt/us/subway-sign/DejaVuSans-Bold.ttf"
    f_upd = ImageFont.truetype(font_path, 38)
    ts = datetime.datetime.now().strftime("%-I:%M %p")
    bat = get_battery_percent()
    label = f"Updated {ts}  •  {bat}" if bat else f"Updated {ts}"
    d.text((10, 32), label, fill=fg, font=f_upd, anchor="lm")
    if KINDLE_ROTATION in (90, 180, 270):
        img = img.rotate(KINDLE_ROTATION, expand=True)
    img.save(out_path, format="PNG")
    if KINDLE_ROTATION in (180, 270):
        x_pos = max(0, 1236 - x_pos - img.width)
        y_pos = max(0, 1648 - y_pos - img.height)
    subprocess.run(["eips", "-g", out_path, "-x", str(x_pos), "-y", str(y_pos)], check=False)

def _draw_back_button(theme="white"):
    fg = 0 if theme == "white" else 255
    bg = 255 if theme == "white" else 0
    img = Image.new("L", (170, 56), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, 167, 53], outline=fg, width=3)
    f_btn = ImageFont.truetype("/mnt/us/subway-sign/DejaVuSans-Bold.ttf", 26)
    d.text((85, 28), "< Back", fill=fg, font=f_btn, anchor="mm")
    if KINDLE_ROTATION in (90, 180, 270):
        img = img.rotate(KINDLE_ROTATION, expand=True)
    img.save("/tmp/back_btn.png", format="PNG")
    bx, by = (25, 25) if KINDLE_ROTATION in (90, 0) else (1236 - img.width - 25, 1648 - img.height - 25)
    subprocess.run(["eips", "-g", "/tmp/back_btn.png", "-x", str(bx), "-y", str(by)], check=False)

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
                    print(f"Tap detected at x={cur_x}, y={cur_y}", flush=True)
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
    subprocess.run(["lipc-set-prop", "com.lab126.powerd", "preventScreenSaver", "1"])
    subprocess.run(["lipc-set-prop", "com.lab126.powerd", "flIntensity", "0"])

    threading.Thread(target=_watch_touch_exit, daemon=True).start()
    last_mtime = None
    while True:
        try:
            cfg = load_config()
            theme = cfg.get("theme", "white")
            cur_mtime = os.path.getmtime(CONFIG_PATH)

            if cur_mtime != last_mtime:
                draw_static_base(cfg)
                last_mtime = cur_mtime

            r1 = fetch_arrivals(cfg["row1"]["line"], cfg["row1"]["stop_id"])
            draw_minutes_patch(r1, "/tmp/row1.png", 290, 53, theme=theme)

            r2 = fetch_arrivals(cfg["row2"]["line"], cfg["row2"]["stop_id"])
            draw_minutes_patch(r2, "/tmp/row2.png", 885, 53, theme=theme)

            draw_updated_patch("/tmp/updated.png", 1130, 50, theme=theme)
            _draw_back_button(theme=theme)
        except Exception as e:
            print("Update error:", e)

        time.sleep(60)

if __name__ == "__main__":
    main_loop()
