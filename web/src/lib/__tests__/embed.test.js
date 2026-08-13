import { describe, it, expect, beforeEach } from "vitest";
import { getEmbedBase, embedUrlFor, buildEmbedHtml } from "../embed.js";

// Keep localStorage clean for every test — the embed base override is set
// by one test and must not leak into the others.
beforeEach(() => {
  localStorage.clear();
});

describe("getEmbedBase", () => {
  it("defaults to the production embed base", () => {
    expect(getEmbedBase()).toBe("https://doi.ronzz.org/embed");
  });

  it("honors the ronzzdoi_embed_base localStorage override", () => {
    localStorage.setItem("ronzzdoi_embed_base", "http://127.0.0.1:6025/embed");
    expect(getEmbedBase()).toBe("http://127.0.0.1:6025/embed");
  });
});

describe("embedUrlFor", () => {
  it("builds a full embed URL for a DOI", () => {
    expect(embedUrlFor("10.ronzz/abc123")).toBe("https://doi.ronzz.org/embed/10.ronzz/abc123");
  });
});

describe("buildEmbedHtml", () => {
  it("builds an iframe pointing at the embed page", () => {
    const html = buildEmbedHtml("10.ronzz/abc123");
    expect(html).toContain('<iframe src="https://doi.ronzz.org/embed/10.ronzz/abc123"');
    expect(html).toContain('width="640"');
    expect(html).toContain('height="240"');
    expect(html).toContain('loading="lazy"');
    expect(html).toContain("allowfullscreen");
    expect(html.startsWith("<iframe ")).toBe(true);
    expect(html.endsWith("</iframe>")).toBe(true);
  });

  it("uses the DOI as iframe title when no title given", () => {
    const html = buildEmbedHtml("10.ronzz/abc123");
    expect(html).toContain('title="10.ronzz/abc123"');
  });

  it("uses the given title in the iframe title attribute", () => {
    const html = buildEmbedHtml("10.ronzz/abc123", "Descartes quote");
    expect(html).toContain('title="Descartes quote"');
  });

  it("escapes the title for safe attribute insertion", () => {
    const html = buildEmbedHtml("10.ronzz/abc123", 'A "quoted" <title> & more');
    expect(html).toContain('title="A &quot;quoted&quot; &lt;title&gt; &amp; more"');
  });
});
