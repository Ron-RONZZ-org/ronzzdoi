<script>
  /**
   * HelpPopup — renders a list of available commands with descriptions.
   *
   * Used by the !help command result tab. Data is an array of
   * {name: string, description: string} objects.
   */
  let { data = [] } = $props();
</script>

<div class="help">
  {#if data.length > 0}
    {#each data as item}
      <div class="row">
        <span class="cmd">!{item.name}</span>
        <span class="desc">{item.description}</span>
      </div>
    {/each}
  {:else}
    <p class="empty">No commands registered.</p>
  {/if}
</div>

<style>
  .help {
    font-family: monospace;
    font-size: 0.85rem;
    padding: 1rem;
  }
  .row {
    display: flex;
    gap: 1rem;
    padding: 0.3rem 0;
    border-bottom: 1px solid #2a2a3e;
  }
  .row:last-child {
    border-bottom: none;
  }
  .cmd {
    color: #e0e0e0;
    min-width: 16rem;
    white-space: pre;
  }
  .desc {
    color: var(--clr-sub, #9292aa);
  }
  .empty {
    color: #666;
    text-align: center;
    padding: 2rem;
  }
</style>
