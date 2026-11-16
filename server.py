#!/usr/bin/env python3
import datetime
import http.server
import io
import json
import os
import time
import urllib.parse
import urllib.request
from google.transit import gtfs_realtime_pb2
from PIL import Image, ImageDraw, ImageFont

PORT = int(os.getenv("PORT", "8080"))
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")
KINDLE_ROTATION = int(os.getenv("KINDLE_ROTATION", "90"))  # 90 or 270 for 1236x1648 portrait Kindle Paperwhite 5 (M2L3EK)

# Official MTA GTFS-RT Feed mapping by train line letter
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

DEFAULT_CONFIG = {
    "theme": "white",
    "row1": {"line": "G", "label": "Queens", "stop_id": "G33N"},
    "row2": {"line": "G", "label": "Brooklyn", "stop_id": "G33S"},
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)
    if "theme" not in cfg:
        cfg["theme"] = "white"
    return cfg

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

def get_colors(theme):
    if str(theme).lower() == "black":
        return 0, 255  # Black background (0), White foreground (255)
    return 255, 0      # White background (255), Black foreground (0)

def format_updated_timestamp():
    now = datetime.datetime.now()
    hour = now.strftime("%I").lstrip("0") or "12"
    return f"Updated {hour}:{now.strftime('%M %p')}"

