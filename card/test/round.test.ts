import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import type { TimerifyCard } from "../src/timerify-card";
import {
  AC,
  AC_NUMBER,
  BOILER,
  NUMBER,
  START,
  acTimer,
  counting,
  fakeHass,
} from "./fake-hass";
import { bodyOf, mountCard, nameOf, popupOf, textOf } from "./mount";

const MINUTE = 60_000;
const SECOND = 1000;
const ROUND = { entity: NUMBER, layout: "round" } as const;

beforeEach(() => {
  vi.useFakeTimers({ now: START });
});

afterEach(() => {
  document.body.replaceChildren();
  vi.useRealTimers();
});

const until = (time: string) => english.card_until.replace("{time}", time);
const stopped = (entity = NUMBER) => ({
  domain: "timerify",
  service: "stop",
  data: {},
  target: { entity_id: entity },
});
const startedWithoutDuration = (entity = NUMBER) => ({
  domain: "timerify",
  service: "run",
  data: {},
  target: { entity_id: entity },
});

const dialogOf = (card: TimerifyCard) => popupOf(card).shadowRoot?.querySelector("dialog");
const isOpen = (card: TimerifyCard) => dialogOf(card)?.open === true;
const part = (card: TimerifyCard, selector: string) => card.shadowRoot?.querySelector(selector);

/** The ring's share that is not drawn: the dash offset in parts of the whole circle. */
function undrawnShare(card: TimerifyCard): number {
  const ring = part(card, "circle.progress");
  const length = Number(ring?.getAttribute("stroke-dasharray"));
  return Number(ring?.getAttribute("stroke-dashoffset")) / length;
}

/** What the centre of the ring says, as text. */
const centreOf = (card: TimerifyCard) => part(card, ".centre")?.textContent?.trim();

/** A pointer event as a browser makes it for a mouse or a finger that is the primary one. */
const pointer = (type: string, init: PointerEventInit = {}) =>
  new PointerEvent(type, {
    bubbles: true,
    composed: true,
    cancelable: true,
    isPrimary: true,
    pointerId: 1,
    pointerType: "mouse",
    ...init,
  });

/**
 * A pointer goes down on the card, stays for `milliseconds` and comes up, and the browser
 * sends the click that follows. Returns the click, to see whether the card let it be.
 */
async function press(card: TimerifyCard, milliseconds: number): Promise<MouseEvent> {
  const body = bodyOf(card);
  body.dispatchEvent(pointer("pointerdown"));
  await vi.advanceTimersByTimeAsync(milliseconds);
  body.dispatchEvent(pointer("pointerup"));
  const click = new MouseEvent("click", { bubbles: true, composed: true, cancelable: true });
  body.dispatchEvent(click);
  await popupOf(card).updateComplete;
  return click;
}

/** Lets the card draw what a second of its countdown changed. */
async function passSeconds(card: TimerifyCard, seconds: number): Promise<void> {
  await vi.advanceTimersByTimeAsync(seconds * SECOND);
  await card.updateComplete;
}

