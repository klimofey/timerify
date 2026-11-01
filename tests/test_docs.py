"""The structure of the user documentation: the same pages in English and in
Russian, links that resolve, README links that survive HACS and the Marketplace, and
the style rules."""

import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote, unquote

import pytest

ROOT = Path(__file__).parent.parent

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
SECTION_SIGN = chr(0xA7)
CYRILLIC = "".join(map(chr, range(0x430, 0x43A)))
"""Ten Cyrillic letters, built from code points, as the sources hold no Cyrillic."""
CYRILLIC_HEADING = f"{CYRILLIC.capitalize()} {CYRILLIC[::-1]}"
FENCE = "`" * 3
RAW = "https://raw.githubusercontent.com/klimofey/timerify/main"
BLOB = "https://github.com/klimofey/timerify/blob/main"

# Every helper below takes the repository root, skips fenced code blocks, and returns
# one human-readable problem per string, or [] when the tree is clean.
README_NAMES = ("README.md", "README.ru.md")
CODE_FENCE = re.compile(r"^\s*(`{3,})")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
TITLE = r'(?:\s+"[^"]*")?'
# `](target)` rather than `[text](target)`: a linked image, `[![alt](image)](page)`,
# holds two targets, and a match of the whole link would hide the second one.
LINK_TARGET = re.compile(rf"\]\((?P<target>[^)\s]+){TITLE}\)")
IMAGE_TARGET = re.compile(rf"!\[[^\]]*\]\((?P<target>[^)\s]+){TITLE}\)")
HTML_LINK_TARGET = re.compile(
    r"""\b(?:src|href)=(?P<quote>["'])(?P<target>.*?)(?P=quote)"""
)
HTML_IMAGE_TARGET = re.compile(
    r"""<img\b[^>]*?\bsrc=(?P<quote>["'])(?P<target>.*?)(?P=quote)"""
)
LINK_TEXT = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
SCHEME = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:")
REPOSITORY_FILE = re.compile(
    r"https://(?:github\.com/klimofey/timerify/(?:blob|tree)|"
    r"raw\.githubusercontent\.com/klimofey/timerify)/main/"
    r"(?P<path>[^\s)\]\"'<>#?]+)"
)
STYLE_RULES = (
    (re.compile(f"[{EM_DASH}{EN_DASH}]"), "long dash"),
    (re.compile(SECTION_SIGN), "section sign"),
    (re.compile(r"\b[RSP]-?\d+[a-z]?\b"), "rule id"),
)


def prose(path: Path) -> str:
    """The text of a Markdown file with its fenced code blocks blanked, line by line."""
    lines: list[str] = []
    fence = ""
    for line in path.read_text("utf-8").splitlines():
        closing = line.strip()
        if fence:
            if set(closing) == {"`"} and len(closing) >= len(fence):
                fence = ""
            lines.append("")
        elif opening := CODE_FENCE.match(line):
            fence = opening[1]
            lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines)


def matches(text: str, *patterns: re.Pattern[str]) -> list[tuple[int, re.Match[str]]]:
    """The matches of the patterns in text order, each with its line number."""
    found = sorted(
        (match for pattern in patterns for match in pattern.finditer(text)),
        key=lambda match: match.start(),
    )
    return [(text.count("\n", 0, match.start()) + 1, match) for match in found]


