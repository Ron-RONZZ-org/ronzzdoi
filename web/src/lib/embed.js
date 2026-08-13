/**
 * Shared embed-snippet helpers — embed base URL + iframe HTML builder.
 *
 * Snippet DOIs (quote, code, KaTeX math) are embedded in third-party sites
 * via an <iframe> pointing at the public embed page
 * (https://doi.ronzz.org/embed/<doi>). Both the snippet tab and the DOI
 * detail view need this logic, so it lives here.
 *
 * The embed base URL can be overridden for development via the localStorage
 * key `ronzzdoi_embed_base` (default: https://doi.ronzz.org/embed).
 */

const DEFAULT_EMBED_BASE = "https://doi.ronzz.org/embed";
const EMBED_STORAGE_KEY = "ronzzdoi_embed_base";

/** Resolve the embed base URL (localStorage override or production default). */
export function getEmbedBase() {
  if (typeof localStorage !== "undefined") {
    return localStorage.getItem(EMBED_STORAGE_KEY) || DEFAULT_EMBED_BASE;
  }
  return DEFAULT_EMBED_BASE;
}

/** Full embed page URL for a snippet DOI. */
export function embedUrlFor(doi) {
  return `${getEmbedBase()}/${doi}`;
}

/**
 * Build the HTML <iframe> tag used to embed a snippet in third-party sites.
 *
 * @param {string} doi - Full snippet DOI (e.g. "10.ronzz/<uuid-hex>").
 * @param {string} [title] - Optional human-readable title; falls back to
 *                           the DOI when omitted.
 * @returns {string} The complete iframe HTML string.
 */
export function buildEmbedHtml(doi, title = "") {
  return (
    `<iframe src="${embedUrlFor(doi)}" title="${escapeAttr(title || doi)}" ` +
    'width="640" height="240" loading="lazy" style="border:0;border-radius:8px" ' +
    'referrerpolicy="no-referrer" allowfullscreen></iframe>'
  );
}

/** Escape a value for safe inclusion inside an HTML attribute. */
function escapeAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
