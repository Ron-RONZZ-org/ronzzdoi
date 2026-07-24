<script>
  /**
   * KeyboardShortcutOverlay — modal overlay listing global keyboard shortcuts.
   *
   * Toggled by pressing `h` on the home tab (when input is not focused).
   */

  let { onDismiss = () => {} } = $props();

  /** Global shortcuts relevant to ronzzdoi's GUI. */
  let shortcuts = [
    {
      category: "General",
      keys: [
        { key: "h", desc: "Toggle this help overlay" },
        { key: "i", desc: "Focus command input" },
        { key: "q / Esc", desc: "Close current tab" },
        { key: "Alt+1–9", desc: "Switch to tab by number" },
      ],
    },
    {
      category: "Commands",
      keys: [
        { key: "!command", desc: "Execute a DOI command" },
        { key: "!help", desc: "Show available commands" },
        { key: "Tab", desc: "Autocomplete command" },
        { key: "↑ / ↓", desc: "Navigate command history / suggestions" },
      ],
    },
    {
      category: "Auth",
      keys: [
        { key: "Clear Key", desc: "Remove API key (from auth banner)" },
      ],
    },
  ];

  function handleKeydown(e) {
    if (e.key === "Escape") {
      onDismiss();
      e.preventDefault();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="overlay" onclick={onDismiss} role="dialog" aria-label="Keyboard shortcuts" tabindex="0">
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="dialog" onclick={(e) => e.stopPropagation()} role="document">
    <h3>Keyboard Shortcuts</h3>
    <p class="hint">Press <kbd>h</kbd> or <kbd>Esc</kbd> to close</p>

    {#each shortcuts as group}
      <div class="group">
        <h4>{group.category}</h4>
        {#each group.keys as shortcut}
          <div class="row">
            <span class="key">
              {#each shortcut.key.split(" / ") as part, i}
                {#if i > 0}<span class="sep"> / </span>{/if}
                <kbd>{part}</kbd>
              {/each}
            </span>
            <span class="desc">{shortcut.desc}</span>
          </div>
        {/each}
      </div>
    {/each}
  </div>
</div>

<style>
  .overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 200;
  }
  .dialog {
    background: #1e1e32;
    border: 1px solid #444;
    border-radius: 10px;
    padding: 1.5rem;
    min-width: 420px;
    max-width: 520px;
    max-height: 80vh;
    overflow-y: auto;
    font-family: monospace;
    color: #e0e0e0;
  }
  h3 {
    margin: 0 0 0.2rem;
    font-size: 1rem;
    font-weight: 600;
  }
  .hint {
    color: var(--clr-muted, #82829a);
    font-size: 0.75rem;
    margin-bottom: 1rem;
  }
  .hint kbd {
    display: inline-block;
    padding: 1px 4px;
    font-family: monospace;
    background: #222;
    border: 1px solid #444;
    border-radius: 3px;
    color: var(--clr-kbd, #999);
    font-size: 0.7rem;
  }
  .group {
    margin-bottom: 1rem;
  }
  .group:last-child {
    margin-bottom: 0;
  }
  h4 {
    margin: 0 0 0.4rem;
    font-size: 0.78rem;
    color: var(--clr-sub, #9292aa);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .row {
    display: flex;
    gap: 1rem;
    padding: 0.2rem 0;
    font-size: 0.82rem;
  }
  .key {
    min-width: 12rem;
    flex-shrink: 0;
    white-space: nowrap;
  }
  .key kbd {
    display: inline-block;
    padding: 1px 5px;
    font-family: monospace;
    background: #222;
    border: 1px solid #444;
    border-radius: 3px;
    color: #ddd;
    font-size: 0.75rem;
  }
  .key .sep {
    color: var(--clr-dim, #888);
    font-size: 0.7rem;
  }
  .desc {
    color: #aaa;
  }
</style>
