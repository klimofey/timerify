"""The Voice settings entry: it writes the sentence files for the built-in agent, keeps
them in step with the timers, and takes them away again.

The file of a language is `custom_sentences/<language>/timerify.yaml`. It is the shipped
sentences with the names of the timers' targets in them and the titles of their schedule
intervals, and it is rewritten whenever those may have changed. Writing a file and
removing one are followed by a reload of the built-in agent's sentences, so that the
change is heard at once.

The path is the user's directory, and a file at it is Timerify's only if its first line
is `MANAGED_HEADER`: Timerify writes where there is no file or its own, removes only its
own, and leaves any other alone.
"""

import logging
from collections.abc import Iterable, Sequence
from contextlib import suppress
from enum import Enum, auto
from pathlib import Path
from typing import TypeIs

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.start import async_at_started
from homeassistant.util.file import write_utf8_file_atomic

from ..const import (
    CONF_LANGUAGES,
    CONF_WRITE_SENTENCES,
    MANAGED_HEADER,
    MANUAL_SENTENCES_DIR,
    SIGNAL_TIMERS_CHANGED,
    VOICE_LANGUAGES,
    VOICE_SYNC_COOLDOWN,
    is_voice_options,
)
from ..controller import TimerifyConfigEntry
from .base import loaded_timers
from .sentences import (
    InvalidSentences,
    VoiceName,
    VoiceSettingValues,
    build,
    interval_names,
    load_sources,
    read_back,
    render,
    validate,
    voice_names,
    voice_setting_values,
)

_LOGGER = logging.getLogger(__name__)

CONVERSATION_DOMAIN = "conversation"
"""The integration that has the built-in agent, and the service that reloads its
sentences."""

_ENTITY_CHANGES = frozenset(
    {"name", "aliases", "original_name", "entity_id", "device_id"}
)
"""What of a registered entity decides the names it is known by."""
_DEVICE_CHANGES = frozenset({"name", "name_by_user"})
"""What of a device decides the full names of the entities on it."""

type VoiceConfigEntry = ConfigEntry[SentenceFiles]


def is_voice_entry(
    entry: TimerifyConfigEntry | VoiceConfigEntry,
) -> TypeIs[VoiceConfigEntry]:
    """Whether `entry` holds the voice settings, not a timer. Options tell, not the
    runtime data, which is gone when an entry is removed."""
    return is_voice_options(entry.options)


def _managed_path(hass: HomeAssistant, language: str) -> Path:
    """The file Timerify writes for `language`."""
    return Path(hass.config.path("custom_sentences", language, "timerify.yaml"))


class WriteResult(Enum):
    """What came of writing the sentences of a language."""

    UNCHANGED = auto()
    """The file says what it should."""
    WRITTEN = auto()
    """The file was made or changed."""
    FOREIGN = auto()
    """A file that Timerify did not write is in the way, and was left as it is."""


def _first_line(path: Path) -> str | None:
    """The first line of the file at `path`, without its line break; None if there is no
    such file. What is not text is read as the replacement character, which no header
    has."""
    try:
        with path.open(encoding="utf-8", errors="replace") as file:
            return file.readline().removesuffix("\n")
    except FileNotFoundError:
        return None


def _write_if_changed(
    path: Path,
    language: str,
    names: Sequence[VoiceName],
    settings: VoiceSettingValues,
    intervals: Sequence[VoiceName],
) -> WriteResult:
    """Build the sentences of `language`, check that the built-in agent can read the
    text that would be written, and write it to `path` unless it is what is there
    already, or the file there is not Timerify's.

    Raises `InvalidSentences`, with the file untouched, when the sentences are not fit
    to be read.
    """
    first_line = _first_line(path)
    if first_line is not None and first_line != MANAGED_HEADER:
        return WriteResult.FOREIGN
    text = render(build(load_sources(language), names, settings, intervals))
    validate(language, read_back(text))
    if first_line is not None and path.read_text("utf-8", errors="replace") == text:
        return WriteResult.UNCHANGED
    path.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_file_atomic(str(path), text)
    return WriteResult.WRITTEN


