import { describe, it, expect } from "vitest";
import { resolveUrl } from "../api.js";

describe("resolveUrl", () => {
  it("builds a canonical doi.ronzz.org URL by default", () => {
    expect(resolveUrl("10.ronzz/bc16e5775c6148fba9584ee6ed01a7ad")).toBe(
      "https://doi.ronzz.org/10.ronzz/bc16e5775c6148fba9584ee6ed01a7ad",
    );
  });

  it("handles multi-segment suffixes", () => {
    expect(resolveUrl("10.ronzz/country/FR")).toBe(
      "https://doi.ronzz.org/10.ronzz/country/FR",
    );
  });

  it("never derives the base from window.location (issue #40)", () => {
    // Even if the GUI is served from the admin origin, the resolved URL
    // must point at the canonical resolver host.
    const url = resolveUrl("10.ronzz/abc");
    expect(url.startsWith("https://doi.ronzz.org/")).toBe(true);
    expect(url.includes("doi-admin.ronzz.org")).toBe(false);
  });
});
