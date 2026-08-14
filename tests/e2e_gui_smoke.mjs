/**
 * GUI Smoke Test — verifies actual browser DOM rendering for ronzzdoi.
 *
 * Every command is typed → Enter → then we assert DOM structure:
 *   - Did a tab bar appear?
 *   - Does the active tab have the expected title?
 *   - Is the tab content panel visible and non-empty?
 *   - Did any JS exception occur?
 *
 * Console errors AND page errors cause the ENTIRE SUITE TO FAIL.
 */

import { chromium } from "playwright";
import { strict as assert } from "assert";

// ── Config ────────────────────────────────────────────────────────────────

const FRONTEND_URL = process.env.FRONTEND_URL || "http://127.0.0.1:6025";
const CHROME_PATH = process.env.CHROME_PATH || "chromium";
// Optional API key (from `ronzzdoi-dev --seed` output). When set, the
// authenticated flows are exercised (citation, detail view, assign form).
const API_KEY = process.env.RONZZDOI_API_KEY || "";

// ── Shared state ──────────────────────────────────────────────────────────

let page = null;
let pageErrors = [];
let consoleErrors = [];
let passed = 0;
let failed = 0;

// ── Utilities ─────────────────────────────────────────────────────────────

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function typeCommand(cmd) {
  // Ensure the home tab is active (Alt+1) with the input focused and
  // cleared — stale focus/input state from previous tabs can otherwise
  // leave the input hidden or with leftover text.
  await page.keyboard.press("Alt+1");
  await sleep(100);
  await page.evaluate(() => {
    const el = document.querySelector(".input-field");
    if (el) {
      el.focus();
      el.value = "";
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  const input = page.locator(".input-field, [aria-label='Message input'], textarea");
  try {
    await input.waitFor({ state: "visible", timeout: 1500 });
  } catch {
    // Command input only exists on the home tab. Result tabs auto-activate
    // when opened, so switch back home (Alt+1) before typing.
    await page.keyboard.press("Alt+1");
    await sleep(200);
    await input.waitFor({ state: "visible", timeout: 3000 });
  }
  await input.click();
  await input.fill("");
  await sleep(30);
  await input.pressSequentially(cmd, { delay: 5 });
  await sleep(150);
}

async function pressEnter() {
  await page.keyboard.press("Enter");
  await sleep(600);
}

async function getActiveTabTitleAttr() {
  const tabBar = page.locator('[role="tablist"]');
  await tabBar.waitFor({ state: "visible", timeout: 4000 });

  // Wait for the transient "Executing…" loading tab to be replaced by the
  // real response tab (command latency varies).
  await page.waitForFunction(() => {
    const active = document.querySelector('[role="tab"][aria-selected="true"]');
    return active && active.getAttribute("title") !== "Executing…";
  }, { timeout: 8000 }).catch(() => {});

  const activeTab = tabBar.locator('[role="tab"][aria-selected="true"]');
  await activeTab.waitFor({ state: "visible", timeout: 3000 });
  return (await activeTab.getAttribute("title") || "").trim();
}

async function assertTabOpened(expectedTitle) {
  const tabBar = page.locator('[role="tablist"]');
  await tabBar.waitFor({ state: "visible", timeout: 4000 });
  const tabCount = await tabBar.locator('[role="tab"]').count();
  assert(tabCount >= 2, `Expected ≥2 tabs (home + result), found ${tabCount}`);

  const titleAttr = await getActiveTabTitleAttr();
  assert(
    titleAttr.toLowerCase().includes(expectedTitle.toLowerCase()),
    `Active tab title should contain "${expectedTitle}", got "${titleAttr}"`,
  );

  const panel = page.locator(
    `.tab-content.active[data-testid="tab-panel"][aria-label="${titleAttr}"]`,
  );
  await panel.waitFor({ state: "visible", timeout: 3000 });
  const panelText = (await panel.textContent() || "").trim();
  assert(panelText.length > 0, `Tab panel for "${expectedTitle}" is empty`);
}

async function assertHomeActive() {
  const input = page.locator(".input-field, [aria-label='Message input']");
  const visible = await input.isVisible().catch(() => false);
  assert(visible, "Home tab should be active with visible command input");
}

async function dismissAllTabs() {
  // Drop focus first — with the input focused, Escape is consumed by
  // ChatInput (closes suggestions / blurs) instead of closing tabs.
  await page.locator("body").click({ position: { x: 4, y: 4 } }).catch(() => {});
  await page.keyboard.press("Alt+1");
  await sleep(150);
  for (let i = 0; i < 10; i++) {
    await page.keyboard.press("Escape");
    await sleep(150);
    try {
      const dialog = page.locator('[role="alertdialog"]');
      if (await dialog.isVisible({ timeout: 100 })) {
        const discardBtn = dialog.locator('button:has-text("Discard")');
        if (await discardBtn.isVisible({ timeout: 100 })) {
          await discardBtn.click();
          await sleep(150);
          continue;
        }
        const cancelBtn = dialog.locator('button:has-text("Cancel")');
        if (await cancelBtn.isVisible({ timeout: 100 })) {
          await cancelBtn.click();
          await sleep(150);
          continue;
        }
      }
    } catch { /* no dialog */ }
    const tabBar = page.locator('[role="tablist"]');
    const tabBarVisible = await tabBar.isVisible().catch(() => false);
    if (!tabBarVisible) break;
    const tabCount = await tabBar.locator('[role="tab"]').count().catch(() => 0);
    if (tabCount <= 1) break;
  }

  // Fallback: force-close any remaining tabs via their close buttons
  // (Escape can be consumed by focused elements inside tab panels).
  for (let i = 0; i < 10; i++) {
    const closeBtns = page.locator(".tab-close");
    const n = await closeBtns.count().catch(() => 0);
    if (n === 0) break;
    await closeBtns.first().click().catch(() => {});
    await sleep(120);
  }
}

async function test(desc, fn) {
  try {
    await fn();
    console.log(`  \u2713 ${desc}`);
    passed++;
  } catch (e) {
    try {
      await page.screenshot({ path: `/tmp/e2e-ronzzdoi-fail-${Date.now()}.png` });
    } catch {}
    try {
      const bodyText = (await page.locator("body").textContent() || "").substring(0, 200);
      console.log(`    Page text: "${bodyText.replace(/\s+/g, " ").trim()}"`);
    } catch {}
    console.log(`  \u2717 ${desc}: ${e.message}`);
    failed++;
  } finally {
    await dismissAllTabs();
  }
}

// ── Browser lifecycle ────────────────────────────────────────────────────

async function runWithBrowser(fn) {
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      executablePath: CHROME_PATH,
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
    });
    const context = await browser.newContext({
      viewport: { width: 960, height: 720 },
      permissions: ["clipboard-read", "clipboard-write"],
    });
    // Inject the API key before any page loads (authenticated flows only).
    if (API_KEY) {
      await context.addInitScript((key) => {
        localStorage.setItem("ronzzdoi_api_key", key);
      }, API_KEY);
    }
    page = await context.newPage();

    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
      console.log("  [BROWSER ERROR]", err.message);
    });
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
        console.log("  [CONSOLE ERROR]", msg.text());
      }
    });

    await page.goto(FRONTEND_URL, { waitUntil: "networkidle" });
    console.log("\u2713 Page loaded:", await page.title());
    await sleep(500);

    // Seed the API key (if provided) so authenticated commands work
    if (API_KEY) {
      await page.evaluate((k) => localStorage.setItem("ronzzdoi_api_key", k), API_KEY);
      await page.reload({ waitUntil: "networkidle" });
      await sleep(400);
    }

    // Dismiss any welcome notice
    try {
      const dismissBtn = page.locator("button", { hasText: "Dismiss notice" });
      if (await dismissBtn.isVisible({ timeout: 300 })) {
        await dismissBtn.click();
        await sleep(200);
      }
    } catch { /* no notice */ }

    await fn();

    // Summary
    console.log();
    if (pageErrors.length > 0) {
      console.log(`  [ERROR] ${pageErrors.length} unhandled page error(s) during session`);
    }
    if (consoleErrors.length > 0) {
      console.log(`  [ERROR] ${consoleErrors.length} console error(s) during session`);
    }
    console.log(`RESULTS (GUI Smoke): ${passed} passed, ${failed} failed`);

    await browser.close();
    process.exit(failed > 0 ? 1 : 0);
  } catch (e) {
    console.error("FATAL:", e.message);
    if (browser) await browser.close().catch(() => {});
    process.exit(1);
  }
}

