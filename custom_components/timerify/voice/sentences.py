"""The sentence files Timerify writes for the built-in agent: what goes into them, and
the proof that the built-in agent can read them.

The shipped sentences (`sentences/<language>/*.yaml`) are complete but for the names of
the devices; the names are what this module adds. A file that Home Assistant cannot load
makes the built-in agent fail for the whole language, whatever the request, so a file is
built here, parsed the way the agent parses it, and written only when it passes
(`validate`).

Everything here is blocking, except `voice_names`, and runs in the executor.
"""

import copy
import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import yaml
from hassil.expression import (
    Expression,
    ListReference,
    RuleReference,
    Sentence,
    TextChunk,
)
from hassil.expression import Sequence as SequenceExpression
from hassil.intents import Intent, Intents, TextSlotList
from hassil.util import is_template, merge_dict, normalize_text, remove_punctuation
from home_assistant_intents import get_intents
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent

from ..const import (
    LIST_HVAC_MODE,
    LIST_MODE,
    LIST_TARGET,
    MANAGED_HEADER,
    SENTENCES_DIR,
)
from ..domains import supported_settings
from .base import loaded_timers

RULE_PREFIX: Final = "timerify_"
"""What the names of the lists and expansion rules the sentences define start with."""

_TEMPLATE_CHARACTERS: Final = re.compile(r"([\\()\[\]{}<>|@])")

_LOADER: Final = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
"""The loader of the sentence files: the one built on libyaml where there is libyaml, as
Home Assistant's own is, since the files run to tens of kilobytes."""


class _SentenceDumper(yaml.SafeDumper):
    """The safe YAML dumper, but a text of several lines is written as a block, as the
    text is, not as a line of escapes, and a list that two places share is written out
    in both: the files are read by people and by tools that take no anchors on faith."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


def _represent_text(dumper: _SentenceDumper, text: str) -> yaml.ScalarNode:
    style = "|" if "\n" in text else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style=style)


_SentenceDumper.add_representer(str, _represent_text)


class InvalidSentences(ValueError):
    """Sentences the built-in agent would not load, or would not match as said."""


@dataclass(frozen=True)
class VoiceName:
    """One way a target is called: what is said, and what is meant by it."""

    spoken: str
    """The name as the built-in agent compares it with what it hears: punctuation
    removed."""
    name: str
    """The name as Home Assistant shows it, which the intent receives."""
    domain: str
    """The domain of the target."""


@dataclass(frozen=True)
class VoiceSettingValues:
    """The values of the settings that the targets support, which a person may say."""

    hvac_modes: frozenset[str] = frozenset()
    """The HVAC modes of the targets, as Home Assistant names them."""
    modes: frozenset[str] = frozenset()
    """The modes of the targets that "mode" means, as their devices name them: the fan
    modes of thermostats, the presets of fans, the modes of humidifiers, the operation
    modes of water heaters."""


NO_SETTING_VALUES: Final = VoiceSettingValues()
"""No target supports a setting that has words."""


def spoken_form(name: str) -> str:
    """The name as the built-in agent compares it with what it hears, which is how it
    lists the names of every entity it knows."""
    return remove_punctuation(name).strip()


def spoken_mode(mode: str) -> str:
    """The mode of a device as a person says it: as the device names it, with the
    underscores of a name such as `eco_plus` for spaces."""
    return spoken_form(mode.replace("_", " "))


NAME_LISTS: Final[Mapping[str, Callable[[str], str]]] = {
    LIST_TARGET: spoken_form,
    LIST_MODE: spoken_mode,
}
"""The lists of the sentences that hold names as people say them, each with how a value
is said, which `validate` proves are matched as said."""


def escape_template(text: str) -> str:
    """`text` as a value of a list that is read as the text it is.

    Home Assistant reads a value that has any of the characters `()[]{}<>|@` as a
    sentence template: a backslash makes such a character itself. A backslash is itself
    only until a template character is there to be escaped, so a value without any is
    left as it is, and one with any has its backslashes escaped as well.
    """
    if not is_template(text):
        return text
    return _TEMPLATE_CHARACTERS.sub(r"\\\1", text)


@callback
def voice_names(hass: HomeAssistant) -> list[VoiceName]:
    """Every name the built-in agent would know the targets of the timers by.

    The names of an entity are its aliases, the computed name among them, as the
    built-in agent lists them, so that a name is matched as it is for any other
    entity. A target that has no state yet is listed by its registry entry. A name that
    is nothing but punctuation is left out: it would match anywhere.
    """
    registry = er.async_get(hass)
    names: list[VoiceName] = []
    for entry in loaded_timers(hass):
        entity_id = entry.runtime_data.target_entity_id
        registered = registry.async_get(entity_id)
        if (state := hass.states.get(entity_id)) is not None:
            aliases = intent.async_get_entity_aliases(hass, registered, state=state)
        elif registered is not None:
            aliases = er.async_get_entity_aliases(hass, registered, allow_empty=False)
        else:
            aliases = []
        domain = split_entity_id(entity_id)[0]
        names.extend(
            VoiceName(spoken, alias, domain)
            for alias in aliases
            if (spoken := spoken_form(alias))
        )
    return names


@callback
def voice_setting_values(hass: HomeAssistant) -> VoiceSettingValues:
    """The values of the settings that the targets of the timers support now, from their
    states or, without one, their registry entries: the same judgement a command is
    judged by, so that nothing is offered that a target would refuse."""
    hvac_modes: set[str] = set()
    modes: set[str] = set()
    for entry in loaded_timers(hass):
        for choice in supported_settings(hass, entry.runtime_data.target_entity_id):
            if choice.name == "hvac_mode":
                hvac_modes.update(choice.options)
            elif choice.voice == "mode":
                modes.update(choice.options)
    return VoiceSettingValues(frozenset(hvac_modes), frozenset(modes))


def load_sources(language: str) -> dict[str, Any]:
    """The shipped sentences of `language` as the built-in agent reads them: every file
    of the language's directory, merged, in the order of their names."""
    sources: dict[str, Any] = {}
    for path in sorted((SENTENCES_DIR / language).glob("*.yaml")):
        merge_dict(sources, read_back(path.read_text("utf-8")))
    return sources


