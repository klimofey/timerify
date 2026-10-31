import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { common as russian } from "../../custom_components/timerify/translations/ru.json";
import type { TimerifyCard } from "../src/timerify-card";
import {
  AC,
  AC_ENDS_AT,
  AC_NEXT_COMMAND,
  AC_NUMBER,
  ENDS_AT,
  NEXT_COMMAND,
  NUMBER,
  START,
  acTimer,
  boilerTimer,
  fakeHass,
  type FakeHass,
  type Language,
} from "./fake-hass";
import { mountCard, popupOf } from "./mount";

const MINUTE = 60_000;
const SECOND = 1000;

/** The boiler's one interval, "06:30–07:15", and the switch that enables it. */
const INTERVAL = { entity_id: "switch.boiler_schedule_06_30_07_15_mon_sun", title: "06:30–07:15" };

/** A pending command as the "Next command" sensor lists it. */
interface Command {
  id: string;
  at: string;
  action: "on" | "off";
  minutes: number | null;
  settings: Record<string, unknown>;
}

const isoAt = (moment: number) => new Date(moment).toISOString();

/** On in a quarter of an hour (09:15 on the server's clock) for an hour. */
const TURN_ON: Command = {
  id: "c1",
  at: isoAt(START + 15 * MINUTE),
  action: "on",
  minutes: 60,
  settings: {},
};
/** Off at 07:00 on Tuesday, the server's clock. */
const TURN_OFF: Command = {
  id: "c2",
  at: isoAt(Date.UTC(2026, 0, 6, 5, 0)),
  action: "off",
  minutes: null,
  settings: {},
};

beforeEach(() => {
  vi.useFakeTimers({ now: START });
});

afterEach(() => {
  vi.restoreAllMocks();
  document.body.replaceChildren();
  vi.useRealTimers();
});

interface Situation {
  /** Minutes left of a countdown that began now; none if the timer is idle. */
  counting?: number;
  commands?: Command[];
  isAdmin?: boolean;
  language?: Language;
}

/** The Boiler timer, with its one interval, as the scenarios of the pop-up find it. */
function boilerHass({ counting, commands = [], isAdmin, language }: Situation = {}): FakeHass {
  let hass = fakeHass({
    timers: [boilerTimer({ intervals: [INTERVAL] })],
    timeFormat: "24",
    isAdmin,
    language,
  });
  if (counting !== undefined) {
    hass = hass.state(ENDS_AT, isoAt(START + counting * MINUTE), { started_at: isoAt(START) });
  }
  return hass.state(NEXT_COMMAND, commands[0]?.at ?? "unknown", { commands });
}

/** The AC, which runs with no countdown when it is `running`, as a thermostat does. */
function acHass({ commands = [] }: Situation = {}, running = false): FakeHass {
  const hass = fakeHass({ timers: [acTimer()], timeFormat: "24" });
  return (running ? hass.state(AC, "cool", { friendly_name: "AC", temperature: 24 }) : hass).state(
    AC_NEXT_COMMAND,
    commands[0]?.at ?? "unknown",
    { commands },
  );
}

/** The words of an element as a person reads them: its text, in one line. */
const textIn = (element: Element | null | undefined) =>
  (element?.textContent ?? "").replace(/\s+/g, " ").trim();

/** What the control is called to someone who cannot see it. */
const nameOfControl = (control: Element) =>
  control.getAttribute("aria-label") ?? textIn(control);

async function opened(hass: FakeHass, config: Record<string, unknown> = { entity: NUMBER }) {
  const card = await mountCard(hass, config);
  const popup = popupOf(card);
  popup.open();
  await popup.updateComplete;
  return { card, popup, root: popup.shadowRoot as ShadowRoot };
}

const dialogOf = (root: ShadowRoot) => root.querySelector("dialog") as HTMLDialogElement;

/** The one control (button or link) with this name; the scenario fails if there are not one. */
function control(root: ShadowRoot, name: string): HTMLElement {
  const found = [...root.querySelectorAll<HTMLElement>("button, a, [role='switch']")].filter(
    (candidate) => nameOfControl(candidate) === name,
  );
  expect(found, `the controls named "${name}"`).toHaveLength(1);
  return found[0] as HTMLElement;
}

