"""The proof that the built-in agent can read the sentence files before they are
written: what it refuses, and that it lets the shipped sentences through. A file the
agent cannot load breaks it for the whole language, so each way a file can be unfit is
tried here on the shipped sentences with the names of a timer's target in them.
"""

import copy
import re
from collections.abc import Callable
from typing import Any

import pytest
import yaml

from custom_components.timerify.const import (
    CONTEXT_HVAC_MODES,
    LIST_HVAC_MODE,
    LIST_INTERVAL,
    LIST_MODE,
    LIST_TARGET,
    MANAGED_HEADER,
    VOICE_LANGUAGES,
)
from custom_components.timerify.spelling import fold_yo
from custom_components.timerify.voice.sentences import (
    BuiltSentences,
    InvalidSentences,
    ModeSource,
    VoiceName,
    VoiceSettingValues,
    VoiceTitle,
    build,
    dump_sentences,
    hvac_key,
    load_sources,
    read_back,
    render,
    spoken_variants,
    validate,
)

NAMES = tuple(VoiceName(name, "switch") for name in ("Boiler", "Boiler (main)"))
"""A target known by a plain name and by one with characters in it that a sentence
template would read as its own."""

Mutation = Callable[[dict[str, Any]], object]


def modes_of_devices(*modes: str) -> VoiceSettingValues:
    """The settings of a fan that takes the presets `modes`, which no integration has
    words for."""
    return VoiceSettingValues(
        mode_sources=(ModeSource("fan", None, None, None, "preset_mode", modes),)
    )


def built_sentences(language: str = "en") -> BuiltSentences:
    """The shipped sentences of `language` with the names of `NAMES` in them."""
    return build(load_sources(language), NAMES)


def timerify_sentences(built: dict[str, Any]) -> list[str]:
    """The sentences of the first data block of the first intent in `built`."""
    return built["intents"][next(iter(built["intents"]))]["data"][0]["sentences"]


def first_name(built: dict[str, Any]) -> dict[str, Any]:
    name: dict[str, Any] = built["lists"][LIST_TARGET]["values"][0]
    return name


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_the_shipped_sentences_with_names_are_fit_to_be_read(language: str) -> None:
    built = built_sentences(language)

    validate(language, built.data, built.said)


def test_a_language_home_assistant_has_no_sentences_in_is_refused() -> None:
    built = built_sentences()

    with pytest.raises(InvalidSentences, match="no sentences in zz"):
        validate("zz", built.data, built.said)


@pytest.mark.parametrize(
    ("mutation", "complaint"),
    [
        pytest.param(
            lambda built: built["lists"].update({"timerify_bad": {"wrong": 1}}),
            "Unknown slot list type",
            id="a list that is neither values nor a range",
        ),
        pytest.param(
            lambda built: timerify_sentences(built).append("how long [is left"),
            "ParseError",
            id="a sentence that is not a template, found only when it is parsed",
        ),
        pytest.param(
            lambda built: timerify_sentences(built).append("how long on {nothing}"),
            "No list nothing",
            id="a list that is not there",
        ),
        pytest.param(
            lambda built: timerify_sentences(built).append("how long <nothing>"),
            "No expansion rule nothing",
            id="an expansion rule that is not there",
        ),
        pytest.param(
            lambda built: built.setdefault("expansion_rules", {}).update(
                {"timerify_rule": "{nothing} <nothing_either>"}
            ),
            "No ",
            id="a rule of Timerify's own, that no sentence uses, that is broken",
        ),
        pytest.param(
            lambda built: first_name(built).update({"in": "Boiler|Heater"}),
            "would not be matched as said",
            id="a name that is read as a choice of two",
        ),
        pytest.param(
            lambda built: first_name(built).update({"in": "[Boiler]"}),
            "would not be matched as said",
            id="a name that is read as an optional word",
        ),
        pytest.param(
            lambda built: first_name(built).update({"in": "Heater"}),
            "would not be matched as said",
            id="a name that is another text",
        ),
        pytest.param(
            lambda built: first_name(built).update({"in": "Boiler (main"}),
            "ParseError",
            id="a name that is not a template at all",
        ),
    ],
)
def test_sentences_the_built_in_agent_would_not_read_as_wanted_are_refused(
    mutation: Mutation, complaint: str
) -> None:
    built = built_sentences()
    mutation(built.data)

    with pytest.raises(InvalidSentences, match=complaint):
        validate("en", built.data, built.said)


