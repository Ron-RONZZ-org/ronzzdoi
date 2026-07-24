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
  import ConfirmDialog from "@lightercore/ui/ConfirmDialog.svelte";

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
  let metadataEntries = $derived.by(() => {
    const meta = d.metadata_json || d.metadata || {};
    if (typeof meta === "string") {
      try { return Object.entries(JSON.parse(meta)); } catch { return []; }
    }
    return Object.entries(meta || {});
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

  // ── Actions ───────────────────────────────────────────────────

  function handleNew() {
    tabStore.open("form", "Assign DOI", {
      form: "doi-assign",
      initialData: {},
    }, { idKey: "form-doi-assign" });
  }

  function copyDoi() {
    if (d.doi) {
      navigator.clipboard.writeText(d.doi).catch(() => {});
      banner.show("DOI copied: " + d.doi, "success");
    }
  }

  function openUrl() {
    if (d.target_url) {
      window.open(d.target_url, "_blank", "noopener,noreferrer");
    }
  }

  function openModifyForm() {
    if (d.doi) {
      tabStore.open("form", "Modify DOI: " + d.doi, {
        form: "doi-modify",
        initialData: {
          doi: d.doi,
          url: d.target_url || "",
          title: typeof d.title === "string" ? d.title : JSON.stringify(d.title || {}),
          doi_type: d.doi_type || "",
          metadata: d.metadata_json ? JSON.stringify(d.metadata_json, null, 2) : "{}",
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
      <button class="btn-small" onclick={copyDoi} title="Copy DOI to clipboard">📋 Copy DOI</button>
    {/if}
    {#if d.target_url}
      <button class="btn-small" onclick={openUrl} title="Open target URL in new tab">🔗 Open URL</button>
    {/if}
    {#if d.doi}
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
  {#if metadataEntries.length > 0}
    <details class="section" open>
      <summary class="section-title">Metadata</summary>
      <table class="detail-table metadata-table">
        <tbody>
          {#each metadataEntries as [key, value]}
            <tr>
              <td class="dt-key">{key}</td>
              <td class="dt-value">
                {#if typeof value === "object"}
                  <pre class="json-pre">{JSON.stringify(value, null, 2)}</pre>
                {:else}
                  {String(value)}
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
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
          {#if field.key === "Target URL" || field.key === "URL"}
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
                {field.value === null || field.value === undefined
                  ? <span class="null-value">—</span>
                  : String(field.value)}
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
  .json-pre {
    background: #222;
    padding: 0.3rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    color: #c8c8e8;
    overflow-x: auto;
    max-width: 500px;
    white-space: pre-wrap;
  }
</style>
