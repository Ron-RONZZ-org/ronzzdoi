<script>
  /** Detail tab — renders a DOI/citation detail view.
   *
   * Props:
   *   data — response data from the backend
   *   tabId — tab identifier for tabStore operations
   */

  import { tabStore } from "@lightercore/ui/tabStore.svelte.js";
  import { banner } from "@lightercore/ui/bannerStore.svelte.js";

  let { data = {}, tabId } = $props();
  let d = $derived(data || {});

  // ── Language picker for multi-lingual titles ──────────────────────────
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

  // ── Actions ───────────────────────────────────────────────────────────

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
        initialData: { doi: d.doi, url: d.target_url || "", title: typeof d.title === "string" ? d.title : JSON.stringify(d.title || {}), doi_type: d.doi_type || "", metadata: d.metadata_json ? JSON.stringify(d.metadata_json, null, 2) : "{}" },
      }, { idKey: `form-doi-modify-${d.doi}` });
    }
  }

  function confirmDelete() {
    if (d.doi && confirm(`Are you sure you want to tombstone "${d.doi}"?`)) {
      // Dispatch delete command
      const apiKey = localStorage.getItem("ronzzdoi_api_key") || "";
      fetch("/api/v1/command", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
        },
        body: JSON.stringify({ tokens: ["doi", "delete", d.doi], flags: {}, raw_input: `!doi delete ${d.doi}` }),
      })
        .then((resp) => resp.json())
        .then((result) => {
          if (result.type === "error") {
            banner.show(result.data?.message || "Delete failed", "error", 5000);
          } else {
            banner.show("DOI tombstoned: " + d.doi, "success");
            if (tabId) tabStore.close(tabId);
          }
        })
        .catch((err) => {
          banner.show("Error: " + err.message, "error", 5000);
        });
    }
  }

  function confirmMerge() {
    // For merge, additional input is needed — open form
    if (!d.doi) return;
    const target = prompt("Merge this DOI into target DOI (enter target):");
    if (target && target.trim()) {
      const apiKey = localStorage.getItem("ronzzdoi_api_key") || "";
      fetch("/api/v1/command", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
        },
        body: JSON.stringify({ tokens: ["doi", "merge", d.doi, target.trim()], flags: {}, raw_input: `!doi merge ${d.doi} ${target.trim()}` }),
      })
        .then((resp) => resp.json())
        .then((result) => {
          if (result.type === "error") {
            banner.show(result.data?.message || "Merge failed", "error", 5000);
          } else {
            banner.show("DOI merged", "success");
            if (tabId) tabStore.close(tabId);
          }
        })
        .catch((err) => {
          banner.show("Error: " + err.message, "error", 5000);
        });
    }
  }

  // ── Metadata renderer ─────────────────────────────────────────────────
  let metadataEntries = $derived.by(() => {
    const meta = d.metadata_json || {};
    if (typeof meta === "string") {
      try { return Object.entries(JSON.parse(meta)); } catch { return []; }
    }
    return Object.entries(meta || {});
  });

  let redirectHistory = $derived(d.redirect_history || []);

  // Filter out non-display fields
  let infoEntries = $derived(
    Object.entries(d).filter(([key]) =>
      !["title", "metadata_json", "redirect_history", "data", "message"].includes(key)
      && typeof d[key] !== "object",
    ),
  );
</script>

