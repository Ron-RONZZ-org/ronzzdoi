<script>
  /** Detail tab — renders a DOI/citation detail view.
   *
   * Enhanced layout:
   *   - Toolbar with action buttons (+ New, Copy DOI, Open URL, Modify, Merge, Tombstone)
   *   - Title + type badge inline
   *   - Metadata (author, year, publisher…) shown first
   *   - Technical info (DOI, Status, Created, Updated…) collapsible at bottom
   *   - Redirect history as subsection of Technical Info
   *   - ConfirmDialog for tombstone
   *
   * Props:
   *   data — response data from the backend
   *   tabId — tab identifier for tabStore operations
   */

  import { tabStore } from "@lightercore/ui/tabStore.svelte.js";
  import { banner } from "@lightercore/ui/bannerStore.svelte.js";
  import { createCopyState } from "@lightercore/ui/listTabSelection.svelte.js";
  import ConfirmDialog from "@lightercore/ui/ConfirmDialog.svelte";
  import { citationApi } from "./api.js";
  import { flattenValue, formatKey } from "./formatValue.js";
  import { buildEmbedHtml } from "./embed.js";

  /** Auth headers for API calls (mirrors api.js / FormTab). */
  function authHeaders() {
    const apiKey = localStorage.getItem("ronzzdoi_api_key") || "";
    return apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
  }

  let { data = {}, tabId } = $props();
  let d = $derived(data || {});

  // ── DOI type badge ─────────────────────────────────────────────
  const TYPE_BADGES = {
    book: "📖 book",
    film: "🎬 film",
    article: "📄 article",
    website: "🌐 website",
    conference: "🎤 conference",
    transcript: "📝 transcript",
    presentation: "📊 presentation",
    circulaire: "📋 circulaire",
    rulebook: "📜 rulebook",
    document: "📄 document",
    media: "🎥 media",
    external: "🔗 external",
  };

  let typeBadgeText = $derived(TYPE_BADGES[d.doi_type] || d.doi_type || "external");

  // ── Language picker for multi-lingual titles ──────────────────
  let titleData = $derived(d.title || {});
  let titleLanguages = $derived(
    typeof titleData === "object" && !Array.isArray(titleData)
      ? Object.keys(titleData)
      : [],
  );
  let selectedLanguage = $state("en");

  let displayTitle = $derived(
    titleLanguages.includes(selectedLanguage)
      ? titleData[selectedLanguage]
      : titleLanguages.length > 0
        ? titleData[titleLanguages[0]]
        : typeof titleData === "string"
          ? titleData
          : "",
  );

  // ── Metadata entries (from metadata_json) ─────────────────────
  // Flattened to human-friendly leaf rows — no raw JSON in the table.
  let metadataRows = $derived.by(() => {
    let meta = d.metadata_json !== undefined ? d.metadata_json : d.metadata;
    if (typeof meta === "string") {
      try { meta = JSON.parse(meta); } catch { return []; }
    }
    if (!meta || typeof meta !== "object" || Array.isArray(meta)) return [];
    return flattenValue(meta).map((row, i) => ({ ...row, id: i }));
  });

  // ── Technical info fields (shown in collapsible section) ──────
  let techFields = $derived([
    { key: "DOI", value: d.doi },
    { key: "DOI Type", value: d.doi_type },
    { key: "Status", value: d.status || "active" },
    { key: "Created", value: d.created_at },
    { key: "Updated", value: d.updated_at },
    { key: "Owner", value: d.owner },
  ].filter((f) => f.value != null && f.value !== ""));

  // ── Redirect history ──────────────────────────────────────────
  let redirectHistory = $derived(d.redirect_history || []);

  // ── Citation ──────────────────────────────────────────────────
  let availableStyles = $state(["apa"]);
  let citationStyle = $state("apa");
  let citationText = $state("");
  let citationLoading = $state(false);
  let citationError = $state("");

  // Entity types (person, abstract_entity, country) and snippet DOIs
  // (embeddable content) are not citable — the backend refuses citations
  // for them (issue #41).
  const NON_CITABLE_TYPES = new Set(["person", "abstract_entity", "country", "snippet"]);
  let isCitable = $derived(d.doi && !NON_CITABLE_TYPES.has(d.doi_type));

  /** Fetch available styles for this DOI. */
  async function fetchStyles() {
    if (!d.doi) return;
    try {
      const data = await citationApi.styles(d.doi);
      if (data.styles && data.styles.length > 0) {
        availableStyles = data.styles;
        if (!availableStyles.includes(citationStyle)) {
          citationStyle = availableStyles[0];
        }
      }
    } catch {
      // Styles endpoint failed — proceed with defaults
    }
  }

  /** Fetch formatted citation for the current style. */
  async function loadCitation() {
    if (!d.doi || !isCitable) return;
    citationLoading = true;
    citationError = "";
    try {
      const data = await citationApi.show(d.doi, citationStyle);
      citationText = data.citation || "";
    } catch (err) {
      citationError = err.message || "Failed to load citation";
      citationText = "";
    } finally {
      citationLoading = false;
    }
  }

  // Fetch styles and citation when DOI becomes available
  $effect(() => {
    if (d.doi && isCitable) {
      fetchStyles();
      loadCitation();
    } else {
      citationText = "";
      citationError = "";
    }
  });

  // Re-fetch citation when style changes
  $effect(() => {
    if (d.doi && isCitable && citationStyle) {
      loadCitation();
    }
  });

  // ── Snippet embed (issue #43) ──────────────────────────────────────
  let isSnippet = $derived(d.doi_type === "snippet");
  let embedHtml = $derived(isSnippet ? buildEmbedHtml(d.doi || "", displayTitle) : "");

  function copyEmbed() {
    if (!embedHtml) return;
    copyState.copyToClipboard(embedHtml);
    banner.show("Embed code copied", "success");
  }

  // ── Copy state for tech fields ────────────────────────────────
  let copyState = createCopyState();

  // ── Actions ───────────────────────────────────────────────────

  function handleNew() {
    tabStore.open("form", "Assign DOI", {
      form: "doi-assign",
      initialData: {},
    }, { idKey: "form-doi-assign" });
  }

  /** Browser-resolvable URL for this DOI (issue #38). */
  function doiResolveUrl() {
    return d.resolve_url || `${window.location.origin}/${d.doi}`;
  }

  function copyDoi() {
    if (d.doi) {
      const url = doiResolveUrl();
      navigator.clipboard.writeText(url).catch(() => {});
      banner.show("Resolution URL copied: " + url, "success");
    }
  }

  /** Copy the full DOI record as JSON (issue #37). */
  function copyJson() {
    const payload = JSON.stringify({
      doi: d.doi,
      doi_type: d.doi_type,
      title: d.title || "",
      target_url: d.target_url || "",
      metadata: (d.metadata_json !== undefined ? d.metadata_json : d.metadata) || {},
      created_at: d.created_at,
      updated_at: d.updated_at,
      ...(d.deleted_at ? { deleted_at: d.deleted_at } : {}),
    }, null, 2);
    navigator.clipboard.writeText(payload).catch(() => {});
    banner.show("DOI data copied as JSON", "success");
  }

  function openUrl() {
    if (d.target_url) {
      window.open(d.target_url, "_blank", "noopener,noreferrer");
    }
  }

  function openModifyForm() {
    if (d.doi) {
      const metadata = d.metadata_json !== undefined ? d.metadata_json : d.metadata;
      tabStore.open("form", "Modify DOI: " + d.doi, {
        form: "doi-modify",
        initialData: {
          doi: d.doi,
          url: d.target_url || "",
          title: typeof d.title === "string" ? d.title : JSON.stringify(d.title || {}),
          doi_type: d.doi_type || "",
          metadata: metadata || {},
        },
      }, { idKey: `form-doi-modify-${d.doi}` });
    }
  }

  // ── Merge ─────────────────────────────────────────────────────
  let mergeTarget = $state("");

  function confirmMerge() {
    if (!d.doi) return;
    mergeTarget = prompt("Merge this DOI into target DOI (enter target):");
    if (mergeTarget && mergeTarget.trim()) {
      executeMerge(mergeTarget.trim());
    }
    mergeTarget = "";
  }

  async function executeMerge(target) {
    const apiKey = localStorage.getItem("ronzzdoi_api_key") || "";
    try {
      const resp = await fetch("/api/v1/command", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
        },
        body: JSON.stringify({
          tokens: ["doi", "merge", d.doi, target],
          flags: {},
          raw_input: `!doi merge ${d.doi} ${target}`,
        }),
      });
      const result = await resp.json();
      if (result.type === "error") {
        banner.show(result.data?.message || "Merge failed", "error", 5000);
      } else {
        banner.show("DOI merged", "success");
        if (tabId) tabStore.close(tabId);
      }
    } catch (err) {
      banner.show("Error: " + err.message, "error", 5000);
    }
  }

  // ── Tombstone (delete) ────────────────────────────────────────
  let confirmDelete = $state(false);

  function requestTombstone() {
    if (!d.doi) return;
    confirmDelete = true;
  }

  async function executeTombstone() {
    confirmDelete = false;
    if (!d.doi) return;
    const apiKey = localStorage.getItem("ronzzdoi_api_key") || "";
    try {
      const resp = await fetch("/api/v1/command", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
        },
        body: JSON.stringify({
          tokens: ["doi", "delete", d.doi],
          flags: {},
          raw_input: `!doi delete ${d.doi}`,
        }),
      });
      const result = await resp.json();
      if (result.type === "error") {
        banner.show(result.data?.message || "Delete failed", "error", 5000);
      } else {
        banner.show("DOI tombstoned: " + d.doi, "success");
        if (tabId) tabStore.close(tabId);
      }
    } catch (err) {
      banner.show("Error: " + err.message, "error", 5000);
    }
  }

  function cancelTombstone() {
    confirmDelete = false;
  }

  // ── Collapsible sections ──────────────────────────────────────
  let techOpen = $state(false);

  // ── Keyboard shortcuts ────────────────────────────────────────
  function handleWindowKeydown(e) {
    const tag = e.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || e.target.isContentEditable) return;
    if (confirmDelete) {
      if (e.key === "Escape") { cancelTombstone(); e.preventDefault(); }
      return;
    }
    const plain = !e.ctrlKey && !e.metaKey && !e.altKey;
    if (e.key === "n" && plain) { handleNew(); e.preventDefault(); }
  }
