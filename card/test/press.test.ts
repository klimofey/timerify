// What a person can make the card do with a tap, a double tap and a long press, and what each
// is set to by default. The card is pressed as a person presses it: with the pointer and the
// keyboard, and the time that a double tap waits for passes on the fake clock.
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { DOUBLE_TAP_MS, HOLD_MS } from "../src/press";
import type { TimerifyCard } from "../src/timerify-card";
import { BOILER, NUMBER, START, counting, fakeHass } from "./fake-hass";
import { bodyOf, mountCard, popupOf } from "./mount";

beforeEach(() => {
  vi.useFakeTimers({ now: START });
});

afterEach(() => {
  document.body.replaceChildren();
  vi.useRealTimers();
});

const target = (entity = NUMBER) => ({ entity_id: entity });
const ran = { domain: "timerify", service: "run", data: {}, target: target() };
const stopped = { domain: "timerify", service: "stop", data: {}, target: target() };
const setToZero = { domain: "number", service: "set_value", data: { value: 0 }, target: target() };

const isOpen = (card: TimerifyCard) => popupOf(card).shadowRoot?.querySelector("dialog")?.open;

/** A pointer event as a browser makes it for a mouse that is the primary pointer. */
const pointer = (type: string) =>
  new PointerEvent(type, {
    bubbles: true,
    composed: true,
    cancelable: true,
    isPrimary: true,
    pointerId: 1,
    pointerType: "mouse",
  });

/** One click on the card, as the browser sends it for a tap with a mouse or a finger. */
function clickNow(card: TimerifyCard): void {
  bodyOf(card).dispatchEvent(
    new MouseEvent("click", { bubbles: true, composed: true, cancelable: true }),
  );
}

/** The same, and the card draws what came of it. */
async function click(card: TimerifyCard): Promise<void> {
  clickNow(card);
  await card.updateComplete;
}

/** Presses the card for `milliseconds` and lets go; the click the browser sends follows. */
async function pressFor(card: TimerifyCard, milliseconds: number): Promise<void> {
  const body = bodyOf(card);
  body.dispatchEvent(pointer("pointerdown"));
  await vi.advanceTimersByTimeAsync(milliseconds);
  body.dispatchEvent(pointer("pointerup"));
  await click(card);
}

/** Lets `milliseconds` of the fake clock pass, and the card draw what came of them. */
async function wait(card: TimerifyCard, milliseconds: number): Promise<void> {
  await vi.advanceTimersByTimeAsync(milliseconds);
  await popupOf(card).updateComplete;
}

/** The `hass-action` events that reach the page: what Home Assistant's own handler hears. */
function actionsHeard(): { config: Record<string, unknown>; action: string }[] {
  const heard: { config: Record<string, unknown>; action: string }[] = [];
  const listener = (event: Event) =>
    heard.push((event as CustomEvent<(typeof heard)[number]>).detail);
  document.body.addEventListener("hass-action", listener);
  onTestFinished(() => document.body.removeEventListener("hass-action", listener));
  return heard;
}

const PILL = { entity: NUMBER, layout: "pill" } as const;
const ROUND = { entity: NUMBER, layout: "round" } as const;

describe("a tap", () => {
  it("opens the pop-up by default on both layouts", async () => {
    for (const config of [PILL, ROUND]) {
      const hass = fakeHass();
      const card = await mountCard(hass, config);

      await click(card);
      await popupOf(card).updateComplete;

      expect(isOpen(card), config.layout).toBe(true);
      expect(hass.calls).toEqual([]);
      card.remove();
    }
  });

  it("acts at once when no double tap is set", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...PILL, tap: "run" });

    await click(card);

    expect(hass.calls).toEqual([ran]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does nothing when it is set to nothing", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...PILL, tap: "none" });

    await click(card);
    await popupOf(card).updateComplete;

    expect(isOpen(card)).toBe(false);
    expect(hass.calls).toEqual([]);
  });

  it("a long press on the round tile starts or stops as before; on the pill it does nothing", async () => {
    const round = fakeHass();
    const roundCard = await mountCard(round, ROUND);
    const pill = fakeHass();
    const pillCard = await mountCard(pill, PILL);

    await pressFor(roundCard, HOLD_MS);
    await pressFor(pillCard, HOLD_MS);

    expect(round.calls).toEqual([ran]);
    expect(isOpen(roundCard)).toBe(false);
    // A long press with a mouse on the pill is a tap.
    expect(pill.calls).toEqual([]);
    expect(isOpen(pillCard)).toBe(true);
  });
});

