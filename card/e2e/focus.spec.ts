// The helpers that tell where the focus is must see through shadow roots, or a test that
// asks "is the focus still in the dialog" is wrong for a pop-up with a control of a custom
// element in it. They are tried on a page of their own, without Home Assistant on it.
import { expect, test } from "@playwright/test";
import { focusedPlace, hasFocus } from "./focus";

test.beforeEach(async ({ page }) => {
  await page.setContent(`
    <button id="behind">behind</button>
    <dialog id="dialog" open>
      <button id="plain">plain</button>
      <div id="outer"></div>
    </dialog>`);
  await page.evaluate(() => {
    const outer = document.querySelector("#outer")!.attachShadow({ mode: "open" });
    outer.innerHTML = `<div id="inner"></div>`;
    const inner = outer.querySelector("#inner")!.attachShadow({ mode: "open" });
    inner.innerHTML = `<button id="deep">deep</button>`;
  });
});

test("the focus on a control of the dialog is in the dialog", async ({ page }) => {
  await page.locator("#plain").focus();

  expect(await focusedPlace(page.locator("#dialog"))).toBe("the dialog");
  expect(await hasFocus(page.locator("#plain"))).toBe(true);
});

test("the focus on a control in shadow roots inside the dialog is in the dialog", async ({
  page,
}) => {
  await page.locator("#deep").focus();

  expect(await focusedPlace(page.locator("#dialog"))).toBe("the dialog");
  expect(await hasFocus(page.locator("#deep"))).toBe(true);
});

test("the focus on the page behind the dialog is told apart", async ({ page }) => {
  await page.locator("#behind").focus();

  expect(await focusedPlace(page.locator("#dialog"))).toBe("the page behind: <button>");
});

test("a page without a focused control has the focus nowhere", async ({ page }) => {
  await page.locator("#plain").focus();
  await page.locator("#plain").blur();

  expect(await focusedPlace(page.locator("#dialog"))).toBe("nowhere");
  expect(await hasFocus(page.locator("#plain"))).toBe(false);
});
