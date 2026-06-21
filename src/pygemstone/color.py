"""Colour packing helpers for the Gemstone API.

Gemstone stores every colour as a single 32-bit integer using a
**little-endian, red-in-the-low-byte** layout::

    bits  0- 7  →  R   (red)
    bits  8-15  →  G   (green)
    bits 16-23  →  B   (blue)
    bits 24-31  →  W   (dedicated white LED channel on RGBW strips)

So ``0x00000000WWBBGGRR``. This is *not* the conventional ``0xRRGGBB`` /
ARGB ordering, which is an easy and costly mistake to make — pure red
``(255, 0, 0)`` is stored as the integer ``255`` (``0x000000FF``), which
naively read as ``0xRRGGBB`` decodes to blue.

Reference values straight from the cloud's own swatch data:

    255         → "Red"         (0x000000FF)
    65280       → "Green"       (0x0000FF00)
    16711680    → blue          (0x00FF0000)
    16777215    → "Cool White"  (0x00FFFFFF)
    4278190080  → "Warm White"  (0xFF000000 — white channel only, no RGB)

The :class:`~pygemstone.models.Pattern` / :class:`~pygemstone.models.SwatchColor`
models keep these as raw ints (so they can be replayed to the API
unchanged). Use the helpers here whenever you need to *interpret* or
*construct* a colour rather than echo one back verbatim.
"""

from __future__ import annotations

from typing import Any

__all__ = ["unpack_color", "pack_color", "color_to_hex"]


def unpack_color(value: Any) -> tuple[int, int, int, int]:
    """Split a packed Gemstone colour int into ``(r, g, b, w)`` byte values.

    ``w`` is the dedicated white-LED channel (top byte). Each component is
    an ``int`` in the range ``0``–``255``.

    >>> unpack_color(255)
    (255, 0, 0, 0)
    >>> unpack_color(65280)
    (0, 255, 0, 0)
    >>> unpack_color(4278190080)
    (0, 0, 0, 255)

    :raises GemstoneValueError: if ``value`` is not an integer.
    """
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        from .errors import GemstoneValueError

        raise GemstoneValueError(f"not a packed colour int: {value!r}") from exc
    return (n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF, (n >> 24) & 0xFF)


def pack_color(r: int, g: int, b: int, w: int = 0) -> int:
    """Pack ``(r, g, b, w)`` byte components into a Gemstone colour int.

    Inverse of :func:`unpack_color`. Each component is masked to 0–255.

    >>> pack_color(255, 0, 0)
    255
    >>> pack_color(0, 255, 0)
    65280
    >>> pack_color(0, 0, 0, 255)
    4278190080
    """
    return (
        (int(r) & 0xFF)
        | ((int(g) & 0xFF) << 8)
        | ((int(b) & 0xFF) << 16)
        | ((int(w) & 0xFF) << 24)
    )


def color_to_hex(value: Any) -> str:
    """Convert a packed Gemstone colour int to a CSS ``#rrggbb`` string.

    The white channel is dropped — only the RGB triplet is represented.
    Callers that care about the white channel (e.g. to show a warm-white
    swatch) should use :func:`unpack_color` directly.

    >>> color_to_hex(255)
    '#ff0000'
    >>> color_to_hex(16777215)
    '#ffffff'

    :raises GemstoneValueError: if ``value`` is not an integer.
    """
    r, g, b, _ = unpack_color(value)
    return "#%02x%02x%02x" % (r, g, b)
