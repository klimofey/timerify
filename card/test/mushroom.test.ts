// The Mushroom style of the card: the card takes Mushroom's look when its config asks for it and
// Mushroom's cards are on the page. The page is never given Mushroom itself: a stand-in for one
// of its cards is defined, which is all the card looks for.
//
// A custom element cannot be undefined once it is defined, so the scenarios of one file share
// the page and run in the order they are written: first those in which Mushroom is not there,
// then the one in which it arrives, then those in which it is.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TimerifyCard } from "../src/timerify-card";
import { NUMBER, START, counting, fakeHass, type FakeHass } from "./fake-hass";
import { mountCard, renders } from "./mount";

const MUSHROOM = "mushroom-entity-card";
const LAYOUTS = ["pill", "round"] as const;
type Layout = (typeof LAYOUTS)[number];

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(START);
});

afterEach(() => {
  document.body.replaceChildren();
  vi.useRealTimers();
});

/** What Mushroom does on a page: its cards become known to the browser. */
function loadMushroom(): void {
  customElements.define(MUSHROOM, class extends HTMLElement {});
}

const inMushroomStyle = (card: TimerifyCard) => card.hasAttribute("data-mushroom");

/** A card of the layout on a timer that counts: it shows the countdown, the chip and Turn off. */
function mushroomCard(layout: Layout, options: Record<string, unknown> = {}, hass = counting(45)) {
  return mountCard(hass, {
    entity: NUMBER,
    layout,
    show_turn_off: true,
    ...(layout === "pill" && { chip: 15 }),
    ...options,
  });
}

/** The computed style of the part of the card that matches `selector`. */
function styleOf(card: TimerifyCard, selector: string): CSSStyleDeclaration {
  const part = card.shadowRoot?.querySelector(selector);
  if (!part) {
    throw new Error(`The card has no ${selector}`);
  }
  return getComputedStyle(part);
}

/**
 * What a card looks like in the Home Assistant look, in the parts that the Mushroom style
 * changes: what every card without the option has, and what one with it has until Mushroom is
 * on the page.
 */
const HOME_ASSISTANT_LOOK = {
  pill: {
    ".content": { paddingLeft: "8px", paddingRight: "12px", gap: "12px" },
    ".icon": { width: "40px", height: "40px" },
    ".name": { fontSize: "14px", fontWeight: "500" },
    ".status": { fontSize: "12px" },
    ".chip": { height: "32px", borderRadius: "16px" },
    ".turn-off": { height: "32px", borderRadius: "16px" },
  },
  round: {
    ".content": { paddingLeft: "8px", paddingRight: "8px", gap: "4px" },
    ".name": { fontSize: "14px", fontWeight: "500" },
    ".time": { fontSize: "16px", fontWeight: "500" },
    ".turn-off": { height: "32px", borderRadius: "16px" },
  },
} as const;

/** The variables of a theme that sets Mushroom's look, which a card in another look ignores. */
const MUSHROOM_THEME = {
  "--mush-spacing": "30px",
  "--mush-icon-size": "60px",
  "--mush-icon-border-radius": "4px",
  "--mush-card-primary-font-size": "30px",
  "--mush-card-primary-font-weight": "900",
  "--mush-card-secondary-font-size": "28px",
  "--mush-control-height": "60px",
  "--mush-control-border-radius": "2px",
  "--mush-chip-height": "60px",
  "--mush-chip-border-radius": "2px",
};

/** Sets the variables of a theme on the card, as Home Assistant does for the page. */
function applyTheme(card: TimerifyCard, theme: Record<string, string>): void {
  for (const [name, value] of Object.entries(theme)) {
    card.style.setProperty(name, value);
  }
}

/** Fails unless the card looks as every card does in the Home Assistant look. */
function expectHomeAssistantLook(card: TimerifyCard, layout: Layout): void {
  for (const [selector, look] of Object.entries(HOME_ASSISTANT_LOOK[layout])) {
    const style = styleOf(card, selector);
    for (const [property, wanted] of Object.entries(look)) {
      const shown = style[property as keyof CSSStyleDeclaration];
      expect(shown, `${layout} ${selector} ${property}`).toBe(wanted);
    }
  }
}