describe("the ring and its centre", () => {
  it("shows a ring of the share left, the time in its centre and the name below", async () => {
    vi.setSystemTime(START + 15 * MINUTE);
    const card = await mountCard(counting(60), ROUND);

    expect(undrawnShare(card)).toBeCloseTo(0.25, 6);
    expect(centreOf(card)).toBe("45:00");
    expect(nameOf(card)).toBe("Boiler");
    // The dash is the circle's own length, so that its offset is a share of the whole.
    const ring = part(card, "circle.progress");
    expect(Number(ring?.getAttribute("stroke-dasharray"))).toBeCloseTo(
      2 * Math.PI * Number(ring?.getAttribute("r")),
      6,
    );
  });

  it("draws the track the ring runs along, whole", async () => {
    const card = await mountCard(counting(60), ROUND);

    const track = part(card, "circle.track");
    expect(track).not.toBeNull();
    expect(track?.getAttribute("r")).toBe(part(card, "circle.progress")?.getAttribute("r"));
  });

  it("counts down every second and empties as the countdown passes", async () => {
    const card = await mountCard(counting(60), ROUND);
    expect(undrawnShare(card)).toBeCloseTo(0, 6);

    await passSeconds(card, 30 * 60 + 1);

    expect(centreOf(card)).toBe("29:59");
    expect(undrawnShare(card)).toBeCloseTo(0.5 + 1 / 3600, 6);

    card.remove();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("counts by the server's clock when the browser's is off", async () => {
    vi.setSystemTime(START + 15 * MINUTE);

    const card = await mountCard(counting(60, { serverClockAhead: -15 * MINUTE }), ROUND);

    expect(centreOf(card)).toBe("1:00:00");
    expect(undrawnShare(card)).toBeCloseTo(0, 6);
    await passSeconds(card, 30 * 60);
    expect(centreOf(card)).toBe("30:00");
    expect(undrawnShare(card)).toBeCloseTo(0.5, 6);
  });

  it("is not fooled by a clock that runs ahead", async () => {
    vi.setSystemTime(START + 50 * MINUTE);

    const card = await mountCard(counting(45), ROUND);

    expect(centreOf(card)).toBe("0:00");
    expect(undrawnShare(card)).toBeCloseTo(1, 6);
  });

  it("shows the icon in the centre when idle or on without a countdown", async () => {
    const idle = fakeHass();
    const card = await mountCard(idle, ROUND);

    expect(part(card, ".centre .icon")).not.toBeNull();
    expect(part(card, ".time")).toBeNull();
    expect(undrawnShare(card)).toBeCloseTo(1, 6);

    card.hass = idle.state(BOILER, "on", { friendly_name: "Boiler" });
    await card.updateComplete;

    expect(part(card, ".centre .icon")).not.toBeNull();
    expect(part(card, ".time")).toBeNull();
    expect(undrawnShare(card)).toBeCloseTo(0, 6);
  });

  it("shows the icon and an empty ring while the timer is unavailable", async () => {
    const card = await mountCard(fakeHass().state(NUMBER, "unavailable"), ROUND);

    expect(part(card, ".centre .icon")).not.toBeNull();
    expect(undrawnShare(card)).toBeCloseTo(1, 6);
  });

  it("has no chip, whatever the config says", async () => {
    const card = await mountCard(counting(45), { ...ROUND, chip: 15 });

    expect(card.shadowRoot?.querySelectorAll("button, [role='button']")).toHaveLength(1);
  });

  it("names its button by the name and what the card says of the state", async () => {
    const card = await mountCard(counting(45), ROUND);

    const label = card.shadowRoot?.getElementById(
      bodyOf(card).getAttribute("aria-labelledby") ?? "",
    );

    expect(label?.textContent?.replace(/\s+/g, " ").trim()).toBe(`Boiler 45:00 ${until("09:45")}`);
  });

  it("names its button by the state of the target when nothing counts", async () => {
    const card = await mountCard(fakeHass(), ROUND);

    const label = card.shadowRoot?.getElementById(
      bodyOf(card).getAttribute("aria-labelledby") ?? "",
    );

    expect(label?.textContent?.replace(/\s+/g, " ").trim()).toBe("Boiler off");
  });
});

describe("pressing the round card", () => {
  it("opens the pop-up on a tap", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, ROUND);

    bodyOf(card).click();
    await popupOf(card).updateComplete;

    expect(isOpen(card)).toBe(true);
    expect(hass.calls).toEqual([]);
  });

  it("is reached and pressed from the keyboard", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);
    const body = bodyOf(card);
    expect(body.getAttribute("role")).toBe("button");
    expect(body.getAttribute("tabindex")).toBe("0");

    const entered = new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      composed: true,
      cancelable: true,
    });
    body.dispatchEvent(entered);
    await popupOf(card).updateComplete;

    expect(entered.defaultPrevented).toBe(true);
    expect(isOpen(card)).toBe(true);
    expect(hass.calls).toEqual([]);
  });

  it("opens the pop-up on a tap that goes down and up quickly", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);

    const click = await press(card, 120);

    expect(click.defaultPrevented).toBe(false);
    expect(isOpen(card)).toBe(true);
    expect(hass.calls).toEqual([]);
  });
});