const queryControl = (root: ShadowRoot, name: string) =>
  [...root.querySelectorAll("button, a")].find((c) => nameOfControl(c) === name) ?? null;

const isDisabled = (element: HTMLElement) => (element as HTMLButtonElement).disabled;

const addTime = (minutes: number, entity = NUMBER) => ({
  domain: "timerify",
  service: "add_time",
  data: { minutes },
  target: { entity_id: entity },
});
const stopped = (entity = NUMBER) => ({
  domain: "number",
  service: "set_value",
  data: { value: 0 },
  target: { entity_id: entity },
});

/** Lets what a press started (a call to Home Assistant) and what it changed settle. */
async function settle(card: TimerifyCard): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
  await card.updateComplete;
  await popupOf(card).updateComplete;
}

describe("the presets", () => {
  it("runs a preset and stays open", async () => {
    const hass = boilerHass();
    const { card, root } = await opened(hass);

    control(root, "45 min").click();
    await settle(card);

    expect(hass.calls).toEqual([
      { domain: "number", service: "set_value", data: { value: 45 }, target: { entity_id: NUMBER } },
    ]);
    expect(dialogOf(root).open).toBe(true);
  });

  it("offers the presets of the card, in its order", async () => {
    const { root } = await opened(boilerHass(), { entity: NUMBER, presets: [90, 15, 60] });

    const presets = [...root.querySelectorAll(".preset")].map(textIn);

    expect(presets).toEqual(["1 hr 30 min", "15 min", "1 hr"]);
  });

  it("labels presets in the user's language", async () => {
    const { root } = await opened(boilerHass(), { entity: NUMBER, presets: [15, 60, 90] });

    const presets = [...root.querySelectorAll(".preset")].map(textIn);

    // Intl's own composition, as English writes hours and minutes.
    const unit = (count: number, name: "hour" | "minute") =>
      new Intl.NumberFormat("en", {
        style: "unit",
        unit: name,
        unitDisplay: "short",
        useGrouping: false,
      }).format(count);
    expect(presets).toEqual([
      unit(15, "minute"),
      unit(1, "hour"),
      `${unit(1, "hour")} ${unit(30, "minute")}`,
    ]);
  });

  it("labels presets in Russian through Intl", async () => {
    const unit = (count: number, name: "hour" | "minute") =>
      new Intl.NumberFormat("ru", {
        style: "unit",
        unit: name,
        unitDisplay: "short",
        useGrouping: false,
      }).format(count);
    const { root } = await opened(boilerHass({ language: "ru" }), {
      entity: NUMBER,
      presets: [1, 2, 5, 21, 90],
    });

    const presets = [...root.querySelectorAll(".preset")].map(textIn);

    expect(presets).toEqual([
      unit(1, "minute"),
      unit(2, "minute"),
      unit(5, "minute"),
      unit(21, "minute"),
      `${unit(1, "hour")} ${unit(30, "minute")}`,
    ]);
    // No word of the English file is glued to a number.
    const englishWords = Object.values(english)
      .flatMap((text) => text.split(/[^A-Za-z]+/))
      .concat(["min", "hr"])
      .filter((word) => word.length > 1);
    for (const preset of presets) {
      for (const word of englishWords) {
        expect(preset, `"${word}" in a Russian preset`).not.toMatch(new RegExp(`\\b${word}\\b`));
      }
    }
  });
});

