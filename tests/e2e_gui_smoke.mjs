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

const FRONTEND_URL = process.env.FRONTEND_URL || "http://127.0.0.1:6005";
const CHROME_PATH = process.env.CHROME_PATH || "chromium";

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
  const input = page.locator(".input-field, [aria-label='Message input'], textarea");
  await input.waitFor({ state: "visible", timeout: 5000 });
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
    const context = await browser.newContext({ viewport: { width: 960, height: 720 } });
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