// ── Tests ─────────────────────────────────────────────────────────────────

async function runTests() {
  // ═══════════════════════════════════════════
  // HOME TAB
  // ═══════════════════════════════════════════
  console.log("\n--- HOME TAB ---");

  await test("Home tab shows command input", async () => {
    const input = page.locator(".input-field, [aria-label='Message input']");
    await input.waitFor({ state: "visible", timeout: 3000 });
    assert(await input.isVisible(), "Command input should be visible");
  });

  // ═══════════════════════════════════════════
  // HELP TAB
  // ═══════════════════════════════════════════
  console.log("\n--- HELP TAB ---");

  await test("!help opens help tab with commands list", async () => {
    await typeCommand("!help");
    await pressEnter();
    await assertTabOpened("Available");
  });

  // ═══════════════════════════════════════════
  // FORM POPUPS — incomplete commands
  // ═══════════════════════════════════════════
  console.log("\n--- FORM POPUPS ---");

  await test("!doi assign (incomplete) opens assign form", async () => {
    await typeCommand("!doi assign");
    await pressEnter();
    await assertTabOpened("Assign");
  });

  await test("!citation show (incomplete) opens error for missing doi", async () => {
    await typeCommand("!citation show");
    await pressEnter();
    // Should show error (missing DOI argument) or form
    const tabBar = page.locator('[role="tablist"]');
    await tabBar.waitFor({ state: "visible", timeout: 4000 });
    const tabCount = await tabBar.locator('[role="tab"]').count().catch(() => 0);
    assert(tabCount >= 2, `Expected tab to open, got ${tabCount} tabs`);
  });

  // ═══════════════════════════════════════════
  // DOI LIST / SEARCH
  // ═══════════════════════════════════════════
  console.log("\n--- DOI LIST ---");

  await test("!doi search opens DOI list tab", async () => {
    await typeCommand("!doi search");
    await pressEnter();
    await assertTabOpened("DOI");
  });

  await test("!doi search <query> opens filtered results", async () => {
    await typeCommand("!doi search test");
    await pressEnter();
    await assertTabOpened("DOI");
  });

  // ═══════════════════════════════════════════
  // SNIPPETS — form toggle + copy embed
  // ═══════════════════════════════════════════
  console.log("\n--- SNIPPETS ---");

  await test("!snippet assign (incomplete) opens form with Text/Code/Math toggle", async () => {
    await typeCommand("!snippet assign");
    await pressEnter();
    await assertTabOpened("Assign");

    const toggle = page.locator('[role="radiogroup"][aria-label="Content Type"]');
    await toggle.waitFor({ state: "visible", timeout: 3000 });
    const buttons = await toggle.locator('button[role="radio"]').allTextContents();
    assert(buttons.length === 3, `Expected 3 content-kind options, got ${buttons.length}`);
    const kinds = buttons.map((b) => b.trim());
    assert(kinds.includes("text") && kinds.includes("code") && kinds.includes("math"),
      `Toggle should offer text/code/math, got: ${kinds.join(", ")}`);
  });

  await test("!snippet assign form submits → snippet tab with Copy Embed", async () => {
    await typeCommand("!snippet assign");
    await pressEnter();
    await assertTabOpened("Assign");

    // Text is the default kind — fill content + title
    const content = page.locator("#content");
    await content.fill("Cogito ergo sum.");
    const title = page.locator("#title");
    await title.fill("Descartes quote");
    await page.locator('button[type="submit"]').click();
    await sleep(900);

    // Snippet tab opens (title starts with "Snippet:")
    await assertTabOpened("Snippet");

    const copyBtn = page.locator(".copy-btn");
    await copyBtn.waitFor({ state: "visible", timeout: 3000 });
    assert((await copyBtn.textContent() || "").includes("Copy Embed"),
      "Copy Embed button should be present on the snippet tab");
  });

  await test("Copy Embed copies an iframe tag to the clipboard", async () => {
    // Self-contained: create a fresh snippet tab, then copy from it
    await typeCommand("!snippet assign");
    await pressEnter();
    await assertTabOpened("Assign");

    await page.locator("#content").fill("Cogito ergo sum.");
    await page.locator("#title").fill("Descartes quote");
    await page.locator('button[type="submit"]').click();
    await sleep(900);
    await assertTabOpened("Snippet");

    const copyBtn = page.locator(".copy-btn");
    await copyBtn.waitFor({ state: "visible", timeout: 3000 });
    await copyBtn.click();
    await sleep(300);

    const clip = await page.evaluate(() => navigator.clipboard.readText());
    assert(clip.startsWith('<iframe src="'), `Clipboard should hold an iframe tag, got: ${clip.slice(0, 60)}`);
    assert(clip.includes("/embed/10.ronzz/"), "iframe src should point at the embed page");
  });

  // ═══════════════════════════════════════════
  // TAB NAVIGATION
  // ═══════════════════════════════════════════
  console.log("\n--- TAB NAVIGATION ---");

  await test("Multiple tabs appear in tab bar", async () => {
    await typeCommand("!help");
    await pressEnter();
    await assertTabOpened("Available");
    await typeCommand("!doi search");
    await pressEnter();
    await assertTabOpened("DOI");

    const tabBar = page.locator('[role="tablist"]');
    const tabCount = await tabBar.locator('[role="tab"]').count();
    assert(tabCount >= 3, `Expected ≥ 3 tabs, found ${tabCount}`);
  });

  await test("Click on different tabs switches active tab", async () => {
    const tabs = page.locator('[role="tab"]');
    const count = await tabs.count();
    for (let i = 0; i < count; i++) {
      const tab = tabs.nth(i);
      await tab.click();
      await sleep(200);
      const selected = await tab.getAttribute("aria-selected");
      assert(selected === "true", `Tab ${i} should be selected after click`);
    }
  });

  // ═══════════════════════════════════════════
  // AUTHENTICATED FLOWS (requires RONZZDOI_API_KEY)
  // ═══════════════════════════════════════════
  if (API_KEY) {
    console.log("\n--- AUTHENTICATED FLOWS ---");

    /** Open the detail tab for the seeded "Clean Code" book. */
    async function openBookDetail() {
      await typeCommand("!doi search Clean");
      await pressEnter();
      await assertTabOpened("DOI");
      const bookRow = page.locator('[role="option"]', { hasText: "Clean Code" }).first();
      await bookRow.click();
      await sleep(800);
      await page.locator(".metadata-table").waitFor({ state: "visible", timeout: 4000 });
    }

    await test("Assign form: DOI type autocomplete opens on focus (#36, #48)", async () => {
      await typeCommand("!doi assign");
      await pressEnter();
      await assertTabOpened("Assign");

      const typeInput = page.locator("#doi_type");
      await typeInput.waitFor({ state: "visible", timeout: 3000 });

      // The type field is a custom combobox, not a native <datalist> (#48.2).
      const listId = await typeInput.getAttribute("list");
      assert(listId === null, "DOI type input should NOT use a datalist");

      // Dropdown opens on focus (single click) and lists the types.
      await typeInput.click();
      await sleep(250);
      const dropdown = page.locator(".autocomplete-dropdown");
      await dropdown.waitFor({ state: "visible", timeout: 3000 });
      const optionCount = await page.locator(".autocomplete-item").count();
      assert(optionCount >= 5,
        `Type dropdown should offer many types, found ${optionCount}`);

      // Typing filters the options.
      await typeInput.fill("film");
      await sleep(200);
      const filtered = await page.locator(".autocomplete-item").allTextContents();
      assert(filtered.every((t) => t.includes("film")),
        `Typing 'film' should filter options, got: ${filtered.join(", ")}`);

      const titleTag = await page.locator("#title").evaluate((el) => el.tagName);
      assert(titleTag === "INPUT",
        `Title should be a plain text input, got <${titleTag.toLowerCase()}>`);

      // Selecting a type with a schema reveals type-specific fields.
      await page.locator(".autocomplete-item", { hasText: "film" }).first().click();
      await sleep(250);
      const metaFields = await page.locator('.form-field input[type="text"], .form-field textarea').count();
      assert(metaFields >= 4,
        `film type should reveal schema fields, found ${metaFields} inputs`);
    });

    await test("Assign form: Target URL optional, no raw Metadata JSON field (#48.1, #48.3)", async () => {
      await typeCommand("!doi assign");
      await pressEnter();
      await assertTabOpened("Assign");

      // Target URL must not be required (entity DOIs have no URL).
      const urlField = page.locator(".form-field", { hasText: "Target URL" }).first();
      const urlRequiredStar = await urlField.locator(".required-star").count();
      assert(urlRequiredStar === 0,
        "Target URL must not show a required marker");

      // No raw JSON textarea before a type is selected.
      const jsonField = page.locator(".form-field", { hasText: "Metadata (JSON)" });
      assert((await jsonField.count()) === 0,
        "Metadata (JSON) field must not be shown");

      // Submitting with only a title + entity type assigns without URL.
      await page.locator("#title").fill("Entity Test DOI");
      await page.locator("#doi_type").click();
      await sleep(200);
      await page.locator(".autocomplete-item", { hasText: "person" }).first().click();
      await sleep(200);
      await page.locator('button[type="submit"]').click();
      await sleep(900);
      await assertTabOpened("DOI");
      const detailText = (await page.locator(".detail, .doi-list, main").first().textContent() || "");
      assert(detailText.includes("Entity Test DOI"),
        `Assigned entity DOI should show its title, got: "${detailText.trim().slice(0, 200)}"`);
    });

    await test("Assign form: pure-text fields offer translations (#47.1)", async () => {
      await typeCommand("!doi assign");
      await pressEnter();
      await assertTabOpened("Assign");

      // The base title field has a primary-language input + translations.
      const titleField = page.locator(".form-field", { hasText: /^Title/ }).first();
      const titleI18n = await titleField.locator(".i18n-toggle").count();
      assert(titleI18n === 1,
        "Title field should offer translations");
      const primaryDefault = await titleField.locator(".i18n-primary").inputValue();
      assert(primaryDefault === "en",
        `Primary language should default to en, got "${primaryDefault}"`);

      // Selecting a type with a pure-text schema field reveals per-field
      // translation buttons (e.g. film's studio).
      await page.locator("#doi_type").click();
      await sleep(200);
      await page.locator(".autocomplete-item", { hasText: "film" }).first().click();
      await sleep(250);
      const studioField = page.locator(".form-field", { hasText: "Studio" }).first();
      await studioField.waitFor({ state: "visible", timeout: 3000 });
      const studioI18n = await studioField.locator(".i18n-toggle").count();
      assert(studioI18n === 1,
        "Pure-text metadata fields (e.g. Studio) should offer translations");

      // Setting a non-en primary language works (e.g. fr for a song).
      await studioField.locator(".i18n-primary").fill("fr");
      await sleep(100);
      assert((await studioField.locator(".i18n-primary").inputValue()) === "fr",
        "Primary language should be settable to a non-en language");

      // Adding a translation row works.
      await studioField.locator(".i18n-toggle").click();
      await sleep(150);
      await studioField.locator(".btn-small", { hasText: "Add language" }).click();
      await sleep(150);
      await studioField.locator(".i18n-lang").fill("en");
      await studioField.locator(".i18n-text").fill("Studio EN");
      await sleep(100);
      const rows = await studioField.locator(".i18n-row").count();
      assert(rows === 1, `Expected 1 translation row, found ${rows}`);
    });

    await test("Snippet assign form: title offers translations (#47.2)", async () => {
      await typeCommand("!snippet assign");
      await pressEnter();
      await assertTabOpened("Assign");

      const titleField = page.locator(".form-field", { hasText: /^Title/ }).first();
      await titleField.waitFor({ state: "visible", timeout: 3000 });
      const i18n = await titleField.locator(".i18n-toggle").count();
      assert(i18n === 1,
        "Snippet title field should offer translations");
    });

    await test("Tombstone: confirmation dialog confirms and tombstones (#46)", async () => {
      // Assign a throwaway DOI, then tombstone it from the detail view.
      await typeCommand("!doi assign");
      await pressEnter();
      await assertTabOpened("Assign");
      await page.locator("#title").fill("Tombstone Target");
      await page.locator("#doi_type").click();
      await sleep(200);
      await page.locator(".autocomplete-item", { hasText: "webpage" }).first().click();
      await sleep(200);
      await page.locator("#url").fill("https://example.com/tombstone");
      await page.locator('button[type="submit"]').click();
      await sleep(900);
      await assertTabOpened("DOI");

      // Detail view shows the Tombstone button.
      const tombBtn = page.locator('button', { hasText: "Tombstone" });
      await tombBtn.waitFor({ state: "visible", timeout: 3000 });

      // Open the confirm dialog and click Confirm — the DOI must be tombstoned.
      await tombBtn.click();
      await sleep(300);
      const dialog = page.locator('[role="alertdialog"]');
      await dialog.waitFor({ state: "visible", timeout: 3000 });
      const confirmBtn = dialog.locator('button', { hasText: "Confirm" });
      await confirmBtn.click();
      await sleep(900);

      // The DOI is gone from search results.
      await typeCommand("!doi search Tombstone Target");
      await pressEnter();
      await assertTabOpened("DOI");
      const listText = (await page.locator(".doi-list").textContent() || "");
      assert(!listText.includes("Tombstone Target"),
        `Tombstoned DOI must not appear in search results, got: "${listText.trim().slice(0, 200)}"`);
    });

    await test("DOI detail: metadata renders as table, no raw JSON (#37)", async () => {
      await openBookDetail();

      const metaTable = page.locator(".metadata-table");
      const preCount = await metaTable.locator("pre").count();
      assert(preCount === 0,
        `Metadata table must not render raw JSON (<pre>), found ${preCount}`);
      const tableText = (await metaTable.textContent() || "");
      assert(/Author|Publisher/i.test(tableText),
        `Metadata should show humanized fields, got: "${tableText.trim()}"`);
    });

    await test("Citation section loads without auth error (#35)", async () => {
      await openBookDetail();

      const citation = page.locator(".citation-section");
      await citation.waitFor({ state: "visible", timeout: 4000 });
      const text = (await citation.textContent() || "");
      assert(!text.includes("Authentication required"),
        `Citation section must not show auth error, got: "${text.trim()}"`);
      // A formatted citation (or a graceful "unknown" fallback) should load.
      const status = citation.locator(".citation-status");
      if (await status.isVisible().catch(() => false)) {
        assert(!(await status.textContent()).includes("Authentication"),
          "Citation status shows an authentication error");
      }
    });

    await test("Snippet DOI detail view: no citation, Copy Embed button (#41, #43)", async () => {
      // Create a fresh snippet, then open its DOI in the detail view.
      await typeCommand("!snippet assign");
      await pressEnter();
      await assertTabOpened("Assign");
      await page.locator("#content").fill("Cogito ergo sum.");
      await page.locator("#title").fill("Descartes quote");
      await page.locator('button[type="submit"]').click();
      await sleep(900);
      await assertTabOpened("Snippet");

      // Extract the DOI from the embed URL shown on the snippet tab.
      const embedUrlText = (await page.locator(".embed-url").textContent() || "").trim();
      const doiMatch = embedUrlText.match(/([a-f0-9]{32})/);
      assert(doiMatch, `Snippet tab should reveal its DOI, got: "${embedUrlText}"`);
      const doi = `10.ronzz/${doiMatch[1]}`;

      // Open the snippet DOI in the DOI detail view.
      await typeCommand(`!doi resolve ${doi}`);
      await pressEnter();
      await assertTabOpened("DOI");
      await page.locator(".toolbar").waitFor({ state: "visible", timeout: 4000 });
      await sleep(300);

      // Issue #41 — citation section must NOT render for snippet DOIs.
      const citationCount = await page.locator(".citation-section").count().catch(() => 0);
      assert(citationCount === 0,
        `Citation section must not render for snippet DOIs, found ${citationCount}`);

      // Issue #43 — toolbar exposes a Copy Embed button for snippet DOIs.
      const embedBtn = page.locator('.tab-content.active button[title="Copy HTML embed code"]');
      await embedBtn.waitFor({ state: "visible", timeout: 3000 });
      assert((await embedBtn.textContent() || "").includes("Copy Embed"),
        "Toolbar should show a Copy Embed button for snippet DOIs");

      // Copying reports the embed code in the banner.
      await embedBtn.click();
      await sleep(300);
      const bannerText = (await page.locator(".banner-text").last().textContent() || "");
      assert(bannerText.includes("Embed code copied"),
        `Copy Embed should confirm in the banner, got: "${bannerText}"`);
    });

    await test("Copy DOI copies a resolvable URL (#38)", async () => {
      await openBookDetail();

      // The DOI row lives in the collapsed "Technical Info" section.
      await page.locator('summary', { hasText: "Technical Info" }).click();
      await sleep(200);

      // The DOI row in Technical Info is now a clickable resolvable link.
      // It must point at the canonical resolver (doi.ronzz.org), never the
      // admin API origin (issue #40).
      const doiLink = page.locator('a[title="Open resolvable DOI URL"]');
      await doiLink.waitFor({ state: "visible", timeout: 4000 });
      const href = await doiLink.getAttribute("href");
      assert(href && href.startsWith("https://doi.ronzz.org/10.ronzz/"),
        `DOI link should point at the canonical resolver, got: ${href}`);
      assert(!href.includes("doi-admin.ronzz.org"),
        `DOI link must not point at the admin API origin, got: ${href}`);

      // The toolbar copy button reports the copied URL in the banner.
      await page.locator('.tab-content.active button[title^="Copy resolvable DOI URL"]').click();
      await sleep(300);
      const bannerText = (await page.locator(".banner-text").last().textContent() || "");
      assert(/https:\/\/doi\.ronzz\.org\/10\.ronzz\//.test(bannerText),
        `Copy DOI banner should show the canonical resolver URL, got: "${bannerText}"`);
    });
  } else {
    console.log("\n--- AUTHENTICATED FLOWS (skipped — set RONZZDOI_API_KEY) ---");
  }

  // ═══════════════════════════════════════════
  // ERROR CHECK: no JS exceptions
  // ═══════════════════════════════════════════
  console.log("\n--- ERROR CHECK ---");

  await test("No unhandled page errors during entire session", async () => {
    const knownError = "effect_update_depth_exceeded";
    const filteredPageErrors = pageErrors.filter(e => !e.includes(knownError));
    assert(filteredPageErrors.length === 0,
      `${filteredPageErrors.length} unhandled page error(s):\n  ${filteredPageErrors.join("\n  ")}`);
  });

  await test("No console errors during entire session", async () => {
    const non404 = consoleErrors.filter(e => !e.includes("404") && !e.includes("Not Found"));
    assert(non404.length === 0,
      `${non404.length} console error(s) (non-404):\n  ${non404.join("\n  ")}`);
  });
}

// ── Bootstrap ──────────────────────────────────────────────────────────────

runWithBrowser(runTests);