describe("adding and taking off time", () => {
  it("adds and takes off five minutes", async () => {
    const hass = boilerHass({ counting: 45 });
    const { card, root } = await opened(hass);

    control(root, "Add 5 min").click();
    control(root, "Take off 5 min").click();
    await settle(card);

    expect(hass.calls).toEqual([addTime(5), addTime(-5)]);
    expect(dialogOf(root).open).toBe(true);
  });

  it("shows the step on the buttons, as it says it to those who cannot see them", async () => {
    const { root } = await opened(boilerHass({ counting: 45 }));

    expect(textIn(control(root, "Add 5 min"))).toBe("+5 min");
    expect(textIn(control(root, "Take off 5 min"))).toBe("−5 min");
  });

  it("names the step in the user's language", async () => {
    const hass = boilerHass({ counting: 45, language: "ru" });
    const { root } = await opened(hass);
    const step = new Intl.NumberFormat("ru", {
      style: "unit",
      unit: "minute",
      unitDisplay: "short",
      useGrouping: false,
    }).format(5);

    expect(control(root, russian.card_add_time.replace("{duration}", step))).toBeTruthy();
    expect(control(root, russian.card_subtract_time.replace("{duration}", step))).toBeTruthy();
  });

  it("offers no minus and no stop while idle", async () => {
    const { root } = await opened(boilerHass());

    expect(isDisabled(control(root, "Take off 5 min"))).toBe(true);
    expect(isDisabled(control(root, "Stop"))).toBe(true);
    // A countdown can still be added to, or begun, from here.
    expect(isDisabled(control(root, "Add 5 min"))).toBe(false);
    expect(isDisabled(control(root, "45 min"))).toBe(false);
  });

  it("offers the minus and the stop while it counts", async () => {
    const { root } = await opened(boilerHass({ counting: 45 }));

    expect(isDisabled(control(root, "Take off 5 min"))).toBe(false);
    expect(isDisabled(control(root, "Stop"))).toBe(false);
  });

  it("offers no minus to a target that runs without a countdown, but a stop", async () => {
    const { root } = await opened(acHass({}, true), { entity: AC_NUMBER });

    expect(isDisabled(control(root, "Take off 5 min"))).toBe(true);
    expect(isDisabled(control(root, "Stop"))).toBe(false);
  });

  it("offers nothing to press while the timer is unavailable", async () => {
    const hass = boilerHass({ counting: 45, commands: [TURN_ON] }).state(NUMBER, "unavailable");
    const { root } = await opened(hass);

    const pressable = [
      "45 min",
      "Add 5 min",
      "Take off 5 min",
      "Stop",
      english.card_cancel_command,
    ].filter((name) => !isDisabled(control(root, name)));

    expect(pressable).toEqual([]);
  });
});

describe("stopping", () => {
  it("stops a timer that counts and a target that runs without one", async () => {
    const counts = boilerHass({ counting: 45 });
    const first = await opened(counts);
    control(first.root, "Stop").click();
    await settle(first.card);
    expect(counts.calls).toEqual([stopped()]);
    expect(dialogOf(first.root).open).toBe(true);

    const runs = acHass({}, true);
    const second = await opened(runs, { entity: AC_NUMBER });
    control(second.root, "Stop").click();
    await settle(second.card);
    expect(runs.calls).toEqual([stopped(AC_NUMBER)]);
  });

  it("stops being offered when the timer has stopped", async () => {
    const hass = boilerHass({ counting: 45 });
    const { card, root } = await opened(hass);

    card.hass = hass.state(ENDS_AT, "unknown");
    await settle(card);

    expect(isDisabled(control(root, "Stop"))).toBe(true);
    expect(isDisabled(control(root, "Take off 5 min"))).toBe(true);
  });
});

describe("the title", () => {
  const remainingOf = (root: ShadowRoot) => textIn(root.querySelector(".remaining"));
  const untilOf = (root: ShadowRoot) => textIn(root.querySelector(".until"));

  it("says the time left and when the countdown ends", async () => {
    const { root } = await opened(boilerHass({ counting: 45 }));

    expect(remainingOf(root)).toBe("45:00");
    expect(untilOf(root)).toBe(english.card_until.replace("{time}", "09:45"));
  });

  it("says nothing of a countdown while there is none", async () => {
    const { root } = await opened(boilerHass());

    expect(root.querySelector(".remaining")).toBeNull();
    expect(root.querySelector(".until")).toBeNull();
  });

  it("counts down while open", async () => {
    const { card, root } = await opened(boilerHass({ counting: 45 }));

    await vi.advanceTimersByTimeAsync(SECOND);
    await card.updateComplete;
    await popupOf(card).updateComplete;
    expect(remainingOf(root)).toBe("44:59");

    await vi.advanceTimersByTimeAsync(59 * SECOND);
    await card.updateComplete;
    await popupOf(card).updateComplete;
    expect(remainingOf(root)).toBe("44:00");
  });

  it("follows the timer while open", async () => {
    const hass = boilerHass({ counting: 45 });
    const { card, root } = await opened(hass);

    card.hass = hass.state(ENDS_AT, isoAt(START + 50 * MINUTE), { started_at: isoAt(START) });
    await settle(card);

    expect(remainingOf(root)).toBe("50:00");
    expect(untilOf(root)).toBe(english.card_until.replace("{time}", "09:50"));
  });
});

