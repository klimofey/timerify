"""The brand icon is the picture of Timerify in the integrations list, on the page of
its devices and in the dialog that adds it. Home Assistant serves the files of the
integration's `brand` folder, so there is nothing for the user to set up; the files are
drawn by `scripts/brand/draw_icon.py`, and a test shows they are what the script draws.
"""

import io
import struct
from http import HTTPStatus
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from PIL import Image
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.timerify.const import DOMAIN
from scripts.brand.draw_icon import BRAND_DIR, ICONS, write_icons


def pixels(png: bytes) -> tuple[tuple[int, int], bytes]:
    """The size and the RGBA pixels of a picture. What a file shows is its pixels; the
    bytes of the file also depend on the zlib that wrote it."""
    with Image.open(io.BytesIO(png)) as picture:
        rgba = picture.convert("RGBA")
        return rgba.size, rgba.tobytes()


def chunk_types(png: bytes) -> set[str]:
    """The kinds of chunk a PNG file is made of: after the 8 bytes of signature, each
    has a 4-byte length, a 4-byte type, its data and a 4-byte checksum."""
    types = set()
    offset = 8
    while offset < len(png):
        (length,) = struct.unpack(">I", png[offset : offset + 4])
        types.add(png[offset + 4 : offset + 8].decode("ascii"))
        offset += 12 + length
    return types


@pytest.mark.parametrize(("name", "side"), ICONS.items())
def test_the_icons_are_square_transparent_and_trimmed(name: str, side: int) -> None:
    """A browser shows the file as it is, over a light or a dark page: a PNG of exactly
    the size Home Assistant's brands ask for, with nothing behind the drawing, and no
    empty border around it. The timer has a stem on top, so it is taller than wide: it
    fills the height and stands in the middle of the width."""
    with Image.open(BRAND_DIR / name) as icon:
        assert icon.format == "PNG"
        assert icon.size == (side, side)
        assert icon.mode == "RGBA"
        alpha = icon.getchannel("A")

    assert alpha.getpixel((0, 0)) == 0
    left, top, right, bottom = alpha.getbbox() or (0, 0, 0, 0)
    assert (top, bottom) == (0, side)
    assert abs(left - (side - right)) <= 1
    assert 0 <= left <= side // 10


@pytest.mark.parametrize("name", ICONS)
def test_the_icons_carry_nothing_but_the_picture(name: str) -> None:
    """A file that came out of an editor or an optimiser may hold a comment, a gamma or
    a colour profile that changes how the browser shows it, or a time stamp that makes
    the next drawing differ. The script writes the header, the pixels and the end."""
    assert chunk_types((BRAND_DIR / name).read_bytes()) == {"IHDR", "IDAT", "IEND"}


def test_the_icons_are_what_the_script_draws(tmp_path: Path) -> None:
    """The committed pictures are not edited by hand: the script draws them again to the
    last pixel, so a change of the design is a change of the script."""
    write_icons(tmp_path)

    assert {path.name for path in tmp_path.iterdir()} == set(ICONS)
    for name in ICONS:
        assert pixels((tmp_path / name).read_bytes()) == pixels(
            (BRAND_DIR / name).read_bytes()
        )


def test_the_script_writes_the_same_bytes_every_time(tmp_path: Path) -> None:
    """Drawing again changes nothing in the repository: the files carry no time stamp
    or anything else that differs from one run to the next."""
    write_icons(tmp_path / "first")
    write_icons(tmp_path / "second")

    for name in ICONS:
        assert (tmp_path / "first" / name).read_bytes() == (
            tmp_path / "second" / name
        ).read_bytes()


@pytest.mark.parametrize(
    ("asked_for", "shipped"),
    [
        ("icon.png", "icon.png"),
        ("icon@2x.png", "icon@2x.png"),
        # The frontend asks for the dark and the logo variants too, and Home Assistant
        # answers them with the icon: Timerify ships no more than the two files.
        ("dark_icon.png", "icon.png"),
        ("dark_icon@2x.png", "icon@2x.png"),
        ("logo.png", "icon.png"),
    ],
)
async def test_home_assistant_serves_the_icon(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    asked_for: str,
    shipped: str,
) -> None:
    """The integrations list of the logged-in user shows the icon of Timerify, not the
    placeholder of an integration with no brand: Home Assistant answers the address
    the frontend asks for with the file of the integration."""
    assert await async_setup_component(hass, "brands", {})
    client = await hass_client()

    response = await client.get(f"/api/brands/integration/{DOMAIN}/{asked_for}")

    assert response.status == HTTPStatus.OK
    assert response.content_type == "image/png"
    assert await response.read() == await hass.async_add_executor_job(
        (BRAND_DIR / shipped).read_bytes
    )
