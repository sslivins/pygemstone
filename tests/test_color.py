"""Tests for the colour packing helpers.

Ground-truth values are the named swatch colours the Gemstone cloud
itself returns (see test_models.py fixtures): 255 == "Red", etc.
"""

from __future__ import annotations

import pytest

from pygemstone import color_to_hex, pack_color, unpack_color
from pygemstone.errors import GemstoneValueError


@pytest.mark.parametrize(
    "packed,rgbw",
    [
        (255, (255, 0, 0, 0)),          # "Red"
        (65280, (0, 255, 0, 0)),        # "Green"
        (16711680, (0, 0, 255, 0)),     # blue
        (16777215, (255, 255, 255, 0)),  # "Cool White"
        (4278190080, (0, 0, 0, 255)),   # "Warm White" — white channel only
        (4294967295, (255, 255, 255, 255)),
    ],
)
def test_unpack_color(packed, rgbw):
    assert unpack_color(packed) == rgbw


@pytest.mark.parametrize(
    "rgbw,packed",
    [
        ((255, 0, 0, 0), 255),
        ((0, 255, 0, 0), 65280),
        ((0, 0, 255, 0), 16711680),
        ((255, 255, 255, 0), 16777215),
        ((0, 0, 0, 255), 4278190080),
    ],
)
def test_pack_color(rgbw, packed):
    assert pack_color(*rgbw) == packed


def test_pack_unpack_round_trip():
    for value in (0, 255, 65280, 16711680, 16777215, 4278190080, 4294967295):
        assert pack_color(*unpack_color(value)) == value


def test_pack_color_masks_out_of_range():
    assert pack_color(256, -1, 0) == pack_color(0, 255, 0)


def test_color_to_hex():
    assert color_to_hex(255) == "#ff0000"
    assert color_to_hex(65280) == "#00ff00"
    assert color_to_hex(16711680) == "#0000ff"
    assert color_to_hex(16777215) == "#ffffff"
    # White channel is dropped — warm white has no RGB.
    assert color_to_hex(4278190080) == "#000000"


def test_invalid_input_raises():
    with pytest.raises(GemstoneValueError):
        unpack_color("nope")
    with pytest.raises(GemstoneValueError):
        color_to_hex(None)
