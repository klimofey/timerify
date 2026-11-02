import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { common as russian } from "../../custom_components/timerify/translations/ru.json";
import type { HassEntity } from "../src/hass";
import type { TimerifyCard } from "../src/timerify-card";
import {
  AC,
  AC_ENDS_AT,
  AC_NEXT_COMMAND,
  AC_NUMBER,
  BOILER,
  ENDS_AT,
  NEXT_COMMAND,
  NUMBER,
  START,
  acTimer,
  boilerTimer,
  counting,
  fakeHass,
  localizeFor,
  type FakeHass,
} from "./fake-hass";
import { bodyOf, mountCard, nameOf, popupOf, renders, textOf } from "./mount";

// Another card of the page that registered itself before this one's module was loaded.
const earlierCards = vi.hoisted(() => {
  const cards = [{ type: "another-card", name: "Another card" }];
  window.customCards = cards;
  return cards;
});

const MINUTE = 60_000;
const SECOND = 1000;

const EVENING = "switch.boiler_schedule_18_00_19_00_mon_sun";
const EVENING_INTERVAL = { entity_id: EVENING, title: "18:00–19:00" };

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(START);
});

afterEach(() => {
  document.body.replaceChildren();
  vi.useRealTimers();
});

const warningOf = (card: TimerifyCard) => card.shadowRoot?.querySelector('[role="alert"]') ?? null;
const lookups = (hass: FakeHass) => hass.requests.filter(({ type }) => type === "timerify/timer");
const dialogOf = (card: TimerifyCard) => popupOf(card).shadowRoot?.querySelector("dialog");

/** How many times the card rendered because `hass` changed the state of one entity. */
async function rendersForChangeOf(card: TimerifyCard, hass: FakeHass, entityId: string) {
  card.hass = hass;
  await card.updateComplete;
  const before = renders(card);
  card.hass = hass.state(entityId, "changed");
  await card.updateComplete;
  return renders(card) - before;
}

describe("finding its timer", () => {
  it("asks Timerify for the timer of its number", async () => {
    const hass = fakeHass();

    await mountCard(hass);

    expect(hass.requests).toEqual([{ type: "timerify/timer", entity_id: NUMBER }]);
  });

  it("asks again when its number is another", async () => {
    const hass = fakeHass({ timers: [boilerTimer(), acTimer()] });
    const card = await mountCard(hass);

    card.setConfig({ entity: AC_NUMBER });
    await card.updateComplete;

    expect(lookups(hass).map(({ entity_id }) => entity_id)).toEqual([NUMBER, AC_NUMBER]);
    expect(nameOf(card)).toBe("AC");
  });

  it("does not ask again when only its looks change", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass);

    card.setConfig({ entity: NUMBER, name: "Water heater" });
    await card.updateComplete;

    expect(lookups(hass)).toHaveLength(1);
    expect(nameOf(card)).toBe("Water heater");
  });

  it("asks one question at a time, and shows the answer to the newest", async () => {
    const hass = fakeHass({ timers: [boilerTimer(), acTimer()] });
    hass.holdAnswers();
    const card = document.createElement("timerify-card") as TimerifyCard;
    card.setConfig({ entity: NUMBER });
    card.hass = hass;
    document.body.append(card);

    card.setConfig({ entity: AC_NUMBER });
    expect(lookups(hass)).toHaveLength(1);

    hass.answerNext();
    await vi.advanceTimersByTimeAsync(0);
    expect(lookups(hass).map(({ entity_id }) => entity_id)).toEqual([NUMBER, AC_NUMBER]);
    expect(textOf(card)).toBe("AC Run for");

    hass.answerNext();
    await card.updateComplete;
    expect(nameOf(card)).toBe("AC");
  });

  it("asks again when the connection returns", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass);

    card.hass = hass.with({ connected: false });
    await card.updateComplete;
    expect(lookups(hass)).toHaveLength(1);

    card.hass = hass.with({ connected: true });
    await card.updateComplete;
    expect(lookups(hass)).toHaveLength(2);
  });

  it("asks again when the entity registry changes", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass);

    card.hass = hass.with({ connected: true });
    await card.updateComplete;
    expect(lookups(hass)).toHaveLength(1);

    card.hass = hass.with({ entities: { ...hass.entities } });
    await card.updateComplete;
    expect(lookups(hass)).toHaveLength(2);
  });
});