describe("the schedule", () => {
  const switchOf = (root: ShadowRoot) => root.querySelector<HTMLElement>('[role="switch"]');

  it("switches an interval", async () => {
    const hass = boilerHass();
    const { card, root } = await opened(hass);
    const interval = control(root, INTERVAL.title);
    expect(interval.getAttribute("role")).toBe("switch");
    expect(interval.getAttribute("aria-checked")).toBe("true");

    interval.click();
    await settle(card);
    expect(hass.calls).toEqual([
      { domain: "switch", service: "turn_off", data: {}, target: { entity_id: INTERVAL.entity_id } },
    ]);

    // Home Assistant switches it; the pop-up shows what it was told, and stays open.
    card.hass = hass.state(INTERVAL.entity_id, "off");
    await settle(card);
    expect(switchOf(root)?.getAttribute("aria-checked")).toBe("false");
    switchOf(root)?.click();
    await settle(card);
    expect(hass.calls.at(-1)).toEqual({
      domain: "switch",
      service: "turn_on",
      data: {},
      target: { entity_id: INTERVAL.entity_id },
    });
    expect(dialogOf(root).open).toBe(true);
  });

  it("is titled in the user's language", async () => {
    const { root } = await opened(boilerHass({ language: "ru" }));

    expect(textIn(root.querySelector(".schedule h3"))).toBe(russian.card_schedule);
  });

  it("leaves out the schedule when there is no interval", async () => {
    const hass = fakeHass({ timers: [boilerTimer()] });
    const { root } = await opened(hass);

    expect(root.querySelector(".schedule")).toBeNull();
    expect(root.querySelector('[role="switch"]')).toBeNull();
    expect(root.textContent).not.toContain(english.card_schedule);
  });

  it("shows an interval whose switch is disabled as unavailable", async () => {
    // A disabled entity has no state; Timerify lists its switch all the same.
    const hass = boilerHass().with({ states: { [INTERVAL.entity_id]: null } });
    const { card, root } = await opened(hass);

    const interval = control(root, `${INTERVAL.title} unavailable`);

    expect(interval.getAttribute("role")).toBe("switch");
    expect(interval.getAttribute("aria-checked")).toBe("false");
    expect(isDisabled(interval)).toBe(true);
    interval.click();
    await settle(card);
    expect(hass.calls).toEqual([]);
  });

  it("shows an interval whose switch is unavailable the same way", async () => {
    const hass = boilerHass().state(INTERVAL.entity_id, "unavailable");
    const { root } = await opened(hass);

    const interval = control(root, `${INTERVAL.title} unavailable`);

    expect(isDisabled(interval)).toBe(true);
    expect(interval.getAttribute("aria-checked")).toBe("false");
  });

  it("returns to the switch when the entity comes back", async () => {
    const hass = boilerHass().with({ states: { [INTERVAL.entity_id]: null } });
    const { card, root } = await opened(hass);

    card.hass = hass.state(INTERVAL.entity_id, "on");
    await settle(card);

    const interval = control(root, INTERVAL.title);
    expect(isDisabled(interval)).toBe(false);
    expect(interval.getAttribute("aria-checked")).toBe("true");
  });
});

