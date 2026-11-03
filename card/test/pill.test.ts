import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import {
  common as russian,
  entity as russianEntities,
} from "../../custom_components/timerify/translations/ru.json";
import type { TimerifyCard } from "../src/timerify-card";
import {
  BOILER,
  ENDS_AT,
  NUMBER,
  START,
  counting,
  fakeHass,
  limited,
} from "./fake-hass";
import { bodyOf, mountCard, popupOf, textOf, turnOffOf } from "./mount";

const MINUTE = 60_000;
const SECOND = 1000;

beforeEach(() => {
  vi.useFakeTimers({ now: START });
});

afterEach(() => {
  document.body.replaceChildren();
  vi.useRealTimers();
});

const until = (time: string) => english.card_until.replace("{time}", time);
const untilLatest = (time: string) => english.card_until_latest.replace("{time}", time);
const addTime = (minutes: number) => ({
  domain: "timerify",
  service: "add_time",
  data: { minutes },
  target: { entity_id: NUMBER },
});
const stopped = {
  domain: "timerify",
  service: "stop",
  data: {},
  target: { entity_id: NUMBER },
};

const fillOf = (card: TimerifyCard) =>
  card.shadowRoot?.querySelector<HTMLElement>(".fill")?.style.width;
const dialogOf = (card: TimerifyCard) => popupOf(card).shadowRoot?.querySelector("dialog");

/** The boiler runs with no countdown: a target that is on, and nothing counting. */
const running = () => fakeHass().state(BOILER, "on", { friendly_name: "Boiler" });

function chipOf(card: TimerifyCard): HTMLButtonElement {
  const chip = card.shadowRoot?.querySelector<HTMLButtonElement>("button.chip");
  if (!chip) {
    throw new Error("The card has no chip");
  }
  return chip;
}

/** Lets the card draw what a second of its countdown changed. */
async function passSeconds(card: TimerifyCard, seconds: number): Promise<void> {
  await vi.advanceTimersByTimeAsync(seconds * SECOND);
  await card.updateComplete;
}