describe("what it shows while it has no timer", () => {
  it("names the missing entity", async () => {
    const card = await mountCard(fakeHass({ timers: [] }));

    expect(textOf(card)).toBe(english.card_entity_not_found.replace("{entity}", NUMBER));
  });

  it("says when a number is not a timer's", async () => {
    const hass = fakeHass({ timers: [], states: { [NUMBER]: { state: "45" } } });

    const card = await mountCard(hass);

    expect(textOf(card)).toBe(english.card_not_a_timer.replace("{entity}", NUMBER));
  });

  it.each(["unavailable", "unknown"])(
    "tells a timer that cannot be shown, and not that its number is no timer's, while the number is %s",
    async (state) => {
      const hass = fakeHass({ states: { [NUMBER]: { state } } });
      hass.answerWith("timer_incomplete");

      const card = await mountCard(hass);

      expect(warningOf(card)?.textContent?.trim()).toBe(
        english.card_timer_incomplete.replace("{entity}", NUMBER),
      );
      expect(textOf(card)).not.toBe(english.card_not_a_timer.replace("{entity}", NUMBER));
      expect(card.shadowRoot?.querySelector("timerify-card-popup")).toBeNull();
    },
  );

  it("tells a timer that cannot be shown in the user's language", async () => {
    const hass = fakeHass({ language: "ru" });
    hass.answerWith("timer_incomplete");

    const card = await mountCard(hass);

    expect(textOf(card)).toBe(russian.card_timer_incomplete.replace("{entity}", NUMBER));
  });

  it("shows the timer again when what was missing is back", async () => {
    const hass = fakeHass();
    hass.answerWith("timer_incomplete");
    const card = await mountCard(hass);
    expect(warningOf(card)).not.toBeNull();

    hass.answerNormally();
    card.hass = hass.with({ entities: { ...hass.entities } });
    await card.updateComplete;

    expect(warningOf(card)).toBeNull();
    expect(nameOf(card)).toBe("Boiler");
  });

  it.each(["unavailable", "unknown"])("does not warn while the number is %s", async (state) => {
    const hass = fakeHass({ states: { [NUMBER]: { state } } });
    hass.answerWith("not_found");
    const card = await mountCard(hass);
    expect(warningOf(card)).toBeNull();

    hass.answerNormally();
    card.hass = hass.state(NUMBER, "0");
    await card.updateComplete;

    expect(lookups(hass)).toHaveLength(2);
    expect(nameOf(card)).toBe("Boiler");
    expect(warningOf(card)).toBeNull();
  });

  it("recovers when the number appears again", async () => {
    const hass = fakeHass({ states: { [NUMBER]: null } });
    hass.answerWith("not_found");
    const card = await mountCard(hass);
    expect(textOf(card)).toBe(english.card_entity_not_found.replace("{entity}", NUMBER));

    hass.answerNormally();
    card.hass = hass.state(NUMBER, "0", { friendly_name: "Boiler Run for" });
    await card.updateComplete;

    expect(lookups(hass)).toHaveLength(2);
    expect(nameOf(card)).toBe("Boiler");
  });

  it("asks again when the timer comes back after a restart", async () => {
    const hass = fakeHass({ states: { [NUMBER]: { state: "unavailable" } } });
    hass.answerWith("unknown_command");
    const card = await mountCard(hass);
    expect(warningOf(card)).toBeNull();

    hass.answerNormally();
    card.hass = hass.state(NUMBER, "45");
    await card.updateComplete;

    expect(lookups(hass)).toHaveLength(2);
    expect(nameOf(card)).toBe("Boiler");
    expect(warningOf(card)).toBeNull();
  });

  it("tells a user who may not see the timer so, and does not show it as unavailable", async () => {
    // The frontend sends a user no state of an entity the user may not read.
    const hass = fakeHass({ states: { [NUMBER]: null } });
    hass.answerWith("unauthorized");

    const card = await mountCard(hass);

    expect(warningOf(card)?.textContent?.trim()).toBe(
      english.card_not_allowed.replace("{entity}", NUMBER),
    );
    expect(card.shadowRoot?.querySelector("timerify-card-popup")).toBeNull();
    expect(card.shadowRoot?.querySelector(".status")).toBeNull();
  });

  it("tells it in the user's language", async () => {
    const hass = fakeHass({ language: "ru", states: { [NUMBER]: null } });
    hass.answerWith("unauthorized");

    const card = await mountCard(hass);

    expect(textOf(card)).toBe(russian.card_not_allowed.replace("{entity}", NUMBER));
  });

  it("recovers when the user is given the permission", async () => {
    const hass = fakeHass();
    hass.answerWith("unauthorized");
    const card = await mountCard(hass);
    expect(warningOf(card)).not.toBeNull();

    hass.answerNormally();
    card.hass = hass.with({ entities: { ...hass.entities } });
    await card.updateComplete;

    expect(warningOf(card)).toBeNull();
    expect(nameOf(card)).toBe("Boiler");
  });

  it("says nothing of a failure it cannot name, which may be a start", async () => {
    const hass = fakeHass();
    hass.answerWith("unknown_command");

    const card = await mountCard(hass);

    expect(warningOf(card)).toBeNull();
    expect(textOf(card)).toBe("Boiler Run for");
  });
});

