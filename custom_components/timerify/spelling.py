"""The one fold of spelling that Timerify makes, for every place that compares what was
said or typed with what is stored."""

from typing import Final

_YO_TO_YE: Final = str.maketrans(
    {
        "\N{CYRILLIC SMALL LETTER IO}": "\N{CYRILLIC SMALL LETTER IE}",
        "\N{CYRILLIC CAPITAL LETTER IO}": "\N{CYRILLIC CAPITAL LETTER IE}",
    }
)


def fold_yo(text: str) -> str:
    """`text` with each Russian "yo", small and capital, written as the "ye" it is
    printed as: Russian prints the one for the other, and a speech recogniser does not
    tell them apart."""
    return text.translate(_YO_TO_YE)
