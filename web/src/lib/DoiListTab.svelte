<script>
  /** DOI list tab — single-line rows with selection, delete, inline search.
   *
   * Props:
   *   data — response data from !doi search { results: [...], total, query }
   *   tabId — tab identifier
   */

  import { tabStore } from "@lightercore/ui/tabStore.svelte.js";
  import { banner } from "@lightercore/ui/bannerStore.svelte.js";
  import {
    createSelectionManager,
    createCopyState,
  } from "@lightercore/ui/listTabSelection.svelte.js";
  import ConfirmDialog from "@lightercore/ui/ConfirmDialog.svelte";
  import { deriveIdKey } from "./commandExecutor.js";

  let { data = {}, tabId } = $props();
  let d = $derived(data || {});

  // Items — local writable copy so deleted items can be removed
  let items = $state(
    d.results || d.items || d.data || d.keys || d.entries || [],
  );

  // Re-initialize from data prop when it changes (new search results)
  $effect(() => {
    const fresh =
      d.results || d.items || d.data || d.keys || d.entries || [];
    if (fresh.length > 0) {
      items = fresh;
    }
  });

  // ── View-mode focus ────────────────────────────────────────────
  let focusedIndex = $state(items.length > 0 ? 0 : -1);
  let focusedDoi = $derived(
    focusedIndex >= 0 && focusedIndex < items.length
      ? items[focusedIndex].doi || items[focusedIndex].id
      : null,
  );

  // Auto-focus first item when list loads
  $effect(() => {
    if (items.length > 0 && focusedIndex === -1) {
      focusedIndex = 0;
    } else if (items.length === 0) {
      focusedIndex = -1;
    }
  });

  // ── Client-side search filter ──────────────────────────────────
  let showSearch = $state(false);
  let searchQuery = $state("");

  let filteredItems = $derived(
    !searchQuery
      ? items
      : items.filter((item) => {
          const title = (item.title || "").toLowerCase();
          const doi = (item.doi || "").toLowerCase();
          const q = searchQuery.toLowerCase();
          return title.includes(q) || doi.includes(q);
        }),
  );

  // Adjust focused index after filtering
  $effect(() => {
    if (focusedIndex >= filteredItems.length) {
      focusedIndex = Math.max(0, filteredItems.length - 1);
    }
  });

  // ── Selection manager (for selection mode) ─────────────────────
  let sel = createSelectionManager(
    () => filteredItems,
    (doi) => openDetail(doi),
    async (dois) => {
      await batchTombstone([...dois]);
    },
    () => {},
    { getKey: (item) => item.doi || item.id },
  );

  let uuidCopy = createCopyState();

  // ── Open detail tab ────────────────────────────────────────────
  async function openDetail(doi) {
    if (!doi) return;
    const apiKey = localStorage.getItem("ronzzdoi_api_key") || "";
    try {
      const resp = await fetch("/api/v1/command", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
        },
        body: JSON.stringify({
          tokens: ["doi", "resolve", doi],
          flags: {},
          raw_input: `!doi resolve ${doi}`,
        }),
      });
      const result = await resp.json();
      if (result.type === "error") {
        // Fallback: show what we have
        const item = items.find((it) => (it.doi || it.id) === doi);
        if (item) {
          tabStore.open("detail", "DOI: " + doi, item, {
            idKey: `detail-${doi}`,
          });
        }
        return;
      }
      const idKey = deriveIdKey("detail", result.data, ["doi", "resolve"], {});
      tabStore.open("detail", result.title || "DOI: " + doi, result.data, {
        idKey: idKey || `detail-${doi}`,
      });
    } catch {
      const item = items.find((it) => (it.doi || it.id) === doi);
      if (item) {
        tabStore.open("detail", "DOI: " + doi, item, {
          idKey: `detail-${doi}`,
        });
      }
    }
  }

  // ── Tombstone (delete) ─────────────────────────────────────────
  let confirmDelete = $state(false);
  let deleteTarget = $state(null); // null = batch, string = single DOI

  function requestDeleteSingle() {
    if (!focusedDoi) return;
    deleteTarget = focusedDoi;
    confirmDelete = true;
  }

  function requestDeleteBatch() {
    deleteTarget = null;
    confirmDelete = true;
  }

  async function executeTombstone(doi) {
    const apiKey = localStorage.getItem("ronzzdoi_api_key") || "";
    const resp = await fetch("/api/v1/command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
      },
      body: JSON.stringify({
        tokens: ["doi", "delete", doi],
        flags: {},
        raw_input: `!doi delete ${doi}`,
      }),
    });
    const result = await resp.json();
    if (result.type === "error") {
      throw new Error(result.data?.message || "Delete failed");
    }
  }

  async function handleConfirmDelete() {
    confirmDelete = false;
    try {
      if (deleteTarget) {
        // Single delete (normal mode)
        await executeTombstone(deleteTarget);
        banner.show("DOI tombstoned: " + deleteTarget, "success");
        // Remove from local list
        items = items.filter((it) => (it.doi || it.id) !== deleteTarget);
        if (items.length === 0 && tabId) {
          tabStore.close(tabId);
        }
      } else {
        // Batch delete (selection mode)
        const keys = [...sel.selectedKeys];
        const failed = [];
        for (const doi of keys) {
          try {
            await executeTombstone(doi);
          } catch (err) {
            failed.push(doi);
            banner.show(`Delete ${doi} failed: ${err.message}`, "error");
          }
        }
        const succeeded = keys.filter((k) => !failed.includes(k));
        items = items.filter((it) => !succeeded.includes(it.doi || it.id));
        if (succeeded.length > 0) {
          banner.show(
            `Deleted ${succeeded.length} DOI${succeeded.length !== 1 ? "s" : ""}`,
            "success",
          );
        }
        sel.toggleSelectionMode();
      }
    } catch (err) {
      banner.show(`Delete failed: ${err.message}`, "error");
    }
    deleteTarget = null;
  }

  function handleCancelDelete() {
    confirmDelete = false;
    deleteTarget = null;
  }

  // ── New DOI ────────────────────────────────────────────────────
  function handleNew() {
    tabStore.open("form", "Assign DOI", {
      form: "doi-assign",
      initialData: {},
    }, { idKey: "form-doi-assign" });
  }

  // ── Key handlers ───────────────────────────────────────────────
  function handleWindowKeydown(e) {
    const tag = e.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || e.target.isContentEditable) {
      // Allow Escape to close search even when input is focused
      if (e.key === "Escape" && showSearch) {
        closeSearch();
        e.preventDefault();
        e.stopPropagation();
      }
      return;
    }

    if (confirmDelete) {
      if (e.key === "Escape") {
        handleCancelDelete();
        e.preventDefault();
      }
      // Let ConfirmDialog handle Enter
      return;
    }

    const plain = !e.ctrlKey && !e.metaKey && !e.altKey;

    switch (e.key) {
      case "n":
        if (plain) {
          handleNew();
          e.preventDefault();
        }
        return;
      case "/":
        if (plain && !sel.selectionMode) {
          showSearch = !showSearch;
          if (showSearch) {
            requestAnimationFrame(() =>
              document.querySelector(".dl-search-input")?.focus(),
            );
          } else {
            closeSearch();
          }
          e.preventDefault();
        }
        return;
      case "v":
        if (plain && !sel.selectionMode) {
          sel.toggleSelectionMode();
          e.preventDefault();
        }
        return;
      case "Escape":
        if (showSearch) {
          closeSearch();
          e.preventDefault();
          return;
        }
        if (sel.selectionMode) {
          sel.toggleSelectionMode();
          e.preventDefault();
          return;
        }
        // Let TabView handle tab close
        return;
      case "ArrowDown":
        if (plain && !sel.selectionMode && filteredItems.length > 0) {
          e.preventDefault();
          focusedIndex = Math.min(focusedIndex + 1, filteredItems.length - 1);
          scrollToRow(focusedDoi);
        }
        return;
      case "ArrowUp":
        if (plain && !sel.selectionMode && focusedIndex > 0) {
          e.preventDefault();
          focusedIndex = Math.max(focusedIndex - 1, 0);
          scrollToRow(focusedDoi);
        }
        return;
      case "Enter":
        if (plain && !sel.selectionMode && focusedDoi) {
          e.preventDefault();
          openDetail(focusedDoi);
        }
        return;
      case "Delete":
        if (plain && sel.selectionMode && sel.numSelected > 0) {
          requestDeleteBatch();
          e.preventDefault();
        } else if (plain && !sel.selectionMode && focusedDoi) {
          requestDeleteSingle();
          e.preventDefault();
        }
        return;
    }

    sel.handleKeydown(e);
  }

  function scrollToRow(doi) {
    if (!doi) return;
    const el = document.getElementById(`drow-${CSS.escape(doi)}`);
    if (el) el.scrollIntoView({ block: "nearest" });
  }

  function closeSearch() {
    showSearch = false;
    searchQuery = "";
  }

  function handleRowClick(e, item) {
    const doi = item.doi || item.id;
    if (!doi) return;

    if (sel.selectionMode) {
      sel.handleRowClick(e, doi);
      return;
    }

    // View mode: focus the row
    const idx = filteredItems.findIndex((it) => (it.doi || it.id) === doi);
    if (idx >= 0) focusedIndex = idx;

    // Open detail on click
    openDetail(doi);
  }

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

  function typeBadge(doiType) {
    return TYPE_BADGES[doiType] || doiType || "external";
  }
