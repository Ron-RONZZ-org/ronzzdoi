/** Snippet rich-text rendering — markdown → sanitized HTML.
 *
 * Text snippets store raw markdown/HTML (what the user pasted; the edit
 * form shows it verbatim).  At display time the content is rendered to
 * HTML via `marked` and sanitized with DOMPurify so the admin GUI can
 * inject it safely with Svelte's `{@html}`.
 *
 * Code and math snippets are NOT rendered here — the admin GUI shows
 * them as plain `<pre>` blocks (the public-web embed highlights code
 * and renders KaTeX server-side).
 */

import { marked } from "marked";
import DOMPurify from "dompurify";

// Allowlist shared with the public-web embed renderer (snippetEmbed.ts):
// text-formatting quotation markup only — no script, iframe, object,
// img, or event-handler attributes.
const ALLOWED_TAGS = [
  "p", "br", "strong", "em", "b", "i", "u", "s", "strike", "del", "ins",
  "a", "ul", "ol", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
  "code", "pre", "span", "hr", "sub", "sup", "q", "mark", "small",
];

const ALLOWED_ATTR = ["href", "title", "rel", "target"];

marked.setOptions({ gfm: true, breaks: false });

/**
 * Render text-snippet content to sanitized HTML.
 *
 * @param {object} data - Snippet record (`content_kind`, `content`).
 * @returns {string} Sanitized HTML for `{@html}`, or `""` for
 *   code/math snippets (rendered elsewhere) and empty content.
 */
export function renderSnippetHtml(data) {
  const kind = data?.content_kind || "text";
  if (kind !== "text") return "";
  const content = data?.content || "";
  if (!content.trim()) return "";
  return sanitizeSnippetHtml(marked.parse(content, { async: false }));
}

/**
 * Sanitize markdown-rendered HTML with the snippet allowlist.
 *
 * @param {string} html - Raw rendered HTML (may contain pasted markup).
 * @returns {string} Sanitized HTML safe for `{@html}` injection.
 */
export function sanitizeSnippetHtml(html) {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
  });
}
