import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { common as russian } from "../../custom_components/timerify/translations/ru.json";
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

  it("shows no warning when it is refused", async () => {
    const hass = fakeHass();
    hass.answerWith("unauthorized");

    const card = await mountCard(hass);

    expect(warningOf(card)).toBeNull();
    expect(textOf(card)).toBe("Boiler Run for");
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
