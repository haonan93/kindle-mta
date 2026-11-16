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
KINDLE_ROTATION = int(os.getenv("KINDLE_ROTATION", "90"))

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
    f_bullet = ImageFont.truetype(FONT_PATH, 268)
    f_dir = ImageFont.truetype(FONT_PATH, 180)

    for cy, ty, row_key in [(340, 72, "row1"), (936, 670, "row2")]:
        letter = cfg[row_key]["line"]
        draw.ellipse([236 - 198, cy - 198, 236 + 198, cy + 198], fill=fg)
        tb = draw.textbbox((0, 0), letter, font=f_bullet)
        draw.text((236 - (tb[2] - tb[0]) / 2, cy - (tb[3] - tb[1]) / 2 - 24), letter, fill=bg, font=f_bullet)
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
    f_times = ImageFont.truetype(FONT_PATH, 235)
    text = ",".join(str(m) for m in minutes_list) if minutes_list else "--"
    draw.text((0, 150), text, fill=fg, font=f_times, anchor="lm")

    if KINDLE_ROTATION in (90, 180, 270):
        img = img.rotate(KINDLE_ROTATION, expand=True)
    img.save(out_path, format="PNG")
    subprocess.run(["eips", "-g", out_path, "-x", str(x_pos), "-y", str(y_pos)])

def draw_updated_patch(out_path, x_pos, y_pos, theme="white"):
    bg, fg = get_colors(theme)
    img = Image.new("L", (460, 64), color=bg)
    draw = ImageDraw.Draw(img)
    f_meta = ImageFont.truetype(FONT_PATH, 40)
    now = datetime.datetime.now()
    hour = now.strftime("%I").lstrip("0") or "12"
    ts = f"Updated {hour}:{now.strftime('%M %p')}"
    draw.text((460, 32), ts, fill=fg, font=f_meta, anchor="rm")

    if KINDLE_ROTATION in (90, 180, 270):
        img = img.rotate(KINDLE_ROTATION, expand=True)
    img.save(out_path, format="PNG")
    subprocess.run(["eips", "-g", out_path, "-x", str(x_pos), "-y", str(y_pos)])

def main_loop():
    subprocess.run(["/etc/init.d/framework", "stop"])
    subprocess.run(["lipc-set-prop", "com.lab126.powerd", "preventScreenSaver", "1"])
    subprocess.run(["lipc-set-prop", "com.lab126.powerd", "flIntensity", "0"])

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

            draw_updated_patch("/tmp/updated.png", 20, 40, theme=theme)
        except Exception as e:
            print("Update error:", e)

        time.sleep(60)

if __name__ == "__main__":
    main_loop()