describe("a double tap", () => {
  const withDoubleTap = { ...PILL, double_tap: "run" } as const;

  it("a single tap still opens the pop-up when a double tap is set", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, withDoubleTap);

    await click(card);
    // The card waits for a second tap, and has done nothing yet.
    await wait(card, DOUBLE_TAP_MS - 1);
    expect(isOpen(card)).toBe(false);
    await wait(card, 1);

    expect(isOpen(card)).toBe(true);
    expect(hass.calls).toEqual([]);
  });

  it("a double tap does the double tap action alone", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, withDoubleTap);

    await click(card);
    await wait(card, DOUBLE_TAP_MS - 1);
    await click(card);
    // Long after the window: the first tap does not come late.
    await wait(card, 10 * DOUBLE_TAP_MS);

    expect(hass.calls).toEqual([ran]);
    expect(isOpen(card)).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("two taps further apart than the window are two single taps", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...PILL, tap: "stop", double_tap: "run" });

    await click(card);
    await wait(card, DOUBLE_TAP_MS);
    await click(card);
    await wait(card, DOUBLE_TAP_MS);

    expect(hass.calls).toEqual([stopped, stopped]);
  });

  it("a third tap starts a new wait", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...PILL, tap: "stop", double_tap: "run" });

    await click(card);
    await click(card);
    await click(card);
    expect(hass.calls).toEqual([ran]);
    await wait(card, DOUBLE_TAP_MS);

    expect(hass.calls).toEqual([ran, stopped]);
  });

  it("Enter does the tap action at once with a double tap set", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...withDoubleTap, tap: "stop" });

    bodyOf(card).dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }),
    );

    expect(hass.calls).toEqual([stopped]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("Space does the tap action at once when it comes up, with a double tap set", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...withDoubleTap, tap: "stop" });
    const body = bodyOf(card);

    body.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true }));
    body.dispatchEvent(new KeyboardEvent("keyup", { key: " ", bubbles: true, cancelable: true }));

    expect(hass.calls).toEqual([stopped]);
  });

  it("stops waiting for a second tap when the card leaves the page", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, withDoubleTap);
    await click(card);

    card.remove();

    expect(vi.getTimerCount()).toBe(0);
    await vi.advanceTimersByTimeAsync(DOUBLE_TAP_MS);
    expect(hass.calls).toEqual([]);
  });

  it("does not count a tap twice when the card is set again while it waits", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, withDoubleTap);
    await click(card);

    card.setConfig({ ...PILL, tap: "stop" });
    await card.updateComplete;
    await click(card);
    await wait(card, 10 * DOUBLE_TAP_MS);

    // The second tap meets a card that has no double tap: it acts at once, and the one before
    // it is not counted twice.
    expect(hass.calls).toEqual([stopped]);
  });
});

describe("a long press", () => {
  it("acts on the pill too when it is set to", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...PILL, hold: "run" });
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown"));
    await vi.advanceTimersByTimeAsync(HOLD_MS);
    expect(card.hasAttribute("data-held")).toBe(true);
    body.dispatchEvent(pointer("pointerup"));
    await click(card);
    await popupOf(card).updateComplete;

    expect(hass.calls).toEqual([ran]);
    expect(isOpen(card)).toBe(false);
    expect(card.hasAttribute("data-held")).toBe(false);
  });

  it("leaves a long press on the round tile alone when it is set to nothing", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...ROUND, hold: "none" });
    const body = bodyOf(card);

    body.dispatchEvent(pointer("pointerdown"));
    await vi.advanceTimersByTimeAsync(2 * HOLD_MS);
    expect(card.hasAttribute("data-held")).toBe(false);
    body.dispatchEvent(pointer("pointerup"));
    await click(card);
    await popupOf(card).updateComplete;

    // With a mouse it is a tap.
    expect(hass.calls).toEqual([]);
    expect(isOpen(card)).toBe(true);
  });

  it("can open the pop-up, so that a tap can do something else", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...ROUND, tap: "run", hold: "popup" });

    await pressFor(card, HOLD_MS);

    expect(isOpen(card)).toBe(true);
    expect(hass.calls).toEqual([]);
  });
});

describe("what a press can be set to", () => {
  it("run runs the timer for its default duration, as a bare run does", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass, { ...PILL, tap: "run" });

    await click(card);

    // Nothing in the data: Timerify chooses the duration.
    expect(hass.calls).toEqual([ran]);
    expect(Object.keys(hass.calls[0]?.data ?? { none: true })).toEqual([]);
  });

  it("stop stops the timer with Timerify's own action", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, { ...PILL, tap: "stop" });

    await click(card);

    expect(hass.calls).toEqual([stopped]);
  });

  it("start or stop runs a timer that is idle and stops one that runs", async () => {
    const idle = fakeHass();
    const idleCard = await mountCard(idle, { ...PILL, tap: "run_or_stop" });
    const running = counting(45);
    const runningCard = await mountCard(running, { ...PILL, tap: "run_or_stop" });

    await click(idleCard);
    await click(runningCard);

    expect(idle.calls).toEqual([ran]);
    expect(running.calls).toEqual([setToZero]);
  });

  it("start or stop does nothing to a timer that is unavailable", async () => {
    const hass = fakeHass().state(NUMBER, "unavailable");
    const card = await mountCard(hass, { ...PILL, tap: "run_or_stop" });

    await click(card);

    expect(hass.calls).toEqual([]);
  });

  it("leaves the card as it was when Home Assistant refuses", async () => {
    const hass = counting(45);
    const card = await mountCard(hass, { ...PILL, tap: "stop" });
    hass.rejectNext(new Error("The timer refused"));

    await click(card);
    await vi.advanceTimersByTimeAsync(0);

    // Home Assistant has shown its toast; nothing of the card fails.
    expect(hass.calls).toEqual([stopped]);
    expect(isOpen(card)).toBe(false);
  });
});