</script>

<svelte:window onkeydown={handleWindowKeydown} />

<div class="detail">
  <!-- ════════ Toolbar ════════ -->
  <div class="toolbar">
    <button class="btn-small" onclick={handleNew} title="Assign new DOI (n)">+ New</button>
    {#if d.doi}
      <button class="btn-small" onclick={copyDoi} title="Copy resolvable DOI URL to clipboard">📋 Copy DOI</button>
      <button class="btn-small" onclick={copyJson} title="Copy this DOI record as JSON">📋 JSON</button>
    {/if}
    {#if d.target_url}
      <button class="btn-small" onclick={openUrl} title="Open target URL in new tab">🔗 Open URL</button>
    {/if}
    {#if d.doi}
      {#if isSnippet}
        <button class="btn-small" onclick={copyEmbed} title="Copy HTML embed code">📋 Copy Embed</button>
      {/if}
      <button class="btn-small" onclick={openModifyForm} title="Modify this DOI">✏ Modify</button>
      <button class="btn-small" onclick={confirmMerge} title="Merge this DOI into another">🔀 Merge</button>
      <button class="btn-small danger" onclick={requestTombstone} title="Tombstone this DOI">🗑 Tombstone</button>
    {/if}
  </div>

  <!-- ════════ Title + type badge ════════ -->
  <div class="title-section">
    {#if titleLanguages.length > 0}
      <h2 class="detail-title">{displayTitle}</h2>
    {:else if d.title}
      <h2 class="detail-title">
        {typeof d.title === "string" ? d.title : ""}
      </h2>
    {/if}
    {#if d.doi_type}
      <span class="doi-type-badge">{typeBadgeText}</span>
    {/if}
    {#if titleLanguages.length > 0}
      <div class="language-picker">
        <span class="lang-label">Language:</span>
        <select bind:value={selectedLanguage} class="lang-select">
          {#each titleLanguages as lang}
            <option value={lang}>{lang}</option>
          {/each}
        </select>
      </div>
    {/if}
  </div>

  <!-- ════════ Metadata (human-relevant fields first) ════════ -->
  {#if metadataRows.length > 0}
    <details class="section" open>
      <summary class="section-title">Metadata</summary>
      <table class="detail-table metadata-table">
        <tbody>
          {#each metadataRows as row (row.id)}
            <tr>
              <td
                class="dt-key"
                style="padding-left: {0.25 + row.depth * 1.15}rem"
                title={row.path}
              >{formatKey(row.path)}</td>
              <td class="dt-value">{row.value === "" ? "—" : String(row.value)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </details>
  {/if}

  <!-- ════════ Citation ════════ -->
  {#if isCitable}
    <details class="section citation-section">
      <summary class="section-title">Citation</summary>
      <div class="citation-controls">
        <select bind:value={citationStyle} class="style-select" disabled={citationLoading}>
          {#each availableStyles as style}
            <option value={style}>{style}</option>
          {/each}
        </select>
        {#if citationLoading}
          <span class="citation-status">Loading…</span>
        {:else if citationError}
          <span class="citation-status error">{citationError}</span>
        {:else if citationText}
          <button
            class="btn-icon copy-cite-btn"
            title="Copy citation"
            onclick={() => copyState.copyToClipboard(citationText)}
          >
            {#if copyState.copiedKey === citationText}
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            {:else}
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><rect x="10" y="10" width="11" height="11" rx="1.5" opacity="0.5"/><rect x="5" y="4" width="11" height="11" rx="1.5"/></svg>
            {/if}
          </button>
        {/if}
      </div>
      {#if citationText}
        <pre class="citation-text">{citationText}</pre>
      {/if}
    </details>
  {/if}

  <!-- ════════ Technical Info (collapsible at bottom) ════════ -->
  <details class="section" bind:open={techOpen}>
    <summary class="section-title">
      Technical Info {techFields.length > 0 ? `(${techFields.length})` : ""}
    </summary>
    <table class="detail-table">
      <tbody>
        {#each techFields as field}
          {#if field.key === "DOI"}
            <tr>
              <td class="dt-key">DOI</td>
              <td class="dt-value">
                <a href={doiResolveUrl()} target="_blank" rel="noopener noreferrer" class="url-link" title="Open resolvable DOI URL">{field.value}</a>
              </td>
            </tr>
          {:else if field.key === "Target URL" || field.key === "URL"}
            <tr>
              <td class="dt-key">{field.key}</td>
              <td class="dt-value">
                <a href={field.value} target="_blank" rel="noopener noreferrer" class="url-link">{field.value}</a>
              </td>
            </tr>
          {:else}
            <tr>
              <td class="dt-key">{field.key}</td>
              <td class="dt-value">
                {#if field.value === null || field.value === undefined}
                  <span class="null-value">—</span>
                {:else}
                  <span
                    class="copy-field"
                    title="Click to copy"
                    role="button"
                    tabindex="0"
                    onclick={() => copyState.copyToClipboard(String(field.value))}
                    onkeydown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        copyState.copyToClipboard(String(field.value));
                      }
                    }}
                  >
                    {String(field.value)}
                    {#if copyState.copiedKey === String(field.value)}
                      <svg class="copy-check" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    {/if}
                  </span>
                {/if}
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>

    <!-- ── Redirect History (subsection) ── -->
    {#if redirectHistory.length > 0}
      <details class="subsection">
        <summary class="subsection-title">
          Redirect History ({redirectHistory.length})
        </summary>
        <table class="detail-table">
          <thead>
            <tr>
              <th class="dt-key">Previous URL</th>
              <th class="dt-key">Redirected At</th>
            </tr>
          </thead>
          <tbody>
            {#each redirectHistory as entry}
              <tr>
                <td class="dt-value">
                  <a href={entry.previous_url || entry.url} target="_blank" class="url-link">
                    {entry.previous_url || entry.url}
                  </a>
                </td>
                <td class="dt-value">
                  {entry.redirected_at || entry.timestamp || "—"}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </details>
    {/if}
  </details>
</div>

{#if confirmDelete}
  <ConfirmDialog
    message={`Tombstone "${d.doi}"? This action cannot be undone.`}
    onConfirm={executeTombstone}
    onDismiss={cancelTombstone}
  />
{/if}

<style>
  .detail {
    padding: 0;
    max-width: 800px;
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  /* ── Toolbar ──────────────────────────────── */
  .toolbar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0.4rem 0.75rem;
    border-bottom: 1px solid #2a2a3e;
    background: #1a1a2e;
    flex-shrink: 0;
    flex-wrap: wrap;
  }
  .btn-small {
    padding: 0.2rem 0.5rem;
    background: #2a2a3e;
    border: 1px solid #444;
    border-radius: 3px;
    color: #e0e0e0;
    cursor: pointer;
    font-family: monospace;
    font-size: 0.78rem;
    white-space: nowrap;
  }
  .btn-small:hover {
    background: #3a3a4e;
  }
  .btn-small.danger {
    border-color: #a33;
    color: #f77;
  }
  .btn-small.danger:hover {
    background: #3a1a1a;
  }

  /* ── Title section ────────────────────────── */
  .title-section {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    padding: 0.75rem 0.75rem 0.5rem;
    flex-wrap: wrap;
  }
  .detail-title {
    font-size: 1.1rem;
    color: #e0e0e0;
    font-weight: 600;
    font-family: monospace;
    word-break: break-word;
    margin: 0;
  }
  .doi-type-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.75rem;
    background: #2a2a3e;
    color: #9292aa;
    white-space: nowrap;
    font-family: monospace;
  }
  .language-picker {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-family: monospace;
    font-size: 0.78rem;
    color: #7c7c9a;
    margin-left: auto;
  }
  .lang-select {
    background: #2a2a3e;
    border: 1px solid #555;
    color: #e0e0e0;
    border-radius: 3px;
    padding: 0.15rem 0.3rem;
    font-family: monospace;
    font-size: 0.78rem;
  }

  /* ── Sections ──────────────────────────────── */
  .section {
    margin: 0.25rem 0.75rem;
    border: 1px solid #2a2a3e;
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
  }
  .section-title {
    font-family: monospace;
    font-size: 0.82rem;
    color: #7c7c9a;
    cursor: pointer;
    padding: 0.25rem 0;
    user-select: none;
  }
  .section-title:hover {
    color: #b0b0c0;
  }

  .subsection {
    margin: 0.5rem 0 0.25rem 0;
    border: 1px solid #2a2a3e;
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
  }
  .subsection-title {
    font-family: monospace;
    font-size: 0.8rem;
    color: #7c7c9a;
    cursor: pointer;
    padding: 0.2rem 0;
    user-select: none;
  }
  .subsection-title:hover {
    color: #b0b0c0;
  }

  /* ── Tables ────────────────────────────────── */
  .detail-table {
    width: 100%;
    border-collapse: collapse;
    font-family: monospace;
    font-size: 0.82rem;
  }
  .detail-table tr {
    border-bottom: 1px solid #2a2a3e;
  }
  .detail-table tr:last-child {
    border-bottom: none;
  }
  .detail-table td, .detail-table th {
    padding: 0.3rem 0.5rem;
    vertical-align: top;
  }
  .dt-key {
    color: #7c7c9a;
    white-space: nowrap;
    width: 1%;
    padding-right: 1rem;
    text-transform: capitalize;
  }
  .dt-value {
    color: #e0e0e0;
    word-break: break-all;
  }
  .detail-table th.dt-key {
    text-align: left;
    font-weight: 600;
    border-bottom: 1px solid #444;
  }
  .url-link {
    color: #7c9ad4;
    text-decoration: none;
  }
  .url-link:hover {
    text-decoration: underline;
  }
  .null-value {
    color: #666;
    font-style: italic;
  }

  .metadata-table {
    margin-bottom: 0;
  }

  /* ── Citation section ─────────────────────────── */
  .citation-section {
    margin: 0.25rem 0.75rem;
  }
  .citation-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0;
  }
  .style-select {
    background: #2a2a3e;
    border: 1px solid #555;
    color: #e0e0e0;
    border-radius: 3px;
    padding: 0.15rem 0.3rem;
    font-family: monospace;
    font-size: 0.78rem;
  }
  .style-select:disabled {
    opacity: 0.5;
  }
  .citation-status {
    font-family: monospace;
    font-size: 0.78rem;
    color: #7c7c9a;
  }
  .citation-status.error {
    color: #f77;
  }
  .citation-text {
    background: #222;
    padding: 0.5rem 0.6rem;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.78rem;
    color: #c8c8e8;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.4;
    margin: 0.25rem 0 0.5rem;
  }
  .copy-cite-btn {
    background: none;
    border: none;
    color: #7c7c9a;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 3px;
    font-size: 0.85rem;
    line-height: 1;
    margin-left: auto;
  }
  .copy-cite-btn:hover {
    color: #e0e0e0;
    background: #2a2a3e;
  }

  /* ── Click-to-copy fields ─────────────────────── */
  .copy-field {
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 1px 3px;
    border-radius: 3px;
    transition: background 0.1s;
  }
  .copy-field:hover {
    background: #2a2a3e;
    outline: 1px solid #444;
  }
  .copy-check {
    color: #4a6fa5;
    flex-shrink: 0;
  }
</style>