def relative_name(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def page_names(root: Path, language: str) -> set[str]:
    """The pages under `docs/<language>`, named by their path inside that folder."""
    folder = root / "docs" / language
    return {relative_name(folder, page) for page in folder.rglob("*.md")}


def readmes(root: Path) -> list[Path]:
    return [root / name for name in README_NAMES if (root / name).is_file()]


def user_pages(root: Path) -> list[Path]:
    """The pages written for the people who use Timerify: both READMEs and `docs/en`,
    `docs/ru`. The rest of `docs/` is for contributors."""
    pages = [
        root / "docs" / language / name
        for language in ("en", "ru")
        for name in sorted(page_names(root, language))
    ]
    return readmes(root) + pages


def language_pairs(root: Path) -> list[tuple[Path, Path]]:
    """The English files with their Russian counterparts, for the pairs that exist."""
    english, russian = root / "docs" / "en", root / "docs" / "ru"
    pairs = [
        (english / name, russian / name)
        for name in sorted(page_names(root, "en") & page_names(root, "ru"))
    ]
    english_readme, russian_readme = (root / name for name in README_NAMES)
    if english_readme.is_file() and russian_readme.is_file():
        pairs.append((english_readme, russian_readme))
    return pairs


def slug(heading: str) -> str:
    """The anchor GitHub gives a heading: the text without its links, in lower case,
    with the characters that are not word characters, spaces or hyphens dropped and the
    spaces turned into hyphens. Unicode letters are kept."""
    text = LINK_TEXT.sub(r"\1", heading).lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def headings(path: Path) -> list[tuple[int, str]]:
    """The ATX headings of a file as (level, text)."""
    found = (HEADING.match(line) for line in prose(path).splitlines())
    return [(len(match[1]), match[2]) for match in found if match]


def anchors(path: Path) -> set[str]:
    """The anchors of a file's headings; a repeated one is numbered: `-1`, `-2`."""
    seen: dict[str, int] = {}
    found: set[str] = set()
    for _, heading in headings(path):
        base = slug(heading)
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return found


def image_targets(path: Path) -> list[str]:
    found = matches(prose(path), IMAGE_TARGET, HTML_IMAGE_TARGET)
    return [match["target"] for _, match in found]


def unpaired_pages(root: Path) -> list[str]:
    """Pages that exist in one language of `docs/` and not in the other."""
    english, russian = page_names(root, "en"), page_names(root, "ru")
    return [
        f"docs/en/{name} has no Russian page docs/ru/{name}"
        for name in sorted(english - russian)
    ] + [
        f"docs/ru/{name} has no English page docs/en/{name}"
        for name in sorted(russian - english)
    ]


def heading_and_image_mismatches(root: Path) -> list[str]:
    """Pairs whose translation has other `##` or `###` headings, or other images."""
    problems: list[str] = []
    for original, translation in language_pairs(root):
        original_name = relative_name(root, original)
        translation_name = relative_name(root, translation)
        original_levels = [level for level, _ in headings(original)]
        translation_levels = [level for level, _ in headings(translation)]
        for level in (2, 3):
            expected, actual = (
                original_levels.count(level),
                translation_levels.count(level),
            )
            if actual != expected:
                problems.append(
                    f'{translation_name} has {actual} "{"#" * level}" headings, '
                    f"{original_name} has {expected}"
                )
        original_images, translation_images = (
            image_targets(original),
            image_targets(translation),
        )
        if translation_images != original_images:
            problems.append(
                f"{translation_name} has the images {translation_images}, "
                f"{original_name} has {original_images}"
            )
    return problems


def broken_relative_links(root: Path) -> list[str]:
    """Links to a file, or to a heading of a Markdown file, that is not there."""
    problems: list[str] = []
    contributing = root / "CONTRIBUTING.md"
    sources = user_pages(root) + ([contributing] if contributing.is_file() else [])
    for source in sources:
        for line, match in matches(prose(source), LINK_TARGET, HTML_LINK_TARGET):
            target = match["target"]
            if SCHEME.match(target):
                continue
            where = f"{relative_name(root, source)}:{line}: {target}"
            location, _, fragment = target.partition("#")
            destination = source.parent / unquote(location) if location else source
            if not destination.exists():
                problems.append(f"{where} does not exist")
            elif (
                fragment
                and destination.suffix == ".md"
                and unquote(fragment) not in anchors(destination)
            ):
                problems.append(
                    f"{where} has no such heading in {relative_name(root, destination)}"
                )
    return problems


def relative_links_in_readmes(root: Path) -> list[str]:
    """README links and images that are not an http(s) URL or a pure anchor. HACS and
    the Marketplace show the README away from the repository, where a relative path
    breaks."""
    return [
        f"{relative_name(root, readme)}:{line}: {match['target']} "
        "is not an absolute URL or an anchor"
        for readme in readmes(root)
        for line, match in matches(prose(readme), LINK_TARGET, HTML_LINK_TARGET)
        if not match["target"].startswith(("https://", "http://", "#"))
    ]


def missing_repository_targets(root: Path) -> list[str]:
    """Absolute links into this repository that name a file which is not in the tree."""
    return [
        f"{relative_name(root, page)}:{line}: {match['path']} does not exist in this "
        "repository"
        for page in user_pages(root)
        for line, match in matches(prose(page), REPOSITORY_FILE)
        if not (root / unquote(match["path"])).exists()
    ]


def style_violations(root: Path) -> list[str]:
    """Long dashes, section signs and rule ids in the user pages."""
    problems: list[str] = []
    for page in user_pages(root):
        text = prose(page)
        found = [
            (line, match, label)
            for pattern, label in STYLE_RULES
            for line, match in matches(text, pattern)
        ]
        found.sort(key=lambda item: (item[0], item[1].start()))
        problems.extend(
            f'{relative_name(root, page)}:{line}: {label} "{match[0]}"'
            for line, match, label in found
        )
    return problems


def write(root: Path, name: str, text: str = "") -> None:
    """Create the file `name` under `root`, with its folders."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")


@pytest.mark.parametrize(
    "check",
    [
        unpaired_pages,
        heading_and_image_mismatches,
        broken_relative_links,
        relative_links_in_readmes,
        missing_repository_targets,
        style_violations,
    ],
)
def test_a_tree_without_user_docs_has_no_problems(
    tmp_path: Path, check: Callable[[Path], list[str]]
) -> None:
    assert check(tmp_path) == []


def test_every_english_page_has_a_russian_page_and_back() -> None:
    assert unpaired_pages(ROOT) == []


def test_a_page_in_one_language_only_is_reported(tmp_path: Path) -> None:
    write(tmp_path, "docs/en/timers.md")
    write(tmp_path, "docs/en/card.md")
    write(tmp_path, "docs/ru/card.md")
    write(tmp_path, "docs/ru/limits.md")

    assert unpaired_pages(tmp_path) == [
        "docs/en/timers.md has no Russian page docs/ru/timers.md",
        "docs/ru/limits.md has no English page docs/en/limits.md",
    ]


def test_pages_in_both_languages_have_the_same_headings_and_images() -> None:
    assert heading_and_image_mismatches(ROOT) == []


def test_a_translation_with_other_headings_or_images_is_reported(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        "docs/en/timers.md",
        "# Timers\n\n## One\n\n## Two\n\n### Deep\n\n![a](../screenshots/a.png)\n",
    )
    write(
        tmp_path,
        "docs/ru/timers.md",
        "# Timers\n\n## One\n\n### Deep\n\n### Deeper\n\n![b](../screenshots/b.png)\n",
    )

    assert heading_and_image_mismatches(tmp_path) == [
        'docs/ru/timers.md has 1 "##" headings, docs/en/timers.md has 2',
        'docs/ru/timers.md has 2 "###" headings, docs/en/timers.md has 1',
        "docs/ru/timers.md has the images ['../screenshots/b.png'], "
        "docs/en/timers.md has ['../screenshots/a.png']",
    ]


def test_a_translation_that_matches_is_not_reported(tmp_path: Path) -> None:
    page = "# Timers\n\n## One\n\n### Deep\n\n![a](../screenshots/a.png)\n"
    write(tmp_path, "docs/en/timers.md", page)
    write(tmp_path, "docs/ru/timers.md", page.replace("Timers", CYRILLIC_HEADING))

    assert heading_and_image_mismatches(tmp_path) == []


def test_comments_in_code_blocks_are_not_headings(tmp_path: Path) -> None:
    write(
        tmp_path,
        "docs/en/services.md",
        f"## Call\n\n{FENCE}sh\n## a shell comment\n{FENCE}\n",
    )
    write(tmp_path, "docs/ru/services.md", "## Call\n")

    assert heading_and_image_mismatches(tmp_path) == []


def test_the_readmes_are_compared_once_both_exist(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "## One\n\n## Two\n")
    assert heading_and_image_mismatches(tmp_path) == []

    write(tmp_path, "README.ru.md", "## One\n")

    assert heading_and_image_mismatches(tmp_path) == [
        'README.ru.md has 1 "##" headings, README.md has 2'
    ]


def test_relative_links_and_anchors_resolve() -> None:
    assert broken_relative_links(ROOT) == []


def test_a_link_to_a_missing_file_or_heading_is_reported(tmp_path: Path) -> None:
    write(tmp_path, "docs/en/timers.md", "# Timers\n\n## Modes\n")
    write(
        tmp_path,
        "docs/en/card.md",
        "[a](timers.md)\n"
        "[b](timers.md#modes)\n"
        "[c](gone.md)\n"
        "[d](timers.md#missing)\n"
        "[e](#nothing)\n"
        "![f](../screenshots/gone.png)\n",
    )

    assert broken_relative_links(tmp_path) == [
        "docs/en/card.md:3: gone.md does not exist",
        "docs/en/card.md:4: timers.md#missing has no such heading in docs/en/timers.md",
        "docs/en/card.md:5: #nothing has no such heading in docs/en/card.md",
        "docs/en/card.md:6: ../screenshots/gone.png does not exist",
    ]


def test_a_link_inside_a_linked_image_is_checked_too(tmp_path: Path) -> None:
    write(
        tmp_path, "docs/en/card.md", "[![badge](https://example.com/b.svg)](gone.md)\n"
    )

    assert broken_relative_links(tmp_path) == [
        "docs/en/card.md:1: gone.md does not exist"
    ]


def test_anchors_follow_the_github_slug_rule(tmp_path: Path) -> None:
    write(tmp_path, "docs/en/other.md")
    write(
        tmp_path,
        "docs/en/anchors.md",
        "# Anchors\n\n"
        "## Run for N minutes\n\n"
        "## What's next? Strict & loose\n\n"
        "## Notes\n\n"
        "## Notes\n\n"
        "## `code` and [a link](other.md)\n\n"
        f"## {CYRILLIC_HEADING}\n\n"
        "[a](#run-for-n-minutes)\n"
        "[b](#whats-next-strict--loose)\n"
        "[c](#notes)\n"
        "[d](#notes-1)\n"
        "[e](#code-and-a-link)\n"
        f"[f](#{CYRILLIC_HEADING.lower().replace(' ', '-')})\n"
        f"[g](#{quote(CYRILLIC_HEADING.lower().replace(' ', '-'))})\n",
    )

    assert broken_relative_links(tmp_path) == []


def test_links_to_other_sites_and_links_in_code_blocks_are_not_followed(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        "docs/en/card.md",
        "[a](https://example.com/gone.md#nothing)\n"
        "[b](mailto:someone@example.com)\n"
        f"{FENCE}markdown\n[c](gone.md)\n{FENCE}\n",
    )

    assert broken_relative_links(tmp_path) == []


def test_the_readmes_and_contributing_are_checked_for_links_too(
    tmp_path: Path,
) -> None:
    write(tmp_path, "README.md", "## Modes\n\n[a](#modes)\n[b](#gone)\n")
    write(tmp_path, "CONTRIBUTING.md", "[c](docs/en/gone.md)\n")

    assert broken_relative_links(tmp_path) == [
        "README.md:4: #gone has no such heading in README.md",
        "CONTRIBUTING.md:1: docs/en/gone.md does not exist",
    ]


def test_readmes_link_to_this_repository_only_by_absolute_urls() -> None:
    assert relative_links_in_readmes(ROOT) == []


def test_a_relative_link_or_image_in_a_readme_is_reported(tmp_path: Path) -> None:
    write(
        tmp_path,
        "README.md",
        '<img src="custom_components/timerify/brand/icon.png" alt="Timerify">\n'
        '<a href="LICENSE">License</a>\n'
        "![shot](docs/screenshots/a.png)\n"
        "[guide](docs/en/README.md)\n"
        "[![badge](https://example.com/b.svg)](docs/en/timers.md)\n"
        "[ok](https://example.com)\n"
        f"![raw]({RAW}/docs/screenshots/a.png)\n"
        "[top](#top)\n",
    )
    write(tmp_path, "README.ru.md", "[guide](docs/ru/README.md)\n")

    assert relative_links_in_readmes(tmp_path) == [
        "README.md:1: custom_components/timerify/brand/icon.png is not an absolute URL "
        "or an anchor",
        "README.md:2: LICENSE is not an absolute URL or an anchor",
        "README.md:3: docs/screenshots/a.png is not an absolute URL or an anchor",
        "README.md:4: docs/en/README.md is not an absolute URL or an anchor",
        "README.md:5: docs/en/timers.md is not an absolute URL or an anchor",
        "README.ru.md:1: docs/ru/README.md is not an absolute URL or an anchor",
    ]


def test_relative_links_in_code_blocks_of_a_readme_are_not_reported(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        "README.md",
        f"{FENCE}yaml\ntype: custom:card\nsrc: [a](docs/a.md)\n{FENCE}\n",
    )

    assert relative_links_in_readmes(tmp_path) == []


def test_absolute_links_into_this_repository_point_at_files_that_exist() -> None:
    assert missing_repository_targets(ROOT) == []


def test_an_absolute_link_to_a_file_that_is_not_there_is_reported(
    tmp_path: Path,
) -> None:
    write(tmp_path, "docs/screenshots/a.png")
    write(tmp_path, "docs/en/timers.md")
    write(
        tmp_path,
        "README.md",
        f"![a]({RAW}/docs/screenshots/a.png)\n"
        f"[license]({BLOB}/LICENSE)\n"
        f"![b]({RAW}/docs/screenshots/b.png)\n"
        f"[folder](https://github.com/klimofey/timerify/tree/main/docs/gone)\n"
        f"[page]({BLOB}/docs/en/timers.md#modes)\n"
        "[other](https://github.com/other/repository/blob/main/nothing.md)\n",
    )
    write(tmp_path, "docs/ru/timers.md", f"[a]({BLOB}/docs/ru/gone.md)\n")

    assert missing_repository_targets(tmp_path) == [
        "README.md:2: LICENSE does not exist in this repository",
        "README.md:3: docs/screenshots/b.png does not exist in this repository",
        "README.md:4: docs/gone does not exist in this repository",
        "docs/ru/timers.md:1: docs/ru/gone.md does not exist in this repository",
    ]


def test_user_docs_have_no_long_dashes_or_rule_ids() -> None:
    assert style_violations(ROOT) == []


def test_long_dashes_section_signs_and_rule_ids_are_reported(tmp_path: Path) -> None:
    write(
        tmp_path,
        "docs/en/timers.md",
        f"A pause {EM_DASH} for a while.\n"
        f"From 06:30{EN_DASH}07:15.\n"
        f"See {SECTION_SIGN}4. Rules R3, S1 and P-7e apply, and so does R12a.\n",
    )
    write(tmp_path, "README.md", f"Timerify {EM_DASH} timers.\n")

    assert style_violations(tmp_path) == [
        f'README.md:1: long dash "{EM_DASH}"',
        f'docs/en/timers.md:1: long dash "{EM_DASH}"',
        f'docs/en/timers.md:2: long dash "{EN_DASH}"',
        f'docs/en/timers.md:3: section sign "{SECTION_SIGN}"',
        'docs/en/timers.md:3: rule id "R3"',
        'docs/en/timers.md:3: rule id "S1"',
        'docs/en/timers.md:3: rule id "P-7e"',
        'docs/en/timers.md:3: rule id "R12a"',
    ]


def test_the_russian_pages_and_the_readme_are_held_to_the_same_style(
    tmp_path: Path,
) -> None:
    write(tmp_path, "docs/ru/timers.md", f"{CYRILLIC} {EM_DASH}\n")
    write(tmp_path, "README.ru.md", f"{CYRILLIC} {EN_DASH}\n")

    assert style_violations(tmp_path) == [
        f'README.ru.md:1: long dash "{EN_DASH}"',
        f'docs/ru/timers.md:1: long dash "{EM_DASH}"',
    ]


def test_clean_text_code_blocks_and_notes_for_contributors_are_not_reported(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        "docs/en/services.md",
        f"Turn on the boiler, then wait. Prose, Roster and S-curve are words.\n"
        f"{FENCE}yaml\nnote: {EM_DASH} R3 {SECTION_SIGN}\n{FENCE}\n",
    )
    write(tmp_path, "docs/ru/services.md", f"{CYRILLIC}\n")
    write(
        tmp_path,
        "docs/superpowers/specs/design.md",
        f"Rule R3 {EM_DASH} {SECTION_SIGN}2\n",
    )

    assert style_violations(tmp_path) == []