def fetch_stop_arrivals(line_letter, stop_id):
    feed_url = MTA_FEEDS.get(line_letter.upper(), MTA_FEEDS["G"])
    feed = gtfs_realtime_pb2.FeedMessage()
    req = urllib.request.Request(feed_url, headers={"User-Agent": "re-kindle-mta/1.0"})
    with urllib.request.urlopen(req, timeout=8) as res:
        feed.ParseFromString(res.read())

    now = time.time()
    mins_list = []

    for entity in feed.entity:
        if entity.HasField("trip_update"):
            for stu in entity.trip_update.stop_time_update:
                if stu.stop_id == stop_id:
                    t = stu.arrival.time or stu.departure.time
                    if t and t >= now:
                        mins_list.append(int((t - now) // 60))

    return sorted(list(set(mins_list)))[:3]

def get_fonts():
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]
    font_path = next((p for p in font_candidates if os.path.exists(p)), None)
    if font_path:
        return {
            "bullet": ImageFont.truetype(font_path, 268),
            "dir": ImageFont.truetype(font_path, 180),
            "times": ImageFont.truetype(font_path, 235),
            "meta": ImageFont.truetype(font_path, 40),
        }
    default = ImageFont.load_default()
    return {"bullet": default, "dir": default, "times": default, "meta": default}

def draw_bullet(draw, center_x, center_y, radius, letter, font, fg, bg):
    bbox = [center_x - radius, center_y - radius, center_x + radius, center_y + radius]
    draw.ellipse(bbox, fill=fg)
    tb = draw.textbbox((0, 0), letter, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    draw.text((center_x - tw / 2, center_y - th / 2 - 24), letter, fill=bg, font=font)

def apply_rotation(img, rotate_deg):
    if rotate_deg in (90, 180, 270):
        return img.rotate(rotate_deg, expand=True)
    return img

def render_static_base(cfg, rotate_deg=KINDLE_ROTATION, theme_override=None):
    """Renders ONLY the static layout at native Paperwhite 5 (M2L3EK) landscape (1648x1236)."""
    theme = theme_override or cfg.get("theme", "white")
    bg, fg = get_colors(theme)

    img = Image.new("L", (1648, 1236), color=bg)
    draw = ImageDraw.Draw(img)
    fonts = get_fonts()

    # Row 1 Static (Bullet + Direction)
    draw_bullet(draw, 236, 340, 198, cfg["row1"]["line"], fonts["bullet"], fg=fg, bg=bg)
    draw.text((485, 72), cfg["row1"]["label"], fill=fg, font=fonts["dir"])

    # Dotted Divider Line
    for x in range(40, 1608, 40):
        draw.ellipse([x - 8, 628 - 8, x + 8, 628 + 8], fill=fg)

    # Row 2 Static (Bullet + Direction)
    draw_bullet(draw, 236, 936, 198, cfg["row2"]["line"], fonts["bullet"], fg=fg, bg=bg)
    draw.text((485, 670), cfg["row2"]["label"], fill=fg, font=fonts["dir"])

    img = apply_rotation(img, rotate_deg)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def render_minutes_patch(minutes_list, rotate_deg=KINDLE_ROTATION, theme="white"):
    """Renders ONLY the 1130x300 box containing the countdown minutes without clipping."""
    bg, fg = get_colors(theme)
    img = Image.new("L", (1130, 300), color=bg)
    draw = ImageDraw.Draw(img)
    fonts = get_fonts()

    text = ",".join(str(m) for m in minutes_list) if minutes_list else "--"
    draw.text((0, 150), text, fill=fg, font=fonts["times"], anchor="lm")

    img = apply_rotation(img, rotate_deg)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def render_updated_patch(rotate_deg=KINDLE_ROTATION, theme="white"):
    """Renders ONLY the 460x64 top-right box containing 'Updated HH:MM AM/PM' in 40pt bold."""
    bg, fg = get_colors(theme)
    img = Image.new("L", (460, 64), color=bg)
    draw = ImageDraw.Draw(img)
    fonts = get_fonts()

    draw.text((460, 32), format_updated_timestamp(), fill=fg, font=fonts["meta"], anchor="rm")

    img = apply_rotation(img, rotate_deg)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def render_full_preview(cfg, rotate_deg=0, theme_override=None):
    """Combines static base + live minutes + top-right timestamp, with optional rotation and theme override."""
    theme = theme_override or cfg.get("theme", "white")
    base_bytes = render_static_base(cfg, rotate_deg=0, theme_override=theme)
    img = Image.open(io.BytesIO(base_bytes))
    r1_mins = fetch_stop_arrivals(cfg["row1"]["line"], cfg["row1"]["stop_id"])
    r2_mins = fetch_stop_arrivals(cfg["row2"]["line"], cfg["row2"]["stop_id"])
    p1 = Image.open(io.BytesIO(render_minutes_patch(r1_mins, rotate_deg=0, theme=theme)))
    p2 = Image.open(io.BytesIO(render_minutes_patch(r2_mins, rotate_deg=0, theme=theme)))
    p_ts = Image.open(io.BytesIO(render_updated_patch(rotate_deg=0, theme=theme)))
    img.paste(p1, (485, 290))
    img.paste(p2, (485, 885))
    img.paste(p_ts, (1148, 20))

    img = apply_rotation(img, rotate_deg)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def render_kiosk_html(cfg, rotate_deg=90):
    """Full-screen auto-refreshing wrapper for Kindle Experimental Browser testing."""
    theme = cfg.get("theme", "white")
    bg_hex = "#000000" if theme == "black" else "#ffffff"
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Kindle Subway Sign Kiosk</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ width: 100%; height: 100%; background: {bg_hex}; overflow: hidden; display: flex; align-items: center; justify-content: center; }}
    img {{ max-width: 100vw; max-height: 100vh; object-fit: contain; }}
  </style>
  <script>
    setInterval(function() {{
      document.getElementById('sign').src = '/preview.png?rotate={rotate_deg}&t=' + Date.now();
    }}, 60000);
  </script>
</head>
<body>
  <img id="sign" src="/preview.png?rotate={rotate_deg}&t={int(time.time())}" alt="Subway Sign">
