# User documentation: a short README, pages in English and Russian, and a public repository

Date: 2026-11-01. Owner: klimofey.

## Why

The README of 1.0.0 is 1231 lines. It reads like a specification: rule numbers, attribute
names, edge cases, and how the project is tested. Someone who finds Timerify in HACS wants
three things: what it does, how to install it, and where to read more. They get a wall of
text instead.

The owner also wants the repository public. From Home Assistant 2026.11 on, HACS is replaced by
the built-in **Marketplace**, and it adds only **public** repositories.
- Source: <https://next.home-assistant.io/integrations/marketplace/>, section "Adding custom
  repositories".
- 2026.11 is due in the first week of November 2026.

A private Timerify cannot be installed by anyone.

## Goals

1. **A short README** (`README.md`). The order is fixed by the owner:
   1. The icon and the badges (already on branch `readme-header`), and a language link
      "English | Russian", with "Russian" written in Russian.
   2. One or two sentences: what Timerify is.
   3. **Installation, right after the description, with buttons, like other integrations:**
      - A My Home Assistant button that opens the repository in HACS or the Marketplace:
        `https://my.home-assistant.io/redirect/hacs_repository/?owner=klimofey&repository=timerify&category=integration`,
        with badge `https://my.home-assistant.io/badges/hacs_repository.svg`.
        - The my.home-assistant redirect list maps this legacy name to `marketplace_repository`
          on 2026.11.
        - The Marketplace page says "HACS buttons still work".
      - Short manual steps for each case:
        - Home Assistant 2026.10: HACS, then the menu, then Custom repositories, then the URL,
          with type Integration.
        - Home Assistant 2026.11 and later: Settings, then Marketplace, then Add from link,
          then `klimofey/timerify`.
        - By hand: copy `custom_components/timerify`.
      - Then "restart Home Assistant".
      - Then a second button, "Add integration":
        `https://my.home-assistant.io/redirect/config_flow_start/?domain=timerify`, with badge
        `https://my.home-assistant.io/badges/config_flow_start.svg`.
   4. One screenshot.
   5. "What it can do": about six bullets, one per feature. Each is one plain sentence with a
      link to its page.
   6. License.
   - **Target length:** about 100 lines.
2. **Topic pages** in `docs/en/` and `docs/ru/`, with the same file names in both. The set,
   taken from today's README sections:
   - `README.md`: an index of the pages.
   - `timers.md`: Run for, the modes, the entities, the settings for turning on, the supported
     devices.
   - `pending-commands.md`
   - `schedules.md`
   - `voice.md`: what can be said, the Voice settings entry, the manual copy, and LLM agents.
   - `card.md`
   - `runtime.md`
   - `services.md`: the reference. This page may stay exact and technical.
   - `limits.md`: what is not here yet, and known issues.
3. **A Russian README**, `README.ru.md`, the same as the English one in Russian.
4. **`CONTRIBUTING.md`** (English only) takes the developer sections, moved as they are:
   - Verification
   - Development
   - The card
   - hassfest
   - Smoke test
5. **Plain, human language** in every user page and both READMEs:
   - short sentences;
   - "you";
   - no long dashes (— or –) used as punctuation;
   - no internal terms ("wish", "fold", "R3", "§5.7", "loose/strict" without a plain
     explanation);
   - no stacked clauses.
6. **The repository goes public** after the new docs are on main, then a GitHub Release
   `v1.0.0`. The Marketplace shows versions and release notes from releases.

## Non-goals

- No change in behaviour, strings in `translations/`, or voice sentences.
- `RULINGS.md`, the spec, plans and research stay as they are: English developer documents.
- No documentation website (GitHub Pages, MkDocs). Plain Markdown in the repository.
- No new screenshots, except where a page clearly needs one. The existing files in
  `docs/screenshots/` are reused.

## Anti-goals (a failure even if it "works")

- **A user page that claims something the code does not do.** The source of truth is today's
  README, checked against the code where the wording changes. Simpler wording must not become
  wrong wording. Example: "turned off by hand clears the countdown" stays true to the rules.
