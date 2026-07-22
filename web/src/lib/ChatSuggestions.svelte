<script>
  /** Autocomplete dropdown for command input. */

  let {
    suggestions = [],
    dataCompletions = [],
    hints = [],
    positionals = [],
    selectedSuggestion = -1,
    selectedDataIndex = -1,
    isCommandMode = false,
    showSuggestions = false,
    onSelect = () => {},
  } = $props();

  let currentDataIdx = $derived(selectedDataIndex);

  // Filter out hints for the selected item when dataCompletions are present
  let showDataCompletions = $derived(dataCompletions.length > 0);
</script>

{#if showSuggestions}
  <div class="suggestions-dropdown" role="listbox" aria-label="Command suggestions">
    {#if positionals.length > 0}
      <div class="positional-tracker">
        {#each positionals as pos}
          <span class="pos-item" class:pos-entered={pos.entered} class:pos-required={pos.required}>
            <span class="pos-name">{pos.name}</span>
            {#if pos.entered}
              <span class="pos-check">✓</span>
            {/if}
            {#if pos.required && !pos.entered}
              <span class="pos-req">*</span>
            {/if}
          </span>
        {/each}
      </div>
    {/if}

    {#if showDataCompletions}
      <div class="data-completions">
        {#each dataCompletions as dc, i}
          <button
            class="suggestion-item"
            class:selected={i === currentDataIdx}
            role="option"
            aria-selected={i === currentDataIdx}
            onclick={() => onSelect(dc.value || dc.uuid?.slice(0, 8) || "")}
          >
            <span class="suggestion-text">{dc.value || dc.uuid?.slice(0, 8) || ""}</span>
            {#if dc.label}
              <span class="suggestion-hint">{dc.label}</span>
            {/if}
          </button>
        {/each}
      </div>
    {:else if suggestions.length > 0}
      <div class="suggestion-list">
        {#each suggestions as sug, i}
          <button
            class="suggestion-item"
            class:selected={i === selectedSuggestion}
            role="option"
            aria-selected={i === selectedSuggestion}
            onclick={() => onSelect(sug)}
          >
            <span class="suggestion-text">{sug}</span>
            {#if hints[i]}
              <span class="suggestion-hint">{hints[i]}</span>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .suggestions-dropdown {
    position: absolute;
    bottom: 100%;
    left: 0;
    right: 0;
    max-height: 240px;
    overflow-y: auto;
    background: #1e1e32;
    border: 1px solid #444;
    border-radius: 8px 8px 0 0;
    box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.3);
    z-index: 100;
  }
  .positional-tracker {
    display: flex;
    gap: 4px;
    padding: 6px 8px;
    border-bottom: 1px solid #333;
    flex-wrap: wrap;
  }
  .pos-item {
    display: flex;
    align-items: center;
    gap: 3px;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.72rem;
    color: #7c7c9a;
    background: #2a2a3e;
  }
  .pos-entered {
    color: #8fdb9f;
    background: #1e3a2e;
  }
  .pos-required {
    border: 1px solid #7a5a3a;
  }
  .pos-name { text-transform: capitalize; }
  .pos-check { color: #4a8a4a; }
  .pos-req { color: #ba6a3a; }
  .suggestion-list,
  .data-completions {
    padding: 4px;
  }
  .suggestion-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    padding: 6px 8px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: #e0e0e0;
    font-family: monospace;
    font-size: 0.82rem;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s;
  }
  .suggestion-item:hover,
  .suggestion-item.selected {
    background: #2a2a44;
  }
  .suggestion-text {
    flex-shrink: 0;
  }
  .suggestion-hint {
    color: #7c7c9a;
    font-size: 0.72rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