def build(
    sources: Mapping[str, Any],
    names: Sequence[VoiceName],
    settings: VoiceSettingValues = NO_SETTING_VALUES,
) -> dict[str, Any]:
    """The sentences of `sources` with the lists of what the targets are called and
    can be turned on in filled in.

    A name is listed under what is said (`in`, escaped so that it is read as text) and
    what it means (`out`), with the domain of its target as context. The words for an
    HVAC mode are those of the sources that mean a mode some target supports; the modes
    are listed as the devices name them, said with spaces for underscores.
    """
    built = copy.deepcopy(dict(sources))
    lists = built.setdefault("lists", {})
    lists[LIST_TARGET] = {
        "values": [
            {
                "in": escape_template(name.spoken),
                "out": name.name,
                "context": {"domain": name.domain},
            }
            for name in names
        ]
    }
    lists[LIST_HVAC_MODE] = {
        "values": [
            word
            for word in lists.get(LIST_HVAC_MODE, {}).get("values", [])
            if word["out"] in settings.hvac_modes
        ]
    }
    lists[LIST_MODE] = {"values": _mode_values(settings.modes)}
    return built


def _mode_values(modes: Iterable[str]) -> list[dict[str, Any]]:
    """The values of the list of modes: each said as `spoken_mode` says it, and meaning
    the mode as the device names it. A mode that is nothing but punctuation is left
    out: it would match anywhere."""
    return [
        {"in": escape_template(spoken), "out": mode}
        for mode in sorted(modes)
        if (spoken := spoken_mode(mode))
    ]


