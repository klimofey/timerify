"""The pre-commit hook: Cyrillic is refused everywhere in the repository but in the
translations of the product and of its user documentation."""

import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).parent.parent / ".githooks" / "pre-commit"
CYRILLIC = "".join(chr(code) for code in (0x442, 0x430, 0x439, 0x43C, 0x435, 0x440))
"""A word in Cyrillic, built from code points, as the sources hold no Cyrillic."""
SENTENCES = "custom_components/timerify/sentences"
TRANSLATIONS = "custom_components/timerify/translations"


def commit_attempt(repository: Path, path: str) -> subprocess.CompletedProcess[str]:
    """Stage a file at `path` that holds Cyrillic in a clean repository, and run the
    hook as a commit would."""
    subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
    staged = repository / path
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text(f"text: {CYRILLIC}\n", "utf-8")
    subprocess.run(["git", "add", "--", path], cwd=repository, check=True)
    return subprocess.run(
        ["bash", str(HOOK)],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "path",
    [
        "README.ru.md",
        "docs/ru/timers.md",
        "docs/ru/notes/deeper.md",
        f"{TRANSLATIONS}/ru.json",
        f"{SENTENCES}/ru/timerify.yaml",
        f"{SENTENCES}/ru/src/timerify.yaml",
        f"{SENTENCES}/ru/src/macros.jinja",
        f"{SENTENCES}/de/src/deeper/anything.yaml",
    ],
)
def test_cyrillic_is_allowed_in_the_translations_of_the_product(
    tmp_path: Path, path: str
) -> None:
    attempt = commit_attempt(tmp_path, path)

    assert attempt.returncode == 0, attempt.stderr


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "docs/en/timers.md",
        "docs/research/notes.md",
        "custom_components/timerify/const.py",
        f"{TRANSLATIONS}/en.json",
        f"{SENTENCES}/en/timerify.yaml",
        f"{SENTENCES}/en/src/timerify.yaml",
        f"{SENTENCES}/en/src/macros.jinja",
        f"{SENTENCES}/timerify.yaml",
        "tests/voice/test_anything.py",
        "scripts/sentences/ru/generate.py",
        "docs/sentences/ru/notes.md",
    ],
)
def test_cyrillic_is_refused_everywhere_else(tmp_path: Path, path: str) -> None:
    attempt = commit_attempt(tmp_path, path)

    assert attempt.returncode == 1
    assert f"{path} contains Cyrillic" in attempt.stderr
