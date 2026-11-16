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



def log_battery_stats(csv_path="/mnt/us/subway-sign/battery_log.csv"):
    cap, volt_mv, curr_ma = "", "", ""
    for base in glob.glob("/sys/class/power_supply/*"):
        c_file = os.path.join(base, "capacity")
        if os.path.exists(c_file):
            try:
                with open(c_file) as f:
                    cap = f.read().strip()
                v_file = os.path.join(base, "voltage_now")
                if os.path.exists(v_file):
                    with open(v_file) as f:
                        v = int(f.read().strip())
                        volt_mv = str(v // 1000 if v > 10000 else v)
                i_file = os.path.join(base, "current_now")
                if os.path.exists(i_file):
                    with open(i_file) as f:
                        i = int(f.read().strip())
                        curr_ma = str(i // 1000 if abs(i) > 10000 else i)
                break
            except Exception:
                pass
    if not cap or not volt_mv:
        try:
            cap = cap or subprocess.check_output(["gasgauge-info", "-s"], text=True).strip().rstrip("%")
            volt_mv = volt_mv or subprocess.check_output(["gasgauge-info", "-v"], text=True).strip().split()[0]
            curr_ma = curr_ma or subprocess.check_output(["gasgauge-info", "-c"], text=True).strip().split()[0]
        except Exception:
            pass
    write_hdr = not os.path.exists(csv_path)
    with open(csv_path, "a") as f:
        if write_hdr:
            f.write("timestamp,percent,voltage_mv,current_ma\n")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{ts},{cap},{volt_mv},{curr_ma}\n")


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



def _in_time_window(now_dt, rule):
    if now_dt.weekday() not in rule.get("days", [0, 1, 2, 3, 4, 5, 6]):
        return False
    sh, sm = map(int, rule["start"].split(":"))
    eh, em = map(int, rule["end"].split(":"))
    cur_m = now_dt.hour * 60 + now_dt.minute
    start_m = sh * 60 + sm
    end_m = eh * 60 + em
    if start_m <= end_m:
        return start_m <= cur_m < end_m
    return cur_m >= start_m or cur_m < end_m


def get_current_mode(cfg):
    sched = cfg.get("schedule", {})
    intervals = sched.get("intervals_sec", {"live": 60, "off_peak": 120, "battery_saver": 3600})
    now_dt = datetime.datetime.now()

    for rule in sched.get("battery_saver", [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "22:00", "end": "06:00"}]):
        if _in_time_window(now_dt, rule):
            return "battery_saver", "BATTERY SAVER", int(intervals.get("battery_saver", 3600))

    default_live = [
        {"days": [0, 1, 2, 3, 4], "start": "08:00", "end": "10:00"},
        {"days": [5, 6], "start": "08:00", "end": "18:00"},
    ]
    for rule in sched.get("live", default_live):
        if _in_time_window(now_dt, rule):
            return "live", "LIVE", int(intervals.get("live", 60))

    return "off_peak", "OFF PEAK", int(intervals.get("off_peak", 120))


def draw_mode_badge(mode_key, mode_label, theme="white"):
    bg, fg = get_colors(theme)
    img = Image.new("L", (340, 68), color=bg)
    draw = ImageDraw.Draw(img)
    if mode_key == "live":
        draw.rectangle([2, 2, 337, 65], fill=fg)
        draw.ellipse([20, 24, 40, 44], fill=bg)
        draw.text((190, 34), mode_label, fill=bg, font=get_font(32), anchor="mm")
    else:
        draw.rectangle([2, 2, 337, 65], outline=fg, width=4)
        draw.text((170, 34), mode_label, fill=fg, font=get_font(32), anchor="mm")
    # y_pos=1283 -> 1648 - 1283 - 340 = 25px from left edge; x_pos=25 -> 25px from top edge
    _blit_rotated(img, "/tmp/mode_badge.png", 25, 1283)


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
    last_bat = None
    last_mode = None
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
                last_bat = None
                last_mode = None
                ticks = 0

            row1_spec = (cfg["row1"]["line"], cfg["row1"]["stop_id"])
            row2_spec = (cfg["row2"]["line"], cfg["row2"]["stop_id"])
            arrivals = fetch_all_arrivals([row1_spec, row2_spec])

            r1 = arrivals[row1_spec[1]]
            r1_changed = (r1 != last_r1)
            if r1_changed:
                draw_minutes_patch(r1, "/tmp/row1.png", 290, 53, theme=theme)
                last_r1 = r1

            r2 = arrivals[row2_spec[1]]
            r2_changed = (r2 != last_r2)
            if r2_changed:
                draw_minutes_patch(r2, "/tmp/row2.png", 885, 53, theme=theme)
                last_r2 = r2

            bat = get_battery_percent()
            if r1_changed or r2_changed or bat != last_bat or (ticks % 5 == 0):
                draw_updated_patch("/tmp/updated.png", 1130, 50, theme=theme)
                last_bat = bat
            if ticks % 5 == 0:
                log_battery_stats()
            mode_key, mode_label, interval_sec = get_current_mode(cfg)
            if mode_key != last_mode:
                draw_mode_badge(mode_key, mode_label, theme=theme)
                last_mode = mode_key
            ticks += 1
        except Exception as e:
            print("Update error:", e, flush=True)

        time.sleep(max(5.0, interval_sec - (time.time() % interval_sec)))


if __name__ == "__main__":
    main_loop()
