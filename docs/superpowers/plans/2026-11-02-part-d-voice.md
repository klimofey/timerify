# Timerify 1.1.0 Part D (Voice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the voice issues of 1.1.0. Assist understands "for 1 hour 30" (#26), delays past 100 (#29), commands at a clock time (#19), the start time of a generated interval title (#22), names said with ye for yo (#23), Russian words for device modes (#24), HVAC words per thermostat (#25), and a renamed YAML target (#20). The phrasings found so far that core's gazetteer took are Timerify's (#21), and the Russian plural answers are pinned by fixtures (#27).

**Architecture:** Two layers change. The shipped sentences (`sentences/<lang>/src/*.yaml`, and `scripts/generate_core_commands.py`, which writes `core_commands.yaml`) gain new rules, lists and one new intent, `TimerifyCommandAt`. The generator learns to copy every rule of a settings scope, not only `timerify_settings`, so a scope can override a global rule. The managed file writer (`voice/sentences.py`, `voice/files.py`) gains one spelling fold, per-language mode words from Home Assistant's translations, per-set HVAC blocks, interval aliases, and a state listener on the targets. Handlers change only where a slot means something new. A rule still lives in the controller.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4, hassil 3.12.1, home-assistant-intents 2026.10.6, gazetteer-matcher 1.1.0, all read in `.venv/lib/python3.14/site-packages` (written `sp/` below):
- **Block rules and lists win over global ones.** `sp/hassil/recognize.py:248-256` matches a data block with `{**global_lists, **block.slot_lists}` and `{**global_rules, **block.expansion_rules}`; `sp/hassil/fst.py:530-534` looks a rule up in the block first. So a rule a block defines also replaces it inside a global rule that the block's sentences use. `requires_context` is checked at `recognize.py:232-239` against the contexts of the matched list values. Probed: per-block lists with a context key on the name work (`turn on the ac in heat` is not matched for an AC whose block lists only `cool`).
- **Clock text.** `sp/hassil/util.py:40-50`: a `:` or `.` between digits is not punctuation. Probed with a range list: `at 7:30`, `at 07:30`, `at 7 30`, `at seven thirty`, `at 7.30`, `at 7 o'clock`, `at 7:30 p.m.` all match; `25:00` and `7:60` do not.
- **Range multiplier.** `sp/hassil/intents.py:585-595` and `sp/hassil/string_matcher.py:800-801`: a range list with `multiplier: 24` fills its slot with the count times 24.
- **Core's delay lists** `timer_hours`, `timer_minutes`, `timer_seconds` are `range 1..100` in `en` and `ru` (`home_assistant_intents.get_intents`). Core has no clock-time sentence in either language.
- **The gazetteer.** `sp/homeassistant/components/conversation/default_agent.py:495` hands a sentence to the gazetteer when hassil has no result or one with unmatched entities. `:704-718` skips it only for a custom sentence matched with an unmatched entity. `gazetteer.py:96-136` builds its home from every exposed entity, with no exclusion; `:206-208` makes it English only. Probed with `GazetteerMatcher` (accepted as a bare `HassTurnOn`/`HassTurnOff`): "turn on the AC for an hour in heat", "turn off scheduling for the boiler", "turn off the boiler in 2 days", "turn on the boiler in 8 days", "turn off the boiler at 7", "turn on the boiler tomorrow at 7", "turn on the boiler at noon", "turn off the boiler in 3 weeks", "turn off the boiler tonight". Rejected: "turn on the boiler at 7:30", "turn off the boiler in 200 hours", "turn on the boiler for 1 hour 30".
- **2026.11.** 2026.11.0b2 is not on PyPI; the newest is 2026.11.0b1 (2026-10-29). Its wheel, downloaded and not installed, is in `/private/tmp/claude-501/-Users-klimofey-GIT-timerify/65cac539-b99c-4f20-8330-5c3a07d9abbe/scratchpad/ha-2026.11/src/`. Its `conversation/manifest.json` pins hassil 3.12.1 and home-assistant-intents 2026.10.27. `default_agent.py:502` and `:720-734` are the same gate as 2026.10.4, and `gazetteer.py` differs only in renaming `_async_get_matcher` to `async_get_matcher` (`:222`, `:263`). There is no way to keep a custom intent's names out of the fallback (#21 stays open).
- **Translations.** `sp/homeassistant/helpers/translation.py:335-358` `async_get_translations(hass, language, category, integrations)` is public and takes a language. `:497-533` `async_translate_state_attr` gives the lookup order but uses `hass.config.language` and the cache only. `:208-256`: a language's translations are laid over English, so a missing key comes back in English. Domain-level words exist for `climate` `fan_mode`, `humidifier` `mode` and `water_heater` `operation_mode` (`entity_component._.state_attributes.<attr>.state`, in `components/<domain>/translations/ru.json`). `fan` has none at domain level: a preset's word is the platform's, as `components/demo/strings.json` `entity.fan.demo.state_attributes.preset_mode.state` (`auto`, `on`, `sleep`, `smart`, with `ru.json`).
- **State tracking.** `sp/homeassistant/helpers/event.py:304` `async_track_state_change_event(hass, entity_ids, action)`.
- **Time zones.** In `Asia/Jerusalem` the clock jumps from 02:00 to 03:00 on 2026-03-27, and `datetime.combine(date(2026, 3, 27), time(2, 30), zone).astimezone(UTC)` is 00:30 UTC, 03:30 on the wall (checked with `zoneinfo`). `schedule.window_on` (`custom_components/timerify/schedule.py:77-92`) uses that rule.

**Spec:** `docs/superpowers/specs/2026-11-01-release-1.1.0-design.md`, section "Part D: voice", with "Non-goals" and "Constraints". The owner's decisions: `.superpowers/issue-triage-1.1.0.md` (#21, #27). Issues: `gh issue view N --json title,body` for N in 19 20 21 22 23 24 25 26 27 29 (plain `gh issue view` prints nothing in a non-terminal shell). The base spec and `RULINGS.md` hold where this is silent.