describe("a card that has not asked for the Mushroom style", () => {
  it("is not in Mushroom style, and looks as it always has", async () => {
    for (const layout of LAYOUTS) {
      const card = await mushroomCard(layout);

      expect(inMushroomStyle(card), layout).toBe(false);
      expectHomeAssistantLook(card, layout);
    }
  });

  it("keeps the Home Assistant look whatever the theme says of Mushroom", async () => {
    for (const layout of LAYOUTS) {
      const card = await mushroomCard(layout);
      applyTheme(card, MUSHROOM_THEME);

      expectHomeAssistantLook(card, layout);
    }
  });
});

describe("a card that asks for the Mushroom style where Mushroom is not", () => {
  it("keeps the Home Assistant look, whatever the theme says of Mushroom", async () => {
    for (const layout of LAYOUTS) {
      const card = await mushroomCard(layout, { mushroom: true });
      applyTheme(card, MUSHROOM_THEME);

      expect(inMushroomStyle(card), layout).toBe(false);
      expectHomeAssistantLook(card, layout);
    }
  });

  it("is not held up by the wait for Mushroom", async () => {
    const card = await mushroomCard("pill", { mushroom: true });

    // The mount waited for it, and so does anyone else: no frontend code does, and none may.
    await expect(card.updateComplete).resolves.toBe(true);
  });
});

describe("Mushroom loading after the cards, as a resource of a dashboard does", () => {
  // Mushroom can arrive once in a file, so the cards that it must and must not reach are all
  // on the page before it does.
  it("styles the cards that ask, and not the one that went or the one that stopped asking", async () => {
    const waiting = [
      await mushroomCard("pill", { mushroom: true }),
      await mushroomCard("round", { mushroom: true }),
      await mushroomCard("pill", { mushroom: true }, fakeHass()),
    ];
    const gone = await mushroomCard("pill", { mushroom: true });
    gone.remove();
    const drawn = renders(gone);
    // This one waits for Mushroom, and then its config says that the style is not wanted.
    const declined = await mushroomCard("pill", { mushroom: true });
    declined.setConfig({
      entity: NUMBER,
      layout: "pill",
      show_turn_off: true,
      chip: 15,
      mushroom: false,
    });
    await declined.updateComplete;
    const declinedDrawn = renders(declined);
    expect(waiting.map(inMushroomStyle)).toEqual([false, false, false]);

    loadMushroom();
    await customElements.whenDefined(MUSHROOM);
    await Promise.all(waiting.map((card) => card.updateComplete));
    await vi.advanceTimersByTimeAsync(0);

    expect(waiting.map(inMushroomStyle)).toEqual([true, true, true]);
    // Nobody asked the card that went to draw, so it did not find out that Mushroom came.
    expect(renders(gone)).toBe(drawn);
    expect(inMushroomStyle(gone)).toBe(false);
    // The card that no longer asks was not waiting for it: it is not drawn again, and it keeps
    // the look it has, whatever the theme says of Mushroom.
    applyTheme(declined, MUSHROOM_THEME);
    expect(renders(declined)).toBe(declinedDrawn);
    expect(inMushroomStyle(declined)).toBe(false);
    expectHomeAssistantLook(declined, "pill");

    // Back on the page, the card that went finds out then.
    document.body.append(gone);
    await gone.updateComplete;
    expect(inMushroomStyle(gone)).toBe(true);
  });
});