describe("holding the round card", () => {
  it("holding for half a second starts the timer without a duration", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);

    // A moment short of it is a tap.
    await press(card, 499);
    expect(hass.calls).toEqual([]);
    expect(isOpen(card)).toBe(true);
    popupOf(card).close();
    await popupOf(card).updateComplete;

    await press(card, 500);

    expect(hass.calls).toEqual([startedWithoutDuration()]);
  });

  it("a hold does not also open the pop-up", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);

    const click = await press(card, 500);

    expect(hass.calls).toEqual([startedWithoutDuration()]);
    expect(isOpen(card)).toBe(false);
    expect(click.defaultPrevented).toBe(true);
  });

  it("keeps the click that follows a hold from reaching anything above the card", async () => {
    const card = await mountCard(fakeHass(), ROUND);
    const reached = vi.fn();
    document.body.addEventListener("click", reached);

    await press(card, 500);

    expect(reached).not.toHaveBeenCalled();
    document.body.removeEventListener("click", reached);
  });

  it("holding stops a running timer", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, ROUND);

    await press(card, 500);

    expect(hass.calls).toEqual([stopped()]);
    expect(isOpen(card)).toBe(false);
  });

  it("holding stops a target that runs without a countdown", async () => {
    const hass = fakeHass({ timers: [acTimer()] }).state(AC, "cool", { friendly_name: "AC" });
    const card = await mountCard(hass, { entity: AC_NUMBER, layout: "round" });

    await press(card, 500);

    expect(hass.calls).toEqual([stopped(AC_NUMBER)]);
    expect(isOpen(card)).toBe(false);
  });

  it("a hold while the timer is unavailable does nothing", async () => {
    const hass = fakeHass().state(NUMBER, "unavailable");
    const card = await mountCard(hass, ROUND);

    const click = await press(card, 500);

    expect(hass.calls).toEqual([]);
    expect(isOpen(card)).toBe(false);
    expect(click.defaultPrevented).toBe(true);
  });

  it("leaves the card as it was when Home Assistant refuses the hold", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, ROUND);
    hass.rejectNext(new Error("The timer refused"));

    await press(card, 500);
    await vi.advanceTimersByTimeAsync(0);
    await card.updateComplete;

    // Home Assistant has shown its toast; the card neither fails nor opens its pop-up.
    expect(hass.calls).toEqual([stopped()]);
    expect(isOpen(card)).toBe(false);
    expect(centreOf(card)).toBe("45:00");
  });

  it("marks a hold once it is long enough", async () => {
    const card = await mountCard(fakeHass(), ROUND);
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown"));
    await vi.advanceTimersByTimeAsync(499);
    expect(card.hasAttribute("data-held")).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(card.hasAttribute("data-held")).toBe(true);

    body.dispatchEvent(pointer("pointerup"));
    expect(card.hasAttribute("data-held")).toBe(false);
  });

  it("a cancelled press does nothing", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown"));
    await vi.advanceTimersByTimeAsync(600);
    expect(card.hasAttribute("data-held")).toBe(true);
    body.dispatchEvent(pointer("pointercancel"));
    // The browser took the gesture for a scroll: there is neither a release nor a click.
    await vi.advanceTimersByTimeAsync(600);

    expect(card.hasAttribute("data-held")).toBe(false);
    expect(hass.calls).toEqual([]);
    expect(isOpen(card)).toBe(false);
  });

  it("a pointer that leaves the card takes the hold back", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown"));
    await vi.advanceTimersByTimeAsync(600);
    body.dispatchEvent(pointer("pointerleave"));
    body.dispatchEvent(pointer("pointerup"));

    expect(card.hasAttribute("data-held")).toBe(false);
    expect(hass.calls).toEqual([]);
    expect(isOpen(card)).toBe(false);
  });

  it("a touch is let go before the browser reports that the finger left", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown", { pointerType: "touch" }));
    await vi.advanceTimersByTimeAsync(500);
    body.dispatchEvent(pointer("pointerup", { pointerType: "touch" }));
    body.dispatchEvent(pointer("pointerleave", { pointerType: "touch" }));
    body.click();
    await popupOf(card).updateComplete;

    expect(hass.calls).toEqual([startedWithoutDuration()]);
    expect(isOpen(card)).toBe(false);
  });

  it("does not start with a button that is not the main one", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown", { button: 2 }));
    await vi.advanceTimersByTimeAsync(600);
    body.dispatchEvent(pointer("pointerup", { button: 2 }));

    expect(card.hasAttribute("data-held")).toBe(false);
    expect(hass.calls).toEqual([]);
  });

  it("is not ended by a second finger that lifts", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown", { pointerId: 1, pointerType: "touch" }));
    body.dispatchEvent(pointer("pointerdown", { pointerId: 2, isPrimary: false }));
    await vi.advanceTimersByTimeAsync(500);
    body.dispatchEvent(pointer("pointerup", { pointerId: 2, isPrimary: false }));
    expect(card.hasAttribute("data-held")).toBe(true);
    expect(hass.calls).toEqual([]);

    body.dispatchEvent(pointer("pointerup", { pointerId: 1, pointerType: "touch" }));
    expect(hass.calls).toEqual([startedWithoutDuration()]);
  });

  it("still opens its pop-up on the next tap when no click followed a hold", async () => {
    // A long touch on Android sends no click after it.
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);
    const body = bodyOf(card);
    body.dispatchEvent(pointer("pointerdown", { pointerType: "touch" }));
    await vi.advanceTimersByTimeAsync(500);
    body.dispatchEvent(pointer("pointerup", { pointerType: "touch" }));
    expect(hass.calls).toEqual([startedWithoutDuration()]);

    await press(card, 100);

    expect(isOpen(card)).toBe(true);
    expect(hass.calls).toEqual([startedWithoutDuration()]);
  });

  it("keeps the browser's menu from a long touch", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);
    const body = bodyOf(card);
    const menu = () =>
      new MouseEvent("contextmenu", { bubbles: true, composed: true, cancelable: true });

    body.dispatchEvent(pointer("pointerdown", { pointerType: "touch" }));
    await vi.advanceTimersByTimeAsync(400);
    const early = menu();
    body.dispatchEvent(early);
    await vi.advanceTimersByTimeAsync(100);
    const late = menu();
    body.dispatchEvent(late);
    body.dispatchEvent(pointer("pointerup", { pointerType: "touch" }));

    expect(early.defaultPrevented).toBe(true);
    expect(late.defaultPrevented).toBe(true);
    expect(hass.calls).toEqual([startedWithoutDuration()]);
  });

  it("leaves the browser's menu to a right click", async () => {
    const card = await mountCard(fakeHass(), ROUND);
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown", { button: 2 }));
    const menu = new MouseEvent("contextmenu", { bubbles: true, composed: true, cancelable: true });
    body.dispatchEvent(menu);

    expect(menu.defaultPrevented).toBe(false);
  });

  it("stops waiting for the hold when the card leaves the page", async () => {
    const card = await mountCard(fakeHass(), ROUND);

    bodyOf(card).dispatchEvent(pointer("pointerdown"));
    await vi.advanceTimersByTimeAsync(500);
    expect(card.hasAttribute("data-held")).toBe(true);
    card.remove();

    expect(card.hasAttribute("data-held")).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("the pill has no long press", () => {
  it("the pill has no long press", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { entity: NUMBER, layout: "pill" });

    const click = await press(card, 600);

    // With a mouse a long press is a tap.
    expect(click.defaultPrevented).toBe(false);
    expect(isOpen(card)).toBe(true);
    expect(hass.calls).toEqual([]);
    expect(card.hasAttribute("data-held")).toBe(false);
  });

  it("a long touch on the pill does nothing", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { entity: NUMBER, layout: "pill" });
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown", { pointerType: "touch" }));
    await vi.advanceTimersByTimeAsync(600);
    body.dispatchEvent(
      new MouseEvent("contextmenu", { bubbles: true, composed: true, cancelable: true }),
    );
    body.dispatchEvent(pointer("pointercancel", { pointerType: "touch" }));
    await popupOf(card).updateComplete;

    expect(hass.calls).toEqual([]);
    expect(isOpen(card)).toBe(false);
    expect(card.hasAttribute("data-held")).toBe(false);
  });
});

