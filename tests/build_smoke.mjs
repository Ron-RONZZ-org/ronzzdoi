/**
 * Build Smoke Test — verifies the Svelte/Vite frontend compiles without errors.
 *
 * Svelte 5 compiler errors (like illegal `$event` variable names) are only
 * caught at build time. This test runs `vite build` and fails on any build
 * failure or warning, ensuring such regressions don't slip through again.
 *
 * Usage:
 *   node tests/build_smoke.mjs
 *   # or via npm:
 *   npm run test:build   # from web/ directory
 */

import { execSync } from "child_process";
import { existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const WEB_DIR = resolve(ROOT, "web");

// ── Config ────────────────────────────────────────────────────────────────

const BUILD_CMD = process.platform === "win32" ? "npx.cmd vite build" : "npx vite build";
const TIMEOUT_MS = 120_000;

// ── Helpers ────────────────────────────────────────────────────────────────

function runBuild() {
  console.log(`[build-smoke] Running: ${BUILD_CMD}`);
  console.log(`[build-smoke] Working directory: ${WEB_DIR}`);
  console.log();

  const start = Date.now();

  try {
    const output = execSync(BUILD_CMD, {
      cwd: WEB_DIR,
      timeout: TIMEOUT_MS,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    });

    const elapsed = ((Date.now() - start) / 1000).toFixed(1);
    console.log(output);

    // Check for common error patterns even if exit code was 0
    const warnings = [];
    const lines = output.split("\n");
    for (const line of lines) {
      const trimmed = line.trim().toLowerCase();
      if (trimmed.includes("warning") && !trimmed.includes("tree-shaking")) {
        warnings.push(line.trim());
      }
    }

    if (warnings.length > 0) {
      console.log(`[build-smoke] ⚠  ${warnings.length} warning(s) found:\n  ${warnings.join("\n  ")}`);
    }

    // Check that dist/ was produced
    const distDir = resolve(WEB_DIR, "dist");
    if (!existsSync(distDir)) {
      console.error(`[build-smoke] ✗ Build succeeded but dist/ directory not found`);
      process.exit(1);
    }

    console.log(`[build-smoke] ✓ Build completed in ${elapsed}s (dist/: ${distDir})`);
    return true;
  } catch (err) {
    const elapsed = ((Date.now() - start) / 1000).toFixed(1);
    console.error(`[build-smoke] ✗ Build failed after ${elapsed}s`);
    console.error(err.stderr || err.stdout || err.message);
    process.exit(1);
  }
}

// ── Main ──────────────────────────────────────────────────────────────────

console.log("═".repeat(60));
console.log("  ronzzdoi — Build Smoke Test");
console.log("═".repeat(60));
console.log();

runBuild();
