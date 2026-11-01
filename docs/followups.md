# Follow-ups

Open items are tracked as GitHub issues in klimofey/timerify. Decisions made on purpose
are in `RULINGS.md`.

One line per issue: its number and its title, under the area it belongs to.

## Card

- [#7](https://github.com/klimofey/timerify/issues/7) Raise the minimum Home Assistant to 2026.11 to drop the first-load "Custom element doesn't exist" error
- [#8](https://github.com/klimofey/timerify/issues/8) Card countdown is off by the browser's clock error
- [#9](https://github.com/klimofey/timerify/issues/9) Card editor option labels can be in the wrong language before any card has loaded
- [#30](https://github.com/klimofey/timerify/issues/30) Between a HACS update and the restart the card can get a bundle newer than the server's timerify/timer answer

## Engine

- [#42](https://github.com/klimofey/timerify/issues/42) Carry out a command at the moment it was given, not when it gets the lock

## Schedules

- [#14](https://github.com/klimofey/timerify/issues/14) Windows keep the old time zone after "Reload core configuration"

## Voice

- [#19](https://github.com/klimofey/timerify/issues/19) Assist sentences for commands at a clock time ("turn on the boiler at 7:30")
- [#20](https://github.com/klimofey/timerify/issues/20) Follow friendly_name and mode-list changes of targets without a registry entry in the voice file
- [#21](https://github.com/klimofey/timerify/issues/21) Phrasings Timerify lacks can be matched by core's gazetteer and switch the device
- [#22](https://github.com/klimofey/timerify/issues/22) A spoken form for generated interval titles ("the 6:30 schedule")
- [#23](https://github.com/klimofey/timerify/issues/23) Voice names and interval titles with the Russian letter yo are not matched when said with ye
- [#24](https://github.com/klimofey/timerify/issues/24) Russian Assist sentences should use HA's translations of fan_mode and preset_mode
- [#25](https://github.com/klimofey/timerify/issues/25) Scope HVAC mode words per thermostat instead of the union over timers
- [#26](https://github.com/klimofey/timerify/issues/26) Understand "for 1 hour 30" as 90 minutes for devices without a temperature
- [#29](https://github.com/klimofey/timerify/issues/29) Voice delays above 100 minutes or 100 hours are not understood ("in 120 minutes")

## Tests and tooling

- [#27](https://github.com/klimofey/timerify/issues/27) Pin the Russian plural forms of voice answers with rendered fixtures
- [#28](https://github.com/klimofey/timerify/issues/28) Pin happy-dom 21.0.4 (advisory GHSA-834v-8h66-3h79) on or after 2026-11-03