def _remove(paths: Iterable[Path]) -> bool:
    """Remove the files among `paths` that Timerify wrote. Whether there were any."""
    removed = False
    for path in paths:
        if _first_line(path) == MANAGED_HEADER:
            with suppress(FileNotFoundError):
                path.unlink()
                removed = True
    return removed


def _manual_installs(directories: Iterable[Path]) -> list[Path]:
    """The directories of `directories` that exist."""
    return [directory for directory in directories if directory.is_dir()]


async def _async_reload_sentences(hass: HomeAssistant) -> None:
    """Make the built-in agent read its sentences again, in every language, when it is
    there to be told."""
    if hass.services.has_service(CONVERSATION_DOMAIN, SERVICE_RELOAD):
        await hass.services.async_call(
            CONVERSATION_DOMAIN, SERVICE_RELOAD, blocking=True
        )


async def async_remove_sentence_files(
    hass: HomeAssistant, languages: Iterable[str] = VOICE_LANGUAGES
) -> None:
    """Remove the files Timerify wrote, for `languages`, and tell the built-in agent if
    there were any. A file at the path that Timerify did not write stays.

    A function of its own, since the entry that wrote the files has no runtime data
    left by the time it is removed.
    """
    paths = [_managed_path(hass, language) for language in languages]
    if await hass.async_add_executor_job(_remove, paths):
        await _async_reload_sentences(hass)


