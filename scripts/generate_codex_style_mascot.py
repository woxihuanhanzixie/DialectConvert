from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
REF_DIR = ROOT / "参考img"

SCALE = 6
W, H = 72, 80

OUTLINE = (43, 61, 36, 255)
OUTLINE_SOFT = (89, 111, 62, 255)
CREAM = (246, 229, 181, 255)
CREAM_DARK = (224, 200, 148, 255)
SCREEN = (246, 236, 197, 255)
BODY = (226, 223, 177, 255)
BODY_DARK = (178, 180, 130, 255)
GREEN = (137, 204, 58, 255)
GREEN_LIGHT = (177, 227, 96, 255)
GREEN_DARK = (82, 132, 39, 255)
BROWN = (121, 82, 43, 255)
EYE = (42, 55, 64, 255)
BLUSH = (238, 151, 151, 255)
SHADOW = (67, 67, 78, 255)
SHADOW_LIGHT = (96, 97, 112, 255)
WHITE = (255, 255, 235, 255)


def leaf(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, flip: bool = False) -> None:
    x0, y0, x1, y1 = box
    draw.ellipse(box, fill=GREEN, outline=GREEN_DARK, width=2)
    inset = 3
    draw.ellipse((x0 + inset, y0 + 2, x1 - inset, y1 - 3), fill=GREEN_LIGHT)
    if flip:
        draw.line((x1 - 4, (y0 + y1) // 2, x0 + 5, y0 + 4), fill=GREEN_DARK, width=1)
    else:
        draw.line((x0 + 4, (y0 + y1) // 2, x1 - 5, y0 + 4), fill=GREEN_DARK, width=1)


def draw_frame(eyes: str) -> Image.Image:
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # Ground shadow, like the Codex desktop floating pet.
    d.rounded_rectangle((16, 70, 58, 77), radius=3, fill=SHADOW, outline=OUTLINE, width=2)
    d.rectangle((19, 71, 55, 72), fill=SHADOW_LIGHT)

    # Legs behind the body.
    d.rounded_rectangle((27, 61, 33, 72), radius=2, fill=BODY_DARK, outline=OUTLINE, width=2)
    d.rounded_rectangle((43, 61, 49, 72), radius=2, fill=BODY_DARK, outline=OUTLINE, width=2)

    # Body.
    d.rounded_rectangle((24, 50, 52, 68), radius=7, fill=BODY, outline=OUTLINE, width=2)
    d.rounded_rectangle((27, 53, 49, 66), radius=5, fill=(237, 232, 183, 255))
    d.polygon((36, 56, 44, 60, 40, 66, 32, 62), fill=GREEN, outline=GREEN_DARK)
    d.line((35, 60, 41, 62), fill=GREEN_LIGHT, width=1)

    # Arms.
    d.rounded_rectangle((18, 53, 27, 61), radius=4, fill=BODY, outline=OUTLINE, width=2)
    d.rounded_rectangle((49, 53, 58, 61), radius=4, fill=BODY, outline=OUTLINE, width=2)

    # Stem and leaves.
    d.rectangle((35, 9, 39, 20), fill=BROWN)
    d.rectangle((35, 9, 36, 20), fill=(91, 60, 30, 255))
    d.line((36, 12, 27, 8), fill=BROWN, width=2)
    d.line((38, 12, 49, 8), fill=BROWN, width=2)
    leaf(d, (17, 0, 32, 13), flip=False)
    leaf(d, (44, 0, 59, 13), flip=True)

    # TV hood/head.
    d.rounded_rectangle((14, 18, 62, 50), radius=10, fill=OUTLINE_SOFT, outline=OUTLINE, width=2)
    d.rounded_rectangle((18, 22, 58, 46), radius=7, fill=SCREEN, outline=CREAM_DARK, width=2)
    d.rectangle((20, 23, 56, 25), fill=WHITE)

    if eyes == "blink":
        d.rectangle((27, 34, 32, 35), fill=EYE)
        d.rectangle((44, 34, 49, 35), fill=EYE)
    else:
        d.rectangle((28, 31, 32, 36), fill=EYE)
        d.rectangle((44, 31, 48, 36), fill=EYE)
        d.point((29, 32), fill=WHITE)
        d.point((45, 32), fill=WHITE)

    d.ellipse((22, 37, 30, 41), fill=BLUSH)
    d.ellipse((47, 37, 55, 41), fill=BLUSH)
    d.arc((34, 35, 42, 42), start=20, end=160, fill=(124, 91, 70, 255), width=1)

    # Subtle side pixels add the little desktop-pet silhouette.
    d.rectangle((12, 28, 15, 43), fill=OUTLINE)
    d.rectangle((61, 28, 64, 43), fill=OUTLINE)

    return im


def scale(im: Image.Image) -> Image.Image:
    bbox = im.getbbox()
    if not bbox:
        return im
    x0, y0, x1, y1 = bbox
    cropped = im.crop((max(0, x0 - 2), max(0, y0 - 2), min(W, x1 + 2), min(H, y1 + 2)))
    return cropped.resize((cropped.width * SCALE, cropped.height * SCALE), Image.Resampling.NEAREST)


def main() -> None:
    STATIC_DIR.mkdir(exist_ok=True)
    REF_DIR.mkdir(exist_ok=True)
    open_frame = scale(draw_frame("open"))
    blink_frame = scale(draw_frame("blink"))
    open_frame.save(STATIC_DIR / "mascot.png")
    blink_frame.save(STATIC_DIR / "mascot_blink.png")
    open_frame.save(REF_DIR / "codex_style_mascot_open.png")
    blink_frame.save(REF_DIR / "codex_style_mascot_blink.png")
    print(f"wrote {STATIC_DIR / 'mascot.png'} {open_frame.size}")


if __name__ == "__main__":
    main()
