// The one way the scenarios put a card on a page, and the few things they look at in it.
import type { LitElement } from "lit";
import type { TimerifyCardPopup } from "../src/popup";
import "../src/timerify-card";
import type { TimerifyCard } from "../src/timerify-card";
import { NUMBER, type FakeHass } from "./fake-hass";

/**
 * Puts a card with this config on the page the way a dashboard does, and waits until it has
 * shown what Timerify answered.
 */
export async function mountCard(
  hass: FakeHass,
  config: Record<string, unknown> = { entity: NUMBER },
): Promise<TimerifyCard> {
  const card = document.createElement("timerify-card") as TimerifyCard;
  card.setConfig(config);
  card.hass = hass;
  document.body.append(card);
  await card.updateComplete;
  return card;
}

/** The pop-up in the card's shadow DOM; the card has one once it has found its timer. */
export function popupOf(card: TimerifyCard): TimerifyCardPopup {
  const popup = card.shadowRoot?.querySelector("timerify-card-popup");
  if (!popup) {
    throw new Error("The card has no pop-up");
  }
  return popup as TimerifyCardPopup;
}

/** The part of the card that is pressed; it holds the name and the icon. */
export function bodyOf(card: TimerifyCard): HTMLElement {
  const body = card.shadowRoot?.querySelector<HTMLElement>('[role="button"]');
  if (!body) {
    throw new Error("The card has no body to press");
  }
  return body;
}

/** The name the card shows, apart from whatever else it says. */
export function nameOf(card: TimerifyCard): string {
  return card.shadowRoot?.querySelector(".name")?.textContent?.trim() ?? "";
}

/** The words on the card itself, as a person reads them (the pop-up's are its own). */
export function textOf(card: TimerifyCard): string {
  const copy = document.createElement("div");
  for (const child of card.shadowRoot?.childNodes ?? []) {
    copy.append(child.cloneNode(true));
  }
  copy.querySelectorAll("style").forEach((style) => style.remove());
  return (copy.textContent ?? "").replace(/\s+/g, " ").trim();
}

const counts = new WeakMap<LitElement, { updates: number }>();

/**
 * How many times the element has rendered since this was first asked of it, which is the
 * point the scenario starts counting from.
 */
export function renders(element: LitElement): number {
  let count = counts.get(element);
  if (!count) {
    const fresh = { updates: 0 };
    count = fresh;
    element.addController({
      hostUpdated() {
        fresh.updates += 1;
      },
    });
    counts.set(element, fresh);
  }
  return count.updates;
}