describe("a card in the Mushroom style", () => {
  it("is in Mushroom style from the first draw when Mushroom is already there", async () => {
    for (const layout of LAYOUTS) {
      const card = await mushroomCard(layout, { mushroom: true });

      expect(inMushroomStyle(card), layout).toBe(true);
    }
  });

  it("is in Mushroom style only while its config says so", async () => {
    const card = await mushroomCard("pill", { mushroom: true });

    card.setConfig({ entity: NUMBER, mushroom: false });
    await card.updateComplete;
    expect(inMushroomStyle(card)).toBe(false);

    card.setConfig({ entity: NUMBER, mushroom: true });
    await card.updateComplete;
    expect(inMushroomStyle(card)).toBe(true);
  });

  it("stays in Mushroom style when it is moved on the page", async () => {
    const card = await mushroomCard("pill", { mushroom: true });
    const elsewhere = document.createElement("div");
    document.body.append(elsewhere);

    elsewhere.append(card);
    await card.updateComplete;

    expect(inMushroomStyle(card)).toBe(true);
  });

  it("keeps the Home Assistant look when the card does not ask for the style", async () => {
    for (const layout of LAYOUTS) {
      const card = await mushroomCard(layout);
      applyTheme(card, MUSHROOM_THEME);

      expect(inMushroomStyle(card), layout).toBe(false);
      expectHomeAssistantLook(card, layout);
    }
  });

  it("is spaced by Mushroom's default, and by the theme's --mush-spacing", async () => {
    for (const layout of LAYOUTS) {
      const card = await mushroomCard(layout, { mushroom: true });
      expect(styleOf(card, ".content").paddingLeft, layout).toBe("10px");

      card.style.setProperty("--mush-spacing", "20px");

      expect(styleOf(card, ".content").paddingLeft, layout).toBe("20px");
      expect(styleOf(card, ".content").paddingRight, layout).toBe("20px");
    }
  });

  it("writes the name and the state in Mushroom's fonts, and in the theme's", async () => {
    for (const layout of LAYOUTS) {
      const card = await mushroomCard(layout, { mushroom: true });
      const name = (fontOf: CSSStyleDeclaration) => ({
        size: fontOf.fontSize,
        weight: fontOf.fontWeight,
        height: fontOf.lineHeight,
        spacing: fontOf.letterSpacing,
      });
      expect(name(styleOf(card, ".name")), layout).toEqual({
        size: "14px",
        weight: "500",
        height: "20px",
        spacing: "0.1px",
      });

      card.style.setProperty("--mush-card-primary-font-size", "18px");
      card.style.setProperty("--mush-card-primary-font-weight", "700");

      expect(name(styleOf(card, ".name")), layout).toMatchObject({ size: "18px", weight: "700" });
    }
    const pill = await mushroomCard("pill", { mushroom: true });
    expect(styleOf(pill, ".status")).toMatchObject({
      fontSize: "12px",
      fontWeight: "400",
      lineHeight: "16px",
      letterSpacing: "0.4px",
    });
    pill.style.setProperty("--mush-card-secondary-font-size", "13px");
    expect(styleOf(pill, ".status").fontSize).toBe("13px");
  });

  it("draws the icon in Mushroom's shape, as large as the theme says", async () => {
    // The round tile shows its icon in the dial while nothing counts.
    for (const [layout, hass] of [
      ["pill", counting(45)],
      ["round", fakeHass()],
    ] as const) {
      const card = await mushroomCard(layout, { mushroom: true }, hass);
      expect(styleOf(card, ".icon"), layout).toMatchObject({
        width: "36px",
        height: "36px",
        borderRadius: "50%",
      });

      card.style.setProperty("--mush-icon-size", "48px");
      card.style.setProperty("--mush-icon-border-radius", "8px");

      expect(styleOf(card, ".icon"), layout).toMatchObject({
        width: "48px",
        height: "48px",
        borderRadius: "8px",
      });
    }
  });

  it("draws the chip as Mushroom's chip, and the Turn off button as its control", async () => {
    for (const layout of LAYOUTS) {
      const card = await mushroomCard(layout, { mushroom: true });

      expect(styleOf(card, ".turn-off"), layout).toMatchObject({
        height: "42px",
        borderRadius: "12px",
      });
      card.style.setProperty("--mush-control-height", "50px");
      card.style.setProperty("--mush-control-border-radius", "6px");
      expect(styleOf(card, ".turn-off"), layout).toMatchObject({
        height: "50px",
        borderRadius: "6px",
      });
    }
    const pill = await mushroomCard("pill", { mushroom: true });
    expect(styleOf(pill, ".chip")).toMatchObject({ height: "36px", borderRadius: "19px" });
    pill.style.setProperty("--mush-chip-height", "30px");
    pill.style.setProperty("--mush-chip-border-radius", "4px");
    expect(styleOf(pill, ".chip")).toMatchObject({ height: "30px", borderRadius: "4px" });
  });
});