describe("a sensor it cannot work without is disabled", () => {
  const withoutEndsAt = () => boilerTimer({ disabled_sensors: [ENDS_AT] });

  it("says which sensor to enable, instead of staying dead and silent", async () => {
    const card = await mountCard(fakeHass({ timers: [withoutEndsAt()] }));

    expect(warningOf(card)?.textContent?.trim()).toBe(
      english.card_ends_at_disabled.replace("{sensor}", ENDS_AT),
    );
    expect(english.card_ends_at_disabled).toContain("Ends at");
    expect(english.card_ends_at_disabled.toLowerCase()).toContain("enable");
    expect(card.shadowRoot?.querySelector("timerify-card-popup")).toBeNull();
  });

  it("says it in the user's language", async () => {
    const card = await mountCard(fakeHass({ language: "ru", timers: [withoutEndsAt()] }));

    expect(textOf(card)).toBe(russian.card_ends_at_disabled.replace("{sensor}", ENDS_AT));
  });

  it("shows the timer again when the sensor is enabled", async () => {
    const timer = withoutEndsAt();
    const hass = fakeHass({ timers: [timer] });
    const card = await mountCard(hass);
    expect(warningOf(card)).not.toBeNull();

    timer.info.disabled_sensors = [];
    card.hass = hass.with({
      entities: { ...hass.entities },
      states: { [ENDS_AT]: { state: "unknown", attributes: { started_at: null } } },
    });
    await card.updateComplete;

    expect(warningOf(card)).toBeNull();
    expect(textOf(card)).toBe("Boiler off");
  });

  it("does not blame a sensor that is enabled and has no state yet", async () => {
    // A timer that is starting: nothing is known of the sensor yet, and the registry says
    // it is enabled. The card waits quietly, as it always did.
    const hass = fakeHass({ states: { [ENDS_AT]: null } });

    const card = await mountCard(hass);

    expect(warningOf(card)).toBeNull();
    expect(nameOf(card)).toBe("Boiler");
  });

  it("does not blame the Next command sensor on the card, which works without it", async () => {
    const card = await mountCard(fakeHass({ timers: [boilerTimer({ disabled_sensors: [NEXT_COMMAND] })] }));

    expect(warningOf(card)).toBeNull();
    expect(nameOf(card)).toBe("Boiler");
  });
});

