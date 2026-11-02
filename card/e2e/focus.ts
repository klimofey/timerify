// Where the keyboard focus is, as a person sees it: the page is made of shadow roots inside
// shadow roots, and the browser's own answers each stop at the edge of one.
import { expect, type Locator, type Page } from "@playwright/test";

/**
 * Gets the keyboard focus to a button of a card as a person does: the card's body has it, and
 * Tab goes on to the next control, the button. (A press of a key also turns on the ring that
 * shows the focus, which a script's `focus()` does not.)
 */
export async function tabToButton(page: Page, card: Locator, button: Locator): Promise<void> {
  await card.locator(".body").focus();
  await page.keyboard.press("Tab");
  await expect(button).toBeFocused();
}

/**
 * Where the keyboard focus is, as seen through the shadow roots of the whole page: inside the
 * dialog (however deep in shadow roots of its own), nowhere (on the document or on nothing),
 * or somewhere in the page behind it.
 */
export function focusedPlace(dialog: Locator): Promise<string> {
  return dialog.evaluate((element) => {
    let active: Element | null = document.activeElement;
    while (active?.shadowRoot?.activeElement) {
      active = active.shadowRoot.activeElement;
    }
    if (active === null || active === document.body || active === document.documentElement) {
      return "nowhere";
    }
    // `contains` stops at a shadow root, so walk up through the hosts instead.
    for (let node: Node | null = active; node !== null; ) {
      if (node === element) {
        return "the dialog";
      }
      node = node instanceof ShadowRoot ? node.host : node.parentNode;
    }
    return `the page behind: <${active.localName}>`;
  });
}

/** Whether the element is the one that has the keyboard focus in its own tree. */
export function hasFocus(element: Locator): Promise<boolean> {
  return element.evaluate((node) => {
    // The root of an element on the page is the document, in a shadow tree its shadow root.
    const root = node.getRootNode() as Document | ShadowRoot;
    return root.activeElement === node;
  });
}
