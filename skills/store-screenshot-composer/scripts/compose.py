#!/usr/bin/env python3
"""Compose App Store / Google Play screenshots from raw captures.

Raw captures (from XCUITest, simctl, adb, ...) go in; store images with a background,
a headline, an optional device bezel and an optional zoomed callout come out. Everything
is driven by one JSON config, so re-capturing the app and re-running this regenerates
every locale and every device size without touching a design tool.

    python3 compose.py store_frames.json                   # every locale in the config
    python3 compose.py store_frames.json --locale ja       # one locale
    python3 compose.py store_frames.json --sheet           # also write an overview image
    python3 compose.py store_frames.json --placeholder     # lay out with dummy captures

Config reference: ../references/config.md
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import unicodedata

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, features
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python3 -m pip install pillow")

# Proportional kana (CSS `font-feature-settings: 'palt'`), the same setting touyou.dev's
# headings use. Needs Pillow built with libraqm; without it the text is just a little looser.
FONT_FEATURES = ["palt"] if features.check("raqm") else None


def measure(font, text):
    return font.getlength(text, features=FONT_FEATURES)

# Sizes App Store Connect accepts for the slots most apps fill (portrait). Landscape is the
# same pair swapped. Google Play only bounds the aspect ratio, so it has no entry here.
PRESETS = {
    "iphone-6.9": (1320, 2868),
    "iphone-6.5": (1284, 2778),
    "iphone-6.3": (1206, 2622),
    "iphone-5.5": (1242, 2208),
    "ipad-13": (2064, 2752),
    "ipad-12.9": (2048, 2732),
    "mac": (2880, 1800),
    "vision": (3840, 2160),
    "watch-ultra": (422, 514),
    "play-phone": (1080, 1920),
}

FONT_CANDIDATES = {
    "bold": [
        "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ],
    "regular": [
        "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ],
}

# Starting points matching the touyou.dev app pages and their OG images: a near-white or
# near-black ground, a heavy #1d1d1f headline, muted grey supporting text, soft shadows.
THEMES = {
    "light": {
        "background": {"type": "gradient", "colors": ["#FBFBFD", "#EDEDF2"], "angle": 165},
        "text_color": "#1D1D1F",
        "subtitle_color": "#6E6E73",
        "shadow": {"blur": 0.05, "opacity": 0.1, "offset": 0.025},
        # A white screen on a near-white ground needs a hairline, like the site's cards.
        "outline": "#00000014",
    },
    "dark": {
        "background": {"type": "gradient", "colors": ["#1A1A1F", "#0A0A0C"], "angle": 165},
        "text_color": "#F5F5F7",
        "subtitle_color": "#A1A1A6",
        "shadow": {"blur": 0.05, "opacity": 0.36, "offset": 0.025},
    },
}

DEFAULTS = {
    "background": {"type": "solid", "color": "#1C1C1E"},
    "align": "center",  # center | left
    "eyebrow": None,  # {"icon": "path.png", "name": "App", "color": "#6E6E73"}
    "text_color": "#FFFFFF",
    "subtitle_color": None,  # falls back to text_color at 75% opacity
    "caption": "top",  # top | bottom
    "caption_height": 0.22,  # fraction of the canvas height reserved for text
    "title_size": 0.075,  # fraction of the canvas width; shrinks to fit
    "subtitle_size": 0.038,
    "max_title_lines": 2,
    "device_width": 0.80,  # fraction of the canvas width the screen (bezel excluded) takes
    "device_offset": 0.0,  # extra vertical shift, fraction of canvas height (+ = down)
    "corner_radius": 0.11,  # fraction of the screen width; ~matches modern iPhones
    "bezel": None,
    "outline": None,  # hairline around the screen, e.g. "#00000014"  # {"width": 0.035, "color": "#0A0A0A", "edge": "#3A3A3C"}
    "shadow": {"blur": 0.03, "opacity": 0.2, "offset": 0.012},
    "tilt": 0.0,  # degrees, counter-clockwise
    "rotate_input": 0,  # 90 / 180 / 270: for landscape captures shown upright, etc.
}


# --- small helpers ---------------------------------------------------------------------


def color(value, alpha=255):
    if value is None:
        return None
    value = value.lstrip("#")
    if len(value) == 6:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)
    if len(value) == 8:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4, 6))
    raise ValueError(f"bad colour: #{value}")


def localized(value, locale):
    """A plain string, or {"ja": ..., "en": ..., "default": ...}."""
    if value is None or isinstance(value, str):
        return value
    return value.get(locale) or value.get(locale.split("-")[0]) or value.get("default")


def find_font(explicit, weight):
    for path in ([explicit] if explicit else []) + FONT_CANDIDATES[weight]:
        if path and pathlib.Path(path).expanduser().exists():
            return str(pathlib.Path(path).expanduser())
    sys.exit(
        f"no {weight} font found. Set fonts.{weight} in the config "
        "(any .ttf/.otf/.ttc that covers the languages you use)."
    )


def is_wide(ch):
    return unicodedata.east_asian_width(ch) in ("W", "F")


def tokens(text):
    """Break opportunities: between CJK characters, and at spaces for everything else."""
    out, word = [], ""
    for ch in text:
        if ch == " ":
            if word:
                out.append(word)
            out.append(" ")
            word = ""
        elif is_wide(ch):
            if word:
                out.append(word)
                word = ""
            out.append(ch)
        else:
            word += ch
    if word:
        out.append(word)
    return out


# Characters that must not start a line in Japanese (kinsoku).
NO_LINE_START = set("、。，．・：；？！ー」』）】〉》〕ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ々,.!?:;)]}")


def wrap(text, font, max_width):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for tok in tokens(paragraph):
            candidate = line + tok
            if line and measure(font, candidate) > max_width and tok != " ":
                if tok in NO_LINE_START and len(tok) == 1:
                    # Hang the punctuation on the current line rather than orphan it.
                    line = candidate
                    continue
                lines.append(line.rstrip())
                line = tok.lstrip()
            else:
                line = candidate
        lines.append(line.rstrip())
    return lines


PREFERRED_BREAKS = "、。，,!?！？・ "


def balanced_wrap(text, font, max_width):
    """Wrap without orphans: the line count of a greedy wrap, at the narrowest width.

    A greedy wrap of a 2-line headline tends to leave one character on the second line.
    For two lines, a break right after a comma or space wins when both halves fit.
    """
    lines = wrap(text, font, max_width)
    if "\n" in text or len(lines) < 2:
        return lines
    if len(lines) == 2:
        best = None
        for i, ch in enumerate(text[:-1]):
            if ch in PREFERRED_BREAKS:
                a, b = text[: i + 1].rstrip(), text[i + 1 :].strip()
                widest = max(measure(font, a), measure(font, b))
                if b and widest <= max_width and (best is None or widest < best[0]):
                    best = (widest, [a, b])
        if best:
            return best[1]
    lo, hi = max_width * 0.4, max_width
    for _ in range(14):
        mid = (lo + hi) / 2
        if len(wrap(text, font, mid)) <= len(lines):
            hi = mid
        else:
            lo = mid
    return wrap(text, font, hi)


def fit_text(text, font_path, start_px, max_width, max_lines, min_px):
    """Largest size (<= start_px) at which `text` wraps into at most `max_lines`."""
    if "\n" in text:
        # Explicit breaks are the author's call: shrink until each line fits, never re-wrap.
        max_lines = text.count("\n") + 1
    size = start_px
    while True:
        font = ImageFont.truetype(font_path, size)
        lines = balanced_wrap(text, font, max_width)
        widest = max((measure(font, line) for line in lines), default=0)
        if (len(lines) <= max_lines and widest <= max_width) or size <= min_px:
            return font, lines
        size = max(min_px, int(size * 0.94))


# --- backgrounds -----------------------------------------------------------------------


def linear_gradient(size, stops, angle):
    w, h = size
    # Render a 1-pixel-wide ramp, then rotate it into place: fast and banding-free enough.
    length = max(2, int(math.hypot(w, h)))
    ramp = Image.new("RGBA", (1, length))
    cols = [color(c) for c in stops]
    for i in range(length):
        t = i / (length - 1) * (len(cols) - 1)
        a, b = cols[int(t)], cols[min(int(t) + 1, len(cols) - 1)]
        f = t - int(t)
        ramp.putpixel((0, i), tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(4)))
    ramp = ramp.resize((length, length))
    # Same convention as CSS linear-gradient: 180 = top to bottom, 90 = left to right.
    # The unrotated ramp already runs top to bottom, i.e. CSS 180.
    ramp = ramp.rotate(180 - angle, resample=Image.BICUBIC, expand=False)
    # A square as wide as the canvas diagonal covers every corner at any angle.
    left, top = (length - w) // 2, (length - h) // 2
    return ramp.crop((left, top, left + w, top + h))


def cover(image, size):
    w, h = size
    scale = max(w / image.width, h / image.height)
    image = image.resize((math.ceil(image.width * scale), math.ceil(image.height * scale)), Image.LANCZOS)
    left, top = (image.width - w) // 2, (image.height - h) // 2
    return image.crop((left, top, left + w, top + h))


def render_background(spec, size, base_dir):
    kind = spec.get("type", "solid")
    if kind == "solid":
        bg = Image.new("RGBA", size, color(spec["color"]))
    elif kind == "gradient":
        bg = linear_gradient(size, spec["colors"], spec.get("angle", 180))
    elif kind == "image":
        bg = cover(Image.open(base_dir / spec["path"]).convert("RGBA"), size)
        if spec.get("dim"):
            bg = Image.alpha_composite(bg, Image.new("RGBA", size, (0, 0, 0, int(255 * spec["dim"]))))
    else:
        raise ValueError(f"unknown background type: {kind}")
    if spec.get("glow"):
        # A soft light blob behind the device: the cheapest way to stop a flat fill looking flat.
        g = spec["glow"]
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        cx, cy = g.get("x", 0.5) * size[0], g.get("y", 0.6) * size[1]
        r = g.get("radius", 0.45) * size[0]
        ImageDraw.Draw(layer).ellipse((cx - r, cy - r, cx + r, cy + r), fill=color(g["color"], int(255 * g.get("opacity", 0.5))))
        bg = Image.alpha_composite(bg, layer.filter(ImageFilter.GaussianBlur(r * 0.5)))
    return bg


# --- device ----------------------------------------------------------------------------


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def build_device(shot, opt, screen_w):
    """The screenshot with rounded corners and an optional bezel, as an RGBA image."""
    scale = screen_w / shot.width
    screen = shot.resize((round(shot.width * scale), round(shot.height * scale)), Image.LANCZOS)
    radius = round(screen.width * opt["corner_radius"])
    bezel = opt.get("bezel")
    if not bezel:
        device = Image.new("RGBA", screen.size, (0, 0, 0, 0))
        device.paste(screen, (0, 0), rounded_mask(screen.size, radius))
        if opt.get("outline"):
            ImageDraw.Draw(device).rounded_rectangle(
                (0, 0, device.width - 1, device.height - 1), radius=radius,
                outline=color(opt["outline"]), width=max(2, device.width // 300))
        return device
    b = round(screen.width * bezel.get("width", 0.035))
    size = (screen.width + 2 * b, screen.height + 2 * b)
    device = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(device)
    edge = bezel.get("edge")
    outer_r = radius + b
    if edge:
        d.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=outer_r, fill=color(edge))
        rim = max(2, b // 6)
        d.rounded_rectangle((rim, rim, size[0] - 1 - rim, size[1] - 1 - rim), radius=outer_r - rim, fill=color(bezel.get("color", "#0A0A0A")))
    else:
        d.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=outer_r, fill=color(bezel.get("color", "#0A0A0A")))
    device.paste(screen, (b, b), rounded_mask(screen.size, radius))
    return device


def drop_shadow(device, opt, canvas_w):
    s = opt.get("shadow")
    if not s:
        return device, (0, 0)
    blur = max(1, round(canvas_w * s.get("blur", 0.03)))
    pad = blur * 3
    out = Image.new("RGBA", (device.width + 2 * pad, device.height + 2 * pad), (0, 0, 0, 0))
    alpha = device.getchannel("A").point(lambda a: int(a * s.get("opacity", 0.2)))
    off = round(canvas_w * s.get("offset", 0.012))
    # Write the alpha directly: pasting an RGBA shadow with itself as the mask squares it.
    mask = Image.new("L", out.size, 0)
    mask.paste(alpha, (pad, pad + off))
    out.putalpha(mask)
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(device, (pad, pad))
    return out, (pad, pad)


def callout(shot, spec, canvas_w):
    """Crop a region of the raw capture and present it as a floating, enlarged card."""
    x, y, w, h = spec["box"]  # fractions of the raw capture
    crop = shot.crop((round(x * shot.width), round(y * shot.height), round((x + w) * shot.width), round((y + h) * shot.height)))
    width = round(canvas_w * spec.get("width", 0.86))
    crop = crop.resize((width, round(crop.height * width / crop.width)), Image.LANCZOS)
    radius = round(width * spec.get("corner_radius", 0.05))
    card = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    card.paste(crop, (0, 0), rounded_mask(crop.size, radius))
    if spec.get("border"):
        ImageDraw.Draw(card).rounded_rectangle(
            (0, 0, card.width - 1, card.height - 1), radius=radius, outline=color(spec["border"]), width=max(2, width // 160)
        )
    return card


# --- one image -------------------------------------------------------------------------


def compose(shot_img, opt, size, background, fonts, title, subtitle):
    W, H = size
    canvas = background.copy()

    if opt.get("rotate_input"):
        shot_img = shot_img.rotate(-opt["rotate_input"], expand=True)

    # Text block.
    cap_h = round(H * opt["caption_height"])
    margin = round(W * 0.08)
    text_w = W - 2 * margin
    blocks = []
    eyebrow = opt.get("eyebrow")
    if eyebrow:
        ef = ImageFont.truetype(fonts["bold"], round(W * opt.get("eyebrow_size", 0.042)))
        blocks.append(("eyebrow", ef, eyebrow))
    bold_block = len(blocks)
    if title:
        f, lines = fit_text(title, fonts["bold"], round(W * opt["title_size"]), text_w, opt["max_title_lines"], round(W * 0.04))
        blocks.append((f, lines, color(opt["text_color"])))
    if subtitle:
        f, lines = fit_text(subtitle, fonts["regular"], round(W * opt["subtitle_size"]), text_w, 3, round(W * 0.025))
        sub_col = color(opt["subtitle_color"]) if opt.get("subtitle_color") else color(opt["text_color"], 191)
        blocks.append((f, lines, sub_col))

    def row_height(block):
        if block[0] == "eyebrow":
            return round(block[1].size * 2.0)
        return len(block[1]) * round(block[0].size * 1.28)

    def block_height():
        total = 0
        for i, block in enumerate(blocks):
            total += row_height(block)
            if i:
                total += round(blocks[i][1 if block[0] == "eyebrow" else 0].size * 0.6)
        return total

    left = opt.get("align") == "left"

    def x_for(width):
        return margin if left else (W - width) / 2

    caption_top = opt["caption"] == "top"
    th = block_height()
    # Top captions start at a fixed line so the app name and headline sit at the same height
    # on every image; the set reads as one row when the store lays them side by side.
    ty = round(H * 0.045) if caption_top else H - cap_h + (cap_h - th) // 2 - round(H * 0.01)
    text_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_layer)
    for i, block in enumerate(blocks):
        if block[0] == "eyebrow":
            _, ef, eb = block
            icon_px = round(ef.size * 2.0)
            gap = round(ef.size * 0.55)
            icon = eb.get("_icon")
            row_w = (icon_px + gap if icon else 0) + measure(ef, eb.get("name", ""))
            x = x_for(row_w)
            if icon:
                icon = icon.resize((icon_px, icon_px), Image.LANCZOS)
                text_layer.paste(icon, (round(x), ty), rounded_mask(icon.size, round(icon_px * 0.225)))
                x += icon_px + gap
            tdraw.text((x, ty + icon_px / 2), eb.get("name", ""), font=ef, fill=color(eb.get("color", "#6E6E73")),
                       anchor="lm", features=FONT_FEATURES)
            ty += icon_px
            continue
        f, lines, col = block
        if i:
            ty += round(f.size * 0.6)
        # No real bold face on this machine (bold and regular resolved to one file):
        # thicken the headline with a same-colour stroke so previews read like the real thing.
        stroke = round(f.size * 0.03) if i == bold_block and fonts["bold"] == fonts["regular"] else 0
        for line in lines:
            tdraw.text((x_for(measure(f, line)), ty), line, font=f, fill=col, features=FONT_FEATURES,
                       stroke_width=stroke, stroke_fill=col)
            ty += round(f.size * 1.28)

    text_bottom = ty

    # Device.
    screen_w = round(W * opt["device_width"])
    device = build_device(shot_img, opt, screen_w)
    if opt.get("tilt"):
        device = device.rotate(opt["tilt"], resample=Image.BICUBIC, expand=True)
    device, (pad_x, pad_y) = drop_shadow(device, opt, W)
    dx = (W - device.width) // 2
    if caption_top:
        # A long headline pushes the device down rather than running into it.
        dy = max(cap_h + round(H * 0.01), text_bottom + round(H * 0.025)) - pad_y
    else:
        dy = H - cap_h - (device.height - 2 * pad_y) - round(H * 0.01) - pad_y
        dy = max(dy, round(H * 0.04) - pad_y)
    dy += round(H * opt["device_offset"])
    # paste, not alpha_composite: the device may hang off the canvas edge on purpose.
    canvas.paste(device, (dx, dy), device)

    if opt.get("callout"):
        spec = opt["callout"]
        card = callout(shot_img, spec, W)
        card, (cpx, cpy) = drop_shadow(card, {"shadow": {"blur": 0.02, "opacity": 0.25, "offset": 0.01}}, W)
        cx = round(W * spec.get("x", 0.5)) - card.width // 2
        cy = round(H * spec.get("y", 0.62)) - card.height // 2
        canvas.paste(card, (cx, cy), card)

    canvas.alpha_composite(text_layer)
    # ASC rejects images with an alpha channel.
    return canvas.convert("RGB")


# --- driver ----------------------------------------------------------------------------


def placeholder(size, label):
    img = Image.new("RGBA", size, (242, 242, 247, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, size[0], round(size[1] * 0.12)), fill=(255, 255, 255, 255))
    for i in range(7):
        y = round(size[1] * (0.16 + i * 0.1))
        d.rounded_rectangle((size[0] * 0.05, y, size[0] * 0.95, y + size[1] * 0.08), radius=size[0] * 0.03, fill=(255, 255, 255, 255))
    d.text((size[0] * 0.06, size[1] * 0.05), label, fill=(60, 60, 67, 255), font=ImageFont.load_default(size=round(size[0] * 0.05)))
    return img


def contact_sheet(paths, out):
    imgs = [Image.open(p) for p in paths]
    if not imgs:
        return
    h = 900
    thumbs = [im.resize((round(im.width * h / im.height), h), Image.LANCZOS) for im in imgs]
    gap = 40
    sheet = Image.new("RGB", (sum(t.width for t in thumbs) + gap * (len(thumbs) + 1), h + 2 * gap), (128, 128, 128))
    x = gap
    for t in thumbs:
        sheet.paste(t, (x, gap))
        x += t.width + gap
    sheet.save(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--locale", action="append", help="limit to these locales (repeatable)")
    ap.add_argument("--set", action="append", default=[], help="limit to these sets by name (repeatable)")
    ap.add_argument("--sheet", action="store_true", help="also write _overview.png per output dir")
    ap.add_argument("--placeholder", action="store_true", help="use dummy captures (layout check)")
    args = ap.parse_args()

    cfg_path = pathlib.Path(args.config).resolve()
    base = cfg_path.parent
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    fonts_cfg = cfg.get("fonts", {})
    locales = args.locale or cfg.get("locales", ["en"])
    sets = cfg["sets"]
    if args.set:
        sets = [s for s in sets if s["name"] in args.set]
    missing, written = [], 0

    for locale in locales:
        lf = fonts_cfg.get(locale, fonts_cfg)
        fonts = {"bold": find_font(lf.get("bold"), "bold"), "regular": find_font(lf.get("regular"), "regular")}
        for st in sets:
            theme = st.get("style", {}).get("theme") or cfg.get("style", {}).get("theme")
            style = {**DEFAULTS, **THEMES.get(theme, {}), **cfg.get("style", {}), **st.get("style", {})}
            size = tuple(st["size"]) if "size" in st else PRESETS[st["preset"]]
            out_dir = base / st["output"].format(locale=locale)
            out_dir.mkdir(parents=True, exist_ok=True)
            shots = st["shots"]

            # Panorama: render one wide background and hand each image its slice, so the
            # images line up into one continuous picture when scrolled in the store.
            panorama = style.get("panorama")
            if panorama:
                wide = render_background(style["background"], (size[0] * len(shots), size[1]), base)

            outputs = []
            for i, shot in enumerate(shots):
                opt = {**style, **shot.get("style", {})}
                if opt.get("eyebrow"):
                    eb = dict(opt["eyebrow"])
                    eb["name"] = localized(eb.get("name"), locale) or ""
                    icon_path = base / eb["icon"] if eb.get("icon") else None
                    if icon_path and icon_path.exists():
                        eb["_icon"] = Image.open(icon_path).convert("RGBA")
                    elif icon_path and args.placeholder:
                        pass  # a layout check should not need the real icon
                    elif icon_path:
                        missing.append(str(icon_path))
                    opt["eyebrow"] = eb
                src = base / st["input"].format(locale=locale) / shot["file"]
                if args.placeholder:
                    img = placeholder(size, shot["file"])
                elif not src.exists():
                    missing.append(str(src))
                    continue
                else:
                    img = Image.open(src).convert("RGBA")
                if panorama:
                    bg = wide.crop((size[0] * i, 0, size[0] * (i + 1), size[1]))
                else:
                    bg = render_background(opt["background"], size, base)
                out = compose(
                    img, opt, size, bg, fonts,
                    localized(shot.get("title"), locale), localized(shot.get("subtitle"), locale),
                )
                dest = out_dir / shot.get("output", shot["file"])
                out.save(dest, optimize=True)
                outputs.append(dest)
                written += 1
            if args.sheet and outputs:
                contact_sheet(outputs, out_dir / "_overview.png")
            print(f"{locale} / {st['name']}: {len(outputs)} image(s) -> {out_dir}")

    if missing:
        print("\nmissing captures (run the capture step first):", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        sys.exit(1)
    print(f"\n{written} image(s) written")


if __name__ == "__main__":
    main()