</script>

<svelte:window onkeydown={handleWindowKeydown} />

<div class="doi-list">
  {#if showSearch}
    <div class="search-bar">
      <input
        class="dl-search-input"
        type="text"
        placeholder="Filter by title or DOI…"
        bind:value={searchQuery}
        onkeydown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            closeSearch();
          }
        }}
      />
      <button class="btn-small" onclick={closeSearch}>✕</button>
    </div>
  {/if}

  <div class="toolbar">
    {#if sel.selectionMode}
      <span class="sel-info"
        >{sel.numSelected} selected</span
      >
      <button class="btn-small" onclick={() => sel.toggleSelectionMode()}
        >Cancel</button
      >
      <button
        class="btn-small danger"
        onclick={requestDeleteBatch}
        disabled={sel.numSelected === 0}
        >Delete</button
      >
    {:else}
      <button class="btn-small" onclick={handleNew}>+ New</button>
      <button
        class="btn-small"
        onclick={() => {
          showSearch = true;
          requestAnimationFrame(() =>
            document.querySelector(".dl-search-input")?.focus(),
          );
        }}
        >/ Search</button
      >
      <button class="btn-small" onclick={() => sel.toggleSelectionMode()}
        >v Select</button
      >
    {/if}
  </div>

  <div
    class="list"
    role="listbox"
    aria-label="DOIs"
    aria-multiselectable={sel.selectionMode}
  >
    {#each filteredItems as item, i (item.doi || item.id)}
      {@const doi = item.doi || item.id}
      {@const selected = sel.isSelected(doi)}
      <div
        id="drow-{CSS.escape(doi)}"
        class="row"
        class:selected={selected}
        class:focused={!sel.selectionMode && i === focusedIndex}
        role="option"
        aria-selected={selected ? "true" : "false"}
        tabindex="-1"
        onclick={() => handleRowClick($event, item)}
        onkeydown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            handleRowClick(e, item);
          }
        }}
      >
        {#if sel.selectionMode}
          <span class="check-col"
            >{selected ? "☑" : "☐"}</span
          >
        {/if}
        <span class="title-col"
          >{item.title || "(untitled)"}</span
        >
        <span class="badge-col">
          <span class="doi-type-badge">{typeBadge(item.doi_type)}</span>
        </span>
        <span class="actions-col">
          <button
            class="btn-icon"
            title="Copy DOI"
            onclick={(e) => {
              e.stopPropagation();
              uuidCopy.copyToClipboard(doi);
            }}
          >
            {#if uuidCopy.copiedKey === doi}
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            {:else}
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><rect x="10" y="10" width="11" height="11" rx="1.5" opacity="0.5"/><rect x="5" y="4" width="11" height="11" rx="1.5"/></svg>
            {/if}
          </button>
          {#if item.target_url}
            <button
              class="btn-icon"
              title="Copy target URL"
              onclick={(e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(item.target_url).catch(() => {});
              }}
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
            </button>
          {/if}
        </span>
      </div>
    {:else}
      <p class="empty">No DOIs found.</p>
    {/each}
  </div>

  {#if d.total !== undefined}
    <div class="pagination-info">
      Showing {filteredItems.length} of {d.total} result
      {d.total !== 1 ? "s" : ""}
    </div>
  {/if}
</div>

{#if confirmDelete}
  <ConfirmDialog
    message={deleteTarget
      ? `Tombstone DOI "${deleteTarget}"? This action cannot be undone.`
      : `Delete ${sel.numSelected} DOI${sel.numSelected !== 1 ? "s" : ""}?`}
    onConfirm={handleConfirmDelete}
    onDismiss={handleCancelDelete}
  />
{/if}

<style>
  .doi-list {
    display: flex;
    flex-direction: column;
    height: 100%;
    font-family: monospace;
    font-size: 0.85rem;
    position: relative;
  }

  .search-bar {
    display: flex;
    gap: 4px;
    padding: 0.5rem;
    border-bottom: 1px solid #333;
    flex-shrink: 0;
  }
  .search-bar input {
    flex: 1;
    padding: 0.3rem 0.5rem;
    background: #2a2a3e;
    border: 1px solid #444;
    border-radius: 4px;
    color: #e0e0e0;
    font-family: monospace;
    font-size: 0.82rem;
    outline: none;
  }
  .search-bar input:focus {
    border-color: #7c7c9a;
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0.4rem 0.75rem;
    border-bottom: 1px solid #2a2a3e;
    background: #1a1a2e;
    flex-shrink: 0;
  }
  .sel-info {
    color: #7c7c9a;
    font-size: 0.8rem;
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
  .btn-small:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .list {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.75rem;
    border-bottom: 1px solid #2a2a3e;
    cursor: pointer;
    min-height: 2rem;
  }
  .row:hover {
    background: #22223a;
  }
  .row.selected {
    background: #2a2a4a;
  }
  .row.focused {
    outline: 1px solid #7c7c9a;
    outline-offset: -1px;
    background: #1e1e3a;
  }

  .check-col {
    flex-shrink: 0;
    width: 1.2rem;
    color: #7c7c9a;
  }

  .title-col {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #e0e0e0;
    font-weight: 500;
  }

  .badge-col {
    flex-shrink: 0;
  }
  .doi-type-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.72rem;
    background: #2a2a3e;
    color: #9292aa;
    white-space: nowrap;
  }

  .actions-col {
    display: flex;
    gap: 2px;
    flex-shrink: 0;
  }
  .btn-icon {
    background: none;
    border: none;
    color: #7c7c9a;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 3px;
    font-size: 0.85rem;
    line-height: 1;
  }
  .btn-icon:hover {
    color: #e0e0e0;
    background: #2a2a3e;
  }

  .empty {
    color: #7c7c9a;
    text-align: center;
    padding: 2rem;
  }
  .pagination-info {
    text-align: center;
    padding: 0.4rem;
    color: #7c7c9a;
    font-family: monospace;
    font-size: 0.75rem;
    border-top: 1px solid #2a2a3e;
    flex-shrink: 0;
  }
</style>