def test_a_rule_that_is_not_timerifys_is_not_the_sentences_to_judge() -> None:
    """Rules of the core sentences refer to lists of their own, which `validate` does
    not claim to check: only what Timerify defines or uses is its to answer for."""
    built = built_sentences()
    built.data.setdefault("expansion_rules", {})["somebody_elses"] = "{nothing}"

    validate("en", built.data, built.said)


def test_building_the_sentences_leaves_the_sources_as_they_were() -> None:
    sources = load_sources("en")
    before = copy.deepcopy(sources)

    build(sources, NAMES)

    assert sources == before


def test_building_without_names_gives_an_empty_list_of_targets() -> None:
    built = build(load_sources("en"), [])

    assert built.data["lists"][LIST_TARGET] == {"values": []}
    assert built.said[LIST_TARGET] == ()


def test_a_name_is_listed_as_said_and_as_meant_with_the_domain_of_its_target() -> None:
    built = built_sentences()

    assert built.data["lists"][LIST_TARGET]["values"][1] == {
        "in": r"Boiler \(main\)",
        "out": "Boiler (main)",
        "context": {"domain": "switch"},
    }
    assert built.said[LIST_TARGET] == ("Boiler", "Boiler (main)")


def test_a_file_says_that_it_is_managed_and_holds_the_sentences() -> None:
    built = built_sentences()

    text = render(built.data)

    assert text.startswith(f"{MANAGED_HEADER}\n")
    assert yaml.safe_load(text) == built.data


def test_a_text_of_several_lines_is_written_as_a_block() -> None:
    """The file is one that people open: an answer is as readable in it as it was
    written, not a line of escapes."""
    text = dump_sentences({"answer": "{% if a %}\n  yes\n{% endif %}", "short": "one"})

    assert text == "answer: |-\n  {% if a %}\n    yes\n  {% endif %}\nshort: one\n"


@pytest.mark.parametrize(
    "text",
    [
        "one\ntwo",
        "one\ntwo\n",
        "one\n\n\ntwo\n\n",
        "  leading\nspace",
        "trailing space \nin the middle",
        "tab\tinside\nand more",
        "\nstarts on a new line",
        "Unicode caf\u00e9\nand more",
    ],
)
def test_a_text_written_as_a_block_is_read_back_as_it_was(text: str) -> None:
    assert read_back(dump_sentences({"answer": text, "after": 1})) == {
        "answer": text,
        "after": 1,
    }


def test_the_text_of_a_file_is_read_as_the_built_in_agent_reads_it() -> None:
    assert read_back("name: yes\nother: 'yes'\n") == {"name": True, "other": "yes"}


SETTINGS = VoiceSettingValues(
    hvac_sets=frozenset({frozenset({"cool", "heat_cool", "fan_only"})}),
    mode_sources=(
        ModeSource("climate", None, None, None, "fan_mode", ("low",)),
        ModeSource(
            "fan", None, None, None, "preset_mode", ("eco_plus", "Turbo (quiet)")
        ),
    ),
)
"""What an air conditioner and a fan with strange presets between them can be turned
on with."""


def built_with_settings(language: str = "en") -> BuiltSentences:
    """The shipped sentences of `language` with names and `SETTINGS` in them."""
    return build(load_sources(language), NAMES, SETTINGS)


