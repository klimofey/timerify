"""The one fold of spelling that Timerify makes: Russian prints "ye" for "yo", and a
speech recogniser does not tell them apart. The letters are named, not typed, so that
this file stays free of Cyrillic."""

import pytest

from custom_components.timerify.spelling import fold_yo

YO = "\N{CYRILLIC SMALL LETTER IO}"
CAPITAL_YO = "\N{CYRILLIC CAPITAL LETTER IO}"
YE = "\N{CYRILLIC SMALL LETTER IE}"
CAPITAL_YE = "\N{CYRILLIC CAPITAL LETTER IE}"


@pytest.mark.parametrize(
    ("text", "folded"),
    [
        (f"t{YO}st", f"t{YE}st"),
        (f"T{CAPITAL_YO}ST", f"T{CAPITAL_YE}ST"),
        (f"{YO}{CAPITAL_YO}{YE}{CAPITAL_YE}", f"{YE}{CAPITAL_YE}{YE}{CAPITAL_YE}"),
        ("Boiler (main) 6:30", "Boiler (main) 6:30"),
        ("", ""),
    ],
    ids=["small", "capital", "all four", "no yo", "empty"],
)
def test_each_yo_is_a_ye_and_nothing_else_changes(text: str, folded: str) -> None:
    assert fold_yo(text) == folded