describe("what it shows of its timer", () => {
  it("shows the target's name and icon", async () => {
    const hass = fakeHass();

    const card = await mountCard(hass);

    expect(nameOf(card)).toBe("Boiler");
    const icon = card.shadowRoot?.querySelector("ha-state-icon") as { stateObj?: unknown };
    expect(icon.stateObj).toBe(hass.states[BOILER]);
  });

  it("takes the name and the icon of its config", async () => {
    const card = await mountCard(fakeHass(), {
      entity: NUMBER,
      name: "Water heater",
      icon: "mdi:water-boiler",
    });

    expect(nameOf(card)).toBe("Water heater");
    expect(card.shadowRoot?.querySelector("ha-state-icon")).toBeNull();
    const icon = card.shadowRoot?.querySelector("ha-icon") as { icon?: string };
    expect(icon.icon).toBe("mdi:water-boiler");
  });

  it("shows a timer whose interval switch is disabled in the registry", async () => {
    const timer = boilerTimer({ intervals: [EVENING_INTERVAL] });
    delete timer.states[EVENING];
    const hass = fakeHass({ timers: [timer] });

    const card = await mountCard(hass);
    expect(nameOf(card)).toBe("Boiler");

    card.hass = hass.state(EVENING, "on");
    await card.updateComplete;
    expect(nameOf(card)).toBe("Boiler");
  });

  it("speaks Russian as soon as its strings arrive", async () => {
    const hass = fakeHass({ language: "ru", stringsLoaded: false });
    const card = await mountCard(hass);

    card.hass = hass.with({ localize: localizeFor("ru") });
    await card.updateComplete;
    popupOf(card).open();
    await popupOf(card).updateComplete;

    const close = popupOf(card).shadowRoot?.querySelector("button.close");
    expect(close?.textContent?.trim()).toBe(russian.card_close);
  });

  it("words its warnings in Russian as soon as its strings arrive", async () => {
    const hass = fakeHass({ language: "ru", stringsLoaded: false, timers: [] });
    const card = await mountCard(hass);
    expect(textOf(card)).toBe(english.card_entity_not_found.replace("{entity}", NUMBER));

    card.hass = hass.with({ localize: localizeFor("ru") });
    await card.updateComplete;

    expect(textOf(card)).toBe(russian.card_entity_not_found.replace("{entity}", NUMBER));
  });
});

describe("rendering only when something it shows has changed", () => {
  it("does not render again for a change elsewhere in the home", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass);
    const before = renders(card);

    card.hass = hass.state("light.kitchen", "on");
    await card.updateComplete;

    expect(renders(card)).toBe(before);
  });

  it("renders again when its target changes", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass);
    const before = renders(card);

    card.hass = hass.state(BOILER, "on");
    await card.updateComplete;

    expect(renders(card)).toBe(before + 1);
  });

  it("uses the entities Timerify names, not the device's", async () => {
    const timers = [boilerTimer({ intervals: [EVENING_INTERVAL] }), acTimer()];
    const separate = fakeHass({ timers });
    const oneDevice = Object.fromEntries(
      Object.entries(separate.entities).map(([id, entry]) => [
        id,
        { ...entry, device_id: "multi_switch_device" },
      ]),
    );
    const hass = separate.with({ entities: oneDevice });
    const card = await mountCard(hass);

    for (const other of [AC_NUMBER, AC_ENDS_AT, AC_NEXT_COMMAND, AC]) {
      expect(await rendersForChangeOf(card, hass, other), other).toBe(0);
    }
    for (const own of [NUMBER, ENDS_AT, NEXT_COMMAND, BOILER, EVENING]) {
      expect(await rendersForChangeOf(card, hass, own), own).toBe(1);
    }
  });
});