- **The Russian pages drifting from the English ones:** a page in one language only, or a
  section missing.
- **Links that break where the README is shown outside GitHub.** HACS and the Marketplace render
  the README in Home Assistant, where relative links do not resolve.
- **Text that reads machine-written:** long dashes, long sentences, filler.

## Constraints

- **Cyrillic.**
  - Repository rule 1 and the `pre-commit` hook already allow `README.ru.md`. The owner now asks
    for it.
  - Add `docs/ru/` to the hook's allowlist, with its test in `tests/test_precommit_hook.py`.
  - Update `CLAUDE.md` rule 1: drop "do not create it until the owner asks", and name
    `docs/ru/`.
- **Links in `README.md` and `README.ru.md`:**
  - Links to pages and to `LICENSE` are absolute `https://github.com/klimofey/timerify/blob/main/...`
    URLs.
  - Images are absolute `https://raw.githubusercontent.com/klimofey/timerify/main/...` URLs.
  - Links inside `docs/` are relative, since those pages are read on GitHub.
- **A test of the docs** (`tests/test_docs.py`), so that the rules above hold after later
  changes:
  - every `docs/en/*.md` has a `docs/ru/*.md` of the same name, and the reverse;
  - every relative link and image in `docs/` resolves to a file;
  - every absolute link of the READMEs into this repository points at a file that exists;
  - no `—` or `–` in `README.md`, `README.ru.md`, `docs/en/` or `docs/ru/`;
  - `tests/test_readme.py` (the Home Assistant badge equals `hacs.json`) keeps passing.
- **A style rule in `CLAUDE.md`** for user documentation: the language rules of goal 5, so later
  changes keep them.
- **The card's screenshot script** writes `docs/screenshots/card-*.png`. Keep those paths.
  - `CLAUDE.md` says "the two pictures of the README". Keep that true, or reword it.
- **The full local gate** before merge, as usual. The docs change no code, but the gate is the
  rule.

## Decided by the owner

- Installation comes right after the short description, with buttons, like other
  integrations, plus manual steps.
- Details go to pages under `docs/`, in English and Russian.
- Simpler, human wording, with no long dashes and no complex sentences.
- The current icon stays. The icon and badges go at the top.
- MIT licence. The stray lines from another project were removed from `LICENSE` (commit
  87b80b9).
- The repository goes public (asked for by the owner on 2026-11-01). The order and the release
  are in goal 6.

## Left to the builder

- The exact wording of each page, within the rules above.
- Which screenshots go on which page.
- Headings inside pages.
- Whether `docs/en/README.md` is an index or the pages link each other.

## Calls made by Claude (the owner may overrule)

- **The release.** `v1.0.0` is tagged on the merge commit of these docs, not on `ec35f9e`, so
  the README the Marketplace shows is the new one. The code is the same: the docs change no
  code. The release notes are short, plain text in English, written to the rules of goal 5.
- **Russian names of Home Assistant's own screens.** The Russian steps use Home Assistant's
  Russian names where its frontend translation has them. They are checked in the installed
  frontend for 2026.10. For 2026.11 they are checked in its translation files once they are
  published. A name that has no Russian translation yet is given in English, as the screen
  shows it.
- **Who checks the Russian.** The owner reads `README.ru.md` and `docs/ru/` before the merge.
  The plan has a stop for that.
- **What becomes visible.** The audit of 2026-11-01 found no secrets, tokens, local paths, IP
  addresses or names from other projects in the files or the history. The smoke screenshots
  show the throwaway test container (`smoke_boiler`, the demo devices), not a real home.
  `CLAUDE.md`, `RULINGS.md` and `docs/superpowers/` stay public, as rule 5 always intended.
- **Who runs the irreversible steps.** The builder stops before the visibility change and the
  release. The controller runs them after the owner says go.

## Decided by the owner (second round)

- The author address in the history stays as it is. The history is not rewritten.

## Open: to check after the repository is public

- The HACS button opens the add dialog for a repository that is not in HACS's default list, on
  2026.10 with HACS and on 2026.11 with the Marketplace. Check it by hand once the repository is
  public, and fix the README if it does not.
