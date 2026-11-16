# Rendering & Partial Refresh Guidelines (Kindle M2L3EK)

- Canvas is rendered in landscape `1648x1236` (8-bit grayscale `L` mode) and rotated `90` (or `270`) degrees (`1236x1648`) for the Kindle Paperwhite 5 (M2L3EK) portrait framebuffer.
- Theme (`"white"` or `"black"`) sets `bg = 255, fg = 0` for light mode or `bg = 0, fg = 255` for dark mode. All layers share the active theme so partial refreshes blend seamlessly.
- Static base (`/base.png`) draws the `396px` diameter train line bullets, `180pt` direction headers, and dotted divider line. It is only flashed via `eips -f -g` when `config.json` is updated (including theme changes).
- Dynamic minute patches (`/row1.png` and `/row2.png`) are `1130x300` (rotated to `300x1130`) with `235pt` vertically centered (`anchor="lm"`) countdown digits, stamped every 60 seconds via `eips -g` (`-x 290 -y 53` and `-x 885 -y 53`).
- Dynamic timestamp patch (`/updated.png`) is `460x64` (rotated to `64x460`) placed at landscape `(1148, 20)` (`-x 20 -y 40` on `M2L3EK` 90° CCW) showing `Updated HH:MM AM/PM` in `40pt` bold text, stamped every 60 seconds without flashing.
- `/preview.png` accepts `?rotate=0|90|180|270` and `?theme=white|black`.
- `/kiosk` serves a full-bleed HTML wrapper with auto-refresh for testing on Kindle Web Browser.