class SentenceFiles:
    """The sentence files of the voice settings entry, and what keeps them current.

    The first writing happens before the entry is set up when Home Assistant is running,
    and once it has started otherwise, when every timer is there to be listed. Only
    after it do changes cause writing: a timer set up or unloaded, which an edit of the
    title of an interval of its schedule is, and a rename of a target, of its device or
    of an alias of it. A burst of changes is one writing, `VOICE_SYNC_COOLDOWN` after
    the last.
    """

    def __init__(self, hass: HomeAssistant, entry: VoiceConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=VOICE_SYNC_COOLDOWN,
            immediate=False,
            function=self.async_sync,
        )
        self._warned_about_manual = False
        self._warned_about_foreign: set[Path] = set()

    async def async_start(self) -> None:
        """Write the files, and then follow the timers; at the start of Home Assistant
        if it is starting."""
        if self._hass.state is CoreState.running:
            await self._async_first_sync()
        else:
            self._entry.async_on_unload(
                async_at_started(self._hass, self._async_started)
            )

    async def _async_started(self, _hass: HomeAssistant) -> None:
        await self._async_first_sync()

    async def _async_first_sync(self) -> None:
        """Write the files, then follow what their names depend on."""
        async with self._debouncer.async_lock():
            await self.async_sync()
        hass = self._hass
        self._entry.async_on_unload(
            async_dispatcher_connect(hass, SIGNAL_TIMERS_CHANGED, self._changed)
        )
        self._entry.async_on_unload(
            hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._entity_updated
            )
        )
        self._entry.async_on_unload(
            hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED, self._device_updated
            )
        )

    async def async_stop(self) -> None:
        """Stop writing: nothing waiting for the cooldown is written, and a writing
        under way is waited for, so that when this returns the files are the caller's
        to remove."""
        self._debouncer.async_shutdown()
        async with self._debouncer.async_lock():
            pass

    async def async_sync(self) -> None:
        """Make the files what they should be now: one for each language chosen, listing
        the targets of the timers, none for the others. The built-in agent reloads its
        sentences once, if anything changed.

        A language whose sentences are not fit to be read is left as it was, and said so
        in the log: a file the built-in agent cannot load breaks it for the language.
        """
        hass = self._hass
        chosen = [
            language
            for language in VOICE_LANGUAGES
            if language in self._entry.options[CONF_LANGUAGES]
        ]
        names = voice_names(hass)
        settings = voice_setting_values(hass)
        intervals = interval_names(hass)
        await self._async_warn_about_manual_installs(chosen)
        changed = False
        try:
            for language in VOICE_LANGUAGES:
                path = _managed_path(hass, language)
                if language not in chosen:
                    changed |= await hass.async_add_executor_job(_remove, [path])
                    continue
                try:
                    result = await hass.async_add_executor_job(
                        _write_if_changed, path, language, names, settings, intervals
                    )
                except InvalidSentences as err:
                    _LOGGER.error(
                        "Not writing the sentences for %s, as the built-in agent could"
                        " not use them: %s",
                        language,
                        err,
                    )
                    continue
                changed |= result is WriteResult.WRITTEN
                self._note_foreign(language, path, result is WriteResult.FOREIGN)
        finally:
            if changed:
                await _async_reload_sentences(hass)

    def _note_foreign(self, language: str, path: Path, foreign: bool) -> None:
        """Say, once, that a file Timerify did not write is where its file for
        `language` belongs, and so the language is not written."""
        if not foreign:
            self._warned_about_foreign.discard(path)
        elif path not in self._warned_about_foreign:
            self._warned_about_foreign.add(path)
            _LOGGER.warning(
                "Not writing the sentences for %s: %s was not written by Timerify, and"
                " is left as it is. Move or delete it to have them written",
                language,
                path,
            )

    async def _async_warn_about_manual_installs(self, languages: list[str]) -> None:
        """Say, once, that the sentences are also installed by hand: both would be read
        and the second copy of each sentence is a source of confusion."""
        if self._warned_about_manual:
            return
        installed = await self._hass.async_add_executor_job(
            _manual_installs,
            [
                Path(
                    self._hass.config.path(
                        "custom_sentences", language, MANUAL_SENTENCES_DIR
                    )
                )
                for language in languages
            ],
        )
        if installed:
            self._warned_about_manual = True
            _LOGGER.warning(
                "Timerify sentences are installed by hand in %s, and the voice settings"
                " write them as well: manual and managed sentences are both installed."
                " Remove one of the two",
                ", ".join(str(directory) for directory in installed),
            )

    @callback
    def _changed(self) -> None:
        """Something that the names depend on may have changed: write again soon."""
        if not self._hass.is_stopping:
            self._debouncer.async_schedule_call()

    def _targets(self) -> set[str]:
        return {
            entry.runtime_data.target_entity_id for entry in loaded_timers(self._hass)
        }

    @callback
    def _entity_updated(self, event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """A registered entity changed: write again when it is a target, and its names
        are what changed."""
        data = event.data
        if data["action"] != "update" or not _ENTITY_CHANGES & data["changes"].keys():
            return
        if {data["entity_id"], data.get("old_entity_id")} & self._targets():
            self._changed()

    @callback
    def _device_updated(self, event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
        """A device changed: write again when a target is on it, and its name is what
        changed."""
        data = event.data
        if data["action"] != "update" or not _DEVICE_CHANGES & data["changes"].keys():
            return
        registry = er.async_get(self._hass)
        for target in self._targets():
            registered = registry.async_get(target)
            if registered is not None and registered.device_id == data["device_id"]:
                self._changed()
                return


async def async_setup_voice_entry(hass: HomeAssistant, entry: VoiceConfigEntry) -> bool:
    """Write the sentence files and keep them, or take them away when the entry says
    not to have any."""
    entry.runtime_data = SentenceFiles(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    if entry.options[CONF_WRITE_SENTENCES]:
        await entry.runtime_data.async_start()
    else:
        await async_remove_sentence_files(hass)
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: VoiceConfigEntry) -> None:
    """Reload the entry whenever its options change, which writes the files, or takes
    them away, as the options now say."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_voice_entry(
    hass: HomeAssistant, entry: VoiceConfigEntry
) -> bool:
    """Let the entry go. The files stay, as they do while the entry reloads, unless the
    entry is disabled: then they go, once nothing is left that could write them
    again."""
    await entry.runtime_data.async_stop()
    if entry.disabled_by is not None:
        await async_remove_sentence_files(hass)
    return True


async def async_remove_voice_entry(
    hass: HomeAssistant, entry: VoiceConfigEntry
) -> None:
    """Take the files away with the entry."""
    await async_remove_sentence_files(hass)