**Starting point:** `part-d-voice` at `main` 094bb74, the merge of part C (PR #48): 2286 pytest tests collected.

## Global Constraints

- Home Assistant `>= 2026.10.4` (`hacs.json`), Python `>= 3.14.2`, `pytest-homeassistant-custom-component==0.13.375`. No new runtime or dev dependency, and no change to `manifest.json`.
- Only public Home Assistant APIs, checked in `.venv` before use. mypy is strict, and schemas use `probatio`.
- Tests are user scenarios with frozen time (`freezer`, `advance`, `advance_to`, `open_sunday`, `restart_after`). They talk to the real built-in agent (`converse`) or the real Assist API (`call_tool`). No `asyncio.sleep`, no polling and no backdoors. Product code gets no test-only branch. An existing test is edited only where a task names it.
- A test name fits the 88 columns of `async def <name>(`, so 77 characters at most.
- **No Cyrillic outside the allowed files.** This plan has none. The implementer writes every Russian sentence, word, answer and page from the English description here. A test says Russian by sampling the shipped files (`samples`, `every_text`, `spoken_values`) or by code points (`"\N{CYRILLIC SMALL LETTER IO}"`), never in letters. After Task 1, `tests/fixtures/ru/` is the one test folder that may hold Cyrillic.
- **Sentences:** edit `sentences/<lang>/src/timerify.yaml` (and `macros.jinja`) and the generator, never the shipped files. Then run `uv run python -m scripts.generate_sentences` and `uv run python -m scripts.generate_core_commands`, and commit the files they write with the task. `test_shipped_sentence_files_are_current` and `test_the_committed_file_is_what_the_generator_writes` must pass. Every new list or rule name starts with `timerify_`.
- **Strings:** this plan adds no key to `translations/`. Every refusal reuses an existing key. A task that finds it needs one stops and reports: the bundle rebuild and hassfest then join that task.
- **Docs:** a user-visible change updates `docs/en/<page>.md` and `docs/ru/<page>.md` in the same commit, with the same `##` and `###` headings (`tests/test_docs.py`) and the CLAUDE.md "User documentation" style: short sentences, "you", no long dashes, no rule ids, no internal words. The English pages transliterate Russian examples, as `docs/en/voice.md` does now. Russian Home Assistant screen names come from `python3 .superpowers/ui-names/ui-term.py "<English name>"`.
- **Follow-ups:** a task that fixes an issue removes its line from `docs/followups.md`. #21 keeps its line.
- Every task ends with these passing: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run mypy`.
- English only. Commit messages are a plain sentence-case subject, with no attribution lines. Never use `--no-verify`. `git add` only the files of the task.
- **RULINGS:** Task 1 adds a subsection `### Voice` under `## Release 1.1.0`, after `### Automations`. Later tasks append to it, in the existing style: a bold decision, then "Why:", then "Cost if wrong:", then the tests that pin it. An entry of phase 4 ("What can be said", "The Voice settings entry and the sentence files") that a task changes is rewritten in place to what holds now (the rule at the top of `RULINGS.md`), not repeated.
- Nothing is opened, commented or labelled in any `home-assistant/*` repository. Docker: start, stop or remove only the containers a task names.
- The PR body says "Closes #19. Closes #20. Closes #22. Closes #23. Closes #24. Closes #25. Closes #26. Closes #27. Closes #29." (one keyword per issue). It does not close #21.

## Review Focus

1. **A phrasing that misses Timerify's sentences falls to the English gazetteer, which switches the device without a timer.** #25 makes an HVAC word the AC lacks "not understood" where it was "understood and refused", and the gazetteer accepts "turn on the AC for an hour in heat" as a bare turn-on. A person expects nothing to switch. Test: Task 8, `test_a_mode_only_another_ac_has_switches_neither_on`. If it fails because the gazetteer acts, stop and report: no workaround.
2. **A clock time that has passed today.** "Turn on the boiler at 7", said at 08:00, means tomorrow at 07:00, and the answer says "tomorrow". "Today at 7", said at 08:00, is refused and keeps nothing. Tests: Task 5, `test_a_clock_time_already_past_today_means_tomorrow` and `test_today_at_a_time_that_has_passed_is_refused`.
3. **A clock time on the night the clock changes.** "At 2:30" on the night of 2026-03-27 in Jerusalem runs at 03:30, as a schedule window does. Test: Task 5, `test_a_wall_time_the_clock_skips_happens_an_hour_later`.
4. **A target that only switches on and off.** Following its state (#20) must not rewrite the file or reload the agent on every switch or temperature report. Test: Task 10, `test_a_target_switching_on_and_off_rewrites_nothing`.
5. **A house set to English that writes the Russian file.** The Russian file gets Russian words for the modes, from the Russian translations, not the house's English ones. Test: Task 7, `test_an_english_house_gets_russian_mode_words_in_russian`.

## Decisions

1. **Task order.** Task 1 (#27) stands alone and pins the Russian answers before anything else changes. Tasks 2 to 5 change the sentences and the generator, each on the one before: the scope rules (#26), the delay lists (#29), the days delay (#21), then the clock intent (#19), which needs all three. Tasks 6 to 10 change the file writer: the fold (#23) first, because every later list uses it; then the mode words (#24); then the HVAC scoping (#25), which also scopes the clock blocks of Task 5; then the interval aliases (#22); then the state listener (#20), which compares what Tasks 7 and 8 write. Task 11 is the gate. Why: each task's tests then run on the final shape of what it uses, and a reviewer can reject one issue without its neighbours.
2. **#26: hours followed by a bare number of minutes is a duration, except for a device that takes a temperature.** `timerify_duration` gains "N hour(s) [and] M" with M from 1 to 59, in both languages. The thermostat and water heater blocks of `TimerifyRun` override `timerify_duration` with `timerify_duration_with_and` (the spelled-out form, or hours, "and" and a bare number of minutes), so "for 1 hour 30" stays one hour at 30 degrees there and "for 1 hour and 30" is 90 minutes, each with one parse (controller ruling after the Task 2 review). The generator copies the override into the delayed and clock blocks of those scopes. Why: the issue's fix, without a new ambiguity for the devices that read a bare number as a temperature.
3. **#29: a delay is said with Timerify's lists, the ones durations use.** Hours 1 to 168 (words), minutes 1 to 1440 (words) and 1441 to 10080 (digits), as `timerify_hours`, `timerify_minutes` and `timerify_long_minutes`. Seconds stay core's 1 to 100. The limits are the controller's: a command to turn on is kept at most 7 days ahead, a command to turn off sets the countdown and so reaches 24 hours. The refusals are the existing texts, which name the limit: `command_too_far` ("A command can be set at most 7 days ahead.") and `duration_out_of_range` ("A timer runs for 1 min to 24 h."). A count past a week in one unit is not understood, as for durations. Why: one bound for every count, already measured for cost (RULINGS, the duration entry), and no new string.
4. **#21: the phrasings found so far become Timerify's; the rest waits on Home Assistant.** "In N days" is a delay, N from 1 to 365, in both languages, into its own slot `delay_days` (a plain range, no multiplier; the handler counts a day as 86400 s), so the LLM tool gains `delay_days`. "In a day", "in half a day", "in a week" and "in N weeks" (1 to 52, slot `delay_weeks`) are Timerify's too, and in English the same spans followed by "from now", "from today" or "later", so the gazetteer never switches a device on for them; past the limits they are refused (controller ruling after the Task 4 review: hassil 3.12.1 caches number words without the multiplier, so a `multiplier: 24` range collides with any other range of the same bounds). In English, "scheduling" is a word for "schedule" in the schedule sentences. 2026.11.0b1 has no way to keep a custom intent's names out of the gazetteer (Tech Stack), so the controller labels #21 `upstream` with a comment (Task 11). Why: each found phrasing is refused or done as asked, instead of switching the device. The bound of 365 days refuses "in 8 days" with the limit instead of letting the gazetteer act on it.
5. **#19: commands at a clock time.**
   - **Forms.** English: "at 7:30", "at 07:30", "at 7 30", "at 7.30", "at 7", "at 7 o'clock", with "am" or "pm" after any of them, "at noon", "at midnight". Russian: "v" with the same digit forms, "v 7 chasov" and "v 7 chasov 30 minut" (the word for hours and minutes in their forms), a day part after the time ("utra" morning, "dnya" afternoon, "vechera" evening, "nochi" night), "v polden" (noon) and "v polnoch" (midnight). A day word may come before or after the time: "today", "tomorrow", "the day after tomorrow" ("segodnya", "zavtra", "poslezavtra"). The time comes after the command or before it, and a command to turn on may add "for <duration>" and its settings, as delayed commands do.
   - **Reading (owner's decision, 2026-11-02).** An hour from 1 to 12 said with no "am", "pm" and no Russian day part means the nearer of its two times ahead: "at 7" said at 18:00 is 19:00 today, said at 06:00 is 07:00 today, said at 20:00 is 07:00 tomorrow. That goes for "at 7:30" and the other digit forms of 1:00 to 12:59 too. An hour of 0 or from 13 to 23 is a 24-hour clock: "at 19" is 19:00, "at 0:30" is 00:30. "am" or "pm", or a Russian day part, fixes the half: 12 am and "12 nochi" are 00:00, 12 pm is 12:00, "nochi" with 1 to 5 is that hour and with 6 to 11 is that hour plus 12; "dnya" and "vechera" are pm, "utra" is am. With a day word ("tomorrow at 7"), a bare 1 to 12 is the earlier of its two times on that date, unless "today" makes the morning one already past, in which case it is the evening one if that is still ahead.
   - **Day.** Without a day word, the time is the next one: today if it is still ahead, else tomorrow (a time equal to now is tomorrow). With a day word it is that date, and "today" at a time that has passed is refused by the controller (`command_in_past`, "07:00 has already passed. Pick a time that is still ahead."). The wall time follows the schedule's rule: a time the clock skips happens later by the gap, one it repeats is its first time (`schedule.wall_moment`, shared with `window_on`).
   - **Mapping.** A command to turn on is `controller.async_add_command("on", <moment>, minutes, settings)`, the pending command `timerify.add_command` makes with `at`. A command to turn off is `controller.async_turn_off_in(<moment>)`, as "turn off in N" is: it sets the countdown of a running device, changes nothing for one that is off, and is refused past 24 hours.
   - **Answer.** The existing `timer_later` answer: "Boiler turns on at 07:30 tomorrow.", "Boiler turns off at 23:00.", "Boiler is already off; nothing changed."
   - **Intent.** A new intent `TimerifyCommandAt` with its own handler, registered for the built-in agent and not offered as an LLM tool: the tool `timerify__delayed_command` already takes `at`, and the sentence slots (`clock_hour`, `clock_minute`, `clock_part`, `clock_day`) would only confuse a model.
   - **Thermostats in English.** "Turn on the AC for an hour at 21" stays a run at 21 degrees. After the settings of a thermostat or water heater, a clock time must have a colon, "o'clock", "am" or "pm", "noon" or "midnight". The rule `timerify_clock_after_extras` is overridden in those two blocks of the English source. Russian needs no override: it says a time with "v" and a temperature with "na".
6. **#23: one fold, `fold_yo`, in `custom_components/timerify/spelling.py`.** It makes each yo, small and capital, a ye. `schedule.title_key` calls it (the LLM and controller comparison of titles). `voice.sentences.spoken_variants` calls it (the file writer), and lists every name, interval title, alias and mode under both spellings, each meaning the same value. The file must list both, because the built-in agent compares what it hears with the file and cannot be told to fold. `validate` then checks each value against the text `build` meant to say (`BuiltSentences.said`), since `in` is no longer a function of `out`.
7. **#24: mode words come from Home Assistant's translations in the language of each file.** The Russian file takes the Russian translations, the English file the English ones, whatever the house language: a house set to English that asks for the Russian file wants Russian words. The lookup order is `async_translate_state_attr`'s: the platform's `entity.<domain>.<translation_key>.state_attributes.<attr>.state.<mode>`, then the domain's `entity_component.<device_class>...`, then `entity_component._...`. Without a translation, Home Assistant's English fallback is what comes back, and it is listed: it is what the UI shows in that language. The raw mode, said with spaces for underscores, is always listed too. A word that is said like a value of another mode is left out, so it cannot mean the wrong one. The modes are the ones "mode" means now: a thermostat's fan mode, a fan's preset, a humidifier's mode and a water heater's operation mode. Water heaters are included because they are in the same list.
8. **#25: one copy of each thermostat block per distinct set of HVAC modes.** A thermostat's name carries the context `timerify_hvac_modes: <its modes sorted, joined by spaces>`. `build` replaces every data block that requires the domain `climate` alone (the `TimerifyRun` block and the generated delayed and clock blocks) by one copy per set. Each copy requires that context and has its own list `timerify_hvac_mode` with that set's words. The global list is empty. A block that requires `climate` with another domain makes `build` raise: the sources are Timerify's own. The shipped files, which the manual route copies, keep the one block with every word. The growth is three blocks per extra set in each language, measured and recorded in RULINGS.
9. **#22: an interval that still has the title Timerify gave it can be said by its start time.** The aliases are the start time with and without its leading zero, with a colon or a dot: "6:30", "06:30", "6.30", "06.30" for 06:30, and "18:00", "18.00" for 18:00. They are the same in every language. The file lists each alias with itself as the value, and the controller matches an asked text against the title and the aliases of each interval (by `title_key`). Every interval of the timer that starts then is switched, as two intervals with one title are. The answer names every interval it switched by its title (Task 9 fix round: one start time can switch intervals with different titles; intervals that share a title read once). An interval the user renamed has no alias. Why: a value that meant a title would make "6:30" ambiguous between two timers, since the list is one for the house.
10. **#20: Timerify follows the state of every target, and writes only when what the file says of it changed.** The writer keeps, per target, what it last wrote: names, HVAC set and mode sources (`TargetVoice`). On a state change of a target it recomputes that target's part and schedules a write only when it differs. A registered target's mode list is followed the same way, since a firmware update changes the state, not the registry entry. Why: the spec's "without churn", for one target at a time.
11. **#27: a hook exception for `tests/fixtures/ru/`, and a fixture written by hand.** `tests/fixtures/ru/answers.yaml` holds, for each answer with a count and each count class, the slots and the Russian text a speaker expects. The implementer writes the text from Russian grammar, never by rendering the templates: a rendered fixture would only repeat the templates. The owner reads the file once (Task 11). CLAUDE.md rule 1 lists the new folder.

---

## File Structure

```
.githooks/pre-commit                 tests/fixtures/ru/ allowed (T1)
CLAUDE.md                            rule 1 names tests/fixtures/ru/ (T1)
custom_components/timerify/
  spelling.py        new: fold_yo (T6)
  schedule.py        wall_moment (T5); title_key uses fold_yo (T6);
                     has_generated_title, start_aliases, spoken_aliases (T9)
  controller.py      async_set_schedule_enabled matches aliases (T9)
  const.py           CONTEXT_HVAC_MODES (T8)
  llm.py             TOOL_HANDLER_TYPES (T5)
  voice/__init__.py  ClockCommandHandler registered, TOOL_HANDLER_TYPES (T5)
  voice/commands.py  DelayedCommandHandler.when, ClockCommandHandler, clock_moment, hour_of_day (T5)
  voice/intervals.py the tool description names the start time (T9)
  voice/sentences.py spoken_variants, BuiltSentences, validate(said) (T6); ModeSource, async_mode_words (T7);
                     hvac sets and scoped blocks (T8); interval aliases (T9); TargetVoice, target_voice (T10)
  voice/files.py     said to validate (T6); per-language words (T7); state listener (T10)
  sentences/en|ru/src/timerify.yaml  (T2, T4, T5); generated en|ru timerify.yaml, core_commands.yaml (T2 to T5)
scripts/generate_core_commands.py    Scope.rules (T2); DELAY_LISTS (T3); OWN_DELAY_RULE (T4); clock blocks (T5)
tests/
  fixtures/ru/answers.yaml           new (T1)
  test_precommit_hook.py             (T1)
  conftest.py                        provide_fake(platform=, translation_key=) (T7)
  voice/test_russian_answers.py      new (T1)
  voice/test_clock_commands.py       new (T5)
  voice/helpers.py                   RESPONSE_SLOTS gets TimerifyCommandAt (T5)
  voice/test_timer_by_voice.py (T2), test_core_commands.py (T2 to T5), test_llm.py (T5),
  test_sentence_validation.py (T6 to T8), test_voice_entry.py (T6 to T8, T10),
  test_schedule_by_voice.py (T4, T6, T9)
docs/en|ru: voice.md (T2 to T10), limits.md (T5), pending-commands.md (T5), schedules.md (T9)
RULINGS.md (T1 to T10); docs/followups.md (T1 to T10)
```

Task 3 changes no source file under `src/`: the delay lists already exist there.

---

### Task 1: Russian answers pinned by fixtures, and the hook exception (#27)

**Files:**
- Modify: `.githooks/pre-commit` (`cyrillic_allowed`, and the header comment), `tests/test_precommit_hook.py`, `CLAUDE.md` (Repository rules, rule 1: add `tests/fixtures/ru/` to the list where Cyrillic is permitted), `RULINGS.md`, `docs/followups.md`.
- Create: `tests/fixtures/ru/answers.yaml`, `tests/voice/test_russian_answers.py`.

**Interfaces:**
- Produces:
  - `cyrillic_allowed` returns 0 for `tests/fixtures/ru/*` (any depth), next to the `docs/ru/*` line.
  - `tests/fixtures/ru/answers.yaml`: a list of cases, each `{intent: str, response: str, unit: minutes | hours | commands, count: int, slots: mapping, answer: str}`. A comment at the top, in English, says the answers are written by hand and read by the owner, and that a change to a Russian answer changes this file in the same commit.
  - `tests/voice/test_russian_answers.py`:
    - `COUNTED: Final[Mapping[tuple[str, str], frozenset[str]]]` = `("TimerifyTimeLeft", "default")`: minutes, hours; `("TimerifyRun", "default")`: minutes, hours (the macro `timer_now`, which Add time and Stop also call); `("TimerifyListCommands", "default")`: commands, minutes (the run of a planned command); `("TimerifyCancelCommands", "default")`: commands.
    - `CLASS_COUNTS: Final[Mapping[str, frozenset[int]]]` = minutes `{1, 2, 5, 11, 21, 22}`, hours `{1, 2, 5, 11, 21}`, commands `{1, 2, 5, 11, 21}`.
    - Each case's slots are built like the helpers of `tests/voice/helpers.py` (`counting`, `listing`, `planned`, `cancelling`), written out in the YAML.

- [ ] **Step 1: Write the failing tests.** In `tests/test_precommit_hook.py`, the allowed list gains `"tests/fixtures/ru/answers.yaml"` and `"tests/fixtures/ru/deeper/more.yaml"`; the refused list gains `"tests/fixtures/en/answers.yaml"`, `"tests/fixtures/answers.yaml"`, `"tests/fixtures/ru.yaml"` and `"tests/voice/fixtures/ru/answers.yaml"`. In `tests/voice/test_russian_answers.py`:

```python
@pytest.mark.parametrize("case", load_cases(), ids=case_id)
async def test_each_russian_answer_reads_as_the_fixture_says(hass, case) -> None:
    template = shipped_answers("ru")[case["intent"]][case["response"]]
    assert render_response(hass, template, case["slots"]) == case["answer"]

def test_the_fixture_has_every_count_class_of_every_counted_answer() -> None:
    # for each (intent, response) in COUNTED and each unit it counts:
    # {case["count"] for the cases of that answer and unit} == CLASS_COUNTS[unit]
```

  `shipped_answers(language)` reads `responses.intents` of `SENTENCES_DIR / language / "timerify.yaml"` with `read_back`. `case_id` is `f"{intent}-{unit}-{count}"`.
- [ ] **Step 2: Run** `uv run pytest tests/test_precommit_hook.py tests/voice/test_russian_answers.py -v`. Expected: the hook tests for `tests/fixtures/ru/` FAIL; the fixture tests FAIL (no file).
- [ ] **Step 3: Implement** the hook line and write the fixture. Write each Russian answer as a speaker would say it for that count, from the rules of Russian plurals (one for 1 and 21, few for 2 and 22, many for 5, 11 and the teens), with the verb of "time left" agreeing with the first counted noun. Do not run the renderer to produce the text. If a test then fails, decide from the grammar which side is wrong; a wrong template is fixed in `sentences/ru/src/`, and the fixture stays as Russian says it.
- [ ] **Step 4: RULINGS.** Add `### Voice` under `## Release 1.1.0`, and in it **"Russian answers are pinned by a fixture written by hand, in the one test folder that may hold Cyrillic."** Why: the plural classes test (`assert_one_form_per_class`) proves the forms differ, not which goes with which count; a swapped "few" and "many" passed. The folder is under `tests/`, not `custom_components/`, so HACS does not ship it. Cost if wrong: a Russian answer changed on purpose needs its fixture line changed too. Tests: those of this task. Remove #27 from `docs/followups.md`.
- [ ] **Step 5: Run** the gate. Expected: all pass.
- [ ] **Step 6: Commit.**

```bash
git add .githooks/pre-commit CLAUDE.md tests/test_precommit_hook.py tests/fixtures/ru/answers.yaml tests/voice/test_russian_answers.py RULINGS.md docs/followups.md
git commit -m "Pin the Russian answers per count class with a fixture written by hand"
```

---

### Task 2: "For 1 hour 30" is 90 minutes for devices without a temperature (#26)

**Files:**
- Modify: `scripts/generate_core_commands.py` (`Scope`, `run_scopes`, `_delayed_blocks`, the module docstring), `sentences/en/src/timerify.yaml`, `sentences/ru/src/timerify.yaml`, the four generated files, `tests/voice/test_timer_by_voice.py`, `tests/voice/test_core_commands.py`, `docs/en/voice.md`, `docs/ru/voice.md`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Produces:
  - `Scope(requires: tuple[str, ...], excludes: tuple[str, ...], rules: Mapping[str, str])`. `rules` is every expansion rule of the `TimerifyRun` block, and must hold `timerify_settings` (else `run_scopes` raises `ValueError`, as it does now for none). `_delayed_blocks` writes `{COMMAND_RULE_NAME: ..., **settings.rules, "timerify_run_extras": EXTRAS_RULE}`.
  - In both sources: global rule `timerify_spelled_duration` = the body `timerify_duration` has now; global `timerify_duration` = `(<timerify_spelled_duration>|<timerify_hours_part> [and] {timerify_minutes_of_hour:minutes})` (Russian: its word for "and"); list `timerify_minutes_of_hour`: `range 1..59`. The `climate` and `water_heater` blocks of `TimerifyRun` add `timerify_duration: "<timerify_spelled_duration>"`, with a comment that a bare number after the hours is their temperature.

- [ ] **Step 1: Write the failing tests.** In `tests/voice/test_timer_by_voice.py`:

```python
async def test_for_an_hour_and_bare_minutes_runs_a_switch_for_90_minutes(...)
    # "turn on the boiler for 1 hour 30": state_of(NUMBER) == "90";
    # speech starts "Boiler runs for 1 hour and 30 minutes, until"

async def test_add_an_hour_and_bare_minutes_adds_90_minutes(...)
    # "add 1 hour 30 to the boiler" on an idle boiler: NUMBER == "90"

async def test_for_an_hour_and_a_bare_number_stays_a_thermostat_s_temperature(...)
    # fake_full_ac: "turn on the AC for 1 hour 30": NUMBER == "60"; the AC's temperature is 30

async def test_russian_hours_and_bare_minutes_run_a_switch_for_90_minutes(...)
    # every text of samples("ru", "TimerifyRun", numbers={"timerify_hours": 1,
    # "timerify_minutes_of_hour": 30}) that has both "1" and "30": NUMBER == "90"
```

  In `tests/voice/test_core_commands.py`:

```python
async def test_a_delayed_turn_on_runs_a_switch_for_hours_and_bare_minutes(...)
    # "turn on the boiler in 15 minutes for 1 hour 30": the pending command has minutes 90

def test_a_scope_carries_every_rule_of_its_block() -> None:
    # run_scopes of the en sources: the climate and water_heater scopes have
    # rules["timerify_duration"] == "<timerify_spelled_duration>"; the generated
    # delayed blocks of those scopes have that rule, the others do not
```

- [ ] **Step 2: Run** `uv run pytest tests/voice/test_timer_by_voice.py tests/voice/test_core_commands.py -v`. Expected: the new tests FAIL; `Scope` has no `rules`.
- [ ] **Step 3: Implement** the interfaces, then run both generators.
- [ ] **Step 4: Docs** (en and ru), `voice.md`, "Run for a time": a new bullet. Hours followed by a bare number of minutes, such as "for 1 hour 30", is 90 minutes. For a thermostat or a water heater the bare number is a temperature, so say "minutes" there.
- [ ] **Step 5: RULINGS.** Rewrite "The unit of the temperature is optional ..." and "The HVAC and temperature parts are scoped ..." of phase 4 where they say that "for 1 hour 30" is not understood for a device without a temperature. Add to `### Voice` **"A scope of settings carries every rule of its block, so a scope can change how a duration is said."** with Decision 2 as Why. Cost if wrong: "for 1 hour 30" said to a thermostat sets 30 degrees, as before. Remove #26 from `docs/followups.md`.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit** the files listed above: `git commit -m "Understand hours followed by bare minutes as a duration for devices without a temperature"`.

---

### Task 3: Delays past 100 are said with Timerify's lists (#29)

**Files:**
- Modify: `scripts/generate_core_commands.py` (`_DELAY_SLOT` use in `delay_rules`, the module docstring), the two generated `core_commands.yaml`, `tests/voice/test_core_commands.py` (the helper `wanted_later`: the regex that renames the delay slots now maps to `DELAY_LISTS`), `docs/en/voice.md`, `docs/ru/voice.md`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Produces: `DELAY_LISTS: Final[Mapping[str, str]]` in the generator:

```python
DELAY_LISTS = {
    "hours": "{timerify_hours:delay_hours}",
    "minutes": "({timerify_minutes:delay_minutes}|{timerify_long_minutes:delay_minutes})",
    "seconds": "{timer_seconds:delay_seconds}",
}
```

  `delay_rules` replaces each `{timer_<unit>:<unit>}` of a shape with `DELAY_LISTS[<unit>]`. The handler is unchanged: `_delay_of` already sums the three slots.

- [ ] **Step 1: Write the failing tests** in `tests/voice/test_core_commands.py`:

```python
async def test_turn_off_in_120_minutes_sets_the_timer(...)
    # boiler on; "turn off the boiler in 120 minutes": SENSOR == (START + 120 min).isoformat()

async def test_turn_on_in_2000_minutes_keeps_a_command(...)
    # NEXT == (START + 2000 min).isoformat(); speech names that time and "in 2 days"

async def test_turn_off_in_2000_minutes_is_refused_with_the_limit(...)
    # refusal == duration_out_of_range with max_hours="24"; NUMBER unchanged

async def test_turn_on_a_week_and_a_minute_ahead_is_refused_with_the_limit(...)
    # "turn on the boiler in 168 hours and 1 minute": command_too_far, days="7"; NEXT unknown

async def test_russian_delays_past_100_reach_the_handler(...)
    # samples("ru", "TimerifyDelayedCommand", takeover=True, numbers={"timerify_minutes": 120,
    # "timerify_hours": 120, "timer_seconds": 5}): each reaches TimerifyDelayedCommand
```

- [ ] **Step 2: Run** `uv run pytest tests/voice/test_core_commands.py -v`. Expected: the new tests FAIL, except the refusal of a week and a minute, which may already PASS through 100 hours and more; it stays.
- [ ] **Step 3: Implement** `DELAY_LISTS`, run `uv run python -m scripts.generate_core_commands`, and edit `wanted_later` as named.
- [ ] **Step 4: Docs** (en and ru), `voice.md`, "Turn on later and turn off later": replace the bullet "By voice, each of the hours, minutes and seconds of a delay is at most 100 ..." with: a delay can be said up to a week, as for "Run for a time": 168 hours, or 10080 minutes with minutes beyond a day in digits. Seconds go up to 100. A delay beyond a command's limit is refused, and the answer names the limit.
- [ ] **Step 5: RULINGS.** Rewrite the phase-4 "A duration is whole minutes ..." entry so the week of hours and minutes is the bound of delays too, and any entry that says a delay stops at 100. Add to `### Voice` **"A delay is said with the lists of a duration, and refused by the controller with its limit."** with Decision 3 as Why. Cost if wrong: "in 200 hours" is not understood. Remove #29 from `docs/followups.md`.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit:** `git commit -m "Say the delays of commands with Timerify's own lists of hours and minutes"`.

---

### Task 4: The phrasings the gazetteer took: days and "scheduling" (#21)

**Files:**
- Modify: both sources (`timerify_own_delay`, `timerify_delay_days`; English schedule sentences), `scripts/generate_core_commands.py` (`OWN_DELAY_RULE`, `delay_rules`), the four generated files, `tests/voice/test_core_commands.py` (`wanted_later` and `expanded` take the own delay rule into account), `tests/voice/test_schedule_by_voice.py`, `docs/en/voice.md`, `docs/ru/voice.md`, `RULINGS.md`.

**Interfaces:**
- Consumes: `delay_rules` and `DELAY_LISTS` of Task 3.
- Produces:
  - In both sources (as built after the Task 4 review): lists `timerify_delay_days` (`range 1..365`, slot `delay_days`) and `timerify_delay_weeks` (`range 1..52`, slot `delay_weeks`), plain ranges with no multiplier; fixed words `timerify_delay_words` ("a day" 1440, "half a day" 720, "a week" 10080 minutes, into `delay_minutes`); global rule `timerify_own_delay`: "in" or "after" with a count of days or weeks or a fixed word, in English also `timerify_own_span` followed by "from now", "from today" or "later"; Russian the word for "in" of the core's delays with the same counts and words in their forms. The handler counts a day as 86400 s and a week as 604800 s.
  - Generator: `OWN_DELAY_RULE: Final = "timerify_own_delay"`. `delay_rules(data, sources)` appends `<timerify_own_delay>` as one more alternative to each rule it writes, when `sources` define it.
  - English `TimerifySetSchedule`: every "schedule" of the sentences that name the device becomes `(schedule|scheduling)`.

- [ ] **Step 1: Write the failing tests.** In `tests/voice/test_core_commands.py`:

```python
async def test_turn_off_in_2_days_is_refused_and_leaves_the_boiler_on(...)
    # boiler on: duration_out_of_range, max_hours="24"; fake_target.calls == [TURN_ON]

async def test_turn_on_in_2_days_keeps_a_command_two_days_ahead(...)
    # NEXT == (START + 48 h).isoformat(); speech ends "the day after tomorrow."

async def test_turn_on_in_8_days_is_refused_with_the_limit(...)
    # command_too_far, days="7"; fake_target.calls == []

async def test_russian_delays_in_days_reach_the_handler(...)
    # samples with numbers={"timerify_delay_days": 2}: reached == "TimerifyDelayedCommand"

async def test_llm_delayed_command_takes_no_day_slot(...)
    # the tool's parameters are those of before: no "delay_days"
```

  In `tests/voice/test_schedule_by_voice.py`:

```python
async def test_turning_off_scheduling_switches_the_schedule_not_the_boiler(...)
    # "turn off scheduling for the boiler": reached == SET_SCHEDULE; switches == ("off", "off");
    # fake_target.calls unchanged
```

- [ ] **Step 2: Run** `uv run pytest tests/voice/test_core_commands.py tests/voice/test_schedule_by_voice.py -v`. Expected: the new tests FAIL, but the LLM one.
- [ ] **Step 3: Implement**, run both generators, and edit the gaps helpers as named.
- [ ] **Step 4: Docs** (en and ru), `voice.md`: in "Turn on later and turn off later", a delay can also be in days ("in 2 days"), up to 100, refused beyond the limit. In "When Home Assistant answers instead", the bullet about wordings Timerify lacks: keep the warning and the advice; replace its examples with ones that still reach Home Assistant, "turn off the boiler in 3 weeks" and "turn off the boiler tonight" (probed, Tech Stack). The Russian page says that Russian has no such matching.
- [ ] **Step 5: RULINGS.** Add to `### Voice` **"The phrasings core's gazetteer took are added as they are found; the gazetteer itself cannot be told to leave Timerify's devices alone."** Name the file:line of Tech Stack, "The gazetteer" and "2026.11", and list the phrasings added and those probed that still reach it. Why: Decision 4. Cost if wrong: a phrasing not yet found switches the device at once, in English. Tests: those of this task. #21 stays in `docs/followups.md`.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit:** `git commit -m "Take over the delays in days and the scheduling wording that core's gazetteer matched"`.

---

### Task 5: Commands at a clock time (#19)

**Files:**
- Modify: both sources (lists, rules, the English overrides, the answer), `scripts/generate_core_commands.py`, the four generated files, `custom_components/timerify/schedule.py`, `voice/commands.py`, `voice/__init__.py`, `llm.py`, `tests/voice/helpers.py` (`RESPONSE_SLOTS`), `tests/voice/test_llm.py` (its tool sets use `TOOL_HANDLER_TYPES`), `tests/voice/test_core_commands.py` (a clock twin of `gaps`), `docs/en|ru/voice.md`, `docs/en|ru/limits.md`, `docs/en|ru/pending-commands.md`, `RULINGS.md`, `docs/followups.md`.
- Create: `tests/voice/test_clock_commands.py`.

**Interfaces:**
- Consumes: `Scope.rules` (Task 2), `delay_rules` (Tasks 3, 4), `controller.async_add_command`, `controller.async_turn_off_in`.
- Produces:
  - `schedule.wall_moment(day: date, clock: time, zone: tzinfo) -> datetime`: the moment in UTC, by `datetime.combine(...).astimezone(UTC)`. `window_on` uses it.
  - `voice.commands.hour_of_day(hour: int, part: Literal["am", "pm", "night"] | None) -> int`, by Decision 5, "Reading", for an hour with a part; the nearer-of-two rule for a bare 1 to 12 is in `clock_moment`, which gets the hour, the minute, the part, the day and `now`.
  - `voice.commands.clock_moment(now: datetime, zone: tzinfo, hour: int, minute: int, part: Literal["am", "pm", "night"] | None, day: int | None) -> datetime`, by Decision 5, "Day", through `wall_moment`.
  - `DelayedCommandHandler.when(self, slots: Mapping[str, Any]) -> datetime | timedelta`: `command_when(_delay_of(slots), _clock_time_of(slots))`; `async_handle_timer` calls it.
  - `ClockCommandHandler(DelayedCommandHandler)`: `intent_type = "TimerifyCommandAt"`. `slot_schema`: `name`, `action`, `clock_hour` (`whole_slot`, 0 to 23), optional `clock_minute` (0 to 59), `clock_part` (`In(["am", "pm", "night"])`), `clock_day` (`In([0, 1, 2])`), `hours`, `minutes`, `PERCENT_SLOT`, `SETTING_SLOTS`. `when` returns `clock_moment(dt_util.utcnow(), dt_util.get_default_time_zone(), ...)`.
  - `voice/__init__.py`: `HANDLER_TYPES` adds `ClockCommandHandler`; `TOOL_HANDLER_TYPES: Final` is every handler type but it; `llm.async_get_tools` uses `TOOL_HANDLER_TYPES`.
  - Sources, both languages: lists `timerify_clock_hours` (`range 0..23`), `timerify_half_day_hours` (`range 1..12`), `timerify_clock_minutes` (`range 0..59`), `timerify_day_parts` (values out `am`, `pm`, `night`), `timerify_clock_words` (noon out 12, midnight out 0, into `clock_hour`), `timerify_clock_days` (out 0, 1, 2); rules `timerify_clock` (every form of Decision 5), `timerify_clock_after_command`, `timerify_clock_after_extras` (globally `<timerify_clock_after_command>`), `timerify_clock_before_command`. English only: `timerify_exact_clock` (every form but a bare hour and "H.MM"), and in the `climate` and `water_heater` blocks of `TimerifyRun`, `timerify_clock_after_extras` with `<timerify_exact_clock>`. Answers: `TimerifyCommandAt: delayed: "{{ timer_later(slots) }}"`.
  - Generator: `CLOCK_COMMAND: Final = "TimerifyCommandAt"`, `CLOCK_AFTER_RULE_NAME`, `CLOCK_AFTER_EXTRAS_RULE_NAME`, `CLOCK_BEFORE_RULE_NAME` (the three rule names above). `timed_sentences(block: CommandBlock, after: str | None, after_extras: str | None, before: str | None) -> list[str]` replaces `delayed_sentences`: "<command> <after>", for "on" also "<command> <extras> <after_extras>" and "<after> ... <extras>", and "<before> <command> [<extras>]"; the delayed blocks call it with `after_extras = after`. `_timed_blocks` writes the blocks of either intent; `render` adds `CLOCK_COMMAND` with `slots.action` and `response: delayed`, and raises `ValueError` when the sources lack a clock rule.
  - `tests/voice/helpers.py`: `RESPONSE_SLOTS[("TimerifyCommandAt", "delayed")] = LATER_CASES`.

- [ ] **Step 1: Write the failing tests** in `tests/voice/test_clock_commands.py`. The scenarios run in Jerusalem from `open_sunday` (Sunday 06:00) unless they say otherwise. `at(day, clock)` is `iso(day, clock)` of the Next command sensor.

```python
async def test_turn_on_at_a_clock_time_keeps_a_command_for_then(...)
    # "turn on the boiler at 7:30": state_of(NEXT) == iso(SUNDAY, "07:30");
    # speech == "Boiler turns on at 07:30."; fake_target.calls == []

@pytest.mark.parametrize(("said", "clock", "days"), [
    ("at 7:30", "07:30", 0), ("at 07:30", "07:30", 0), ("at 7 30", "07:30", 0),
    ("at 7.30", "07:30", 0), ("at 7", "07:00", 0), ("at 7 o'clock", "07:00", 0),
    ("at 7 pm", "19:00", 0), ("at 7:30 p.m.", "19:30", 0), ("at 12 am", "00:00", 1),
    ("at 12 pm", "12:00", 0), ("at noon", "12:00", 0), ("at midnight", "00:00", 1),
    ("at 19:05", "19:05", 0), ("tomorrow at 7", "07:00", 1), ("at 7 tomorrow", "07:00", 1),
    ("the day after tomorrow at 7", "07:00", 2)])
async def test_every_english_clock_form_means_its_time(said, clock, days, ...)
    # f"turn on the boiler {said}": NEXT == iso(SUNDAY + timedelta(days=days), clock)

async def test_a_clock_time_already_past_today_means_tomorrow(...)   # Review Focus 2; use "at 6:00" said at 20:00 (both 06:00 and 18:00 are past) or "at 19" said at 20:00
    # at 08:00: "turn on the boiler at 7": NEXT == iso(MONDAY, "07:00"); speech ends "tomorrow."

async def test_today_at_a_time_that_has_passed_is_refused(...)   # Review Focus 2
    # at 08:00: "turn on the boiler today at 7": command_in_past with at="07:00"; NEXT unknown

async def test_a_wall_time_the_clock_skips_happens_an_hour_later(...)   # Review Focus 3
    # 2026-03-26 23:00 Jerusalem: "turn on the boiler at 2:30":
    # NEXT == "2026-03-27T00:30:00+00:00" (03:30 on the wall)

async def test_turn_off_at_a_clock_time_sets_the_countdown_to_end_then(...)
    # boiler on: "turn off the boiler at 7:30": SENSOR == iso(SUNDAY, "07:30")

async def test_turn_off_at_a_time_more_than_a_day_ahead_is_refused(...)
    # boiler on: "turn off the boiler tomorrow at 23:00": duration_out_of_range, max_hours="24"

async def test_turn_on_at_a_time_for_a_while_with_settings(...)
    # fake_full_ac: "turn on the AC at 7:30 for an hour cooling 24 degrees":
    # the pending command has minutes 60, hvac_mode cool, temperature 24

async def test_for_an_hour_at_21_stays_a_temperature_for_a_thermostat(...)
    # "turn on the AC for an hour at 21": reached == "TimerifyRun"; temperature 21; NEXT unknown

async def test_a_thermostat_takes_an_exact_time_after_its_settings(...)
    # "turn on the AC for an hour at 7:30": reached == "TimerifyCommandAt"; NEXT == iso(SUNDAY, "07:30")

async def test_russian_clock_forms_reach_the_clock_handler(...)
    # samples("ru", "TimerifyCommandAt", takeover=True, numbers={"timerify_clock_hours": 7,
    # "timerify_clock_minutes": 30, "timerify_half_day_hours": 7}): each reaches the handler

async def test_russian_day_parts_mean_the_hours_they_name(...)
    # for each word of spoken_values("ru", "timerify_day_parts"), the sampled "7 <word>" text:
    # morning (am) 7 -> 07:00; afternoon and evening (pm) 7 -> 19:00; night 7 -> 19:00, night 2 -> 02:00

async def test_a_bare_hour_said_in_the_evening_is_that_hour_tonight(...)   # owner's decision
    # at 18:00 "turn on the boiler at 7" -> NEXT == 19:00 today; the answer says 19:00, also in Russian ("v 7")

async def test_a_bare_hour_said_early_is_that_hour_this_morning(...)   # owner's decision
    # at 06:00 "at 7" -> 07:00 today; at 20:00 "at 7" -> 07:00 tomorrow; at 18:00 "at 7:30" -> 19:30 today

async def test_an_hour_past_twelve_is_a_24_hour_clock(...)
    # at 06:00 "at 19" -> 19:00 today; at 20:00 "at 0:30" -> 00:30 tomorrow

async def test_tomorrow_with_a_bare_hour_is_the_morning_one(...)   # owner's decision
    # at 18:00 "tomorrow at 7" -> 07:00 tomorrow; "today at 7" at 18:00 -> 19:00 today
```

  In `tests/voice/test_llm.py`: `test_the_clock_sentences_add_no_llm_tool`, the tool names equal `{h.tool_name for h in TOOL_HANDLER_TYPES}` and there are as many tools as `TOOL_HANDLER_TYPES`. In `tests/voice/test_core_commands.py`: `test_the_file_says_every_command_at_a_clock_time_for_every_kind_of_device`, the twin of `gaps` for `CLOCK_COMMAND`.
- [ ] **Step 2: Run** `uv run pytest tests/voice/test_clock_commands.py tests/voice/test_llm.py tests/voice/test_core_commands.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the interfaces, then both generators. Unit-test `hour_of_day` and `clock_moment` inside `test_clock_commands.py` only if a scenario leaves a branch unexercised.
- [ ] **Step 4: Docs** (en and ru):
  - `voice.md`: the table gains "Turn on at a time" ("turn on the boiler at 7:30", "vklyuchi Boiler v 7:30") and "Turn off at a time". "What each sentence does" gains **Turn on or off at a time**: the forms and the day words of Decision 5; an hour from 1 to 12 without "am", "pm" or a Russian time of day is the nearer of its morning and evening times; 0 and 13 to 23 are a 24-hour clock; a time without a day is the next one, today or tomorrow, and "today" at a time that has passed is refused; a time the clock change skips or repeats follows [the schedules' rule](schedules.md#clock-changes-and-time-zones); turning on keeps a pending command; turning off sets the countdown, at most a day ahead. For a thermostat or a water heater, after its settings say the time with minutes or "o'clock". Remove the clock item from "What you cannot say", and the sentence "An agent can plan a command at a clock time, which the built-in agent's sentences cannot" under "Tools for LLM agents".
  - `limits.md`, `### Voice`: drop the clock sentences; keep "taking time off".
  - `pending-commands.md`: "for example 'turn on the boiler in 15 minutes' or 'at 7:30'".
- [ ] **Step 5: RULINGS.** Rewrite the phase-4 entry "Commands at a clock time are for an LLM only" to Decision 5. Add to `### Voice` **"A clock time is a sentence-only intent, not a tool."** with the reason of Decision 5, "Intent". Cost if wrong: a speaker who says "at 7" at 18:00 meaning tomorrow morning hears "19:00" in the answer and must say "in the morning" or "am". Remove #19 from `docs/followups.md`.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit:** `git commit -m "Understand commands at a clock time in English and Russian"`.

---

### Task 6: A name with yo is matched when said with ye (#23)

**Files:**
- Create: `custom_components/timerify/spelling.py`.
- Modify: `custom_components/timerify/schedule.py` (`title_key`; drop `_YO` and `_YE`), `voice/sentences.py`, `voice/files.py` (`_write_if_changed`), `tests/voice/test_sentence_validation.py` (the calls of `validate` and `build` take the new shapes), `tests/voice/test_voice_entry.py`, `tests/voice/test_schedule_by_voice.py`, `docs/en|ru/voice.md`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Produces:
  - `spelling.fold_yo(text: str) -> str`: each `"\N{CYRILLIC SMALL LETTER IO}"` a `"\N{CYRILLIC SMALL LETTER IE}"`, and the capitals alike.
  - `schedule.title_key` folds with `fold_yo`.
  - `sentences.spoken_variants(text: str) -> tuple[str, ...]`: `spoken_form(text)` and `fold_yo` of it, the second only when it differs; `()` for a text of nothing but punctuation. Callers pass raw text, never `spoken_form` output (Task 6 fix round: `spoken_form` is not idempotent; `spoken_mode` was removed, a mode is passed as `mode.replace("_", " ")`).
  - `BuiltSentences(data: dict[str, Any], said: Mapping[str, tuple[str, ...]])`, frozen: `said` maps `LIST_TARGET`, `LIST_INTERVAL` and `LIST_MODE` to the unescaped spoken text of each of their values, in order. `build(...) -> BuiltSentences`. Each name, title and mode is listed once per variant, with the same `out` and context.
  - `validate(language: str, built: Mapping[str, Any], said: Mapping[str, Sequence[str]]) -> None`: `_check_names` compares the parsed text of each value with `normalize_text` of its `said` text, `zip(..., strict=True)`. `NAME_LISTS` goes.
  - `voice/files.py`: `_write_if_changed` renders `built.data` and validates the read-back text with `built.said`.

- [ ] **Step 1: Write the failing tests.** Names are built from code points: `YO_NAME = "\N{CYRILLIC CAPITAL LETTER IO}" + "lka"` and its folded twin.

```python
async def test_a_russian_name_with_yo_is_matched_said_with_ye(...)   # test_voice_entry.py
    # a timer on a target called YO_NAME; Voice settings in ru; a sample of "time left"
    # with names=(fold_yo(YO_NAME),): reached == "TimerifyTimeLeft"; the answer starts with YO_NAME

async def test_a_russian_name_with_yo_is_still_matched_as_written(...)
    # the same with names=(YO_NAME,)

async def test_an_interval_title_with_yo_is_switched_said_with_ye(...)   # test_schedule_by_voice.py
    # an interval titled with a yo; "turn off the <folded title> schedule of the Boiler": off

def test_every_value_is_listed_under_both_spellings() -> None:   # test_sentence_validation.py
    # build with a name, a title and a mode that each have a yo: each list has both values,
    # with one out; said lists the same texts

def test_a_value_not_read_as_the_text_it_was_built_from_is_refused() -> None:
    # validate with said altered for one value: InvalidSentences naming that value
```

- [ ] **Step 2: Run** `uv run pytest tests/voice -k "yo or both_spellings or built_from" -v`. Expected: FAIL.
- [ ] **Step 3: Implement**, and edit the named tests to the new shapes without changing what they assert.
- [ ] **Step 4: Docs** (en and ru), `voice.md`, "Use the Voice settings entry": a name or title with the Russian letter yo is listed twice, with yo and with ye, so either is understood. "Copy the sentences by hand": list such a name twice yourself.
- [ ] **Step 5: RULINGS.** Rewrite the phase-4 entries "The names are listed as the built-in agent lists them ..." and "Titles are compared by `schedule.title_key` ..." to say both spellings are listed and `fold_yo` is the one fold. Add Decision 6 to `### Voice`. Cost if wrong: the file has one more value per such name. Remove #23 from `docs/followups.md`.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit:** `git commit -m "List names, titles and modes with yo under both spellings, folded in one place"`.

---

### Task 7: Mode words from Home Assistant's translations (#24)

**Files:**
- Modify: `voice/sentences.py`, `voice/files.py` (`async_sync` gets the words per language and passes them on), `tests/conftest.py` (`provide_fake` and the `provide` of `provide_target`), `tests/voice/test_voice_entry.py` (`test_every_language_gets_the_same_modes`: the same `out` values, not the same `in`), `tests/voice/test_sentence_validation.py`, `docs/en|ru/voice.md`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Consumes: `spoken_variants`, `BuiltSentences` (Task 6).
- Produces:
  - `ModeSource(domain: str, platform: str | None, translation_key: str | None, device_class: str | None, attribute: str, modes: tuple[str, ...])`, frozen. `attribute` is the `SettingChoice.name` (`fan_mode`, `preset_mode`, `mode`, `operation_mode`). `platform` and `translation_key` come from the registry entry, `device_class` from the state's attribute.
  - `VoiceSettingValues.mode_sources: tuple[ModeSource, ...]`, with a property `modes -> frozenset[str]` (every mode of every source).
  - `async async_mode_words(hass: HomeAssistant, language: str, sources: Sequence[ModeSource]) -> dict[str, frozenset[str]]`: each raw mode to its translated words, by Decision 7's order, through `async_get_translations(hass, language, "entity", platforms)` and `async_get_translations(hass, language, "entity_component", domains)`.
  - `build(sources, names, settings, intervals, mode_words: Mapping[str, frozenset[str]] = {}) -> BuiltSentences`. `_mode_entries(modes, words)`: per mode, sorted, `spoken_variants(mode.replace("_", " "))` then `spoken_variants(word)` of each word, sorted; a value whose casefolded text another mode has already is left out.
  - `tests/conftest.py`: `provide_fake(..., platform: str | None = None, translation_key: str | None = None)`; the registry entry takes that platform (default `<object_id>_maker`, as now) and translation key.

- [ ] **Step 1: Write the failing tests** in `tests/voice/test_voice_entry.py`. The expected words are read from Home Assistant in the test, never written: `word = (await async_get_translations(hass, "ru", "entity", ["demo"]))["component.demo.entity.fan.demo.state_attributes.preset_mode.state.sleep"]`.

```python
async def test_a_fan_preset_is_listed_in_the_words_of_its_integration(...)
    # a fan with platform "demo", translation_key "demo", presets ["sleep", "turbo_x"]:
    # listed(ru file, LIST_MODE) has (word, "sleep"), ("sleep", "sleep"), ("turbo x", "turbo_x")

async def test_a_russian_preset_word_runs_the_fan_in_that_preset(...)
    # a ru sample of "turn on for 10 minutes" with texts={"timerify_mode": word}:
    # the fan is turned on with preset_mode "sleep"

async def test_a_thermostat_fan_mode_uses_the_words_of_the_climate_domain(...)
    # fake_full_ac with fan_modes ["auto", "high"]: the ru file lists the climate domain's
    # word for "high" (entity_component._.state_attributes.fan_mode.state.high) and "high"

async def test_an_english_house_gets_russian_mode_words_in_russian(...)   # Review Focus 5
    # hass.config.language = "en"; Voice settings in en and ru: the ru file has the ru word,
    # the en file the en word, for the same mode

async def test_a_word_said_like_another_mode_is_left_out(...)   # test_sentence_validation.py
    # build with mode_words {"strong": {"Turbo"}} and modes {"strong", "turbo"}:
    # "Turbo" is not listed for "strong"; "turbo" is listed for "turbo"
```

- [ ] **Step 2: Run** `uv run pytest tests/voice/test_voice_entry.py tests/voice/test_sentence_validation.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** `async_sync` computes `voice_setting_values` once, then `await async_mode_words(...)` per chosen language before the executor job.
- [ ] **Step 4: Docs** (en and ru), `voice.md`: in "Use the Voice settings entry", the modes of fans, humidifiers and the like are listed in the words Home Assistant shows for them in that language, and as the device names them. A mode without a word in that language is listed in English, as the interface shows it. Remove the item about Latin modes from "What you cannot say". The manual route keeps the raw modes; say that a translated word can be listed there too.
- [ ] **Step 5: RULINGS.** Rewrite the phase-4 entry "Every setting of §5.4 ..." where it says the other modes are the device's strings. Add Decision 7 to `### Voice`, naming `helpers/translation.py:335-358`, `:497-533` and `:208-256`. Cost if wrong: an English word in the Russian file for a mode no translation covers. Remove #24 from `docs/followups.md`.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit:** `git commit -m "Say the modes of devices in the words Home Assistant translates them to"`.

---

### Task 8: HVAC words per set of modes (#25)

**Files:**
- Modify: `custom_components/timerify/const.py`, `voice/sentences.py`, `tests/voice/test_timer_by_voice.py`, `tests/voice/test_sentence_validation.py` (the entries that read `VoiceSettingValues.hvac_modes` read `hvac_sets`), `tests/voice/test_voice_entry.py`, `docs/en|ru/voice.md`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Consumes: Task 5's clock blocks, Task 7's `VoiceSettingValues`.
- Produces:
  - `const.CONTEXT_HVAC_MODES: Final = "timerify_hvac_modes"`.
  - `sentences.hvac_key(modes: Iterable[str]) -> str`: the modes sorted, joined by a space.
  - `VoiceName(name, domain, hvac_modes: frozenset[str] | None = None)` (Task 6 dropped the derived `spoken` field); `build` writes `context: {"domain": ..., CONTEXT_HVAC_MODES: hvac_key(...)}` when set. `voice_names` sets it for every thermostat target, its supported HVAC modes or none.
  - `VoiceSettingValues.hvac_sets: frozenset[frozenset[str]]` replaces `hvac_modes`.
  - `build`: Decision 8. The copies come in the order of `hvac_key`; with no set, the climate blocks go.

- [ ] **Step 1: Write the failing tests.** `fake_full_ac` has every mode; a second AC, `climate.small_ac` called Small AC, has `off`, `cool` and `fan_only`.

```python
async def test_each_ac_understands_only_its_own_hvac_modes(...)   # test_timer_by_voice.py
    # "turn on the AC for an hour heating": runs with hvac_mode heat;
    # "turn on the small AC for an hour cooling": runs with hvac_mode cool

async def test_a_mode_only_another_ac_has_switches_neither_on(...)   # Review Focus 1
    # "turn on the small AC for an hour heating": response is an error;
    # small_ac.calls == [] and full_ac.calls == []; no pending command

async def test_a_delayed_turn_on_takes_only_the_hvac_modes_of_its_ac(...)
    # "turn on the small AC in 15 minutes heating": no pending command, no call;
    # "... cooling": a pending command with hvac_mode cool

async def test_russian_hvac_words_are_scoped_per_ac(...)
    # ru samples of TimerifyRun for Small AC with each word of spoken_values("ru",
    # "timerify_hvac_mode"): understood exactly for cool and fan_only

async def test_a_hand_listed_ac_keeps_every_hvac_word(...)
    # copy_sentences(hass, ["AC"], {"AC": "climate"}): "turn on the AC for an hour drying" runs

def test_each_set_of_hvac_modes_adds_its_climate_blocks_once() -> None:   # test_sentence_validation.py
    # build with 1, 2 and 3 sets: the data blocks that require climate are 3, 6, 9 in en
    # and ru; two thermostats with the same set give one copy; every copy requires its key
    # and lists only its words
```

- [ ] **Step 2: Run** `uv run pytest tests/voice -k "hvac or each_ac or neither_on" -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** Measure `len(render(built.data))` for one set and for three sets in each language, and note the growth for RULINGS.
- [ ] **Step 4: Docs** (en and ru), `voice.md`: in "Use the Voice settings entry", each thermostat is understood with the HVAC modes it has. Remove the item about two thermostats from "What you cannot say". "Copy the sentences by hand" says that there every thermostat takes every HVAC word, and a mode it lacks is refused.
- [ ] **Step 5: RULINGS.** Rewrite the phase-4 entry "The list of HVAC words is the union ..." to Decision 8, with the measured growth. Cost if wrong: in English, a sentence with a mode the AC lacks is not understood (Review Focus 1 pins that nothing is switched). Remove #25 from `docs/followups.md`.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit:** `git commit -m "Scope the HVAC words of the sentences to the modes of each thermostat"`.

---

### Task 9: A generated interval title is said by its start time (#22)

**Files:**
- Modify: `custom_components/timerify/schedule.py`, `controller.py` (`async_set_schedule_enabled`), `voice/sentences.py` (`interval_names`), `voice/intervals.py` (the tool's description), `tests/voice/test_schedule_by_voice.py`, `docs/en|ru/voice.md`, `docs/en|ru/schedules.md`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Consumes: `spoken_variants` (Task 6), `title_key`.
- Produces:
  - `schedule.has_generated_title(subentry: ConfigSubentry) -> bool`: `subentry.data.get(CONF_GENERATED_TITLE) == subentry.title`.
  - `schedule.start_aliases(start: str) -> tuple[str, ...]`: Decision 9's forms of an `HH:MM`, without repeats, in that order.
  - `schedule.spoken_aliases(subentry: ConfigSubentry) -> tuple[str, ...]`: `start_aliases(subentry.data[CONF_START])` for a generated title, `()` otherwise.
  - The controller's lookup keeps an interval when `title_key(asked)` is its title's key or the key of one of its aliases. The refusal still lists titles.
  - `interval_names` adds `VoiceTitle(alias)` for each alias of every loaded timer, once.
  - `SetScheduleHandler.description` gains: "An interval that still has the title Timerify gave it can also be named by its start time, such as '6:30'."

- [ ] **Step 1: Write the failing tests** in `tests/voice/test_schedule_by_voice.py`, with intervals that keep their generated titles:

```python
async def test_a_generated_title_is_said_by_its_start_time(...)
    # "turn off the 6:30 schedule of the boiler": MORNING off, EVENING on;
    # speech == "The 06:30–07:15, Mon–Sun schedule of Boiler is off."

async def test_the_start_time_switches_every_interval_that_starts_then(...)
    # 06:30-07:15 Mon-Fri and 06:30-08:00 Sat-Sun: "turn off the 06:30 schedule ...": both off

async def test_a_start_time_only_another_timer_has_is_refused(...)
    # the kettle has a generated 18:00 interval, the boiler none at 18:00:
    # unknown_interval refusal listing the boiler's titles

async def test_a_title_the_user_gave_is_not_said_by_its_start_time(...)
    # boiler_schedule (renamed Morning and Evening): "turn off the 6:30 schedule ...":
    # switches unchanged; not reached, or refused

async def test_russian_start_time_switches_the_interval(...)
    # a ru sample of TimerifySetSchedule with texts={"timerify_interval": "6:30"}: MORNING off

async def test_llm_names_an_interval_by_its_start_time(...)
    # timerify__set_schedule with interval "6.30", enabled false: MORNING off

def test_start_aliases_are_the_ways_a_recogniser_writes_the_time() -> None:
    # start_aliases("06:30") == ("6:30", "06:30", "6.30", "06.30");
    # start_aliases("18:00") == ("18:00", "18.00")
```

- [ ] **Step 2: Run** `uv run pytest tests/voice/test_schedule_by_voice.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Docs** (en and ru). `voice.md`, "Switch the schedule": an interval whose title Timerify made can be said by its start time, "turn off the 6:30 schedule of the boiler". That switches every interval of the timer that starts then. Change the item "An interval by the title it is made with" of "What you cannot say" to the days: the days of such a title cannot be said. `schedules.md`, after "You can rename the interval ...": by voice, an interval with Timerify's title is said by its start time; a renamed one by its new name.
- [ ] **Step 5: RULINGS.** Rewrite the phase-4 entries "The schedule is switched as a whole, or one interval by its title ..." and "Titles are compared by ..." with the aliases. Add Decision 9 to `### Voice`. Cost if wrong: two intervals that start together on different days are switched together; the days tell them apart only by title. Remove #22 from `docs/followups.md`.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit:** `git commit -m "Let an interval titled by Timerify be said by its start time"`.

---

### Task 10: The voice file follows the state of the targets (#20)

**Files:**
- Modify: `voice/sentences.py`, `voice/files.py`, `tests/voice/test_voice_entry.py`, `docs/en|ru/voice.md`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Consumes: `VoiceName` (Task 8), `ModeSource` (Task 7).
- Produces:
  - `TargetVoice(names: tuple[VoiceName, ...], hvac_modes: frozenset[str] | None, mode_sources: tuple[ModeSource, ...])`, frozen.
  - `@callback target_voice(hass: HomeAssistant, entity_id: str) -> TargetVoice`: what the file says of one target. `voice_names` and `voice_setting_values` are built from the `target_voice` of each loaded timer.
  - `SentenceFiles`: `_written: dict[str, TargetVoice]`, set by `async_sync` from the inputs it used, whether the write succeeded or not. `_follow_targets()` replaces its `async_track_state_change_event` subscription with one on the current targets, after each sync, and the entry's unload ends it. `_target_state_changed(event)` calls `_changed()` when `target_voice(hass, entity_id)` differs from `_written.get(entity_id)`.

- [ ] **Step 1: Write the failing tests** in `tests/voice/test_voice_entry.py`:

```python
async def test_a_yaml_switch_renamed_by_its_state_is_listed_by_its_new_name(...)
    # provide_target(registered=False, name="Pump"); timer and Voice settings; the state is
    # written again with friendly_name "Well pump"; advance VOICE_SYNC_COOLDOWN:
    # listed(LIST_TARGET) has "Well pump" and not "Pump"; "turn on the well pump" runs it

async def test_a_new_mode_a_device_reports_is_listed(...)
    # fake_fan's state gains a preset in preset_modes: listed(LIST_MODE) has it after the cooldown

async def test_a_registered_thermostat_that_gains_a_fan_mode_is_listed(...)

async def test_a_target_switching_on_and_off_rewrites_nothing(...)   # Review Focus 4
    # after the first write: on, off, on, and fake_full_ac's current_temperature reported
    # three times, each followed by the cooldown: conversation_reloads(hass) == [] and the
    # file's text unchanged

async def test_a_state_change_after_the_entry_is_unloaded_writes_nothing(...)
```

- [ ] **Step 2: Run** `uv run pytest tests/voice/test_voice_entry.py -v`. Expected: the new tests FAIL, but the last two, which may PASS already; they stay.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Docs** (en and ru), `voice.md`, "Use the Voice settings entry": add to the list of what makes Timerify write the file "a device reports another name or another list of modes". Remove the bullet "Names are listed when a timer is set up ... picked up at the next change".
- [ ] **Step 5: RULINGS.** Rewrite the phase-4 entry "The file is rewritten when ..." to drop "(issue #20)" and say the state is followed. Add Decision 10 to `### Voice`. Cost if wrong: one comparison of one target per state change of a target. Remove #20 from `docs/followups.md`.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit:** `git commit -m "Rewrite the voice file when a target reports another name or modes"`.

---

### Task 11: The full gate

**Files:** none, unless a check fails, and then only the files of the fix.

- [ ] **Step 1: Run the full gate on the final tree:**
  - `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run mypy`;
  - hassfest: `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest`;
  - `npm --prefix card ci`, `npm --prefix card run build:check`, `npm --prefix card run typecheck` and `npm --prefix card test`;
  - then compare `date -u +%s` with `docker run --rm alpine date -u +%s`, and run `npm --prefix card run e2e`.
  - `git grep -nP '\p{Cyrillic}' -- ':!README.ru.md' ':!docs/ru' ':!custom_components/timerify/translations' ':!custom_components/timerify/sentences' ':!tests/fixtures/ru'` prints only `translations/` lines of languages other than `en`, if any; nothing else.

  Expected: all pass. No string of the card changed, so the bundle is current.
- [ ] **Step 2: #21.** With the owner's go-ahead, label klimofey/timerify#21 `upstream` and comment, in English: the phrasings this part made Timerify's (Task 4 and the clock times of Task 5); the phrasings probed that still reach the gazetteer ("turn off the boiler in 3 weeks", "turn off the boiler tonight"); that 2026.11.0b1 has no way to exclude a custom intent's names (`conversation/default_agent.py:502`, `:720-734`, `gazetteer.py:96-136`); and that a request to Home Assistant waits for the owner's consent.
- [ ] **Step 3: Report** the counts of pytest, vitest and E2E, against the starting point of 2286 pytest tests. Ask the owner to read `tests/fixtures/ru/answers.yaml` once (Decision 11) and to confirm the CLAUDE.md change of Task 1. Give the PR body line of Global Constraints, and say that #21 stays open, labelled `upstream`.