def validate(language: str, built: Mapping[str, Any]) -> None:
    """Prove that the built-in agent can load `built` next to its own sentences of
    `language`, and will match the names in it as they are said.

    Parsing the dictionary is not enough: Home Assistant parses a sentence on its first
    use, and a sentence that is not a template does not fail until it is matched. So
    this also parses every sentence of every intent `built` defines, checks that every
    list and expansion rule they and Timerify's own rules use is there, and that each
    name is read as exactly the text it stands for.

    Raises `InvalidSentences` for the first thing that is wrong.
    """
    core = get_intents(language)
    if core is None:
        raise InvalidSentences(f"Home Assistant has no sentences in {language}")
    try:
        merged = copy.deepcopy(core)  # Merging changes the dictionary it merges into.
        merge_dict(merged, built)
        intents = Intents.from_dict(merged)
        own_intents = [intents.intents[name] for name in built.get("intents", {})]
        _check_references(intents, own_intents)
        for list_name, spoken in NAME_LISTS.items():
            _check_names(intents, built, list_name, spoken)
    except InvalidSentences:
        raise
    except Exception as err:
        raise InvalidSentences(f"{type(err).__name__}: {err}") from err


def dump_sentences(data: Mapping[str, Any]) -> str:
    """`data` as the text of a sentence file."""
    text: str = yaml.dump(
        dict(data),
        Dumper=_SentenceDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    return text


def read_back(text: str) -> dict[str, Any]:
    """The sentences of the text of a file, as the built-in agent reads the file."""
    sentences: dict[str, Any] = yaml.load(text, Loader=_LOADER)
    return sentences


def render(built: Mapping[str, Any]) -> str:
    """The text of the file for `built`."""
    return f"{MANAGED_HEADER}\n{dump_sentences(built)}"


def _references(expression: Expression) -> Iterator[ListReference | RuleReference]:
    """The lists and rules an expression refers to, at any depth."""
    if isinstance(expression, ListReference | RuleReference):
        yield expression
    for item in getattr(expression, "items", ()):
        yield from _references(item)


def _check_references(intents: Intents, own_intents: Sequence[Intent]) -> None:
    """Every list and expansion rule that a sentence of the intents, or a rule that
    Timerify defines, refers to exists in the sentences, global or of its data block.

    Reading the sentences is what parses them, which Home Assistant leaves until a
    sentence is first matched: one that is not a template fails here.
    """

    def check(
        sentence: Sentence, lists: Mapping[str, Any], rules: Mapping[str, Any]
    ) -> None:
        for reference in _references(sentence.expression):
            if isinstance(reference, ListReference):
                if (
                    reference.list_name not in lists
                    and not reference.is_inline_range
                    and not reference.is_capture
                ):
                    raise InvalidSentences(f"No list {reference.list_name}")
            elif reference.rule_name not in rules:
                raise InvalidSentences(f"No expansion rule {reference.rule_name}")

    for rule_name, rule in intents.expansion_rules.items():
        if rule_name.startswith(RULE_PREFIX):
            check(rule, intents.slot_lists, intents.expansion_rules)
    for own in own_intents:
        for data in own.data:
            lists = {**intents.slot_lists, **data.slot_lists}
            rules = {**intents.expansion_rules, **data.expansion_rules}
            for sentence in (*data.sentences, *data.expansion_rules.values()):
                check(sentence, lists, rules)


def _text_of(expression: Expression) -> str | None:
    """The text that `expression` is read as, if it is nothing but text: parts that
    were split where a character was escaped are put together again."""
    if isinstance(expression, TextChunk):
        return expression.text
    if type(expression) is SequenceExpression:
        parts = [_text_of(item) for item in expression.items]
        if all(part is not None for part in parts):
            return "".join(part for part in parts if part is not None)
    return None


def _check_names(
    intents: Intents,
    built: Mapping[str, Any],
    list_name: str,
    spoken: Callable[[str], str],
) -> None:
    """Every name listed in `list_name` is read as the text that it is said as, which
    is what `spoken` makes of what it means."""
    slot_list = intents.slot_lists[list_name]
    if not isinstance(slot_list, TextSlotList):
        raise InvalidSentences(f"{list_name} is not a list of names")
    for value, parsed in zip(
        built["lists"][list_name]["values"], slot_list.values, strict=True
    ):
        wanted = normalize_text(spoken(value["out"]))
        if _text_of(parsed.text_in) != wanted:
            raise InvalidSentences(
                f"{value['out']!r} would not be matched as said: it is listed as"
                f" {value['in']!r}"
            )