describe("a press set to a Home Assistant action", () => {
  it("fires hass-action for the target", async () => {
    const heard = actionsHeard();
    const card = await mountCard(fakeHass(), {
      ...PILL,
      tap: "action",
      tap_action: { action: "more-info" },
    });

    await click(card);

    // The number is the card's entity, and no switch: the action acts on what the timer runs.
    expect(heard).toStrictEqual([
      { config: { entity: BOILER, tap_action: { action: "more-info" } }, action: "tap" },
    ]);
    expect(isOpen(card)).toBe(false);
  });

  it("fires hass-action as an event that crosses the card's shadow root", async () => {
    const card = await mountCard(fakeHass(), { ...PILL, tap: "action" });
    const event = vi.fn();
    document.body.addEventListener("hass-action", event);

    await click(card);

    expect(event).toHaveBeenCalledOnce();
    document.body.removeEventListener("hass-action", event);
  });

  it("tells Home Assistant which press it is, and hands it every action the user set", async () => {
    const heard = actionsHeard();
    const actions = {
      tap_action: { action: "toggle" },
      double_tap_action: { action: "navigate", navigation_path: "/lovelace/boiler" },
      hold_action: { action: "more-info" },
    };
    const card = await mountCard(fakeHass(), {
      ...ROUND,
      tap: "action",
      double_tap: "action",
      hold: "action",
      ...actions,
    });

    await pressFor(card, HOLD_MS);
    await click(card);
    await click(card);
    await wait(card, DOUBLE_TAP_MS);
    await click(card);
    await wait(card, DOUBLE_TAP_MS);

    expect(heard).toStrictEqual([
      { config: { entity: BOILER, ...actions }, action: "hold" },
      { config: { entity: BOILER, ...actions }, action: "double_tap" },
      { config: { entity: BOILER, ...actions }, action: "tap" },
    ]);
  });

  it("leaves it to Home Assistant to open more-info when no action is given", async () => {
    const heard = actionsHeard();
    const card = await mountCard(fakeHass(), { ...PILL, tap: "action" });

    await click(card);

    expect(heard).toStrictEqual([{ config: { entity: BOILER }, action: "tap" }]);
  });

  it("does nothing before the card has found its timer", async () => {
    const hass = fakeHass();
    hass.holdAnswers();
    const heard = actionsHeard();
    const card = document.createElement("timerify-card") as TimerifyCard;
    card.setConfig({ ...PILL, tap: "action", tap_action: { action: "more-info" } });
    card.hass = hass;
    document.body.append(card);
    await vi.advanceTimersByTimeAsync(0);

    // The card is drawn, and waits for the answer of Timerify.
    clickNow(card);
    expect(heard).toEqual([]);

    hass.answerNext();
    await card.updateComplete;
    clickNow(card);
    expect(heard).toHaveLength(1);
  });

  it("does nothing when Timerify could not tell of the timer", async () => {
    const hass = fakeHass();
    hass.answerWith("unknown_error");
    const heard = actionsHeard();
    const card = await mountCard(hass, { ...PILL, tap: "action" });

    await click(card);

    expect(heard).toEqual([]);
  });
});

describe("how the card describes a tap", () => {
  it("announces a pop-up only when a tap opens one", async () => {
    for (const layout of ["pill", "round"] as const) {
      const opens = await mountCard(fakeHass(), { entity: NUMBER, layout });
      expect(bodyOf(opens).getAttribute("aria-haspopup"), layout).toBe("dialog");
      opens.remove();

      const acts = await mountCard(fakeHass(), { entity: NUMBER, layout, tap: "run" });
      expect(bodyOf(acts).hasAttribute("aria-haspopup"), layout).toBe(false);
      acts.remove();
    }
  });

});

describe("a press the card does not know", () => {
  it("an unknown press choice is refused with its message", () => {
    const card = document.createElement("timerify-card") as TimerifyCard;

    for (const press of ["tap", "double_tap", "hold"]) {
      expect(() => card.setConfig({ ...PILL, [press]: "toggle" }), press).toThrow(
        english.card_error_press,
      );
    }
  });
});
