<script>
  /** List tab — renders arrays of items as a sortable table.
   *
   * Props:
   *   data — response data with an array of items (e.g. { results: [...] })
   *   tabId — tab identifier
   */

  import { tabStore } from "@lightercore/ui/tabStore.svelte.js";
  import { truncate } from "@lightercore/ui/listTabFormat.js";
  import { createSortState } from "@lightercore/ui/listSort.svelte.js";
  import { execute, deriveIdKey } from "./commandExecutor.js";

  let { data = {}, tabId } = $props();
  let d = $derived(data || {});

  // Detect the array field in the data
  let items = $derived(
    d.results || d.items || d.data || d.keys || d.entries || [],
  );

  // Derive columns from the first item's keys
  let columns = $derived(
    items.length > 0
      ? Object.keys(items[0]).filter((k) => !k.startsWith("_"))
      : [],
  );

  // Sort state — uses lightercore's createSortState, which now supports both
  // mode-cycling (cycle()) and column-header-click (toggleColumn()) patterns.
  let sort = $state(createSortState());
  let sortColumn = $derived(sort.mode.column);
  let sortedItems = $derived(items.toSorted(sort.comparator));

  /** Open detail tab for a specific item (DOI result). */
  function openDetail(item) {
    const doi = item.doi || item.id;
    if (!doi) return;

    // Re-execute resolve to get full detail data
    const apiKey = localStorage.getItem("ronzzdoi_api_key") || "";
    fetch("/api/v1/command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
      },
      body: JSON.stringify({ tokens: ["doi", "resolve", doi], flags: {}, raw_input: `!doi resolve ${doi}` }),
    })
      .then((resp) => resp.json())
      .then((result) => {
        if (result.type === "error") {
          // Fallback: show what we have
          tabStore.open("detail", "DOI: " + doi, item, { idKey: `detail-${doi}` });
        } else {
          const idKey = deriveIdKey("detail", result.data, ["doi", "resolve"], {});
          tabStore.open("detail", result.title || "DOI: " + doi, result.data, { idKey });
        }
      })
      .catch(() => {
        tabStore.open("detail", "DOI: " + doi, item, { idKey: `detail-${doi}` });
      });
  }

  /** Format a cell value for display */
  function formatCell(key, value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "object") return JSON.stringify(value).slice(0, 50);
    if (typeof value === "string" && value.startsWith("http")) {
      return truncate(value, 30);
    }
    return truncate(String(value), 40);
  }
</script>

<div class="list-tab">
  {#if data.message}
    <div class="list-message">{data.message}</div>
  {/if}

  {#if items.length === 0}
    <p class="empty-text">No results found.</p>
  {:else}
    <table class="list-table">
      <thead>
        <tr>
          {#each columns as col}
            <th
              class="list-th"
              class:sorted={sortColumn === col}
              onclick={() => sort.toggleColumn(col)}
              role="columnheader"
              aria-sort={sortColumn === col ? (sort.mode.direction === "asc" ? "ascending" : "descending") : "none"}
            >
              <span class="th-label">{col.replace(/_/g, " ")}</span>
              {#if sortColumn === col}
                <span class="sort-arrow">{sort.mode.direction === "asc" ? " ▲" : " ▼"}</span>
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each sortedItems as item, i}
          <tr
            class="list-row"
            class:even={i % 2 === 0}
            onclick={() => openDetail(item)}
            role="button"
            tabindex="0"
            onkeydown={(e) => { if (e.key === "Enter") openDetail(item); }}
          >
            {#each columns as col}
              <td class="list-td">
                {#if col === "doi" || col === "id"}
                  <span class="doi-cell">{formatCell(col, item[col])}</span>
                {:else if typeof item[col] === "string" && item[col].startsWith("http")}
                  <span class="url-cell">{formatCell(col, item[col])}</span>
                {:else}
                  {formatCell(col, item[col])}
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}

  {#if d.total !== undefined}
    <div class="pagination-info">
      Showing {items.length} of {d.total} result{d.total !== 1 ? "s" : ""}
    </div>
  {/if}
</div>

<style>
  .list-tab {
    padding: 0.5rem;
    overflow-x: auto;
  }
  .list-message {
    padding: 0.5rem;
    font-family: monospace;
    font-size: 0.85rem;
    color: #7c7c9a;
    text-align: center;
  }
  .empty-text {
    color: #666;
    font-family: monospace;
    font-size: 0.85rem;
    text-align: center;
    padding: 2rem;
  }
  .list-table {
    width: 100%;
    border-collapse: collapse;
    font-family: monospace;
    font-size: 0.8rem;
  }
  .list-th {
    text-align: left;
    padding: 0.4rem 0.5rem;
    background: #16162a;
    color: #7c7c9a;
    border-bottom: 1px solid #333;
    cursor: pointer;
    white-space: nowrap;
    user-select: none;
    font-weight: 600;
  }
  .list-th:hover { color: #b0b0c0; }
  .list-th.sorted { color: #c0c0e0; }
  .th-label { text-transform: capitalize; }
  .sort-arrow { font-size: 0.65rem; }
  .list-row {
    border-bottom: 1px solid #2a2a3e;
    cursor: pointer;
    transition: background 0.1s;
  }
  .list-row:hover { background: #22223a; }
  .list-row.even { background: #1c1c30; }
  .list-row.even:hover { background: #22223a; }
  .list-td {
    padding: 0.35rem 0.5rem;
    color: #e0e0e0;
    word-break: break-all;
  }
  .doi-cell {
    color: #7c9ad4;
    font-weight: 600;
  }
  .url-cell {
    color: #7c9ad4;
  }
  .pagination-info {
    text-align: center;
    padding: 0.5rem;
    color: #7c7c9a;
    font-family: monospace;
    font-size: 0.75rem;
  }
</style>
