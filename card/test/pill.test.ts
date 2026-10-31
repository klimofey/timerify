import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { common as russian } from "../../custom_components/timerify/translations/ru.json";
import type { TimerifyCard } from "../src/timerify-card";
import {
  BOILER,
  ENDS_AT,
  NUMBER,
  START,
  counting,
  fakeHass,
} from "./fake-hass";
import { bodyOf, mountCard, popupOf, textOf } from "./mount";

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
const addTime = (minutes: number) => ({
  domain: "timerify",
  service: "add_time",
  data: { minutes },
  target: { entity_id: NUMBER },
});

const fillOf = (card: TimerifyCard) =>
  card.shadowRoot?.querySelector<HTMLElement>(".fill")?.style.width;
const dialogOf = (card: TimerifyCard) => popupOf(card).shadowRoot?.querySelector("dialog");

function chipOf(card: TimerifyCard): HTMLButtonElement {
  const chip = card.shadowRoot?.querySelector("button");
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
