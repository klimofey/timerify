import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import type { TimerifyCard } from "../src/timerify-card";
import { BOILER, START, fakeHass } from "./fake-hass";
import { bodyOf, mountCard, popupOf, renders } from "./mount";

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(START);
});

afterEach(() => {
  document.body.replaceChildren();
  vi.useRealTimers();
});

/** A pointer event as a browser makes it for a mouse that is the primary pointer. */
const pointer = (type: "pointerdown" | "pointerup" | "pointercancel") =>
  new PointerEvent(type, {
    bubbles: true,
    composed: true,
    cancelable: true,
    isPrimary: true,
    pointerId: 1,
    pointerType: "mouse",
  });

/**
 * A press that goes down on `from` and up on `to`, and the click the browser sends after it:
 * to the nearest element that holds both (a press from the content to the backdrop is a click
 * on the dialog, which holds the content).
 */
function press(from: Element, to: Element, clicked: Element) {
  from.dispatchEvent(pointer("pointerdown"));
  to.dispatchEvent(pointer("pointerup"));
  clicked.dispatchEvent(new MouseEvent("click", { bubbles: true, composed: true }));
}

const dialogOf = (card: TimerifyCard) => {
  const dialog = popupOf(card).shadowRoot?.querySelector("dialog");
  if (!dialog) {
    throw new Error("The pop-up has no dialog");
  }
  return dialog;
};

async function opened(card: TimerifyCard) {
  popupOf(card).open();
  await popupOf(card).updateComplete;
}

describe("the pop-up of the card", () => {
  it("closes on its close button, on Escape and on the backdrop, and gives focus back", async () => {
    const card = await mountCard(fakeHass());
    const popup = popupOf(card);
    const focusedInCard = () => card.shadowRoot?.activeElement;

    await opened(card);
    expect(dialogOf(card).open).toBe(true);
    popup.shadowRoot?.querySelector<HTMLButtonElement>("button.close")?.click();
    expect(dialogOf(card).open).toBe(false);
    expect(popup.opened).toBe(false);
    expect(focusedInCard()).toBe(bodyOf(card));

    await opened(card);
    dialogOf(card).dispatchEvent(new Event("cancel", { cancelable: true }));
    expect(dialogOf(card).open).toBe(false);
    expect(focusedInCard()).toBe(bodyOf(card));

    await opened(card);
    press(dialogOf(card), dialogOf(card), dialogOf(card));
    expect(dialogOf(card).open).toBe(false);
    expect(focusedInCard()).toBe(bodyOf(card));

    await opened(card);
    popup.shadowRoot?.querySelector<HTMLElement>(".wrapper")?.click();
    expect(dialogOf(card).open).toBe(true);
    expect(popup.opened).toBe(true);
  });

  describe("a click on the backdrop", () => {
    const wrapperOf = (card: TimerifyCard) =>
      popupOf(card).shadowRoot?.querySelector(".wrapper") as HTMLElement;

    it("closes it only when the press began on the backdrop too", async () => {
      const card = await mountCard(fakeHass());
      await opened(card);

      // A text selection that is dragged out of the content and let go over the backdrop is
      // a click on the dialog, since it holds both ends. It is no click on the backdrop.
      press(wrapperOf(card), dialogOf(card), dialogOf(card));

      expect(dialogOf(card).open).toBe(true);
      expect(popupOf(card).opened).toBe(true);
    });

    it("closes it only when the press ended on the backdrop too", async () => {
      const card = await mountCard(fakeHass());
      await opened(card);

      press(dialogOf(card), wrapperOf(card), dialogOf(card));

      expect(dialogOf(card).open).toBe(true);
    });

    it("is not made by a press that began on the title", async () => {
      const card = await mountCard(fakeHass());
      await opened(card);
      const title = popupOf(card).shadowRoot?.querySelector("h2") as HTMLElement;

      press(title, dialogOf(card), dialogOf(card));

      expect(dialogOf(card).open).toBe(true);
    });

    it("needs a press of its own every time", async () => {
      const card = await mountCard(fakeHass());
      await opened(card);
      press(dialogOf(card), dialogOf(card), dialogOf(card));
      expect(dialogOf(card).open).toBe(false);

      // Opened again, a click on the dialog that no press led to, as assistive technology
      // may send, leaves it open.
      await opened(card);
      dialogOf(card).dispatchEvent(new MouseEvent("click", { bubbles: true, composed: true }));

      expect(dialogOf(card).open).toBe(true);
    });

    it("forgets a press that was cancelled", async () => {
      const card = await mountCard(fakeHass());
      await opened(card);

      dialogOf(card).dispatchEvent(pointer("pointerdown"));
      dialogOf(card).dispatchEvent(pointer("pointercancel"));
      dialogOf(card).dispatchEvent(new MouseEvent("click", { bubbles: true, composed: true }));

      expect(dialogOf(card).open).toBe(true);
    });
  });

  it("can be opened again after it was closed", async () => {
    const card = await mountCard(fakeHass());

    await opened(card);
    popupOf(card).close();
    await opened(card);

    expect(dialogOf(card).open).toBe(true);
  });

  it("is not closed by the late announcement of an earlier close", async () => {
    const card = await mountCard(fakeHass());
    await opened(card);
    popupOf(card).close();
    await opened(card);

    // The browser announces a closed dialog after the fact; this one has been opened again.
    dialogOf(card).dispatchEvent(new Event("close"));

    expect(dialogOf(card).open).toBe(true);
    expect(popupOf(card).opened).toBe(true);
  });

  it("closes when the card leaves the page", async () => {
    const card = await mountCard(fakeHass());
    const popup = popupOf(card);
    await opened(card);

    card.remove();

    expect(popup.opened).toBe(false);
    expect(popup.shadowRoot?.querySelector("dialog")?.open).toBe(false);
  });

  it("is titled with the name of the timer, and says close in the user's words", async () => {
    const card = await mountCard(fakeHass());

    await opened(card);

    const popup = popupOf(card);
    const titleId = dialogOf(card).getAttribute("aria-labelledby");
    expect(popup.shadowRoot?.getElementById(titleId ?? "")?.textContent?.trim()).toBe("Boiler");
    expect(popup.shadowRoot?.querySelector("button.close")?.textContent?.trim()).toBe(
      english.card_close,
    );
  });

  it("renders nothing while closed", async () => {
    let hass = fakeHass();
    const card = await mountCard(hass);
    const popup = popupOf(card);
    expect(renders(popup)).toBe(0);
    expect(dialogOf(card).children).toHaveLength(0);

    for (let change = 1; change <= 10; change += 1) {
      hass = hass.state(BOILER, change % 2 ? "on" : "off", { friendly_name: `Boiler ${change}` });
      card.hass = hass;
      await card.updateComplete;
    }

    expect(renders(popup)).toBe(0);
    expect(dialogOf(card).children).toHaveLength(0);
  });

  it("follows the name of the timer while open", async () => {
    const hass = fakeHass();
    const card = await mountCard(hass);
    await opened(card);

    card.hass = hass.state(BOILER, "on", { friendly_name: "Water heater" });
    await card.updateComplete;
    await popupOf(card).updateComplete;

    expect(popupOf(card).shadowRoot?.querySelector("h2")?.textContent?.trim()).toBe("Water heater");
  });
});
