<script>
  /** Snippet tab — renders snippet content with a Copy Embed action.
   *
   * Data shape (from the `!snippet resolve` / `!snippet assign` handlers):
   *   { doi, title, content_kind, content, language, source_doi,
   *     page_start, page_end, status }
   *
   * The embed base URL can be overridden for development via localStorage
   * key `ronzzdoi_embed_base` (default: https://doi.ronzz.org/embed).
   */

  let { data = {} } = $props();

  const doi = data.doi || "";
  const title = data.title || "";
  const contentKind = data.content_kind || "text";
  const content = data.content || "";
  const language = data.language || "";
  const sourceDoi = data.source_doi || null;
  const pageStart = data.page_start || "";
  const pageEnd = data.page_end || "";
  const status = data.status || "active";

  const embedBase = $derived(
    (typeof localStorage !== "undefined" && localStorage.getItem("ronzzdoi_embed_base")) ||
      "https://doi.ronzz.org/embed",
  );
  const embedUrl = $derived(`${embedBase}/${doi}`);
  const iframeHtml = $derived(
    `<iframe src="${embedUrl}" title="${escapeAttr(title || doi)}" width="640" height="240" loading="lazy" style="border:0;border-radius:8px" referrerpolicy="no-referrer" allowfullscreen></iframe>`,
  );

  let copied = $state(false);

  function escapeAttr(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  async function copyEmbed() {
    try {
      await navigator.clipboard.writeText(iframeHtml);
      copied = true;
      setTimeout(() => { copied = false; }, 1500);
    } catch {
      // Clipboard may be unavailable (e.g. non-secure context) — show the tag instead
      copied = false;
    }
  }
</script>

<div class="snippet-tab">
  <div class="snippet-header">
    <span class="kind-badge" class:kind={contentKind}>{contentKind}</span>
    {#if title}
      <span class="snippet-title">{title}</span>
    {/if}
    {#if status === "tombstone"}
      <span class="tombstone-badge">tombstoned</span>
    {/if}
  </div>

  <div class="snippet-body">
    {#if contentKind === "code"}
      <pre class="code-block"><code>{content}</code></pre>
      {#if language}
        <div class="snippet-meta">Language: {language}</div>
      {/if}
    {:else if contentKind === "math"}
      <pre class="math-block">{content}</pre>
    {:else}
      <blockquote class="quote-block">{content}</blockquote>
      {#if sourceDoi}
        <div class="snippet-meta">
          Source: <a href={`https://doi.ronzz.org/doi/${sourceDoi.replace(/^10\.ronzz\//, "")}`} target="_blank" rel="noopener noreferrer">{sourceDoi}</a>
          {#if pageStart || pageEnd}
            , {pageStart}{pageEnd ? `-${pageEnd}` : ""}
          {/if}
        </div>
      {:else if pageStart || pageEnd}
        <div class="snippet-meta">Pages: {pageStart}{pageEnd ? `-${pageEnd}` : ""}</div>
      {/if}
    {/if}
  </div>

  <div class="snippet-actions">
    <button class="copy-btn" onclick={copyEmbed} disabled={!doi}>
      {copied ? "Copied!" : "Copy Embed"}
    </button>
    <span class="embed-url" title={embedUrl}>{embedUrl}</span>
  </div>
</div>

<style>
  .snippet-tab {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1rem;
    overflow-y: auto;
  }
  .snippet-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .kind-badge {
    font-family: monospace;
    font-size: 0.7rem;
    text-transform: uppercase;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    background: #2a2a44;
    color: #9a9ac0;
    border: 1px solid #4a4a6a;
  }
  .kind-badge.kind-code { background: #1e3a3a; color: #7fd4c1; border-color: #2f5c5c; }
  .kind-badge.kind-math { background: #3a2a4a; color: #c9a0f0; border-color: #5c3f7a; }
  .kind-badge.kind-text { background: #2a3a2a; color: #a8d0a8; border-color: #3f5c3f; }
  .snippet-title {
    font-family: monospace;
    font-size: 0.9rem;
    color: #e0e0e0;
    font-weight: 600;
  }
  .tombstone-badge {
    font-family: monospace;
    font-size: 0.7rem;
    color: #db8f8f;
    border: 1px solid #7a3a3a;
    border-radius: 3px;
    padding: 0.1rem 0.4rem;
  }
  .snippet-body {
    background: #101526;
    border: 1px solid #2a2a44;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    overflow-x: auto;
  }
  .quote-block {
    margin: 0;
    padding-left: 0.75rem;
    border-left: 3px solid #4a6a8a;
    color: #d8d8e8;
    font-size: 0.95rem;
    line-height: 1.6;
    font-style: italic;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .code-block, .math-block {
    margin: 0;
    font-family: monospace;
    font-size: 0.85rem;
    color: #d8d8e8;
    white-space: pre-wrap;
    word-break: break-word;
    tab-size: 4;
  }
  .snippet-meta {
    margin-top: 0.5rem;
    font-family: monospace;
    font-size: 0.78rem;
    color: #7c7c9a;
  }
  .snippet-meta a { color: #7fb0e0; text-decoration: none; }
  .snippet-meta a:hover { text-decoration: underline; }
  .snippet-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .copy-btn {
    padding: 0.4rem 0.9rem;
    background: #2a4a3a;
    border: 1px solid #3a7a4a;
    border-radius: 4px;
    color: #8fdb9f;
    font-family: monospace;
    font-size: 0.82rem;
    cursor: pointer;
    font-weight: 600;
  }
  .copy-btn:hover { background: #3a6a4a; }
  .copy-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .embed-url {
    font-family: monospace;
    font-size: 0.72rem;
    color: #7c7c9a;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
