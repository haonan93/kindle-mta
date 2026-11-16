import ctypes
import struct
from PIL import Image, ImageDraw

_ft = ctypes.CDLL("/usr/lib/libfreetype.so.6")

class FT_Vector(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class FT_Bitmap(ctypes.Structure):
    _fields_ = [
        ("rows", ctypes.c_uint),
        ("width", ctypes.c_uint),
        ("pitch", ctypes.c_int),
        ("buffer", ctypes.POINTER(ctypes.c_ubyte)),
        ("num_grays", ctypes.c_ushort),
        ("pixel_mode", ctypes.c_ubyte),
        ("palette_mode", ctypes.c_ubyte),
        ("palette", ctypes.c_void_p),
    ]

# 32-bit ARMv7 (kindlehf) FT_GlyphSlotRec offsets
class FT_GlyphSlotRec(ctypes.Structure):
    _fields_ = [
        ("library", ctypes.c_void_p),
        ("face", ctypes.c_void_p),
        ("next", ctypes.c_void_p),
        ("glyph_index", ctypes.c_uint),
        ("generic_data", ctypes.c_void_p),
        ("generic_finalizer", ctypes.c_void_p),
        ("metrics_width", ctypes.c_long),
        ("metrics_height", ctypes.c_long),
        ("metrics_horiBearingX", ctypes.c_long),
        ("metrics_horiBearingY", ctypes.c_long),
        ("metrics_horiAdvance", ctypes.c_long),
        ("metrics_vertBearingX", ctypes.c_long),
        ("metrics_vertBearingY", ctypes.c_long),
        ("metrics_vertAdvance", ctypes.c_long),
        ("linearHoriAdvance", ctypes.c_long),
        ("linearVertAdvance", ctypes.c_long),
        ("advance", FT_Vector),
        ("format", ctypes.c_uint),
        ("bitmap", FT_Bitmap),
        ("bitmap_left", ctypes.c_int),
        ("bitmap_top", ctypes.c_int),
    ]

class FT_Size_Metrics(ctypes.Structure):
    _fields_ = [
        ("x_ppem", ctypes.c_ushort),
        ("y_ppem", ctypes.c_ushort),
        ("x_scale", ctypes.c_long),
        ("y_scale", ctypes.c_long),
        ("ascender", ctypes.c_long),
        ("descender", ctypes.c_long),
        ("height", ctypes.c_long),
        ("max_advance", ctypes.c_long),
    ]

class FT_SizeRec(ctypes.Structure):
    _fields_ = [
        ("face", ctypes.c_void_p),
        ("generic_data", ctypes.c_void_p),
        ("generic_finalizer", ctypes.c_void_p),
        ("metrics", FT_Size_Metrics),
    ]

class FT_FaceRec(ctypes.Structure):
    _fields_ = [
        ("num_faces", ctypes.c_long),
        ("face_index", ctypes.c_long),
        ("face_flags", ctypes.c_long),
        ("style_flags", ctypes.c_long),
        ("num_glyphs", ctypes.c_long),
        ("family_name", ctypes.c_char_p),
        ("style_name", ctypes.c_char_p),
        ("num_fixed_sizes", ctypes.c_int),
        ("available_sizes", ctypes.c_void_p),
        ("num_charmaps", ctypes.c_int),
        ("charmaps", ctypes.c_void_p),
        ("generic_data", ctypes.c_void_p),
        ("generic_finalizer", ctypes.c_void_p),
        ("bbox", ctypes.c_long * 4),
        ("units_per_EM", ctypes.c_ushort),
        ("ascender", ctypes.c_short),
        ("descender", ctypes.c_short),
        ("height", ctypes.c_short),
        ("max_advance_width", ctypes.c_short),
        ("max_advance_height", ctypes.c_short),
        ("underline_position", ctypes.c_short),
        ("underline_thickness", ctypes.c_short),
        ("glyph", ctypes.POINTER(FT_GlyphSlotRec)),
        ("size", ctypes.POINTER(FT_SizeRec)),
    ]

_lib = ctypes.c_void_p()
if _ft.FT_Init_FreeType(ctypes.byref(_lib)) != 0:
    raise RuntimeError("FT_Init_FreeType failed")

class CtypesFont:
    def __init__(self, path, size):
        self.face = ctypes.POINTER(FT_FaceRec)()
        if _ft.FT_New_Face(_lib, path.encode("utf-8"), 0, ctypes.byref(self.face)) != 0:
            raise RuntimeError(f"Failed to load font: {path}")
        _ft.FT_Set_Pixel_Sizes(self.face, 0, int(size))
        self.size = int(size)

    def _measure(self, text):
        pen_x = 0
        min_x, min_y = 0, 0
        max_x, max_y = 0, 0
        asc = self.face.contents.size.contents.metrics.ascender >> 6
        desc = -(self.face.contents.size.contents.metrics.descender >> 6)
        for ch in str(text):
            if _ft.FT_Load_Char(self.face, ord(ch), 0) != 0:
                continue
            g = self.face.contents.glyph.contents
            adv = g.advance.x >> 6
            pen_x += adv
        return (0, 0, max(1, pen_x), max(1, asc + desc), asc)

    def getbbox(self, text):
        x0, y0, x1, y1, _ = self._measure(text)
        return (x0, y0, x1, y1)

def truetype(font=None, size=10, *args, **kwargs):
    return CtypesFont(font, size)

def _resolve_fill(img_mode, fill):
    if fill is None:
        return 0
    if isinstance(fill, (tuple, list)):
        if img_mode == "L":
            return int(sum(fill[:3]) / 3)
        return tuple(fill)
    if img_mode in ("RGB", "RGBA") and isinstance(fill, int):
        return (fill, fill, fill, 255) if img_mode == "RGBA" else (fill, fill, fill)
    return fill

class _PatchedDraw(ImageDraw.ImageDraw):
    def textbbox(self, xy, text, font=None, anchor=None, *args, **kwargs):
        if isinstance(font, CtypesFont):
            _, _, w, h, asc = font._measure(text)
            x, y = xy
            if anchor:
                if anchor[0] == "r":
                    x -= w
                elif anchor[0] == "m":
                    x -= w // 2
                if len(anchor) > 1:
                    if anchor[1] == "m":
                        y -= h // 2
                    elif anchor[1] == "b":
                        y -= h
                    elif anchor[1] == "s":
                        y -= asc
            return (x, y, x + w, y + h)
        return super().textbbox(xy, text, font=font, anchor=anchor, *args, **kwargs)

    def text(self, xy, text, fill=None, font=None, anchor=None, *args, **kwargs):
        if not isinstance(font, CtypesFont):
            return super().text(xy, text, fill=fill, font=font, anchor=anchor, *args, **kwargs)

        text = str(text)
        _, _, total_w, total_h, asc = font._measure(text)
        x, y = int(xy[0]), int(xy[1])

        if anchor:
            if anchor[0] == "r":
                x -= total_w
            elif anchor[0] == "m":
                x -= total_w // 2
            if len(anchor) > 1:
                if anchor[1] == "m":
                    y -= total_h // 2
                elif anchor[1] == "b":
                    y -= total_h
                elif anchor[1] == "s":
                    y -= asc

        baseline_y = y + asc
        pen_x = x
        color = _resolve_fill(self._image.mode, fill)

        # FT_LOAD_RENDER = 4
        for ch in text:
            if _ft.FT_Load_Char(font.face, ord(ch), 4) != 0:
                continue
            g = font.face.contents.glyph.contents
            bm = g.bitmap
            if bm.width > 0 and bm.rows > 0:
                pitch = abs(bm.pitch)
                size_bytes = pitch * bm.rows
                raw = ctypes.string_at(bm.buffer, size_bytes)
                glyph_mask = Image.frombytes("L", (bm.width, bm.rows), raw, "raw", "L", pitch, 1)
                gx = pen_x + g.bitmap_left
                gy = baseline_y - g.bitmap_top
                self._image.paste(color, (gx, gy), glyph_mask)
            pen_x += (g.advance.x >> 6)

def install():
    from PIL import ImageFont
    ImageFont.truetype = truetype
    ImageDraw.Draw = lambda im, mode=None: _PatchedDraw(im, mode)