describe("redrawing when the frontend brings new words", () => {
  /** A formatter that speaks the other language, as the frontend's does after it changed. */
  const spoken = (language: string) => ({
    formatEntityName: (entity: HassEntity) =>
      `${language} ${entity.attributes.friendly_name ?? entity.entity_id}`,
    formatEntityState: (entity: HassEntity, state?: string) =>
      `${language} ${state ?? entity.state}`,
    formatEntityAttributeValue: (entity: HassEntity, attribute: string, value?: unknown) =>
      `${language} ${value ?? entity.attributes[attribute]}`,
  });

  const textOfPopup = (card: TimerifyCard) =>
    (popupOf(card).shadowRoot?.querySelector("dialog")?.textContent ?? "").replace(/\s+/g, " ");

  /** A card with its pop-up open, on a timer that has an interval with no state and a command. */
  async function mountWithPopup() {
    const timer = boilerTimer({ intervals: [EVENING_INTERVAL] });
    delete timer.states[EVENING];
    const hass = fakeHass({ timers: [timer], timeFormat: "24" }).state(NEXT_COMMAND, "2026-01-05T08:00:00Z", {
      commands: [
        { id: "c1", at: "2026-01-05T08:00:00Z", action: "on", minutes: null, settings: { temperature: 24 } },
      ],
    });
    const card = await mountCard(hass);
    popupOf(card).open();
    await popupOf(card).updateComplete;
    return { hass, card };
  }

  it("renders the card and the open pop-up for a new state formatter alone", async () => {
    const { hass, card } = await mountWithPopup();
    expect(textOf(card)).toBe("Boiler off");
    expect(textOfPopup(card)).toContain("unavailable");
    const [cardBefore, popupBefore] = [renders(card), renders(popupOf(card))];

    card.hass = hass.with({ formatters: { formatEntityState: spoken("ru").formatEntityState } });
    await card.updateComplete;

    expect(renders(card)).toBe(cardBefore + 1);
    expect(renders(popupOf(card))).toBe(popupBefore + 1);
    expect(textOf(card)).toBe("Boiler ru off");
    expect(textOfPopup(card)).toContain("ru unavailable");
  });

  it("renders the card and the open pop-up for a new name formatter alone", async () => {
    const { hass, card } = await mountWithPopup();
    expect(nameOf(card)).toBe("Boiler");
    expect(popupOf(card).shadowRoot?.querySelector("h2")?.textContent).toBe("Boiler");

    card.hass = hass.with({ formatters: { formatEntityName: spoken("ru").formatEntityName } });
    await card.updateComplete;

    expect(nameOf(card)).toBe("ru Boiler");
    expect(popupOf(card).shadowRoot?.querySelector("h2")?.textContent).toBe("ru Boiler");
  });

  it("renders the open pop-up for a new attribute formatter alone", async () => {
    const { hass, card } = await mountWithPopup();
    expect(textOfPopup(card)).toContain("24 °C");

    card.hass = hass.with({
      formatters: { formatEntityAttributeValue: spoken("ru").formatEntityAttributeValue },
    });
    await card.updateComplete;

    expect(textOfPopup(card)).toContain("ru 24");
  });

  it("does not render again when the formatters are the same functions", async () => {
    const { hass, card } = await mountWithPopup();
    const [cardBefore, popupBefore] = [renders(card), renders(popupOf(card))];

    card.hass = hass.state("light.kitchen", "on");
    await card.updateComplete;

    expect(renders(card)).toBe(cardBefore);
    expect(renders(popupOf(card))).toBe(popupBefore);
  });

  it("is in the new language when the user changes it on an open dashboard", async () => {
    const hass = counting(45);
    const card = await mountCard(hass);
    expect(textOf(card)).toBe(`Boiler 45:00 ${english.card_until.replace("{time}", "09:45")}`);

    // What the frontend does, in the order it does it: the language and the locale first,
    // then the card's strings as a new `localize`, and last the formatters it recomputed
    // from them, in an update that changes nothing else.
    const language = hass.with({ language: "ru" });
    card.hass = language;
    await card.updateComplete;
    const withStrings = language.with({ localize: localizeFor("ru") });
    card.hass = withStrings;
    await card.updateComplete;
    card.hass = withStrings.with({ formatters: spoken("ru") });
    await card.updateComplete;

    expect(textOf(card)).toBe(`ru Boiler 45:00 ${russian.card_until.replace("{time}", "9:45")}`);
    popupOf(card).open();
    await popupOf(card).updateComplete;
    expect(textOfPopup(card)).toContain(russian.card_close);
    expect(textOfPopup(card)).toContain("ru Boiler");
  });
});