def climate_blocks(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Every data block of the intents in `data` that requires the domain `climate`,
    alone or in a list, in the order the file has them."""
    blocks: list[dict[str, Any]] = []
    for intent in data["intents"].values():
        for block in intent["data"]:
            domains = block.get("requires_context", {}).get("domain", [])
            if "climate" in ([domains] if isinstance(domains, str) else domains):
                blocks.append(block)
    return blocks


HVAC_SETS = (
    frozenset({"cool", "fan_only"}),
    frozenset({"cool", "heat", "heat_cool"}),
    frozenset({"auto"}),
)
"""Three different sets of HVAC modes that thermostats can have."""


def scoped(block: dict[str, Any], words: list[dict[str, str]], modes: set[str]) -> dict:
    """The block of the sources as it is once it is for the thermostats that have
    `modes`, which are said with those of `words` that mean one of them."""
    copy_of = copy.deepcopy(block)
    copy_of["requires_context"][CONTEXT_HVAC_MODES] = hvac_key(modes)
    copy_of["lists"] = {
        LIST_HVAC_MODE: {"values": [w for w in words if w["out"] in modes]}
    }
    return copy_of


def test_the_key_of_a_set_of_hvac_modes_does_not_depend_on_their_order() -> None:
    assert hvac_key(["fan_only", "cool", "heat"]) == "cool fan_only heat"
    assert hvac_key({"heat", "cool", "fan_only"}) == "cool fan_only heat"
    assert hvac_key([]) == ""


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_the_words_for_a_mode_are_those_of_the_modes_the_thermostats_have(
    language: str,
) -> None:
    """Of the words of the sources only those that mean a mode the thermostats of the
    set have are kept, in the order of the sources, in a list of the blocks for them;
    the list of the file itself has none."""
    sources = load_sources(language)

    built = build(sources, NAMES, SETTINGS)

    assert built.data["lists"][LIST_HVAC_MODE] == {"values": []}
    blocks = climate_blocks(built.data)
    assert len(blocks) == 3
    for block in blocks:
        kept = block["lists"][LIST_HVAC_MODE]["values"]
        assert [value["out"] for value in kept] == ["cool", "fan_only", "heat_cool"]
        assert kept == [
            value
            for value in sources["lists"][LIST_HVAC_MODE]["values"]
            if value["out"] in {"cool", "fan_only", "heat_cool"}
        ]


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
@pytest.mark.parametrize("count", [1, 2, 3])
def test_each_set_of_hvac_modes_adds_its_climate_blocks_once(
    language: str, count: int
) -> None:
    """The sources have three blocks for thermostats (run, delayed, at a clock time).
    Each distinct set of modes has a copy of each, which requires the key of the set
    and has the words of its modes only, and nothing else of the block is changed: the
    copies come in the order of the keys, one block after the other."""
    sources = load_sources(language)
    shipped = climate_blocks(sources)
    assert len(shipped) == 3
    words = sources["lists"][LIST_HVAC_MODE]["values"]
    sets = HVAC_SETS[:count]

    built = build(sources, NAMES, VoiceSettingValues(hvac_sets=frozenset(sets)))

    assert climate_blocks(built.data) == [
        scoped(block, words, set(modes))
        for block in shipped
        for modes in sorted(sets, key=hvac_key)
    ]
    validate(language, built.data, built.said)


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_without_a_set_of_hvac_modes_the_sentences_for_thermostats_go(
    language: str,
) -> None:
    """No thermostat is a target, so no sentence of the file is for one; the other
    blocks stay."""
    sources = load_sources(language)

    built = build(sources, NAMES)

    assert climate_blocks(built.data) == []
    before = len(sources["intents"]["TimerifyRun"]["data"])
    assert len(built.data["intents"]["TimerifyRun"]["data"]) == before - 1
    validate(language, built.data, built.said)


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_a_thermostat_with_no_mode_to_be_turned_on_in_has_a_set_of_its_own(
    language: str,
) -> None:
    """The empty set is a set: a thermostat that can only be off is still run for a
    time, with no word for a mode to say."""
    built = build(
        load_sources(language),
        NAMES,
        VoiceSettingValues(hvac_sets=frozenset({frozenset()})),
    )

    blocks = climate_blocks(built.data)
    assert len(blocks) == 3
    for block in blocks:
        assert block["requires_context"][CONTEXT_HVAC_MODES] == ""
        assert block["lists"][LIST_HVAC_MODE] == {"values": []}
    validate(language, built.data, built.said)


def test_a_block_for_climate_and_another_domain_is_refused() -> None:
    """Only the blocks that are for thermostats alone can be copied for each set of
    modes: Timerify's own sources have no other, so one is a mistake in them."""
    sources = load_sources("en")
    sources["intents"]["TimerifyRun"]["data"].append(
        {
            "sentences": ["run {timerify_target:name}"],
            "requires_context": {"domain": ["climate", "water_heater"]},
        }
    )

    with pytest.raises(InvalidSentences, match="climate"):
        build(sources, NAMES, SETTINGS)


def test_a_thermostat_is_listed_with_the_key_of_the_modes_it_has() -> None:
    names = (
        VoiceName("AC", "climate", frozenset({"heat", "cool"})),
        VoiceName("Heater", "climate", frozenset()),
        VoiceName("Boiler", "switch"),
    )

    built = build(load_sources("en"), names)

    assert [
        value["context"] for value in built.data["lists"][LIST_TARGET]["values"]
    ] == [
        {"domain": "climate", CONTEXT_HVAC_MODES: "cool heat"},
        {"domain": "climate", CONTEXT_HVAC_MODES: ""},
        {"domain": "switch"},
    ]


def test_the_modes_of_the_devices_are_listed_as_said_and_as_meant() -> None:
    """Sorted, so that the file does not change when the devices list them in another
    order; underscores are spaces when said and template characters are escaped."""
    built = built_with_settings()

    assert built.data["lists"][LIST_MODE]["values"] == [
        {"in": r"Turbo \(quiet\)", "out": "Turbo (quiet)"},
        {"in": "eco plus", "out": "eco_plus"},
        {"in": "low", "out": "low"},
    ]
    assert built.said[LIST_MODE] == ("Turbo (quiet)", "eco plus", "low")


def test_the_words_of_a_mode_are_listed_after_its_name_in_the_order_of_the_words() -> (
    None
):
    """Each mode is said as the device names it first, then in each word, the words in
    order; a word is escaped as a name is, and means the mode as the device names it."""
    built = build(
        load_sources("en"),
        NAMES,
        modes_of_devices("eco_plus", "low"),
        mode_words={
            "eco_plus": frozenset({"Saver (plus)", "Economy"}),
            "low": frozenset({"Quiet"}),
        },
    )

    assert built.data["lists"][LIST_MODE]["values"] == [
        {"in": "eco plus", "out": "eco_plus"},
        {"in": "Economy", "out": "eco_plus"},
        {"in": r"Saver \(plus\)", "out": "eco_plus"},
        {"in": "low", "out": "low"},
        {"in": "Quiet", "out": "low"},
    ]
    assert built.said[LIST_MODE] == (
        "eco plus",
        "Economy",
        "Saver (plus)",
        "low",
        "Quiet",
    )
    validate("en", built.data, built.said)


def test_a_word_that_is_the_name_of_its_own_mode_is_listed_once() -> None:
    """English words are mostly the names of the modes with a capital: the built-in
    agent does not tell them apart, so the second would only be a copy."""
    built = build(
        load_sources("en"),
        NAMES,
        modes_of_devices("heat_pump"),
        mode_words={"heat_pump": frozenset({"Heat pump"})},
    )

    assert built.data["lists"][LIST_MODE]["values"] == [
        {"in": "heat pump", "out": "heat_pump"}
    ]


def test_a_word_said_like_another_mode_is_left_out() -> None:
    """A person who says "turbo" means the mode called turbo, whatever another mode is
    called in Home Assistant's words."""
    built = build(
        load_sources("en"),
        NAMES,
        modes_of_devices("strong", "turbo"),
        mode_words={"strong": frozenset({"Turbo", "Powerful"})},
    )

    assert [
        (value["in"], value["out"])
        for value in built.data["lists"][LIST_MODE]["values"]
    ] == [
        ("strong", "strong"),
        ("Powerful", "strong"),
        ("turbo", "turbo"),
    ]


def test_a_word_that_two_modes_have_is_listed_for_the_first() -> None:
    """The built-in agent takes the first value that a text matches: the second would
    never be reached, and is left out."""
    built = build(
        load_sources("en"),
        NAMES,
        modes_of_devices("low", "quiet"),
        mode_words={"low": frozenset({"Soft"}), "quiet": frozenset({"Soft"})},
    )

    assert [
        (value["in"], value["out"])
        for value in built.data["lists"][LIST_MODE]["values"]
    ] == [("low", "low"), ("Soft", "low"), ("quiet", "quiet")]


def test_a_word_of_a_mode_no_target_has_is_not_listed() -> None:
    built = build(
        load_sources("en"),
        NAMES,
        modes_of_devices("low"),
        mode_words={"high": frozenset({"Strong"})},
    )

    assert built.said[LIST_MODE] == ("low",)


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_the_lists_of_settings_are_empty_without_a_target_that_takes_them(
    language: str,
) -> None:
    built = build(load_sources(language), NAMES)

    assert built.data["lists"][LIST_HVAC_MODE] == {"values": []}
    assert built.data["lists"][LIST_MODE] == {"values": []}


def test_a_mode_that_is_nothing_but_punctuation_is_left_out() -> None:
    """It would match anywhere, as a name of the same kind would."""
    built = build(load_sources("en"), NAMES, modes_of_devices("!!!", "low"))

    assert [value["out"] for value in built.data["lists"][LIST_MODE]["values"]] == [
        "low"
    ]


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_the_shipped_sentences_with_settings_are_fit_to_be_read(language: str) -> None:
    built = built_with_settings(language)

    validate(language, built.data, built.said)


def test_a_mode_that_would_not_be_matched_as_said_is_refused() -> None:
    built = built_with_settings()
    built.data["lists"][LIST_MODE]["values"][2]["in"] = "low|high"

    with pytest.raises(InvalidSentences, match="would not be matched as said"):
        validate("en", built.data, built.said)


def test_building_with_settings_leaves_the_sources_as_they_were() -> None:
    sources = load_sources("en")
    before = copy.deepcopy(sources)

    build(sources, NAMES, SETTINGS)

    assert sources == before


def test_a_list_that_two_blocks_share_is_written_out_in_both() -> None:
    """The sources share the sentences of a kind of target between blocks with a YAML
    anchor; the files are read by people and copied by hand, and have no alias."""
    shared = ["one", "two"]

    text = dump_sentences({"first": shared, "second": shared})

    assert text == "first:\n- one\n- two\nsecond:\n- one\n- two\n"


# A letter that a speech recogniser writes as another


YO = "\N{CYRILLIC CAPITAL LETTER IO}"
YO_NAME = f"{YO}lka"
YO_TITLE = f"Day{YO}"
YO_MODE = f"s{YO}ft_mode"
"""A name, a title and a mode of a device that each have the Russian letter yo, in
the code points of the letter so that this file stays free of Cyrillic."""


@pytest.mark.parametrize(
    ("text", "variants"),
    [
        pytest.param("Boiler!", ("Boiler",), id="punctuation removed"),
        pytest.param("Boiler (main)", ("Boiler (main)",), id="no yo, listed once"),
        pytest.param(YO_NAME, (YO_NAME, fold_yo(YO_NAME)), id="a yo and a ye"),
        pytest.param(f"{YO}!", (YO, fold_yo(YO)), id="punctuation, then both"),
        pytest.param("?!", (), id="nothing but punctuation"),
        pytest.param("", (), id="nothing"),
    ],
)
def test_a_text_is_listed_as_it_is_said_and_with_ye_for_each_yo(
    text: str, variants: tuple[str, ...]
) -> None:
    assert spoken_variants(text) == variants


def test_every_value_is_listed_under_both_spellings() -> None:
    """A speech recogniser writes ye for yo, and the built-in agent compares what it
    hears with the file letter by letter: each name, title and mode that has a yo is
    listed with it and with a ye, both meaning the same thing, and said as each."""
    built = build(
        load_sources("en"),
        [VoiceName(YO_NAME, "switch")],
        modes_of_devices(YO_MODE),
        [VoiceTitle(YO_TITLE)],
    )

    lists = built.data["lists"]
    assert lists[LIST_TARGET]["values"] == [
        {"in": YO_NAME, "out": YO_NAME, "context": {"domain": "switch"}},
        {"in": fold_yo(YO_NAME), "out": YO_NAME, "context": {"domain": "switch"}},
    ]
    assert lists[LIST_INTERVAL]["values"] == [
        {"in": YO_TITLE, "out": YO_TITLE},
        {"in": fold_yo(YO_TITLE), "out": YO_TITLE},
    ]
    spoken_mode = YO_MODE.replace("_", " ")
    assert lists[LIST_MODE]["values"] == [
        {"in": spoken_mode, "out": YO_MODE},
        {"in": fold_yo(spoken_mode), "out": YO_MODE},
    ]
    assert built.said == {
        LIST_TARGET: (YO_NAME, fold_yo(YO_NAME)),
        LIST_INTERVAL: (YO_TITLE, fold_yo(YO_TITLE)),
        LIST_MODE: (spoken_mode, fold_yo(spoken_mode)),
    }
    validate("en", built.data, built.said)


def test_a_word_with_a_yo_is_listed_under_both_spellings_like_a_name() -> None:
    word = f"{YO}lka"

    built = build(
        load_sources("ru"),
        NAMES,
        modes_of_devices("tree"),
        mode_words={"tree": frozenset({word})},
    )

    assert [value["in"] for value in built.data["lists"][LIST_MODE]["values"]] == [
        "tree",
        word,
        fold_yo(word),
    ]
    validate("ru", built.data, built.said)


def test_a_value_without_a_yo_is_listed_once() -> None:
    built = built_sentences()

    assert [value["in"] for value in built.data["lists"][LIST_TARGET]["values"]] == [
        "Boiler",
        r"Boiler \(main\)",
    ]


def test_a_value_not_read_as_the_text_it_was_built_from_is_refused() -> None:
    """`in` is no longer a function of `out`, so each value is judged by the text that
    `build` meant to say with it."""
    built = built_sentences()
    said = {**built.said, LIST_TARGET: ("Boiler", "Heater")}

    with pytest.raises(
        InvalidSentences,
        match=re.escape("'Boiler (main)' would not be matched as said"),
    ):
        validate("en", built.data, said)


def test_a_list_with_another_number_of_texts_said_is_refused() -> None:
    built = built_sentences()
    said = {**built.said, LIST_TARGET: ("Boiler",)}

    with pytest.raises(
        InvalidSentences,
        match=f"{LIST_TARGET} lists 2 values, but the said texts number 1",
    ):
        validate("en", built.data, said)


@pytest.mark.parametrize("list_name", [LIST_TARGET, LIST_INTERVAL, LIST_MODE])
def test_a_list_that_nothing_is_said_of_is_refused(list_name: str) -> None:
    """A list left out of `said` would be left unchecked, however wrong its values."""
    built = built_sentences()
    said = {name: texts for name, texts in built.said.items() if name != list_name}

    with pytest.raises(InvalidSentences, match=f"No text is said for .*{list_name}"):
        validate("en", built.data, said)


def test_a_name_and_a_title_of_nothing_but_punctuation_are_left_out() -> None:
    """They would match anywhere, as a mode of the kind would."""
    built = build(
        load_sources("en"),
        [VoiceName("?!", "switch"), VoiceName("Boiler!", "switch")],
        intervals=[VoiceTitle("..."), VoiceTitle("Morning")],
    )

    assert [v["out"] for v in built.data["lists"][LIST_TARGET]["values"]] == ["Boiler!"]
    assert [v["in"] for v in built.data["lists"][LIST_TARGET]["values"]] == ["Boiler"]
    assert built.said[LIST_TARGET] == ("Boiler",)
    assert built.said[LIST_INTERVAL] == ("Morning",)
