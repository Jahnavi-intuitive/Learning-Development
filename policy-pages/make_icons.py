"""Generates the Teams app icons: color.png (192x192, solid) and
outline.png (32x32, transparent, white line-art) for the Learning &
Development certificate-verification test bot. Drawn at 4x and downsampled
for clean anti-aliasing.
"""
from PIL import Image, ImageDraw

ACCENT = (47, 111, 94, 255)  # #2f6f5e, matches the legal pages' accent
WHITE = (255, 255, 255, 255)

SCALE = 4


def make_color_icon(path, size=192):
    s = size * SCALE
    img = Image.new("RGBA", (s, s), ACCENT)
    draw = ImageDraw.Draw(img)

    # Checkmark inside a rounded shield, centered, generous padding.
    cx, cy = s / 2, s / 2
    r = s * 0.30
    # shield: rounded square rotated feel via rounded_rectangle
    pad = s * 0.20
    draw.rounded_rectangle(
        [pad, pad, s - pad, s - pad], radius=s * 0.16, outline=WHITE, width=int(s * 0.045)
    )

    # checkmark
    lw = int(s * 0.06)
    p1 = (cx - r * 0.55, cy + r * 0.05)
    p2 = (cx - r * 0.12, cy + r * 0.48)
    p3 = (cx + r * 0.62, cy - r * 0.42)
    draw.line([p1, p2, p3], fill=WHITE, width=lw, joint="curve")
    for p in (p1, p2, p3):
        draw.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2], fill=WHITE)

    img = img.resize((size, size), Image.LANCZOS)
    img.save(path)


def make_outline_icon(path, size=32):
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = s / 2, s / 2
    r = s * 0.42
    lw = int(s * 0.09)

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=WHITE, width=lw)

    ck = r * 0.62
    p1 = (cx - ck * 0.55, cy + ck * 0.05)
    p2 = (cx - ck * 0.10, cy + ck * 0.5)
    p3 = (cx + ck * 0.65, cy - ck * 0.45)
    draw.line([p1, p2, p3], fill=WHITE, width=lw, joint="curve")
    for p in (p1, p2, p3):
        draw.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2], fill=WHITE)

    img = img.resize((size, size), Image.LANCZOS)
    img.save(path)


if __name__ == "__main__":
    make_color_icon("color.png")
    make_outline_icon("outline.png")
    print("done")
