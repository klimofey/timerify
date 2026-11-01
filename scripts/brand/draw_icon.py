"""Draws the brand icon of Timerify: a round timer face, a ring whose arc is filled for
three quarters of the way round, with a short stem on top and a power symbol in the
middle. Home Assistant shows it in the integrations list, on the page of a device and in
the dialog that adds the integration, once the integration's `brand` folder holds it.

    uv run python -m scripts.brand.draw_icon

The two files, `icon.png` and `icon@2x.png`, are the sizes the brands of Home Assistant
ask for; Home Assistant answers a request for a `logo` or a `dark_` variant with them.
The mark is drawn with one colour, which reads on a light page and on a dark one, over a
transparent background with no text, so that it is clear at 16 pixels as well as at 512.
It is taller than wide, because of the stem: it fills the height of the square and
stands in the middle of the width, with no empty border above or below.

The mark is one colour, so what is drawn is how much of each pixel it covers: a mask,
at four times the size, shrunk with a Lanczos filter for smooth edges, and used as the
opacity of a plain sheet of the colour. Pillow writes no time stamp into a PNG, so the
same drawing is the same bytes every time.
"""

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw

BRAND_DIR: Final = (
    Path(__file__).resolve().parents[2] / "custom_components" / "timerify" / "brand"
)
"""Where Home Assistant looks for the images of a custom integration."""
ICONS: Final[Mapping[str, int]] = {"icon.png": 256, "icon@2x.png": 512}
"""The files, by name, with the side of their square in pixels."""

ACCENT: Final = (13, 148, 136)
"""A teal that reads on white and on near-black, and is not Home Assistant's blue."""
OPAQUE: Final = 255
"""The opacity, out of 255, of the mark itself."""
TRACK_OPACITY: Final = 72
"""The opacity, out of 255, of the quarter of the ring that is not filled."""
SUPERSAMPLING: Final = 4
"""How many times larger than its file the mark is drawn."""

# The geometry, as fractions of the side of the square. The face touches the bottom and
# the stem touches the top, so the mark has no empty border above or below.
FACE_RADIUS: Final = 0.44
RING_WIDTH: Final = 0.11
STEM_HALF_WIDTH: Final = 0.09
STEM_HEIGHT: Final = 0.28
"""Down to below the inside of the ring, which is cut afterwards."""
POWER_RADIUS: Final = 0.18
POWER_WIDTH: Final = 0.09
POWER_GAP: Final = 44.0
"""Half the opening of the power symbol's circle at the top, in degrees."""

# Pillow measures an angle from three o'clock, clockwise.
TWELVE: Final = 270.0
NINE: Final = 180.0

type Point = tuple[float, float]


def _on_circle(centre: Point, radius: float, degrees: float) -> Point:
    """The point of a circle at an angle measured as Pillow does."""
    angle = math.radians(degrees)
    return (centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle))


def _dot(draw: ImageDraw.ImageDraw, centre: Point, radius: float, fill: int) -> None:
    """A filled circle: the round end of a stroke."""
    draw.ellipse(
        (
            centre[0] - radius,
            centre[1] - radius,
            centre[0] + radius,
            centre[1] + radius,
        ),
        fill=fill,
    )


def _arc(
    draw: ImageDraw.ImageDraw,
    centre: Point,
    radius: float,
    width: float,
    angles: tuple[float, float],
    fill: int,
) -> None:
    """A stroke along a circle, clockwise from the first angle to the second, with flat
    ends. The radius is that of the middle of the stroke."""
    outer = radius + width / 2
    draw.arc(
        (centre[0] - outer, centre[1] - outer, centre[0] + outer, centre[1] + outer),
        *angles,
        fill=fill,
        width=round(width),
    )


def draw_icon(side: int) -> Image.Image:
    """The icon as a square of `side` pixels, transparent but for the mark."""
    big = side * SUPERSAMPLING
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)

    face = (big / 2, big * (1 - FACE_RADIUS))
    ring = (FACE_RADIUS - RING_WIDTH / 2) * big
    width = RING_WIDTH * big
    # The filled arc starts at the stem, which hides the flat start of both strokes, and
    # ends in a round cap that covers the flat end of the quarter that is not filled.
    _arc(draw, face, ring, width, (NINE, TWELVE), TRACK_OPACITY)
    _arc(draw, face, ring, width, (TWELVE, NINE), OPAQUE)
    _dot(draw, _on_circle(face, ring, NINE), width / 2, OPAQUE)
    draw.rounded_rectangle(
        (
            big * (0.5 - STEM_HALF_WIDTH),
            0,
            big * (0.5 + STEM_HALF_WIDTH),
            big * STEM_HEIGHT,
        ),
        radius=big * STEM_HALF_WIDTH / 2,
        fill=OPAQUE,
        corners=(True, True, False, False),
    )
    # Cut the inside of the ring, so that the stem ends in the curve of the ring.
    inner = (FACE_RADIUS - RING_WIDTH) * big
    draw.ellipse(
        (face[0] - inner, face[1] - inner, face[0] + inner, face[1] + inner),
        fill=0,
    )

    power = POWER_RADIUS * big
    stroke = POWER_WIDTH * big
    opening = (TWELVE + POWER_GAP, TWELVE - POWER_GAP)
    _arc(draw, face, power, stroke, opening, OPAQUE)
    for end in (*(_on_circle(face, power, degrees) for degrees in opening), face):
        _dot(draw, end, stroke / 2, OPAQUE)
    top = (face[0], face[1] - power)
    draw.line((top, face), fill=OPAQUE, width=round(stroke))
    _dot(draw, top, stroke / 2, OPAQUE)

    icon = Image.new("RGBA", (side, side), ACCENT)
    icon.putalpha(mask.resize((side, side), Image.Resampling.LANCZOS))
    return icon


def write_icons(directory: Path = BRAND_DIR) -> None:
    """Draw every icon into `directory`, which is made if it is not there."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, side in ICONS.items():
        draw_icon(side).save(directory / name, optimize=True)


def main() -> None:
    """Draw the icons of the integration."""
    write_icons()


if __name__ == "__main__":
    main()
