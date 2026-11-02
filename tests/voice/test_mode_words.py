"""The modes of the devices in the sentence files: the Voice settings entry lists each
mode as the device names it and in the words Home Assistant's translations give it, in
the language of the file.

The expected words are read from Home Assistant in the test, never written: the keys
name where they are kept.
"""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_translate_state_attr
from homeassistant.setup import async_setup_component

from custom_components.timerify.const import LIST_MODE

from ..conftest import CLIMATE_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from ..helpers import AC_ATTRS, AC_ID
from .helpers import (
    CLIMATE_FAN_MODE,
    add_voice_entry,
    converse,
    listed,
    outs,
    reached,
    samples,
    word_of,
)

DEMO_SLEEP = "component.demo.entity.fan.demo.state_attributes.preset_mode.state.sleep"
"""Where Home Assistant keeps the word for the preset `sleep` of the fan of the Demo
integration."""


def said_as(language: str, hass: HomeAssistant, mode: str) -> set[str]:
    """Every text the managed file of `language` lists for `mode`, as the built-in agent
    compares it: without a difference of case."""
    return {
        value["in"].casefold()
        for value in listed(hass, language, LIST_MODE)
        if value["out"] == mode
    }


@pytest.mark.usefixtures("assist")
async def test_a_fan_preset_is_listed_in_the_words_of_its_integration(
    hass: HomeAssistant, fake_demo_fan: FakeTarget, setup_target: SetupTarget
) -> None:
    """A preset is listed in the word its integration gives it in the language of the
    file, and as the device names it; one that no integration translates is listed as
    the device names it alone."""
    await setup_target(target=fake_demo_fan.entity_id)
    word = await word_of(hass, "ru", "entity", DEMO_SLEEP)

    await add_voice_entry(hass, languages=("ru",))

    values = {(value["in"], value["out"]) for value in listed(hass, "ru", LIST_MODE)}
    assert word.casefold() != "sleep"
    assert values == {(word, "sleep"), ("sleep", "sleep"), ("turbo x", "turbo_x")}


@pytest.mark.usefixtures("assist")
async def test_a_russian_preset_word_runs_the_fan_in_that_preset(
    hass: HomeAssistant, fake_demo_fan: FakeTarget, setup_target: SetupTarget
) -> None:
    """The word in the Russian file is what a person says: the fan turns on in the
    preset it means, not in the one that the word looks like."""
    await setup_target(target=fake_demo_fan.entity_id)
    await add_voice_entry(hass, languages=("ru",))
    word = await word_of(hass, "ru", "entity", DEMO_SLEEP)
    texts = samples(
        "ru",
        "TimerifyRun",
        names=("Vent",),
        numbers={"timerify_minutes": 10},
        texts={"timerify_mode": word},
    )
    text = next(text for text in texts if word in text)

    response = await converse(hass, text, "ru")

    assert reached(response) == "TimerifyRun", text
    assert fake_demo_fan.call_data == [("turn_on", {"preset_mode": "sleep"})]


@pytest.mark.usefixtures("assist")
async def test_a_thermostat_fan_mode_uses_the_words_of_the_climate_domain(
    hass: HomeAssistant, fake_full_ac: FakeTarget, setup_target: SetupTarget
) -> None:
    """A thermostat of an integration that translates nothing of its own is shown the
    words of the climate domain, and so is it spoken to."""
    await setup_target(target=fake_full_ac.entity_id)
    await add_voice_entry(hass, languages=("ru",))

    values = {(value["in"], value["out"]) for value in listed(hass, "ru", LIST_MODE)}
    for mode in ("auto", "low", "high"):
        word = await word_of(
            hass, "ru", "entity_component", f"{CLIMATE_FAN_MODE}.{mode}"
        )
        assert (word, mode) in values
        assert (mode, mode) in values


@pytest.mark.usefixtures("assist")
async def test_a_thermostat_that_is_not_registered_is_spoken_to_in_the_climate_words(
    hass: HomeAssistant, provide_target: ProvideTarget, setup_target: SetupTarget
) -> None:
    """A thermostat of YAML has no registry entry, so no integration to ask: it has the
    words of its domain."""
    thermostat = provide_target(
        AC_ID,
        CLIMATE_SERVICES,
        name="AC",
        registered=False,
        capability_attributes=AC_ATTRS,
        state_attributes={"temperature": 20, "fan_mode": "auto"},
    )
    await setup_target(target=thermostat.entity_id)
    word = await word_of(hass, "ru", "entity_component", f"{CLIMATE_FAN_MODE}.high")

    await add_voice_entry(hass, languages=("ru",))

    assert (word, "high") in {
        (value["in"], value["out"]) for value in listed(hass, "ru", LIST_MODE)
    }


