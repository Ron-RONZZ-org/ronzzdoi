/** Tests for snippet rich-text rendering (snippetRender.js). */

import { describe, it, expect } from "vitest";
import { renderSnippetHtml, sanitizeSnippetHtml } from "../snippetRender.js";

function snippet(overrides = {}) {
  return { content_kind: "text", content: "hello world", ...overrides };
}

describe("renderSnippetHtml", () => {
  it("renders plain text as a paragraph", () => {
    const html = renderSnippetHtml(snippet());
    expect(html).toContain("<p>hello world</p>");
  });

  it("renders markdown emphasis, links and code spans", () => {
    const html = renderSnippetHtml(
      snippet({ content: "**bold** and `code` — see [the book](https://x)" }),
    );
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<code>code</code>");
    expect(html).toContain('<a href="https://x">the book</a>');
  });

  it("renders headings and lists", () => {
    const html = renderSnippetHtml(snippet({ content: "# Act III\n\n- a\n- b" }));
    expect(html).toContain("<h1>Act III</h1>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<li>a</li>");
  });

  it("passes pasted HTML through and sanitizes it", () => {
    const html = renderSnippetHtml(
      snippet({ content: "<p>A <b>wise</b> quote — <script>alert(1)</script></p>" }),
    );
    expect(html).toContain("<b>wise</b>");
    expect(html).not.toContain("<script");
    expect(html).not.toContain("alert(1)");
  });

  it("strips event handlers and javascript: URLs", () => {
    const html = renderSnippetHtml(
      snippet({
        content: '<a href="javascript:alert(1)" onclick="evil()">click</a>',
      }),
    );
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain("onclick");
  });

  it("drops disallowed elements (img, iframe, table)", () => {
    const html = renderSnippetHtml(
      snippet({ content: 'text <img src="x.png" onerror="alert(1)"> more' }),
    );
    expect(html).not.toContain("<img");
    expect(html).not.toContain("onerror");
  });

  it("returns empty for code and math snippets", () => {
    expect(renderSnippetHtml({ content_kind: "code", content: "print(1)" })).toBe("");
    expect(renderSnippetHtml({ content_kind: "math", content: "x^2" })).toBe("");
  });

  it("returns empty for blank content", () => {
    expect(renderSnippetHtml({ content_kind: "text", content: "   " })).toBe("");
  });
});

describe("sanitizeSnippetHtml", () => {
  it("is idempotent on clean markup", () => {
    expect(sanitizeSnippetHtml("<p>hi <em>there</em></p>")).toBe(
      "<p>hi <em>there</em></p>",
    );
  });

  it("removes script tags entirely", () => {
    expect(sanitizeSnippetHtml("x<script>alert(1)</script>y")).toBe("xy");
  });
});
