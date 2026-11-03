# Timerify 1.2.0: a limit for a device left on

## Why

The owner's boiler has a timer of its own on the device. Timerify drives it in Loose mode,
because Strict mode would turn it back on when that timer turns it off. In Loose mode a
turn-on that names no time has no countdown: the boiler runs until something turns it off.
Until 2026-11-03 an automation, «Auto-off boiler», turned it off after two hours on. It also
cut runs the owner had asked for on purpose, such as "for 3 hours". It has been deleted and
this feature replaces it.

The owner's words: "a fuse against simply forgetting. If I set a timer for 3 hours on
purpose, I need 3 hours." And: "it can say something like 'turns off by 13:30 at the latest',
because by hand I might have set it for 30 minutes."

## The rule

A new optional setting of a timer: the longest time its device may stay on without a
countdown. The examples below use 120 minutes.

- In Loose mode, when the device is on and Timerify has no countdown for it, Timerify sets a
  limit: now plus 120 minutes. When the limit comes, Timerify turns the device off.
- A countdown that someone chose is never cut, and while one runs there is no limit. That
  covers "for 3 hours", Run for, adding time, a schedule window, a pending turn-on with
  minutes, and an action or a voice command with a duration.
- The device turned off by anyone ends the limit: by hand, by its own timer, or from Home
  Assistant. The next turn-on without a countdown starts a new limit of 120 minutes.
- The limit is shown as a bound, not a promise. "Ends at" shows its time with a mark that
  it is a limit. The card says "by 13:30 at the latest" instead of "until 13:30". Assist's
  answer to "how long is left on the boiler" says the same.
- Strict mode is not changed. There, every turn-on already gets a countdown, the default
  duration, so the limit never applies.
- With no limit set, nothing changes from 1.1.1. An entry of an earlier release has none.

## Choices made here (the owner did not say; Claude's calls, to record in RULINGS.md)

- **Every way a device comes to be on without a countdown starts the limit.** That covers a
  turn-on by hand or at the device, a bare voice "turn on the boiler", the card's run, the
  Run action and the Run entity without minutes, and a pending turn-on without minutes. It
  also covers a device found on at start-up and a device back from "unavailable" as on.
  Those are the same paths that 1.1.1 (#58) gives the end of an open window to. With a
  window open, the window's end is a countdown, so there is no limit.
- **The limit counts from the moment Timerify sees the device on.** A device turned on
  while Home Assistant was down gets its limit from start-up, because Home Assistant does
  not keep when a device turned on across a restart.
- **The limit is kept across a restart**, like a countdown, with its mark.
- **Choosing a time replaces the limit with an ordinary countdown.** That covers Run for, a
  run or a voice command with minutes, and a pending command with minutes. Adding time adds
  to the limit: "+15 min" at a limit of 13:30 gives an ordinary countdown to 13:45.
- **When the limit comes, the device is turned off as a Loose countdown's end turns it off**,
  and the countdown-ended announcement says it was the limit. "Countdown started" and
  "Countdown ended" (the triggers and the `timerify_countdown_started` and
  `timerify_countdown_ended` events) fire for a limit too. Their data says it is a limit, so
  an automation can tell "turned off because it was left on" from an ordinary end.
- **The setting is a step of its own for a Loose timer**, as the default duration is a step
  of its own for a Strict one. A new timer in Loose mode, and the settings of one, show a step
  with one box: minutes from 1 to 1440, empty by default. A Strict timer never sees it.
  (Changed while planning: the default duration is not on the first form, so "next to it"
  means a step in the same place.) Proposed name: "Turn off if left on for", with a Russian
  translation in the same sense ("turn off, if forgotten, after").
- **Changing the setting reloads the timer, and a reload is a start-up.** A limit that is
  already running keeps its time. A device that is on with no limit and no countdown gets a
  limit from that moment, as at start-up. A limit is dropped at start-up when the setting is
  empty or the mode is Strict. The device keeps running in both cases. In Strict mode the
  default duration then applies, as it does today. (Changed while planning: every change of
  the settings reloads the timer, so "from the next turn-on" could not hold.)
- **No new entity.** The mark is an attribute of "Ends at". Its name is the builder's call,
  documented in services.md.
- **"Run for" shows 0 while a limit runs.** Run for shows the countdown someone chose, and
  a Loose device on without a countdown shows 0 today. The limit is no promise, so a
  dashboard or an automation reading Run for does not see it. Setting Run for starts an
  ordinary countdown, as above. In the engine, the limit is a deadline of its own, kept
  next to the countdown's end and never both at once, not a marked end.
- **A limit that a chosen countdown replaces is not announced as ended.** The device keeps
  running, and the new countdown is announced as started, with `limit: false`.
- **A bare turn-on while a limit runs keeps the limit.** The device is already on, and a
  bare turn-on of a device that runs keeps how it stands today. No new "Countdown started"
  fires.
- **The events mark the limit with a reason of its own.** `timerify_countdown_ended` gets
  the new reason `limit` when the limit turns the device off, next to `expired`, `stopped`
  and `turned_off`. An automation that waits for `expired` keeps seeing only countdowns that
  someone chose. `timerify_countdown_started` gets `limit: true` for a limit and `false`
  otherwise. The device triggers "Countdown started" and "Countdown ended" fire for a limit
  too, and their variables carry the same data, so a condition can tell them apart.
- **The LLM tools say it the same way.** The `timerify__` tools that report how long is
  left report a limit as "by 13:30 at the latest", not as minutes left.

## Non-goals

- A cap on countdowns that someone chose. The maximum of Run for (#35) limits the slider,
  and nothing here limits a run asked for on purpose.
- A notification. The events and the triggers let an automation send one.
- Changing Strict mode, the schedules or the runtime counter.

## Scope

- The engine (`custom_components/timerify/core.py`) and the controller, the store (a stored
  mark, with a migration if the storage version must change), and the forms (config and
  options flow, `translations/en.json` and `ru.json`).
- The "Ends at" sensor, the `timerify/timer` websocket answer that the card reads, and the
  card (`card/src`, then rebuild the committed bundle). The countdown events and triggers.
  Assist's answers (the `query` answer in English and Russian, with fixtures under
  `tests/fixtures/ru/`).
- Docs in `docs/en` and `docs/ru`: timers.md (the setting and the modes), card.md, voice.md,
  automations.md (the event data) and services.md (the attribute).
- Fold #59 in while the card bundle is open. It covers the card editor's label "Run for the
  default duration" and the card comments that describe a bare run.

## Release

Issue: #62 (and #59). Version 1.2.0 in manifest.json, pyproject.toml and uv.lock. The full local gate runs on the
final tree, including the card E2E against a real Home Assistant and a smoke run. The
GitHub Release is published once the owner says so.