describe("changing the layout", () => {
  it("gives the card the hold of the round layout only while it is round", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, ROUND);
    await press(card, 500);
    expect(hass.calls).toEqual([startedWithoutDuration()]);

    card.setConfig({ entity: NUMBER, layout: "pill" });
    await card.updateComplete;
    await press(card, 500);

    expect(hass.calls).toEqual([startedWithoutDuration()]);
    expect(isOpen(card)).toBe(true);
  });
});

describe("the Turn off button of the round tile", () => {
  const WITH_BUTTON = { ...ROUND, show_turn_off: true } as const;
  const running = () => fakeHass().state(BOILER, "on", { friendly_name: "Boiler" });

  /** The Turn off button, found as a person finds it: by the words on it. */
  function turnOffOf(card: TimerifyCard): HTMLButtonElement | null {
    const buttons = [...(card.shadowRoot?.querySelectorAll("button") ?? [])];
    return buttons.find((button) => button.textContent?.trim() === english.card_turn_off) ?? null;
  }

  it("shows Turn off below the dial and the name while the boiler runs, with or without a countdown", async () => {
    for (const hass of [counting(45), running()]) {
      const card = await mountCard(hass, WITH_BUTTON);
      const button = turnOffOf(card);

      expect(button).not.toBeNull();
      // Below the name in the card's order, and no part of the button that opens the pop-up.
      const name = part(card, ".name");
      expect(name?.compareDocumentPosition(button as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
      expect(bodyOf(card).contains(button)).toBe(false);
      expect(button?.closest('[role="button"]')).toBeNull();
      expect(card.shadowRoot?.querySelectorAll("button, [role='button']")).toHaveLength(2);
      card.remove();
    }
  });

  it("is hidden while the boiler is off, and without the option", async () => {
    const idle = await mountCard(fakeHass(), WITH_BUTTON);
    const counts = await mountCard(counting(45), ROUND);
    const runs = await mountCard(running(), { ...ROUND, show_turn_off: false });

    expect(turnOffOf(idle)).toBeNull();
    expect(turnOffOf(counts)).toBeNull();
    expect(turnOffOf(runs)).toBeNull();
    expect(textOf(runs)).toBe("Boiler on");
  });

  it("is hidden while the timer or the boiler is unavailable, and until the timer is found", async () => {
    const timerGone = await mountCard(running().state(NUMBER, "unavailable"), WITH_BUTTON);
    const boilerGone = await mountCard(
      fakeHass().state(BOILER, "unavailable", { friendly_name: "Boiler" }),
      WITH_BUTTON,
    );
    const hass = running();
    hass.holdAnswers();
    const asking = document.createElement("timerify-card") as TimerifyCard;
    asking.setConfig(WITH_BUTTON);
    asking.hass = hass;
    document.body.append(asking);
    await vi.advanceTimersByTimeAsync(0);

    expect(turnOffOf(timerGone)).toBeNull();
    expect(turnOffOf(boilerGone)).toBeNull();
    expect(turnOffOf(asking)).toBeNull();

    hass.answerNext();
    await asking.updateComplete;
    expect(turnOffOf(asking)).not.toBeNull();
  });

  it("comes with the boiler's running and goes with it", async () => {
    const off = fakeHass();
    const card = await mountCard(off, WITH_BUTTON);
    expect(turnOffOf(card)).toBeNull();

    card.hass = off.state(BOILER, "on", { friendly_name: "Boiler" });
    await card.updateComplete;
    expect(turnOffOf(card)).not.toBeNull();

    card.hass = off;
    await card.updateComplete;
    expect(turnOffOf(card)).toBeNull();
  });

  it("keeps its place while the boiler is off, so that the dial does not move when it comes", async () => {
    const off = fakeHass();
    const card = await mountCard(off, WITH_BUTTON);
    const slot = () => part(card, ".turn-off-slot");

    expect(slot()).not.toBeNull();
    card.hass = off.state(BOILER, "on", { friendly_name: "Boiler" });
    await card.updateComplete;
    expect(slot()?.contains(turnOffOf(card))).toBe(true);

    const without = await mountCard(fakeHass(), ROUND);
    expect(part(without, ".turn-off-slot")).toBeNull();
  });

  it("stops the timer, and does not open the pop-up", async () => {
    for (const [hass, number] of [
      [counting(45), NUMBER],
      [fakeHass({ timers: [acTimer()] }).state(AC, "cool", { friendly_name: "AC" }), AC_NUMBER],
    ] as const) {
      const card = await mountCard(hass, { ...WITH_BUTTON, entity: number });

      turnOffOf(card)?.click();
      await popupOf(card).updateComplete;

      expect(hass.calls).toEqual([stopped(number)]);
      expect(isOpen(card)).toBe(false);
      card.remove();
    }
  });

  it("is no tap or long press of the card", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, { ...WITH_BUTTON, double_tap: "run" });
    const button = turnOffOf(card);

    // The round tile has a long press by default: on the button it is the button's press.
    button?.dispatchEvent(pointer("pointerdown"));
    await vi.advanceTimersByTimeAsync(600);
    expect(card.hasAttribute("data-held")).toBe(false);
    button?.dispatchEvent(pointer("pointerup"));
    button?.click();
    await vi.advanceTimersByTimeAsync(1000);
    await popupOf(card).updateComplete;

    expect(hass.calls).toEqual([stopped()]);
    expect(isOpen(card)).toBe(false);
  });

  it("leaves a tap on the rest of the tile to open the pop-up", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, WITH_BUTTON);

    await press(card, 0);

    expect(isOpen(card)).toBe(true);
    expect(hass.calls).toEqual([]);
  });
});