describe("the pending commands", () => {
  const rowsOf = (root: ShadowRoot) =>
    [...root.querySelectorAll(".commands li")].map((row) => textIn(row.querySelector(".command")));

  it("lists the pending commands and cancels one", async () => {
    const hass = boilerHass({ commands: [TURN_ON, TURN_OFF] });
    const { card, root } = await opened(hass);

    expect(rowsOf(root)).toEqual(["On at 09:15 for 1 hr", "Off at Tue 07:00"]);
    const [first] = root.querySelectorAll<HTMLElement>(".commands li button");
    expect(first?.getAttribute("aria-label")).toBe(english.card_cancel_command);
    first?.click();
    await settle(card);

    expect(hass.calls).toEqual([
      {
        domain: "timerify",
        service: "cancel_command",
        data: { command_id: "c1" },
        target: { entity_id: NUMBER },
      },
    ]);
    expect(dialogOf(root).open).toBe(true);
  });

  it("cancels the command of the row, not another", async () => {
    const hass = boilerHass({ commands: [TURN_ON, TURN_OFF] });
    const { card, root } = await opened(hass);

    root.querySelectorAll<HTMLElement>(".commands li button")[1]?.click();
    await settle(card);

    expect(hass.calls.map(({ data }) => data)).toEqual([{ command_id: "c2" }]);
  });

  it("tells each cancel button apart for someone who cannot see the rows", async () => {
    const { root } = await opened(boilerHass({ commands: [TURN_ON, TURN_OFF] }));

    const described = [...root.querySelectorAll(".commands li button")].map((button) => {
      const id = button.getAttribute("aria-describedby") ?? "";
      return textIn(root.getElementById(id));
    });

    expect(described).toEqual(["On at 09:15 for 1 hr", "Off at Tue 07:00"]);
  });

  it("says a command that turns on with no duration without one", async () => {
    const forever = { ...TURN_ON, minutes: null };
    const { root } = await opened(boilerHass({ commands: [forever] }));

    expect(rowsOf(root)).toEqual(["On at 09:15"]);
  });

  it("writes the times and durations in the user's language", async () => {
    const { root } = await opened(boilerHass({ commands: [TURN_ON], language: "ru" }));
    const hour = new Intl.NumberFormat("ru", {
      style: "unit",
      unit: "hour",
      unitDisplay: "short",
      useGrouping: false,
    }).format(1);

    expect(rowsOf(root)).toEqual([
      russian.card_command_on_for.replace("{time}", "9:15").replace("{duration}", hour),
    ]);
    expect(textIn(root.querySelector(".commands h3"))).toBe(russian.card_commands);
    expect(root.querySelector(".commands button")?.getAttribute("aria-label")).toBe(
      russian.card_cancel_command,
    );
  });

  it("reads right in Russian on the day and on another day of the week", async () => {
    const { root } = await opened(boilerHass({ commands: [TURN_ON, TURN_OFF], language: "ru" }));
    const hour = new Intl.NumberFormat("ru", {
      style: "unit",
      unit: "hour",
      unitDisplay: "short",
      useGrouping: false,
    }).format(1);
    const weekday = new Intl.DateTimeFormat("ru", { weekday: "short", timeZone: "UTC" }).format(
      Date.parse(TURN_OFF.at),
    );

    // No preposition stands before the time: one before a weekday would be wrong Russian.
    expect(rowsOf(root)).toEqual([
      russian.card_command_on_for.replace("{time}", "9:15").replace("{duration}", hour),
      russian.card_command_off.replace("{time}", `${weekday} 07:00`),
    ]);
    expect(weekday).not.toBe("");
  });

  it("leaves out the section when nothing is pending", async () => {
    const { root } = await opened(boilerHass());

    expect(root.querySelector(".commands")).toBeNull();
    expect(root.textContent).not.toContain(english.card_commands);
  });

  it("follows the commands while open", async () => {
    const hass = boilerHass({ commands: [TURN_ON, TURN_OFF] });
    const { card, root } = await opened(hass);

    card.hass = hass.state(NEXT_COMMAND, TURN_OFF.at, { commands: [TURN_OFF] });
    await settle(card);

    expect(rowsOf(root)).toEqual(["Off at Tue 07:00"]);
  });

  it("says a command's settings", async () => {
    const turnOn: Command = {
      ...TURN_ON,
      settings: { hvac_mode: "cool", temperature: 24 },
    };
    const hass = acHass({ commands: [turnOn] });
    hass.formatEntityState = (entity, state) => `${entity.entity_id} is ${state}`;
    hass.formatEntityAttributeValue = (entity, attribute, value) =>
      `${entity.entity_id} ${attribute} ${value}`;
    const { root } = await opened(hass, { entity: AC_NUMBER });

    expect(rowsOf(root)).toEqual(["On at 09:15 for 1 hr climate.ac is cool, climate.ac temperature 24"]);
  });

  it("says the settings of another kind of target in Home Assistant's words for it", async () => {
    const fan = "fan.bedroom";
    const info = acTimer().info;
    const turnOn: Command = { ...TURN_ON, settings: { preset_mode: "sleep", percentage: 40 } };
    const hass = fakeHass({
      timers: [{ ...acTimer(), info: { ...info, target: fan } }],
      timeFormat: "24",
      states: { [fan]: { state: "off", attributes: { friendly_name: "Fan" } } },
    }).state(AC_NEXT_COMMAND, TURN_ON.at, { commands: [turnOn] });
    hass.formatEntityAttributeValue = (entity, attribute, value) =>
      `${entity.entity_id} ${attribute} ${value}`;
    const { root } = await opened(hass, { entity: AC_NUMBER });

    expect(rowsOf(root)).toEqual([
      `On at 09:15 for 1 hr fan.bedroom preset_mode sleep, ${new Intl.NumberFormat("en", { style: "percent" }).format(0.4)}`,
    ]);
  });

  it("leaves out a row it cannot read, and shows the others", async () => {
    const hass = boilerHass().state(NEXT_COMMAND, TURN_OFF.at, {
      commands: [{ id: "broken", at: "not a time" }, null, TURN_OFF],
    });
    const { root } = await opened(hass);

    expect(rowsOf(root)).toEqual(["Off at Tue 07:00"]);
  });

  it("leaves out a command whose action it does not know", async () => {
    const hass = boilerHass().state(NEXT_COMMAND, TURN_OFF.at, {
      commands: [{ ...TURN_ON, id: "strange", action: "toggle" }, TURN_OFF],
    });
    const { root } = await opened(hass);

    expect(rowsOf(root)).toEqual(["Off at Tue 07:00"]);
  });

  it("shows no section for a sensor that has no list", async () => {
    const hass = boilerHass().state(NEXT_COMMAND, "unavailable");
    const { root } = await opened(hass);

    expect(root.querySelector(".commands")).toBeNull();
  });
});