describe("the countdown on the pill", () => {
  it("shows the name, the time left and the end while counting", async () => {
    const card = await mountCard(counting(45));

    expect(textOf(card)).toBe(`Boiler 45:00 ${until("09:45")}`);
  });

  it("counts down every second while it is on the page", async () => {
    const card = await mountCard(counting(45));

    await passSeconds(card, 1);
    expect(textOf(card)).toContain("44:59");
    await passSeconds(card, 59);
    expect(textOf(card)).toContain("44:00");

    card.remove();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("starts counting when a countdown begins while it is on the page", async () => {
    const idle = fakeHass({ timeFormat: "24" });
    const card = await mountCard(idle);
    expect(vi.getTimerCount()).toBe(0);

    card.hass = counting(45);
    await card.updateComplete;
    await passSeconds(card, 1);

    expect(textOf(card)).toBe(`Boiler 44:59 ${until("09:45")}`);
  });

  it("goes on counting after the card is moved on the dashboard", async () => {
    const card = await mountCard(counting(45));
    await passSeconds(card, 1);

    card.remove();
    expect(vi.getTimerCount()).toBe(0);
    await vi.advanceTimersByTimeAsync(4 * SECOND);
    document.body.append(card);
    await card.updateComplete;
    await passSeconds(card, 1);

    expect(textOf(card)).toContain("44:54");
  });

  it("stops at zero and waits for Timerify", async () => {
    const hass = counting(1);
    const card = await mountCard(hass);

    await passSeconds(card, 62);

    expect(textOf(card)).toBe(`Boiler 0:00 ${until("09:01")}`);
    expect(vi.getTimerCount()).toBe(0);

    // Timerify turns the target off and ends the countdown.
    card.hass = hass.state(ENDS_AT, "unknown");
    await card.updateComplete;
    expect(textOf(card)).toBe("Boiler off");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("stops counting when the countdown is ended elsewhere", async () => {
    const hass = counting(45);
    const card = await mountCard(hass);
    expect(vi.getTimerCount()).toBe(1);

    card.hass = hass.state(ENDS_AT, "unknown");
    await card.updateComplete;

    expect(vi.getTimerCount()).toBe(0);
  });

  it("follows an end that moves", async () => {
    const hass = counting(45);
    const card = await mountCard(hass);

    card.hass = hass.state(ENDS_AT, new Date(START + 60 * MINUTE).toISOString(), {
      started_at: new Date(START).toISOString(),
    });
    await card.updateComplete;

    expect(textOf(card)).toBe(`Boiler 1:00:00 ${until("10:00")}`);
    expect(fillOf(card)).toBe("100%");
  });

  it("shows the end in the user's clock and time zone", async () => {
    const card = await mountCard(counting(45, { timeFormat: "12", localeTimeZone: "local" }));

    expect(textOf(card)).toMatch(new RegExp(`^Boiler 45:00 ${until("2:45\\sAM")}$`));
  });
});

describe("the limit on the pill", () => {
  it("a device left on shows the time it turns off at the latest", async () => {
    const card = await mountCard(limited(90));

    expect(textOf(card)).toBe("Boiler by 10:30 at the latest");
    expect(fillOf(card)).toBe("100%");
  });

  it("says the limit in the user's language", async () => {
    const card = await mountCard(limited(90, { language: "ru" }));

    expect(textOf(card)).toBe(`Boiler ${russian.card_until_latest.replace("{time}", "10:30")}`);
    expect(textOf(card)).not.toMatch(/\bat the latest\b/);
  });

  it("shows the time of the limit in the user's clock and time zone", async () => {
    const card = await mountCard(limited(90, { timeFormat: "12", localeTimeZone: "local" }));

    expect(textOf(card)).toMatch(new RegExp(`^Boiler ${untilLatest("3:30\\sAM")}$`));
  });

  it("names the day of a limit that falls on another", async () => {
    const card = await mountCard(limited(17 * 60));

    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 02:00")}`);
  });

  it("does not count down, as a limit is no countdown", async () => {
    const card = await mountCard(limited(90));

    expect(vi.getTimerCount()).toBe(0);
    await passSeconds(card, 60);
    expect(textOf(card)).toBe(`Boiler ${untilLatest("10:30")}`);
  });

  it("adding time to a limit shows an ordinary countdown", async () => {
    const card = await mountCard(limited(90));

    // Timerify gives the limit's end plus the time added as a countdown that someone chose.
    card.hass = counting(105);
    await card.updateComplete;

    expect(textOf(card)).toBe(`Boiler 1:45:00 ${until("10:45")}`);
    expect(vi.getTimerCount()).toBe(1);
    await passSeconds(card, 1);
    expect(textOf(card)).toContain("1:44:59");
  });

  it("goes back to the state of the device when the limit turns it off", async () => {
    const hass = limited(90);
    const card = await mountCard(hass);

    card.hass = hass.state(ENDS_AT, "unknown").state(BOILER, "off", { friendly_name: "Boiler" });
    await card.updateComplete;

    expect(textOf(card)).toBe("Boiler off");
  });
});

describe("the fill of the pill", () => {
  it("fills with the share of the countdown that is left", async () => {
    vi.setSystemTime(START + 15 * MINUTE);
    const card = await mountCard(counting(60));

    expect(fillOf(card)).toBe("75%");
    expect(textOf(card)).toContain("45:00");
  });

  it("empties as the countdown passes", async () => {
    const card = await mountCard(counting(60));
    expect(fillOf(card)).toBe("100%");

    await passSeconds(card, 30 * 60);

    expect(fillOf(card)).toBe("50%");
  });

  it("is full while the target runs without a countdown, and empty while idle", async () => {
    const idle = fakeHass();
    const card = await mountCard(idle);
    expect(fillOf(card)).toBe("0%");
    expect(textOf(card)).toBe("Boiler off");

    card.hass = idle.state(BOILER, "on", { friendly_name: "Boiler" });
    await card.updateComplete;

    expect(fillOf(card)).toBe("100%");
    expect(textOf(card)).toBe("Boiler on");
  });

  it("is not fooled by a clock that runs ahead", async () => {
    vi.setSystemTime(START + 50 * MINUTE);
    const hass = counting(45);

    const card = await mountCard(hass);

    expect(textOf(card)).toBe(`Boiler 0:00 ${until("09:45")}`);
    expect(fillOf(card)).toBe("0%");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("is not fooled by a clock that runs behind", async () => {
    vi.setSystemTime(START - 10 * MINUTE);

    const card = await mountCard(counting(45));

    // The end is the server's, whatever the browser thinks it is now.
    expect(textOf(card)).toBe(`Boiler 55:00 ${until("09:45")}`);
    expect(fillOf(card)).toBe("100%");
  });

  it("still sends what the chip says when the clock is wrong", async () => {
    vi.setSystemTime(START + 50 * MINUTE);
    const hass = counting(45);
    const card = await mountCard(hass, { entity: NUMBER, chip: 15 });

    chipOf(card).click();
    await card.updateComplete;

    expect(hass.calls).toEqual([addTime(15)]);
  });
});

describe("the timer is not there to read", () => {
  it("shows the timer as unavailable when it is", async () => {
    const hass = fakeHass().state(NUMBER, "unavailable");

    const card = await mountCard(hass);

    expect(textOf(card)).toBe("Boiler unavailable");
    expect(fillOf(card)).toBe("0%");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("says nothing of its state while it asks Timerify who it is", async () => {
    const hass = fakeHass();
    hass.holdAnswers();
    const card = document.createElement("timerify-card") as TimerifyCard;
    card.setConfig({ entity: NUMBER });
    card.hass = hass;
    document.body.append(card);
    await vi.advanceTimersByTimeAsync(0);

    expect(textOf(card)).toBe("Boiler Run for");

    hass.answerNext();
    await card.updateComplete;
    expect(textOf(card)).toBe("Boiler off");
  });

  it("stops its countdown when the timer goes", async () => {
    const hass = counting(45);
    const card = await mountCard(hass);

    card.hass = hass.state(NUMBER, "unavailable");
    await card.updateComplete;

    expect(textOf(card)).toBe("Boiler unavailable");
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("the quick chip", () => {
  it("has no chip unless one is configured", async () => {
    const card = await mountCard(counting(45));

    expect(card.shadowRoot?.querySelector("button")).toBeNull();
  });

  it("is labelled with the time it adds", async () => {
    const card = await mountCard(counting(45), { entity: NUMBER, chip: 15 });

    expect(chipOf(card).textContent?.trim()).toBe("+15 min");
    expect(chipOf(card).getAttribute("aria-label")).toBe(
      english.card_add_time.replace("{duration}", "15 min"),
    );
  });

  it("reads the longest chip, a day, in hours", async () => {
    const card = await mountCard(fakeHass(), { entity: NUMBER, chip: 1440 });

    expect(chipOf(card).textContent?.trim()).toBe("+24 hr");
    expect(chipOf(card).getAttribute("aria-label")).toBe(
      english.card_add_time.replace("{duration}", "24 hr"),
    );
  });

  it("is spoken as it is written, so that a voice user can say what they see", async () => {
    for (const language of ["en", "ru"] as const) {
      const card = await mountCard(counting(45, { language }), { entity: NUMBER, chip: 15 });
      for (const chip of [15, 60, 90, 125, 1440]) {
        card.setConfig({ entity: NUMBER, chip });
        await card.updateComplete;

        const written = chipOf(card).textContent?.trim().replace(/^\+/, "");
        expect(written, `${chip} minutes in ${language}`).toMatch(/\S/);
        expect(chipOf(card).getAttribute("aria-label")).toContain(written);
      }
      card.remove();
    }
  });

  it("adds the chip's minutes without opening the pop-up", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, { entity: NUMBER, chip: 15 });

    chipOf(card).click();
    await popupOf(card).updateComplete;

    expect(hass.calls).toEqual([addTime(15)]);
    expect(dialogOf(card)?.open).toBe(false);
  });

  it("is off while the timer is unavailable, as the pop-up's buttons are", async () => {
    const hass = fakeHass().state(NUMBER, "unavailable");
    const card = await mountCard(hass, { entity: NUMBER, chip: 15 });
    expect(chipOf(card).disabled).toBe(true);

    chipOf(card).click();
    await card.updateComplete;
    expect(hass.calls).toEqual([]);

    card.hass = hass.state(NUMBER, "0");
    await card.updateComplete;
    expect(chipOf(card).disabled).toBe(false);
  });

  it("is off while the card does not know its timer yet", async () => {
    const hass = fakeHass();
    hass.holdAnswers();
    const card = document.createElement("timerify-card") as TimerifyCard;
    card.setConfig({ entity: NUMBER, chip: 15 });
    card.hass = hass;
    document.body.append(card);
    await vi.advanceTimersByTimeAsync(0);
    expect(chipOf(card).disabled).toBe(true);

    hass.answerNext();
    await card.updateComplete;
    expect(chipOf(card).disabled).toBe(false);
  });

  it("pressing the chip opens nothing", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, { entity: NUMBER, chip: 15 });
    const chip = chipOf(card);
    const event = (type: string) => new PointerEvent(type, { bubbles: true, composed: true });

    chip.dispatchEvent(event("pointerdown"));
    chip.dispatchEvent(event("pointerup"));
    chip.click();
    // A keyboard user's press on a button is a click too, which the browser makes; the
    // keys themselves are not a tap of the card.
    const key = (type: "keydown" | "keyup", pressed: string) =>
      new KeyboardEvent(type, { key: pressed, bubbles: true, composed: true, cancelable: true });
    chip.dispatchEvent(key("keydown", "Enter"));
    chip.dispatchEvent(key("keyup", " "));
    await popupOf(card).updateComplete;

    expect(hass.calls).toEqual([addTime(15)]);
    expect(dialogOf(card)?.open).toBe(false);
  });

  it("is a control of its own, beside the button that opens the pop-up", async () => {
    const card = await mountCard(counting(45), { entity: NUMBER, chip: 15 });

    const body = bodyOf(card);
    expect(body.contains(chipOf(card))).toBe(false);
    expect(chipOf(card).closest('[role="button"]')).toBeNull();
    expect(card.shadowRoot?.querySelectorAll("button, [role='button']")).toHaveLength(2);
  });

  it("names the button that opens the pop-up by the name and the state, not by the chip", async () => {
    const card = await mountCard(counting(45), { entity: NUMBER, chip: 15 });

    const label = card.shadowRoot?.getElementById(
      bodyOf(card).getAttribute("aria-labelledby") ?? "",
    );

    expect(label?.textContent?.replace(/\s+/g, " ").trim()).toBe(`Boiler 45:00 ${until("09:45")}`);
  });

  it("leaves the rest of the pill to open the pop-up", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, { entity: NUMBER, chip: 15 });

    card.shadowRoot?.querySelector<HTMLElement>('[role="button"]')?.click();
    await popupOf(card).updateComplete;

    expect(dialogOf(card)?.open).toBe(true);
    expect(hass.calls).toEqual([]);
  });

  it("formats the chip in the user's language", async () => {
    const minutes = (count: number, unit: "hour" | "minute") =>
      new Intl.NumberFormat("ru", {
        style: "unit",
        unit,
        unitDisplay: "short",
        useGrouping: false,
      }).format(count);
    const card = await mountCard(counting(45, { language: "ru" }), { entity: NUMBER, chip: 15 });

    for (const chip of [15, 2, 21]) {
      card.setConfig({ entity: NUMBER, chip });
      await card.updateComplete;
      expect(chipOf(card).textContent?.trim(), `${chip} minutes`).toBe(
        `+${minutes(chip, "minute")}`,
      );
      expect(chipOf(card).getAttribute("aria-label")).toBe(
        russian.card_add_time.replace("{duration}", minutes(chip, "minute")),
      );
    }
    card.setConfig({ entity: NUMBER, chip: 90 });
    await card.updateComplete;
    const ninety = `${minutes(1, "hour")} ${minutes(30, "minute")}`;
    expect(chipOf(card).textContent?.trim()).toBe(`+${ninety}`);
    // The pill's own words are Russian too, and no English word is glued to a number.
    expect(textOf(card)).toContain(russian.card_until.replace("{time}", "9:45"));
    expect(textOf(card)).not.toMatch(/\b(min|hr|until)\b/);
  });

  it("leaves the pill as it was when Home Assistant refuses the chip", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, { entity: NUMBER, chip: 15 });
    const before = textOf(card);
    hass.rejectNext(new Error("The timer refused"));

    chipOf(card).click();
    await vi.advanceTimersByTimeAsync(0);
    await card.updateComplete;

    // Home Assistant has shown its toast; the card neither fails nor changes.
    expect(hass.calls).toEqual([addTime(15)]);
    expect(textOf(card)).toBe(before);
    expect(dialogOf(card)?.open).toBe(false);
  });
});

describe("the Turn off button of the pill", () => {
  const WITH_BUTTON = { entity: NUMBER, show_turn_off: true } as const;

  it("shows Turn off while the boiler runs, with or without a countdown, or under a limit", async () => {
    const counts = await mountCard(counting(45), WITH_BUTTON);
    const runs = await mountCard(running(), WITH_BUTTON);
    const limits = await mountCard(limited(90), WITH_BUTTON);

    expect(turnOffOf(counts)).not.toBeNull();
    expect(turnOffOf(runs)).not.toBeNull();
    expect(turnOffOf(limits)).not.toBeNull();
  });

  it("is hidden while the boiler is off, and without the option", async () => {
    const idle = await mountCard(fakeHass(), WITH_BUTTON);
    const counts = await mountCard(counting(45), { entity: NUMBER });
    const runs = await mountCard(running(), { entity: NUMBER, show_turn_off: false });

    expect(turnOffOf(idle)).toBeNull();
    expect(turnOffOf(counts)).toBeNull();
    expect(turnOffOf(runs)).toBeNull();
    expect(textOf(runs)).toBe("Boiler on");
  });

  it("comes with the boiler's running and goes with it", async () => {
    const off = fakeHass();
    const card = await mountCard(off, WITH_BUTTON);
    expect(turnOffOf(card)).toBeNull();

    const on = off.state(BOILER, "on", { friendly_name: "Boiler" });
    card.hass = on;
    await card.updateComplete;
    expect(turnOffOf(card)).not.toBeNull();

    card.hass = on.state(BOILER, "off", { friendly_name: "Boiler" });
    await card.updateComplete;
    expect(turnOffOf(card)).toBeNull();

    card.hass = counting(45);
    await card.updateComplete;
    expect(turnOffOf(card)).not.toBeNull();

    card.hass = counting(45).state(ENDS_AT, "unknown");
    await card.updateComplete;
    expect(turnOffOf(card)).toBeNull();
  });

  it("is hidden while the timer is unavailable, whatever the boiler does", async () => {
    const hass = running().state(NUMBER, "unavailable");
    const card = await mountCard(hass, WITH_BUTTON);
    expect(turnOffOf(card)).toBeNull();

    card.hass = hass.state(NUMBER, "0");
    await card.updateComplete;
    expect(turnOffOf(card)).not.toBeNull();
  });

  it("is hidden while the boiler is unavailable", async () => {
    const card = await mountCard(
      fakeHass().state(BOILER, "unavailable", { friendly_name: "Boiler" }),
      WITH_BUTTON,
    );

    expect(turnOffOf(card)).toBeNull();
  });

  it("is hidden until the card has found its timer", async () => {
    const hass = running();
    hass.holdAnswers();
    const card = document.createElement("timerify-card") as TimerifyCard;
    card.setConfig(WITH_BUTTON);
    card.hass = hass;
    document.body.append(card);
    await vi.advanceTimersByTimeAsync(0);
    expect(turnOffOf(card)).toBeNull();

    hass.answerNext();
    await card.updateComplete;
    expect(turnOffOf(card)).not.toBeNull();
  });

  it("stops the timer, and does not open the pop-up", async () => {
    for (const hass of [counting(45), running()]) {
      const card = await mountCard(hass, WITH_BUTTON);

      turnOffOf(card)?.click();
      await popupOf(card).updateComplete;

      expect(hass.calls).toEqual([stopped]);
      expect(dialogOf(card)?.open).toBe(false);
      card.remove();
    }
  });

  it("stops the timer in one call, whichever the minutes it counts", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, WITH_BUTTON);

    turnOffOf(card)?.click();
    await card.updateComplete;

    // Not `number.set_value`: one command for one meaning, as the pop-up and a press set to Stop.
    expect(hass.calls.map(({ domain, service }) => `${domain}.${service}`)).toEqual([
      "timerify.stop",
    ]);
  });

  it.each(["mouse", "touch"] as const)("is no tap, double tap or long press of the card, by a %s", async (pointerType) => {
    const hass = counting(45);
    const card = await mountCard(hass, {
      ...WITH_BUTTON,
      tap: "popup",
      double_tap: "run",
      hold: "run",
    });
    const button = turnOffOf(card);
    const event = (type: string) =>
      new PointerEvent(type, {
        bubbles: true,
        composed: true,
        cancelable: true,
        isPrimary: true,
        pointerId: 1,
        pointerType,
      });

    // A long press on the button is no long press of the card: nothing is held, and letting
    // go starts nothing; the click that follows is the button's own.
    button?.dispatchEvent(event("pointerdown"));
    await vi.advanceTimersByTimeAsync(600);
    expect(card.hasAttribute("data-held")).toBe(false);
    button?.dispatchEvent(event("pointerup"));
    button?.click();
    // Two more presses at once are two more stops, not a double tap of the card.
    button?.click();
    button?.click();
    await vi.advanceTimersByTimeAsync(1000);
    await popupOf(card).updateComplete;

    expect(hass.calls).toEqual([stopped, stopped, stopped]);
    expect(dialogOf(card)?.open).toBe(false);
  });

  it("is shown for a countdown that goes on while the boiler is unavailable, and ends it", async () => {
    const hass = counting(45).state(BOILER, "unavailable", { friendly_name: "Boiler" });
    const card = await mountCard(hass, WITH_BUTTON);

    expect(textOf(card)).toContain("45:00");
    turnOffOf(card)?.click();
    await popupOf(card).updateComplete;

    expect(hass.calls).toEqual([stopped]);
  });

  it("gives the focus to the body of the card when a keyboard press takes the button away", async () => {
    const running = fakeHass().state(BOILER, "on", { friendly_name: "Boiler" });
    const card = await mountCard(running, WITH_BUTTON);
    const button = turnOffOf(card);
    button?.focus();
    expect(card.shadowRoot?.activeElement).toBe(button);

    // The keyboard presses a button with Enter, which the browser makes a click.
    button?.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true, composed: true }),
    );
    button?.click();
    card.hass = running.state(BOILER, "off", { friendly_name: "Boiler" });
    await card.updateComplete;

    expect(turnOffOf(card)).toBeNull();
    expect(card.shadowRoot?.activeElement).toBe(bodyOf(card));
  });

  it("leaves the focus alone when it was not on the button", async () => {
    const running = fakeHass().state(BOILER, "on", { friendly_name: "Boiler" });
    const card = await mountCard(running, { ...WITH_BUTTON, chip: 15 });
    chipOf(card).focus();

    card.hass = running.state(BOILER, "off", { friendly_name: "Boiler" });
    await card.updateComplete;

    expect(turnOffOf(card)).toBeNull();
    expect(card.shadowRoot?.activeElement).toBe(chipOf(card));
  });

  it("gives the focus to no one when the body of the card is no button", async () => {
    const running = fakeHass().state(BOILER, "on", { friendly_name: "Boiler" });
    const card = await mountCard(running, { ...WITH_BUTTON, tap: "none" });
    // Nothing is set to act on a press, so the body is no button and has no tab stop.
    expect(card.shadowRoot?.querySelector('[role="button"]')).toBeNull();
    turnOffOf(card)?.focus();

    card.hass = running.state(BOILER, "off", { friendly_name: "Boiler" });
    await card.updateComplete;

    expect(card.shadowRoot?.activeElement ?? null).toBeNull();
  });

  it("does not hear the keys that press the card", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, WITH_BUTTON);
    const button = turnOffOf(card);
    const key = (type: "keydown" | "keyup", pressed: string) =>
      new KeyboardEvent(type, { key: pressed, bubbles: true, composed: true, cancelable: true });

    button?.dispatchEvent(key("keydown", "Enter"));
    button?.dispatchEvent(key("keyup", " "));
    await popupOf(card).updateComplete;

    // The browser makes its click of these keys itself; the card's own handlers see none.
    expect(hass.calls).toEqual([]);
    expect(dialogOf(card)?.open).toBe(false);
  });

  it("is a control of its own, beside the button that opens the pop-up and before the chip", async () => {
    const card = await mountCard(counting(45), { ...WITH_BUTTON, chip: 15 });
    const button = turnOffOf(card);

    expect(button).not.toBeNull();
    expect(bodyOf(card).contains(button)).toBe(false);
    expect(button?.closest('[role="button"]')).toBeNull();
    expect(card.shadowRoot?.querySelectorAll("button, [role='button']")).toHaveLength(3);
    expect(
      button?.compareDocumentPosition(chipOf(card)) === Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBe(true);
  });

  it("leaves the rest of the pill to open the pop-up", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, WITH_BUTTON);

    bodyOf(card).click();
    await popupOf(card).updateComplete;

    expect(dialogOf(card)?.open).toBe(true);
    expect(hass.calls).toEqual([]);
  });

  it("is not part of the name of the button that opens the pop-up", async () => {
    const card = await mountCard(counting(45), WITH_BUTTON);

    const label = card.shadowRoot?.getElementById(
      bodyOf(card).getAttribute("aria-labelledby") ?? "",
    );

    expect(label?.textContent?.replace(/\s+/g, " ").trim()).toBe(`Boiler 45:00 ${until("09:45")}`);
  });

  it("is worded in the user's language", async () => {
    const card = await mountCard(counting(45, { language: "ru" }), WITH_BUTTON);

    expect(turnOffOf(card, russian.card_turn_off)).not.toBeNull();
    expect(turnOffOf(card)).toBeNull();
    // The word of the timer's own Turn off button on the device page, so that both agree.
    expect(russian.card_turn_off).toBe(russianEntities.button.turn_off.name);
  });

  it("is a button named Turn off, whether the card shows its words or only its icon", async () => {
    const card = await mountCard(counting(45), WITH_BUTTON);
    const button = turnOffOf(card);

    // A wide card shows the words and a narrow one the power icon: the styles choose, from the
    // width of the card, and both are in the button. The name and the tip hold in both.
    expect(button?.querySelector("ha-icon")?.getAttribute("icon")).toBe("mdi:power");
    expect(button?.getAttribute("aria-label")).toBe(english.card_turn_off);
    expect(button?.getAttribute("title")).toBe(english.card_turn_off);
  });

  it("is named in the user's language in its icon form too", async () => {
    const card = await mountCard(counting(45, { language: "ru" }), WITH_BUTTON);
    const button = turnOffOf(card, russian.card_turn_off);

    expect(button?.getAttribute("aria-label")).toBe(russian.card_turn_off);
    expect(button?.getAttribute("title")).toBe(russian.card_turn_off);
  });

  it("marks its card as one with the button, and only then", async () => {
    const with_ = await mountCard(counting(45), WITH_BUTTON);
    const without = await mountCard(counting(45), { entity: NUMBER, show_turn_off: false });

    // The styles make the content of a marked card the container its button's form follows;
    // a card without the button is left as it was.
    expect(with_.shadowRoot?.querySelector("ha-card")?.classList.contains("with-turn-off")).toBe(
      true,
    );
    expect(
      without.shadowRoot?.querySelector("ha-card")?.classList.contains("with-turn-off"),
    ).toBe(false);
  });

  it("tells its card whether there is a chip, which the room the words need depends on", async () => {
    const withChip = await mountCard(counting(45), { ...WITH_BUTTON, chip: 15 });
    const without = await mountCard(counting(45), WITH_BUTTON);

    expect(withChip.shadowRoot?.querySelector("ha-card")?.classList.contains("with-chip")).toBe(true);
    expect(without.shadowRoot?.querySelector("ha-card")?.classList.contains("with-chip")).toBe(false);
  });

  it("leaves the pill as it was when Home Assistant refuses it", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, WITH_BUTTON);
    const before = textOf(card);
    hass.rejectNext(new Error("The timer refused"));

    turnOffOf(card)?.click();
    await vi.advanceTimersByTimeAsync(0);
    await card.updateComplete;

    expect(hass.calls).toEqual([stopped]);
    expect(textOf(card)).toBe(before);
    expect(dialogOf(card)?.open).toBe(false);
  });
});