describe("the clock the countdown follows", () => {
  const until = (time: string) => english.card_until.replace("{time}", time);

  /** Lets the card draw what some seconds of its countdown changed. */
  async function passSeconds(card: TimerifyCard, seconds: number): Promise<void> {
    await vi.advanceTimersByTimeAsync(seconds * SECOND);
    await card.updateComplete;
  }

  // In these scenarios the server's clock stands at `START`, as Ends at is written by it,
  // and the browser's is the fake clock that a scenario sets.

  it("the countdown follows the server when the browser is 5 minutes fast", async () => {
    vi.setSystemTime(START + 5 * MINUTE);
    const hass = counting(10, { serverClockAhead: -5 * MINUTE });

    const card = await mountCard(hass);

    expect(textOf(card)).toBe(`Boiler 10:00 ${until("09:10")}`);
    await passSeconds(card, 1);
    expect(textOf(card)).toBe(`Boiler 9:59 ${until("09:10")}`);
  });

  it("the countdown follows the server when the browser is 5 minutes slow", async () => {
    vi.setSystemTime(START - 5 * MINUTE);
    const hass = counting(10, { serverClockAhead: 5 * MINUTE });

    const card = await mountCard(hass);

    expect(textOf(card)).toBe(`Boiler 10:00 ${until("09:10")}`);
    await passSeconds(card, 1);
    expect(textOf(card)).toBe(`Boiler 9:59 ${until("09:10")}`);
  });

  it("counts on to the end when the browser's clock says it is over", async () => {
    vi.setSystemTime(START + 5 * MINUTE);
    const card = await mountCard(counting(3, { serverClockAhead: -5 * MINUTE }));
    expect(textOf(card)).toBe(`Boiler 3:00 ${until("09:03")}`);

    await passSeconds(card, 179);
    expect(textOf(card)).toBe(`Boiler 0:01 ${until("09:03")}`);
    expect(vi.getTimerCount()).toBe(1);

    await passSeconds(card, 1);
    expect(textOf(card)).toBe(`Boiler 0:00 ${until("09:03")}`);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("stops at the end when the browser's clock says it goes on", async () => {
    vi.setSystemTime(START - 5 * MINUTE);
    const card = await mountCard(counting(1, { serverClockAhead: 5 * MINUTE }));

    await passSeconds(card, 60);

    expect(textOf(card)).toBe(`Boiler 0:00 ${until("09:01")}`);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("says on which day it ends by the server's date", async () => {
    // Monday 23:58 on the server (UTC+2), and Tuesday 00:03 by the browser's clock.
    const monday = Date.UTC(2026, 0, 5, 21, 58);
    vi.setSystemTime(monday + 5 * MINUTE);

    const card = await mountCard(counting(32, { serverClockAhead: -5 * MINUTE }, monday));

    expect(textOf(card)).toBe(`Boiler 32:00 ${until("Tue 00:30")}`);
  });

  it("takes the clock from the newest answer", async () => {
    vi.setSystemTime(START + 5 * MINUTE);
    const hass = counting(10, { serverClockAhead: -5 * MINUTE });
    const card = await mountCard(hass);
    expect(textOf(card)).toBe(`Boiler 10:00 ${until("09:10")}`);

    // The browser's clock is set right, and the connection comes back.
    vi.setSystemTime(START);
    hass.setServerClockAhead(0);
    card.hass = hass.with({ connected: false });
    await card.updateComplete;
    card.hass = hass.with({ connected: true });
    await card.updateComplete;

    expect(textOf(card)).toBe(`Boiler 10:00 ${until("09:10")}`);
  });
});

describe("its body", () => {
  async function opening() {
    const card = await mountCard(fakeHass());
    return { card, popup: popupOf(card), body: bodyOf(card) };
  }
  const key = (type: "keydown" | "keyup", key: string) =>
    new KeyboardEvent(type, { key, bubbles: true, composed: true, cancelable: true });

  it("opens its pop-up on a tap", async () => {
    const { card, popup, body } = await opening();
    expect(dialogOf(card)?.open).toBe(false);

    body.click();
    await popup.updateComplete;

    expect(dialogOf(card)?.open).toBe(true);
  });

  it("opens its pop-up from the keyboard, on Enter and on Space", async () => {
    const { card, popup, body } = await opening();

    const entered = key("keydown", "Enter");
    body.dispatchEvent(entered);
    await popup.updateComplete;
    expect(entered.defaultPrevented).toBe(true);
    expect(dialogOf(card)?.open).toBe(true);
    popup.close();

    const pressed = key("keydown", " ");
    body.dispatchEvent(pressed);
    await popup.updateComplete;
    expect(pressed.defaultPrevented).toBe(true);
    expect(dialogOf(card)?.open).toBe(false);

    body.dispatchEvent(key("keyup", " "));
    await popup.updateComplete;
    expect(dialogOf(card)?.open).toBe(true);
  });

  it("can be reached with the keyboard", async () => {
    const { body } = await opening();

    expect(body.getAttribute("role")).toBe("button");
    expect(body.tabIndex).toBe(0);
  });

  it("covers the card's border too, however wide the theme draws it", async () => {
    for (const layout of ["pill", "round"]) {
      for (const width of [undefined, "3px"]) {
        const card = await mountCard(fakeHass(), { entity: NUMBER, layout });
        if (width !== undefined) {
          card.style.setProperty("--ha-card-border-width", width);
        }

        // As Home Assistant's tile card does: the body reaches the card's padding box, so it
        // is pulled out over the border by its width (1px unless the theme says otherwise).
        // What an engine computes that margin to differs in form, so the margin is compared
        // with the one it computes for a probe that is given the border's width.
        const probe = document.createElement("div");
        probe.style.margin = `calc(-1 * ${width ?? "1px"})`;
        document.body.append(probe);
        const wanted = getComputedStyle(probe).marginTop;
        const { marginTop, marginRight, marginBottom, marginLeft } = getComputedStyle(
          bodyOf(card),
        );
        for (const side of [marginTop, marginRight, marginBottom, marginLeft]) {
          expect(side, `${layout} with a border of ${width ?? "the default width"}`).toBe(wanted);
        }
        probe.remove();
        card.remove();
      }
    }
  });

  it("cannot be selected by a long touch, in the text that a finger rests on", async () => {
    // What a person can select: text whose element, or one of the card's elements around it,
    // is `user-select: none` (an element that says nothing follows the one around it).
    const cannotBeSelected = (element: Element | null | undefined) => {
      for (let node = element; node; node = node.parentElement) {
        if (getComputedStyle(node).userSelect === "none") {
          return true;
        }
      }
      return false;
    };
    const texts = { pill: [".name", ".status"], round: [".name", ".time"] };
    for (const [layout, selectors] of Object.entries(texts)) {
      const card = await mountCard(counting(45), { entity: NUMBER, layout });

      for (const selector of selectors) {
        const text = card.shadowRoot?.querySelector(selector);
        expect(text?.textContent?.trim(), `${layout} ${selector}`).toBeTruthy();
        expect(cannotBeSelected(text), `${layout} ${selector}`).toBe(true);
      }
      card.remove();
    }
  });
});

describe("its size", () => {
  it("sizes itself for masonry and for sections", async () => {
    const hass = fakeHass();

    const pill = await mountCard(hass, { entity: NUMBER, layout: "pill" });
    expect(pill.getCardSize()).toBe(1);
    expect(pill.getGridOptions()).toEqual({
      columns: 6,
      rows: 1,
      min_columns: 3,
      min_rows: 1,
      max_rows: 1,
    });

    const round = await mountCard(hass, { entity: NUMBER, layout: "round" });
    expect(round.getCardSize()).toBe(3);
    expect(round.getGridOptions()).toEqual({
      columns: 3,
      rows: 2,
      min_columns: 2,
      min_rows: 2,
      max_rows: 3,
    });
  });

  it("makes room for the Turn off button of the round tile, and for it alone", async () => {
    const hass = fakeHass();

    const pill = await mountCard(hass, { entity: NUMBER, layout: "pill", show_turn_off: true });
    expect(pill.getCardSize()).toBe(1);
    expect(pill.getGridOptions()).toMatchObject({ rows: 1, max_rows: 1 });

    const round = await mountCard(hass, { entity: NUMBER, layout: "round", show_turn_off: true });
    expect(round.getCardSize()).toBe(4);
    expect(round.getGridOptions()).toEqual({
      columns: 5,
      rows: 3,
      min_columns: 5,
      min_rows: 3,
      max_rows: 3,
    });

    round.setConfig({ entity: NUMBER, layout: "round" });
    expect(round.getCardSize()).toBe(3);
    expect(round.getGridOptions()).toEqual({
      columns: 3,
      rows: 2,
      min_columns: 2,
      min_rows: 2,
      max_rows: 3,
    });
  });

  it("starts the pill with its Turn off button at the fewest columns that hold what it shows", async () => {
    const hass = fakeHass();
    const sizes = async (config: Record<string, unknown>) =>
      (await mountCard(hass, { entity: NUMBER, layout: "pill", ...config })).getGridOptions();
    const columns = ({ columns, min_columns }: { columns: number; min_columns: number }) => ({
      columns,
      min_columns,
    });

    // The icon, the button, and the chip if there is one, in the longer Russian word, fit in
    // these on the narrowest sections: the measurement is in RULINGS, and in the E2E.
    expect(columns(await sizes({ show_turn_off: true }))).toEqual({ columns: 8, min_columns: 8 });
    expect(columns(await sizes({ show_turn_off: true, chip: 15 }))).toEqual({
      columns: 11,
      min_columns: 11,
    });
    // Without the button the pill is as it was, with the chip or without it.
    expect(columns(await sizes({ chip: 15 }))).toEqual({ columns: 6, min_columns: 3 });
    expect(columns(await sizes({ show_turn_off: false }))).toEqual({ columns: 6, min_columns: 3 });
  });
});

describe("the card picker", () => {
  const entries = () => (window.customCards ?? []).filter(({ type }) => type === "timerify-card");

  it("is listed once, among the cards the page already had", async () => {
    expect(entries()).toHaveLength(1);
    expect(entries()[0]).toMatchObject({
      name: "Timerify",
      preview: true,
      documentationURL: "https://github.com/klimofey/timerify#dashboard-card",
    });
    expect(window.customCards).toBe(earlierCards);
    expect(earlierCards.map(({ type }) => type)).toEqual(["another-card", "timerify-card"]);

    const defined = customElements.get("timerify-card");
    vi.resetModules();
    await import("../src/timerify-card");

    expect(customElements.get("timerify-card")).toBe(defined);
    expect(entries()).toHaveLength(1);
  });

  it("describes the card in the user's language once the strings are there", async () => {
    await mountCard(fakeHass({ language: "ru" }));
    expect(entries()[0]?.description).toBe(russian.card_picker_description);

    await mountCard(fakeHass({ language: "en" }));
    expect(entries()[0]?.description).toBe(english.card_picker_description);
  });
});
