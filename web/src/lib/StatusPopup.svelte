<script>
  /** Status popup — renders arbitrary data as a simple key-value list. */

  let { data = {} } = $props();
  let d = $derived(data || {});

  // Exclude non-scalar fields from display
  let displayEntries = $derived(
    Object.entries(d).filter(
      ([_, v]) => typeof v === "string" || typeof v === "number" || typeof v === "boolean" || v === null,
    ),
  );

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).catch(() => {});
  }
</script>

<div class="status">
  {#if displayEntries.length > 0}
    <table class="kv-table">
      <tbody>
      {#each displayEntries as [key, value]}
        <tr>
          <td class="kv-key">{key}</td>
          <td class="kv-value">
            {#if typeof value === "string" && (value.startsWith("http://") || value.startsWith("https://"))}
              <a href={value} target="_blank" rel="noopener noreferrer" class="url-link">{value}</a>
            {:else if value === null}
              <span class="null-value">null</span>
            {:else}
              {String(value)}
            {/if}
            {#if typeof value === "string"}
              <button class="copy-btn" onclick={() => copyToClipboard(value)} title="Copy">📋</button>
            {/if}
          </td>
        </tr>
      {/each}
      </tbody>
    </table>
  {:else if d.message}
    <p class="message-text">{d.message}</p>
  {:else}
    <p class="empty-text">No data</p>
  {/if}
</div>

<style>
  .status {
    padding: 1rem;
  }
  .kv-table {
    width: 100%;
    border-collapse: collapse;
    font-family: monospace;
    font-size: 0.85rem;
  }
  .kv-table tr {
    border-bottom: 1px solid #2a2a3e;
  }
  .kv-table td {
    padding: 0.4rem 0.5rem;
    vertical-align: top;
  }
  .kv-key {
    color: #7c7c9a;
    white-space: nowrap;
    padding-right: 1rem;
    width: 1%;
    text-transform: capitalize;
  }
  .kv-value {
    color: #e0e0e0;
    word-break: break-all;
  }
  .url-link {
    color: #7c9ad4;
    text-decoration: none;
  }
  .url-link:hover { text-decoration: underline; }
  .null-value { color: #666; font-style: italic; }
  .copy-btn {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 0.75rem;
    padding: 0 0.2rem;
    opacity: 0.4;
    transition: opacity 0.1s;
    vertical-align: middle;
  }
  .copy-btn:hover { opacity: 1; }
  .message-text {
    color: #c0c0d0;
    font-family: monospace;
    font-size: 0.9rem;
    text-align: center;
    padding: 1rem;
  }
  .empty-text {
    color: #666;
    font-family: monospace;
    font-size: 0.85rem;
    text-align: center;
    padding: 2rem;
  }
</style>
