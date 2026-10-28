# Timerify — design

Date: 2026-10-28. Status: draft for owner review.
Background research: `docs/research/2026-10-28-feasibility.md`.

## 1. Intent

Home Assistant users who want "run the boiler for 45 minutes", "every weekday morning" or "turn
the AC on in 15 minutes for an hour, cooling at 24°" today build it out of helper timers plus
several automations per device. The owner does exactly that for their boiler. Timerify replaces
that pile with something that lives **on the device itself**, the way Powercalc attaches power
sensors to devices that have no meter: a plain switch becomes a smart timer socket — countdown,
program by the clock, pending commands — controllable from the dashboard, from the device page
and by voice through any conversation agent.

The mental model is the mechanical timer socket from a hardware store, done properly.

### The owner's real scenarios

- Boiler, winter mornings: on every working day 06:30–07:15, weekends 08:00–09:00, skipping
  Israeli public holidays.
- Boiler, evening before a shower: "turn it on for 45 minutes".
- Running boiler at 07:10: "30 more minutes".
- AC: "turn off in 15 minutes"; "turn on in 15 minutes for an hour, cooling, 24 degrees".
- Grow light, fans, anything else with on/off.

## 2. Goals, non-goals, anti-goals

**Goals**

1. One timer per target entity, the single source of truth for whether the target should run.
2. Works with any entity that can be turned on and off, regardless of domain (switch, light,
   fan, climate, humidifier, water heater, media player, input_boolean, …). No per-device code.
3. Countdown, add/subtract time, stop, pending (delayed) commands with device settings, weekly
   schedules aware of working days and public holidays.
4. Voice and AI control through whatever conversation agent the user has configured — every LLM
   agent and the built-in agent — without Timerify knowing or caring which.
5. Survives Home Assistant restarts and crashes without losing or mis-firing anything.
6. A modern dashboard card in two layouts (long "pill" in the Bubble Card style, and round).
7. Optional runtime counter, enabled per target like Powercalc's energy sensor.

**Non-goals for the first release**

- A sidebar overview page of all timers (planned for a later release; the data model must not
  prevent it).
- Calendar-event-driven scheduling (arbitrary dated events from a calendar entity). Holidays are
  handled through working-day sensors instead (see §5.5).
- Energy accounting (that is Powercalc's job; Timerify only counts runtime).

**Anti-goals — failure even if everything technically works**

- **Heavy setup.** Adding a device must take a few steps with sensible defaults. If a simple
  change needs visits to several screens, the design has failed. The owner named this as the
  most likely reason to uninstall.
- **Awkward add/edit/delete** of timers, schedule intervals, pending commands or counters.
- Ignoring a manual change the user just made (the user always wins over automation).
- Hidden behaviour that only exists in the card: everything the card does must be possible
  through standard entities and services.

## 3. Constraints

- Home Assistant 2026.10 or newer (`hacs.json`), Python 3.14 (dictated by Home Assistant).
- Only public, documented Home Assistant mechanisms. In particular:
  - attach entities to the target's device by setting `entity.device_entry` (from
    `homeassistant.helpers.device.async_entity_id_to_device`), never by copying the device's
    identifiers (that produces a duplicate device since 2026.8);
  - expose LLM tools through an `llm.py` platform (`async_get_tools`, `IntentTool`, tool names
    prefixed `timerify__`, `integration="timerify"`);
  - register intent handlers through `homeassistant.helpers.intent.async_register`.
- Configuration through the UI (config flow, options flow, config subentries). No YAML
  configuration.
- All user-facing strings translatable (`strings.json`). The repository itself is English-only;
  translations ship at least `en` and `ru`.
- One HACS repository can be only one HACS category, so the card ships inside the integration
  and the integration registers it as a dashboard resource itself.
