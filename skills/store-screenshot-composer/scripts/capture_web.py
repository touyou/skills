#!/usr/bin/env python3
"""Shoot a web page laid out as one wide strip of store images, then cut it into images.

The page draws every image side by side at CSS size FRAME (for example 440x956), so
anything placed across an edge continues into the next image. Chrome renders it at
--scale (3 for 1320x2868, the iPhone 6.9" slot), and each slice is written as an RGB PNG,
because App Store Connect rejects images with an alpha channel.

    python3 capture_web.py "http://localhost:3000/store/intento?lang=ja" \
        --frame 440x956 --count 6 --scale 3 --out StoreImages/iphone/ja

Needs Google Chrome or Chromium (set CHROME to its path if it is not found) and Pillow.
"""

from __future__ import annotations

import argparse
import glob
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python3 -m pip install pillow")

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    *sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"), reverse=True),
]


def find_chrome():
    for candidate in ([os.environ["CHROME"]] if os.environ.get("CHROME") else []) + CHROME_CANDIDATES:
        path = candidate if os.path.isabs(candidate) else shutil.which(candidate)
        if path and os.path.exists(path):
            return path
    sys.exit("Chrome / Chromium not found. Set CHROME to its executable.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--frame", required=True, help="one image's CSS size, WIDTHxHEIGHT")
    ap.add_argument("--count", type=int, required=True, help="how many images the strip holds")
    ap.add_argument("--scale", type=float, default=3, help="device pixel ratio (default 3)")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--names", help="comma-separated file names (default 01.png, 02.png, ...)")
    ap.add_argument("--wait", type=int, default=8000, help="ms of page time to let fonts and images load")
    args = ap.parse_args()

    fw, fh = (int(v) for v in args.frame.lower().split("x"))
    names = args.names.split(",") if args.names else [f"{i + 1:02d}.png" for i in range(args.count)]
    if len(names) != args.count:
        sys.exit(f"--names has {len(names)} names for {args.count} images")
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        shot = pathlib.Path(tmp) / "strip.png"
        cmd = [
            find_chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--force-color-profile=srgb", f"--force-device-scale-factor={args.scale}",
            # Headless Chrome counts its (invisible) window frame in --window-size, so ask for a
            # taller window and keep only the top rows; the strip sits at the page's top-left.
            f"--window-size={fw * args.count},{fh + 400}", f"--virtual-time-budget={args.wait}",
            f"--user-data-dir={tmp}/profile", f"--screenshot={shot}", args.url,
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")  # Chrome refuses to start sandboxed as root (containers)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if not shot.exists():
            sys.exit(f"Chrome did not write a screenshot:\n{result.stderr[-2000:]}")
        strip = Image.open(shot).convert("RGB")

    w, h = round(fw * args.scale), round(fh * args.scale)
    # A fractional --scale rounds the whole strip once, not per frame, so frame i starts at
    # round(i * fw * scale) and every frame is cut at exactly w px.
    starts = [round(i * fw * args.scale) for i in range(args.count)]
    if abs(strip.width - round(fw * args.count * args.scale)) > 1 or strip.height < h or starts[-1] + w > strip.width:
        sys.exit(f"got a {strip.size[0]}x{strip.size[1]} shot, expected {round(fw * args.count * args.scale)}x{h} or taller")
    for x, name in zip(starts, names):
        strip.crop((x, 0, x + w, h)).save(out / name, optimize=True)
    strip = strip.crop((0, 0, starts[-1] + w, h))
    strip.resize((round(strip.width * 900 / h), 900)).save(out / "_overview.png")
    print(f"{args.count} image(s) of {w}x{h} -> {out}")


if __name__ == "__main__":
    main()