</body>
</html>"""

def render_admin_html(cfg, saved=False):
    banner = '<div class="alert">Saved! Kindle will redraw base layout on next cycle.</div>' if saved else ""
    cur_theme = cfg.get("theme", "white")
    white_sel = "selected" if cur_theme == "white" else ""
    black_sel = "selected" if cur_theme == "black" else ""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kindle Subway Sign Admin (M2L3EK)</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; max-width: 520px; margin: 20px auto; padding: 0 16px; background: #f4f4f6; color: #111; }}
    h2 {{ margin-bottom: 12px; }}
    .card {{ background: #fff; padding: 16px; border-radius: 10px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    .row-title {{ font-weight: 700; margin-bottom: 10px; font-size: 1.05rem; display: flex; justify-content: space-between; align-items: center; }}
    label {{ display: block; font-size: 0.85rem; font-weight: 600; margin: 8px 0 4px; color: #444; }}
    input, select {{ width: 100%; padding: 10px; font-size: 1rem; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; background: #fff; }}
    button {{ width: 100%; padding: 14px; background: #000; color: #fff; font-size: 1rem; font-weight: 700; border: none; border-radius: 8px; cursor: pointer; }}
    .presets {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
    .preset-btn {{ flex: 1; padding: 8px 10px; background: #e0e0e6; color: #111; font-size: 0.82rem; font-weight: 600; border-radius: 6px; border: none; cursor: pointer; }}
    .rot-controls {{ display: flex; gap: 6px; margin-bottom: 10px; }}
    .rot-btn {{ flex: 1; padding: 6px 8px; background: #eeeef2; color: #111; font-size: 0.8rem; font-weight: 600; border-radius: 6px; border: 1px solid #d0d0d8; cursor: pointer; }}
    .rot-btn.active {{ background: #111; color: #fff; border-color: #111; }}
    .alert {{ background: #d1fae5; color: #065f46; padding: 12px; border-radius: 8px; margin-bottom: 16px; font-weight: 600; }}
    .preview-wrap {{ text-align: center; }}
    img.preview {{ max-width: 100%; max-height: 460px; border: 2px solid #000; border-radius: 6px; }}
  </style>
  <script>
    let currentRot = 0;
    let currentTheme = "{cur_theme}";

    function applyPreset(l1, d1, s1, l2, d2, s2) {{
      document.getElementsByName('r1_line')[0].value = l1;
      document.getElementsByName('r1_label')[0].value = d1;
      document.getElementsByName('r1_stop')[0].value = s1;
      document.getElementsByName('r2_line')[0].value = l2;
      document.getElementsByName('r2_label')[0].value = d2;
      document.getElementsByName('r2_stop')[0].value = s2;
    }}
    function refreshPreview() {{
      document.getElementById('preview-img').src = '/preview.png?rotate=' + currentRot + '&theme=' + currentTheme + '&t=' + Date.now();
    }}
    function setPreviewRotation(deg, btn) {{
      currentRot = deg;
      document.querySelectorAll('.rot-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      refreshPreview();
    }}
    function onThemeChange(sel) {{
      currentTheme = sel.value;
      refreshPreview();
    }}
  </script>
</head>
<body>
  <h2>Kindle Subway Sign Admin</h2>
  {banner}
  <div class="presets">
    <button type="button" class="preset-btn" onclick="applyPreset('G','Queens','G33N','G','Brooklyn','G33S')">Bedford-Nostrand (G Both Ways)</button>
    <button type="button" class="preset-btn" onclick="applyPreset('G','Queens','G29N','L','Manhattan','L10N')">Metropolitan/Lorimer (G + L)</button>
    <button type="button" class="preset-btn" onclick="applyPreset('A','Manhattan','A44N','C','Manhattan','A44N')">Nostrand Av (A + C)</button>
  </div>

  <form method="POST" action="/admin">
    <div class="card">
      <div class="row-title">Display Appearance</div>
      <label>Background Theme</label>
      <select name="theme" onchange="onThemeChange(this)">
        <option value="white" {white_sel}>White Background (Black Text — Lowest E-Ink Ghosting)</option>
        <option value="black" {black_sel}>Black Background (White Text — LED Sign Look)</option>
      </select>
    </div>

    <div class="card">
      <div class="row-title">Top Row (Row 1)</div>
      <label>Train Line Letter</label>
      <input name="r1_line" value="{cfg['row1']['line']}" maxlength="2" required>
      <label>Direction Header</label>
      <input name="r1_label" value="{cfg['row1']['label']}" required>
      <label>MTA Stop ID (e.g. G33N)</label>
      <input name="r1_stop" value="{cfg['row1']['stop_id']}" required>
    </div>

    <div class="card">
      <div class="row-title">Bottom Row (Row 2)</div>
      <label>Train Line Letter</label>
      <input name="r2_line" value="{cfg['row2']['line']}" maxlength="2" required>
      <label>Direction Header</label>
      <input name="r2_label" value="{cfg['row2']['label']}" required>
      <label>MTA Stop ID (e.g. G33S)</label>
      <input name="r2_stop" value="{cfg['row2']['stop_id']}" required>
    </div>

    <button type="submit">Save & Update Sign</button>
  </form>

  <div class="card" style="margin-top: 16px;">
    <div class="row-title"><span>Live Sign Preview</span></div>
    <div class="rot-controls">
      <button type="button" class="rot-btn active" onclick="setPreviewRotation(0, this)">0° (Landscape)</button>
      <button type="button" class="rot-btn" onclick="setPreviewRotation(90, this)">90° (Kindle CCW)</button>
      <button type="button" class="rot-btn" onclick="setPreviewRotation(180, this)">180°</button>
      <button type="button" class="rot-btn" onclick="setPreviewRotation(270, this)">270° (Kindle CW)</button>
    </div>
    <div class="preview-wrap">
      <img id="preview-img" class="preview" src="/preview.png?rotate=0&theme={cur_theme}&t={int(time.time())}" alt="Live Kindle Preview">
    </div>
  </div>
</body>
</html>"""

class PartialDashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            cfg = load_config()
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path in ("/", "/admin"):
                saved = "saved=1" in parsed.query
                html = render_admin_html(cfg, saved=saved)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())
                return

            if path == "/kiosk":
                rot = int(qs.get("rotate", [str(KINDLE_ROTATION)])[0])
                html = render_kiosk_html(cfg, rotate_deg=rot)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())
                return

            if path == "/version":
                mtime = int(os.path.getmtime(CONFIG_PATH))
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(str(mtime).encode())
                return

            theme_override = qs.get("theme", [None])[0]
            active_theme = theme_override or cfg.get("theme", "white")

            if path == "/base.png":
                rot = int(qs.get("rotate", [str(KINDLE_ROTATION)])[0])
                png = render_static_base(cfg, rotate_deg=rot, theme_override=theme_override)
            elif path == "/row1.png":
                rot = int(qs.get("rotate", [str(KINDLE_ROTATION)])[0])
                arr = fetch_stop_arrivals(cfg["row1"]["line"], cfg["row1"]["stop_id"])
                png = render_minutes_patch(arr, rotate_deg=rot, theme=active_theme)
            elif path == "/row2.png":
                rot = int(qs.get("rotate", [str(KINDLE_ROTATION)])[0])
                arr = fetch_stop_arrivals(cfg["row2"]["line"], cfg["row2"]["stop_id"])
                png = render_minutes_patch(arr, rotate_deg=rot, theme=active_theme)
            elif path == "/updated.png":
                rot = int(qs.get("rotate", [str(KINDLE_ROTATION)])[0])
                png = render_updated_patch(rotate_deg=rot, theme=active_theme)
            elif path == "/preview.png":
                rot = int(qs.get("rotate", ["0"])[0])
                png = render_full_preview(cfg, rotate_deg=rot, theme_override=theme_override)
            else:
                self.send_response(404)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(png)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode())

    def do_POST(self):
        if self.path == "/admin":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            params = urllib.parse.parse_qs(body)

            theme = params.get("theme", ["white"])[0].strip().lower()
            if theme not in ("white", "black"):
                theme = "white"

            new_cfg = {
                "theme": theme,
                "row1": {
                    "line": params.get("r1_line", ["G"])[0].strip().upper(),
                    "label": params.get("r1_label", ["Queens"])[0].strip(),
                    "stop_id": params.get("r1_stop", ["G33N"])[0].strip().upper(),
                },
                "row2": {
                    "line": params.get("r2_line", ["G"])[0].strip().upper(),
                    "label": params.get("r2_label", ["Brooklyn"])[0].strip(),
                    "stop_id": params.get("r2_stop", ["G33S"])[0].strip().upper(),
                },
            }
            save_config(new_cfg)
            self.send_response(303)
            self.send_header("Location", "/admin?saved=1")
            self.end_headers()

if __name__ == "__main__":
    print(f"Subway Sign Server & Admin UI (M2L3EK 1648x1236) running at http://0.0.0.0:{PORT}/admin")
    http.server.HTTPServer(("0.0.0.0", PORT), PartialDashboardHandler).serve_forever()