describe("the settings link", () => {
  const URL_OF_BOILER = "/config/integrations/integration/timerify#config_entry=boiler_entry";

  it("shows the settings link to an admin only", async () => {
    const admin = await opened(boilerHass({ isAdmin: true }));
    expect(admin.root.querySelector<HTMLAnchorElement>("a")?.getAttribute("href")).toBe(
      URL_OF_BOILER,
    );
    expect(textIn(admin.root.querySelector("a"))).toBe(english.card_settings);
    document.body.replaceChildren();

    const user = await opened(boilerHass({ isAdmin: false }));
    expect(user.root.querySelector("a")).toBeNull();
    expect(user.root.textContent).not.toContain(english.card_settings);
  });

  /**
   * What Home Assistant's frontend does with every click that reaches the window: it follows
   * the link of a plain anchor of its own origin, unless the click was cancelled. This stands
   * in for that listener, to see what it would be given.
   */
  function watchWindowClicks(root: ShadowRoot, signal: AbortSignal) {
    const seen: { cancelled: boolean; href: string | undefined; popupOpen: boolean }[] = [];
    const listener = (event: MouseEvent) => {
      const anchor = event
        .composedPath()
        .find((node): node is HTMLAnchorElement => node instanceof HTMLAnchorElement);
      seen.push({
        cancelled: event.defaultPrevented,
        href: anchor?.getAttribute("href") ?? undefined,
        popupOpen: dialogOf(root).open,
      });
    };
    window.addEventListener("click", listener, { signal });
    return seen;
  }

  it("closes the pop-up and leaves the navigation to Home Assistant's own", async () => {
    const pushState = vi.spyOn(window.history, "pushState");
    const located = vi.fn();
    window.addEventListener("location-changed", located);
    const { card, root } = await opened(boilerHass({ isAdmin: true }));
    const watch = new AbortController();
    const seen = watchWindowClicks(root, watch.signal);

    root.querySelector("a")?.click();
    await popupOf(card).updateComplete;

    watch.abort();
    window.removeEventListener("location-changed", located);
    // The frontend finds the link, not cancelled, after the pop-up has got out of the way.
    expect(seen).toEqual([{ cancelled: false, href: URL_OF_BOILER, popupOpen: false }]);
    expect(dialogOf(root).open).toBe(false);
    // The card does not navigate on its own: the history entry is the frontend's to make.
    expect(pushState).not.toHaveBeenCalled();
    expect(located).not.toHaveBeenCalled();
  });

  it("leaves a click that asks for a new tab to the browser, and stays open", async () => {
    const { root } = await opened(boilerHass({ isAdmin: true }));
    const link = root.querySelector<HTMLAnchorElement>("a");
    const seen: boolean[] = [];
    // Registered after the card's own handler. It stops the test environment from
    // following the link, which the browser would do in a new tab.
    link?.addEventListener("click", (event) => {
      seen.push(event.defaultPrevented);
      event.preventDefault();
    });

    for (const modifier of ["ctrlKey", "metaKey", "shiftKey", "altKey"] as const) {
      link?.dispatchEvent(
        new MouseEvent("click", { bubbles: true, composed: true, cancelable: true, [modifier]: true }),
      );
    }

    expect(seen).toEqual([false, false, false, false]);
    expect(dialogOf(root).open).toBe(true);
  });
});