- License: MIT. Code from GPL projects (e.g. ha-simple-timer) must not be copied.
- No sub-minute state writes while a timer runs: the precise remaining time is published as an
  end timestamp, and the frontend counts down on its own. Entities whose state is a number of
  minutes (the "Run for" `number`, the runtime counter) update at most once a minute. This keeps
  the recorder database small no matter how many timers exist. *(Assistant's call.)*

## 4. Where things live (decided with the owner)

| Layer | Job | In release 1 |
|---|---|---|
| Dashboard card | **Actions only**: set/add/stop the timer, toggle existing schedule intervals, cancel pending commands, link to settings | yes |
| Integration settings (Settings → Devices & services → Timerify) | **All configuration**: attach a target, binding mode, default duration, runtime counter, working-day sensor, schedule intervals, voice sentences toggle. Fully usable without the card | yes |
| Sidebar overview page | All timers at once, weekly view, comfortable schedule editor — a nicer face over the same data | later |

## 5. Concepts and behaviour

### 5.1 Target and the timer

A **target** is one existing entity. Each target has exactly one **timer**, stored as an
absolute UTC end time (or none). Remaining time is derived, never stored.

Everything that wants the target to run — the card, the `number` entity, services, voice, the
schedule, pending commands — does so **only by changing the timer** through one engine API
(set to a duration or an end time, add/subtract a delta, stop). Nothing else switches the target.
This single decision point is what makes conflicts impossible by construction.

### 5.2 Binding modes (per target)

- **Strict:** the target runs only while the timer is above zero.
- **Loose:** the target may also run with the timer at zero (simply without a countdown); a
  timer above zero means "turn off when it reaches zero".

### 5.3 Rules (normative)

- **R1.** Timer goes from zero to above zero → turn the target on (applying settings if the
  writer supplied them, see §5.4).
- **R2.** Timer reaches zero (expiry or explicit 0/stop) → turn the target off.
- **R3.** Target is turned off by anyone else (wall switch, vendor app, another automation) →
  timer becomes zero. Both modes.
- **R4.** Strict mode only: target is turned on by anyone else while the timer is zero → timer is
  set to the target's **default duration** (configured per target, e.g. 45 min for the boiler).
  This subsumes "auto-off after X": there is no separate auto-off feature.
- **R5.** Loose mode: target turned on by anyone else → nothing happens to the timer.
- **R6.** Timerify recognises its own service calls by their `Context` and does not react to them
  as "someone else".
- **R7.** Adding time to a running timer extends it (07:10, 5 min left, "+30" → ends 07:45).
- **R8.** Manual changes always win over the schedule (see §5.5).
- **R9.** Open-ended run (loose mode only): a command that turns the target on without a
  duration — a pending "turn on" with no duration, voice "turn on X" routed to Timerify, the card's
  long press — turns the target on with the timer at zero. In strict mode the same command sets
  the timer to the default duration. The engine therefore has one more operation besides
  set/add/stop: "run without countdown", valid only in loose mode. *(Assistant's call.)*
- **R10.** `unavailable` and `unknown` are not "off": a Wi-Fi drop never clears a timer. The
  engine keeps the *desired* state (from the timer) apart from the *actual* state. Anything that
  fires while the target is unavailable — expiry, a schedule start, a pending command — is
  applied when the target becomes available again, if it is still relevant then (a timer that
  has meanwhile expired turns the target off; an "on" whose window has passed is dropped and
  logged). The startup reconciliation in §5.7 is the same mechanism. *(Assistant's call.)*

### 5.4 Settings ("turn on how")

A command that turns a target on may carry settings supported by that target: for climate the
HVAC mode, target temperature and fan mode; for a light the brightness; and so on. Available
settings are derived from the target's own capabilities (supported features and attribute lists
such as `hvac_modes`), so the UI and voice only offer what the device can do. Without settings,
the target is turned on plainly.

The same notion applies to schedule intervals (each interval may carry settings) and pending
commands.

When settings are applied *(assistant's call, following "manual wins")*:

- a command that turns the target on applies its settings;
- a pending command applies its settings even when the target is already running (P1 — it is an
  explicit request);
- a schedule interval that starts while the target is already running does **not** push its
  settings (someone chose the current settings by hand); it only extends the timer per S1;
- with overlapping intervals, the timer's end follows S1 and the interval whose end the timer now
  carries is the one S2 remembers.

"Apply settings" is therefore an engine operation separate from changing the timer.

"Is on" and "turn on/off" differ per domain (climate is "on" when its HVAC mode is not `off`;
media players have several active states). A small per-domain table defines these, with a
generic fallback (`homeassistant.turn_on`/`turn_off`, state `on`) for domains not in it. Adding a
domain is a table entry, not new code paths.

### 5.5 Schedules

A target has any number of **schedule intervals**. Each interval has:

- days: either a set of weekdays, or "working days" / "non-working days" according to a chosen
  Workday binary sensor (core `workday` integration, which knows country-specific weekends and
  public holidays — e.g. Israel's Sunday–Thursday week and its holidays);
- start and end time of day (an interval may cross midnight);
- optional settings (§5.4);
- an enabled flag (a `switch` entity, toggled from the card).

Schedules are **declarative**: an interval means "the target should run during this window".

- **S1.** When an interval starts, the timer is set to the interval's end — unless the timer
  already ends later, in which case it is left alone (the manual extension wins).
- **S2.** The timer remembers whether its current end was set by a schedule interval. While it
  was, and nobody changed it manually since, editing or disabling that interval realigns the
  timer immediately: shorten, extend, or stop (and start later if the window moved ahead).
  Editing at 07:00 from 06:00–08:00 to 06:00–07:30 makes the timer end at 07:30.
- **S3.** Once the timer was changed manually (add, set, stop, voice), schedule edits no longer
  touch it until it next reaches zero.
- **S4.** If the target was turned off manually during an interval (R3), the interval does not
  turn it back on before the next window. This suppression is persisted and survives a restart.
- **S5.** Turning the target on by hand during an active window follows R4/R5 as usual (strict
  mode: default duration); the window does not stretch a manual run to its own end.
  *(Assistant's call.)*

### 5.6 Pending commands

A pending command is "at time T, do X": turn on (optionally for a duration, optionally with
settings) or turn off. Created from the card, services or voice ("turn on in 15 minutes for an
hour, cooling, 24"). Several can exist per target. Each can be cancelled individually.

- **P1.** A pending command is a firm promise: at T it executes regardless of the target's state
  at that time. If the AC is already running, it receives cooling 24° and the timer is set to
  60 minutes.
- **P2.** Manual use of the target between now and T does not cancel it. Only an explicit cancel
  (card, service, voice) does.
- **P3.** A "turn on for N" command at T is the same as a manual "set timer to N" at T (so it
  wins over the schedule, R8).

### 5.7 Restarts

On start, after Home Assistant is running and the target is available (event-driven, no
polling loops, no sleeps), Timerify reconciles every target:

- a timer whose end passed while Home Assistant was down → turn the target off;
- a running timer → re-arm for the remainder;
- a schedule window that is active now → apply S1 for the remainder of the window;
- a pending command whose time passed → execute it for whatever is left of its duration, or drop
  it (and log it) if nothing is left;
- the target's actual state disagrees with the timer → apply R3/R4 as if the change had just
  happened.

State is persisted in `homeassistant.helpers.storage.Store` on every change (not via
`RestoreEntity`, which dumps only every 15 minutes).

### 5.8 Runtime counter (optional)

When enabled for a target, a sensor accumulates how long the target was on (counting every "on",
not only those caused by Timerify). It is a `total_increasing` duration that updates once a
minute while the target is on, so long-term statistics attribute runtime to the right hour and
day (a run across midnight splits correctly) and give daily/weekly views without extra entities.

## 6. What the user sees

### 6.1 Entities per target

All attached to the target's device (when the target has no device, Timerify creates one named
after it):

- `number` "Run for" (minutes): reads as the remaining minutes rounded up, refreshed once a
  minute while running (see §3); writing sets the timer, 0 stops.
- `sensor` "Ends at" (timestamp, empty when idle) — the frontend renders "in 7 minutes" by itself.
- `switch` per schedule interval (enabled flag).
- `sensor` "Next command" (timestamp of the next pending command), with the list of pending
  commands available to the card and to voice "what is scheduled".
- `sensor` "Runtime" when the counter is enabled.

### 6.2 Setup and settings (integration page)

Config entries *(assistant's call)*: one config entry per target, as Powercalc does; schedule
intervals are config subentries of that target's entry. The config flow starts with a menu:

- **Add target:** pick the entity → binding mode → default duration (strict only) → optional
  runtime counter → optional Workday sensor. Sensible defaults on every step; three clicks for
  the common case. The options flow changes any of these later.
- **Voice settings:** a single-instance entry holding the "Add voice sentences for the built-in
  agent" option and the languages (§6.4). It is offered in the menu only while it does not exist.

Schedule intervals are added, edited and deleted one by one from the target's entry on the
integration page.

### 6.3 Dashboard card

One custom card, `timerify-card`, with a layout option:

- **Pill (long):** Bubble-Card-style pill; the fill shows timer progress; icon, name, remaining
  time and end time; an optional quick "+N" chip.
- **Round:** compact tile with a progress ring, remaining time in the centre, name below; meant to
  sit several in a row.

Tap opens the same pop-up for both: duration presets, ±, stop, schedule interval toggles, pending
commands with cancel, and a link to the target's settings. Creating and editing schedules is not
done in the pop-up. Long press (round layout) starts the default duration or stops the timer.
The card has a visual editor. Everything it does goes through Timerify's entities and services.

### 6.4 Voice and AI

- **LLM agents** (any of them): Timerify contributes tools through the LLM API — set/add/stop a
  timer, create/cancel pending commands with settings, query remaining time and pending commands,
  enable/disable schedule intervals. Tools act on a target only when the **target entity** is
  exposed to Assist and address it by its exposed name. Timerify's own entities are not meant to
  be exposed (the README says so), so the LLM sees one way to control a timer, not two.
  Language-agnostic. *(Assistant's call.)*
- **Built-in agent:** Timerify registers its intent handlers. Since an integration has no public
  way to add sentences, a global option writes one managed file per language,
  `custom_sentences/<lang>/timerify.yaml` (header: managed by Timerify, do not edit), and
  reloads conversation; unticking removes the files. The README documents copying the same files
  by hand.
- Sentence scope *(owner)*: the full set — set/add/stop the timer, "how much is left", pending
  commands with settings ("in 15 minutes for an hour, cooling, 24"), schedule interval on/off.
  Languages: `en` and `ru` for now.
- **Core delayed commands are taken over for Timerify targets only** *(owner)*. Phrases like
  "turn off the AC in 15 minutes" on a Timerify target become Timerify commands instead of core's
  uncancellable, non-persistent delayed command. For "turn off X in N minutes" on a running
  target this means **set the timer to N** (replacing whatever was left), not a separate pending
  "off"; on a target that is already off, nothing changes and the response says so.
  To keep every other entity on core's behaviour, the managed sentence files match only
  Timerify targets: they carry a generated list of target names, regenerated whenever a target is
  added, renamed or removed. Sentences must never match a non-Timerify entity.
- Voice responses are translated.

## 7. Phasing (recommended build order)

1. Engine + `number`/`sensor` entities + config/options flow + restarts (R1–R8, §5.7). This alone
   replaces the owner's evening "45 minutes" automation.
2. Settings (§5.4) and pending commands (§5.6).
3. Schedules with Workday sensors (§5.5).
4. Voice: LLM tools, intents, managed sentence files.
5. Card (both layouts).
6. Runtime counter.

Each phase ends with a full local run of tests, lint and type checks; behaviour is tested as user
scenarios (manual off during a countdown, restart in the middle of a window, schedule edit while
running, etc.) with time frozen and moved explicitly.

## 8. Left to the builder

- Module layout, the engine's internal API, storage schema (versioned, with migrations).
- Card tooling (Lit + TypeScript is the conventional choice) and how it is bundled and
  registered.
- Exact entity names, icons, translation keys, maximum durations and number step.
- Contents of the per-domain table (§5.4) beyond climate/light/fan/switch.
- E2E approach for the card and the flows (e.g. a real Home Assistant in a container driven by
  Playwright).