@pytest.mark.usefixtures("assist")
async def test_a_mode_without_a_russian_word_is_listed_in_the_english_one(
    hass: HomeAssistant, provide_target: ProvideTarget, setup_target: SetupTarget
) -> None:
    """What the interface shows in Russian for a word nobody translated is the English
    word, and it is what a person reads on the screen: it is listed."""
    key = (
        "component.lg_thinq.entity.climate.climate_air_conditioner"
        ".state_attributes.fan_mode.state.breeze"
    )
    english = await word_of(hass, "en", "entity", key)
    shown = await word_of(hass, "ru", "entity", key)
    assert shown == english, "Home Assistant has translated it: pick a mode it has not"
    thermostat = provide_target(
        AC_ID,
        CLIMATE_SERVICES,
        name="AC",
        platform="lg_thinq",
        translation_key="climate_air_conditioner",
        capability_attributes={**AC_ATTRS, "fan_modes": ["breeze", "low"]},
        state_attributes={"temperature": 20, "fan_mode": "low"},
    )
    await setup_target(target=thermostat.entity_id)

    await add_voice_entry(hass, languages=("ru",))

    assert (english, "breeze") in {
        (value["in"], value["out"]) for value in listed(hass, "ru", LIST_MODE)
    }


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize("house", ["en", "ru"])
async def test_a_file_has_the_words_of_its_own_language_whatever_the_house_speaks(
    hass: HomeAssistant,
    fake_demo_fan: FakeTarget,
    setup_target: SetupTarget,
    house: str,
) -> None:
    """A house set to English may ask for the Russian file as well, and a Russian one
    for the English file: each file has the words of its own language for the same
    mode."""
    hass.config.language = house
    await setup_target(target=fake_demo_fan.entity_id)
    russian = await word_of(hass, "ru", "entity", DEMO_SLEEP)
    english = await word_of(hass, "en", "entity", DEMO_SLEEP)
    assert russian.casefold() != english.casefold()

    await add_voice_entry(hass, languages=("en", "ru"))

    assert said_as("ru", hass, "sleep") == {"sleep", russian.casefold()}
    assert said_as("en", hass, "sleep") == {english.casefold()}
    assert outs(listed(hass, "en", LIST_MODE)) == ["sleep", "turbo_x"]
    assert outs(listed(hass, "ru", LIST_MODE)) == ["sleep", "sleep", "turbo_x"]


@pytest.mark.usefixtures("assist")
async def test_the_words_listed_are_the_words_home_assistant_shows(
    hass: HomeAssistant,
    fake_demo_fan: FakeTarget,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """In a house that speaks Russian, the words of the Russian file for the modes of a
    device are what Home Assistant itself shows for them: those of the integration, of
    the domain, and none for a mode nobody translated."""
    hass.config.language = "ru"
    # `async_translate_state_attr` reads the words of the components Home Assistant has
    # loaded, and the integrations of the fakes are not set up. Fan and climate are set
    # up for real. Demo is only marked as loaded: setting it up would add its own fans
    # and thermostats to the house.
    for component in ("fan", "climate"):
        assert await async_setup_component(hass, component, {})
    hass.config.components.add("demo")
    await setup_target(target=fake_demo_fan.entity_id)
    await setup_target(target=fake_full_ac.entity_id)
    await add_voice_entry(hass, languages=("ru",))

    values = {(value["in"], value["out"]) for value in listed(hass, "ru", LIST_MODE)}
    for target, attribute, mode in [
        (fake_demo_fan, "preset_mode", "sleep"),
        (fake_demo_fan, "preset_mode", "turbo_x"),
        (fake_full_ac, "fan_mode", "high"),
    ]:
        registered = er.async_get(hass).async_get(target.entity_id)
        assert registered is not None
        shown = async_translate_state_attr(
            hass,
            mode,
            target.entity_id.split(".")[0],
            registered.platform,
            registered.translation_key,
            None,
            attribute,
        )
        assert {text for text, out in values if out == mode} == {
            shown.replace("_", " "),
            mode.replace("_", " "),
        }


async def assert_spoken_to_in_the_words_of_the_domain(
    hass: HomeAssistant,
    setup_target: SetupTarget,
    target: FakeTarget,
    attribute: str,
    mode: str,
) -> None:
    """The Russian file lists `mode` of `target` in the word that the translations of
    its domain give the `attribute` it is a value of."""
    domain = target.entity_id.split(".")[0]
    key = f"component.{domain}.entity_component._.state_attributes.{attribute}.state"
    word = await word_of(hass, "ru", "entity_component", f"{key}.{mode}")
    await setup_target(target=target.entity_id)

    await add_voice_entry(hass, languages=("ru",))

    values = {(value["in"], value["out"]) for value in listed(hass, "ru", LIST_MODE)}
    assert word.casefold() != mode
    assert (word, mode) in values


@pytest.mark.usefixtures("assist")
async def test_a_humidifier_mode_uses_the_words_of_the_humidifier_domain(
    hass: HomeAssistant, fake_humidifier: FakeTarget, setup_target: SetupTarget
) -> None:
    await assert_spoken_to_in_the_words_of_the_domain(
        hass, setup_target, fake_humidifier, "mode", "eco"
    )


@pytest.mark.usefixtures("assist")
async def test_a_water_heater_mode_uses_the_words_of_the_water_heater_domain(
    hass: HomeAssistant, fake_tank: FakeTarget, setup_target: SetupTarget
) -> None:
    await assert_spoken_to_in_the_words_of_the_domain(
        hass, setup_target, fake_tank, "operation_mode", "electric"
    )


@pytest.mark.usefixtures("assist")
async def test_a_device_class_without_words_of_its_own_has_the_words_of_the_domain(
    hass: HomeAssistant, fake_dehumidifier: FakeTarget, setup_target: SetupTarget
) -> None:
    """A dehumidifier is a humidifier of its own device class, which Home Assistant has
    no words for the modes of: they are those of every humidifier."""
    await setup_target(target=fake_dehumidifier.entity_id)
    key = "component.humidifier.entity_component._.state_attributes.mode.state.eco"
    word = await word_of(hass, "ru", "entity_component", key)

    await add_voice_entry(hass, languages=("ru",))

    assert (word, "eco") in {
        (value["in"], value["out"]) for value in listed(hass, "ru", LIST_MODE)
    }