describe("when Home Assistant refuses", () => {
  it("stays open when Home Assistant refuses an action", async () => {
    const hass = boilerHass({ counting: 45, commands: [TURN_ON] });
    const { card, root } = await opened(hass);
    const presses = [
      () => control(root, "45 min").click(),
      () => control(root, "Add 5 min").click(),
      () => control(root, "Take off 5 min").click(),
      () => control(root, "Stop").click(),
      () => control(root, INTERVAL.title).click(),
      () => control(root, english.card_cancel_command).click(),
    ];

    for (const [index, press] of presses.entries()) {
      hass.rejectNext(new Error("Home Assistant refused"));
      press();
      await settle(card);
      expect(hass.calls, `after press ${index + 1}`).toHaveLength(index + 1);
      expect(dialogOf(root).open, `after press ${index + 1}`).toBe(true);
    }
  });
});

describe("what it renders", () => {
  it("shows the name of the timer as its title", async () => {
    const { root } = await opened(boilerHass({ counting: 45 }));

    expect(textIn(root.querySelector("h2"))).toBe("Boiler");
  });

  it("speaks the user's language in every section", async () => {
    const { root } = await opened(
      boilerHass({ counting: 45, commands: [TURN_ON], language: "ru", isAdmin: true }),
    );

    expect(nameOfControl(control(root, russian.card_stop))).toBe(russian.card_stop);
    expect(textIn(root.querySelector(".until"))).toBe(russian.card_until.replace("{time}", "9:45"));
    expect(textIn(root.querySelector("a"))).toBe(russian.card_settings);
  });

  it("reads the countdown of its own timer when the page has two", async () => {
    const ac = acTimer();
    const hass = fakeHass({ timers: [boilerTimer(), ac], timeFormat: "24" }).state(
      AC_ENDS_AT,
      isoAt(START + 10 * MINUTE),
      { started_at: isoAt(START) },
    );
    const { root } = await opened(hass, { entity: AC_NUMBER });

    expect(textIn(root.querySelector(".remaining"))).toBe("10:00");
    expect(textIn(root.querySelector("h2"))).toBe("AC");
  });
});