<div class="detail">
  <!-- Title with language picker -->
  {#if titleLanguages.length > 0}
    <div class="title-section">
      <h2 class="detail-title">{displayTitle}</h2>
      <div class="language-picker">
        <span class="lang-label">Language:</span>
        <select bind:value={selectedLanguage} class="lang-select">
          {#each titleLanguages as lang}
            <option value={lang}>{lang}</option>
          {/each}
        </select>
      </div>
    </div>
  {:else if d.title}
    <h2 class="detail-title">{d.title}</h2>
  {/if}

  <!-- Key-value info table -->
  <table class="detail-table">
    <tbody>
    {#each infoEntries as [key, value]}
      <tr>
        <td class="dt-key">{key.replace(/_/g, " ")}</td>
        <td class="dt-value">
          {#if typeof value === "string" && (value.startsWith("http://") || value.startsWith("https://"))}
            <a href={value} target="_blank" rel="noopener noreferrer" class="url-link">{value}</a>
          {:else if value === null}
            <span class="null-value">—</span>
          {:else}
            {String(value)}
          {/if}
        </td>
      </tr>
    {/each}
    </tbody>
  </table>

  <!-- Metadata section -->
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

  <!-- Redirect history -->
  {#if redirectHistory.length > 0}
    <details class="section">
      <summary class="section-title">Redirect History ({redirectHistory.length})</summary>
      <table class="detail-table">
        <thead>
          <tr><th class="dt-key">Previous URL</th><th class="dt-key">Redirected At</th></tr>
        </thead>
        <tbody>
        {#each redirectHistory as entry}
          <tr>
            <td class="dt-value"><a href={entry.previous_url || entry.url} target="_blank" class="url-link">{entry.previous_url || entry.url}</a></td>
            <td class="dt-value">{entry.redirected_at || entry.timestamp || "—"}</td>
          </tr>
        {/each}
        </tbody>
      </table>
    </details>
  {/if}

  <!-- Action buttons -->
  {#if d.doi}
    <div class="actions">
      <button class="btn btn-primary" onclick={copyDoi}>📋 Copy DOI</button>
      {#if d.target_url}
        <button class="btn btn-primary" onclick={openUrl}>🔗 Open URL</button>
      {/if}
      <button class="btn btn-edit" onclick={openModifyForm}>✏ Modify</button>
      <button class="btn btn-merge" onclick={confirmMerge}>🔀 Merge</button>
      <button class="btn btn-danger" onclick={confirmDelete}>🗑 Tombstone</button>
    </div>
  {/if}
</div>

<style>
  .detail {
    padding: 1rem;
    max-width: 800px;
  }
  .title-section {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }
  .detail-title {
    font-size: 1.1rem;
    color: #e0e0e0;
    font-weight: 600;
    font-family: monospace;
    word-break: break-word;
  }
  .language-picker {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-family: monospace;
    font-size: 0.78rem;
    color: #7c7c9a;
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
  .detail-table {
    width: 100%;
    border-collapse: collapse;
    font-family: monospace;
    font-size: 0.82rem;
    margin-bottom: 0.5rem;
  }
  .detail-table tr {
    border-bottom: 1px solid #2a2a3e;
  }
  .detail-table td, .detail-table th {
    padding: 0.35rem 0.5rem;
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
  .url-link {
    color: #7c9ad4;
    text-decoration: none;
  }
  .url-link:hover { text-decoration: underline; }
  .null-value { color: #666; font-style: italic; }

  .section {
    margin: 0.75rem 0;
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
  }
  .metadata-table { margin-bottom: 0; }
  .json-pre {
    background: #222;
    padding: 0.3rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    color: #c8c8e8;
    overflow-x: auto;
    max-width: 500px;
  }

  .actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid #333;
  }
  .btn {
    padding: 0.4rem 0.7rem;
    border: 1px solid #555;
    border-radius: 4px;
    background: #2a2a3e;
    color: #e0e0e0;
    font-family: monospace;
    font-size: 0.78rem;
    cursor: pointer;
    transition: background 0.1s;
  }
  .btn:hover { background: #3a3a5a; }
  .btn-primary { background: #2a4a5a; border-color: #3a6a7a; }
  .btn-primary:hover { background: #3a5a6a; }
  .btn-edit { background: #2a4a3a; border-color: #3a7a4a; }
  .btn-edit:hover { background: #3a6a4a; }
  .btn-merge { background: #3a2a4a; border-color: #5a3a7a; }
  .btn-merge:hover { background: #4a3a5a; }
  .btn-danger { background: #4a2a2a; border-color: #7a3a3a; }
  .btn-danger:hover { background: #6a3a3a; }
</style>
