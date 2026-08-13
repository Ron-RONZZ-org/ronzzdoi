<script>
  import { tabStore } from "@lightercore/ui/tabStore.svelte.js";
  import { overlayStack } from "@lightercore/ui/overlayStack.svelte.js";
  import HomeTab from "./HomeTab.svelte";
  import DetailTab from "./DetailTab.svelte";
  import ListTab from "./ListTab.svelte";
  import DoiListTab from "./DoiListTab.svelte";
  import SnippetTab from "./SnippetTab.svelte";
  import StatusPopup from "./StatusPopup.svelte";
  import ErrorPopup from "./ErrorPopup.svelte";
  import LoadingPopup from "./LoadingPopup.svelte";
  import FormTab from "./FormTab.svelte";
  import HelpPopup from "./HelpPopup.svelte";
  import KeyboardShortcutOverlay from "./KeyboardShortcutOverlay.svelte";

  let showGlobalHelp = $state(false);
  let inputFocused = $state(false);

  // Track command input focus state
  $effect(() => {
    function handler(e) {
      inputFocused = e.detail.focused;
    }
    window.addEventListener("input-focus-changed", handler);
    return () => window.removeEventListener("input-focus-changed", handler);
  });

  // Auto-focus command input when switching to home tab
  $effect(() => {
    if (tabStore.isHome) {
      requestAnimationFrame(() => {
        document.querySelector(".input-field")?.focus();
      });
    }
  });

  /** Tab type → display component mapping */
  const TAB_COMPONENTS = {
    loading: LoadingPopup,
    status: StatusPopup,
    detail: DetailTab,
    list: ListTab,
    "doi-list": DoiListTab,
    snippet: SnippetTab,
    error: ErrorPopup,
    form: FormTab,
    help: HelpPopup,
  };

  // Tab types that manage their own Escape
  const LIST_TAB_TYPES = new Set(["list", "doi-list"]);

  function handleKeydown(e) {
    // Escape — context-sensitive
    if (e.key === "Escape") {
      // Level 1: When command input is focused on the home tab, let ChatInput
      // handle Escape first (close suggestions, then blur on second press).
      // Must come before the general blur (Level 2) so that Ctrl+Escape on
      // the home tab doesn't simultaneously close suggestions AND lose focus.
      if (tabStore.isHome && inputFocused) return;

      // Level 2: Blur focused input on non-home tabs (form fields, search)
      const tag = e.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || e.target?.isContentEditable) {
        if (document.activeElement === e.target) {
          e.target.blur();
          e.preventDefault();
          return;
        }
      }

      // Level 3: Dismiss global help overlay
      if (showGlobalHelp) {
        showGlobalHelp = false;
        e.preventDefault();
        return;
      }

      // Level 4: List tabs manage their own Escape
      const type = tabStore.active?.type;
      if (type && LIST_TAB_TYPES.has(type)) return;

      // Level 5: Close overlay if active
      if (overlayStack.top) {
        overlayStack.top.close();
        e.preventDefault();
        return;
      }

      // Level 6: Close current tab
      if (tabStore.active && tabStore.active.closable && !tabStore.isHome) {
        tabStore.close(tabStore.active.id);
        e.preventDefault();
      } else if (tabStore.isHome) {
        const resultTabs = tabStore.tabs.filter((t) => t.closable);
        if (resultTabs.length > 0) {
          const tab = resultTabs[resultTabs.length - 1];
          tabStore.close(tab.id);
          e.preventDefault();
        }
      }
      return;
    }

    // I — focus command input on home tab
    if ((e.key === "i" || e.key === "I") && tabStore.isHome) {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable)) {
        return;
      }
      e.preventDefault();
      document.querySelector(".input-field")?.focus();
      return;
    }

    // H / h — toggle global help overlay
    if (e.key === "h" || e.key === "H") {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable)) {
        return;
      }
      e.preventDefault();
      showGlobalHelp = !showGlobalHelp;
      return;
    }

    // Q — close current tab
    if ((e.key === "q" || e.key === "Q") && !tabStore.isHome) {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable)) {
        return;
      }
      if (overlayStack.top) {
        overlayStack.top.close();
        e.preventDefault();
        return;
      }
      if (tabStore.active && tabStore.active.closable) {
        tabStore.close(tabStore.active.id);
      }
    }

    // Alt+1–9 — switch to numbered tab
    if (e.altKey && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      const num = parseInt(e.key, 10);
      if (num >= 1 && num <= 9) {
        e.preventDefault();
        tabStore.setActiveIndex(num - 1);
        return;
      }
    }

    // Alt+N / Alt+P — next / previous tab (with wrap)
    if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      if (e.key === "n" || e.key === "N") {
        e.preventDefault();
        const idx = tabStore.activeIndex;
        if (idx < tabStore.count - 1) {
          tabStore.setActiveIndex(idx + 1);
        } else {
          tabStore.setActiveIndex(0);
        }
        return;
      }
      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        const idx = tabStore.activeIndex;
        if (idx > 0) {
          tabStore.setActiveIndex(idx - 1);
        } else {
          tabStore.setActiveIndex(tabStore.count - 1);
        }
        return;
      }
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="tab-view">
  <!-- Tab content: HomeTab is always mounted -->
  <div class="tab-content" class:active={tabStore.isHome} role="region" aria-label="Home tab" data-testid="tab-panel">
    <HomeTab />
  </div>

  {#each tabStore.tabs as tab (tab.id)}
    {#if tab.id !== "home"}
      <div class="tab-content" class:active={tab.id === tabStore.active?.id} role="region" aria-label={tab.title || "Tab content"} data-testid="tab-panel">
        {#if tab.type === "loading"}
          <LoadingPopup message={tab.title} />
        {:else if tab.type === "detail"}
          <DetailTab data={tab.data} tabId={tab.id} />
        {:else if tab.type === "list"}
          <ListTab data={tab.data} tabId={tab.id} />
        {:else if tab.type === "doi-list"}
          <DoiListTab data={tab.data} tabId={tab.id} />
        {:else if tab.type === "snippet"}
          <SnippetTab data={tab.data} />
        {:else if tab.type === "status"}
          <StatusPopup data={tab.data} />
        {:else if tab.type === "error"}
          <ErrorPopup data={tab.data} />
        {:else if tab.type === "form"}
          <FormTab data={tab.data} tabId={tab.id} />
        {:else if tab.type === "help"}
          <HelpPopup data={tab.data} />
        {:else}
          <StatusPopup data={tab.data} />
        {/if}
      </div>
    {/if}
  {/each}

  <!-- Tab bar (hidden when only home tab exists) -->
  {#if tabStore.count > 1}
    <div class="tab-bar" role="tablist" aria-label="Open tabs">
      {#each tabStore.tabs as tab (tab.id)}
        <button
          role="tab"
          class="tab"
          class:active={tab.id === tabStore.active?.id}
          onclick={() => tabStore.setActive(tab.id)}
          aria-selected={tab.id === tabStore.active?.id}
          title={tab.title}
        >
          <span class="tab-icon">{tabIcon(tab.type)}</span>
          <span class="tab-label">{truncate(tab.title, 22)}</span>
          {#if tab.closable}
            <span
              class="tab-close"
              role="button"
              tabindex="-1"
              onclick={(e) => {
                e.stopPropagation();
                tabStore.close(tab.id);
              }}
              onkeydown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  tabStore.close(tab.id);
                }
              }}
            >✕</span>
          {/if}
        </button>
      {/each}
      <span class="tab-bar-spacer"></span>
      <span class="tab-hint" title="Keyboard shortcuts">
        {#if tabStore.isHome}
          {#if inputFocused}
            <kbd>Esc</kbd> blur
          {:else}
            <kbd>i</kbd> input
          {/if}
          <span class="hint-sep">·</span>
          <kbd>h</kbd> help
          <span class="hint-sep">·</span>
        {/if}
        {#if !tabStore.isHome}
          <span class="hint-sep">·</span>
          <kbd>q</kbd> <kbd>Esc</kbd> close
        {/if}
        {#if tabStore.count > 1}
          <span class="hint-sep">·</span>
          <kbd>Alt+N</kbd> <kbd>P</kbd> prev/next
          <span class="hint-sep">·</span>
          <kbd>Alt+1–9</kbd> switch
        {/if}
      </span>
    </div>
  {:else}
    <!-- Home-only hint strip -->
    <div class="home-hints">
      <span class="tab-hint" title="Keyboard shortcuts">
        {#if inputFocused}
          <kbd>Esc</kbd> blur
        {:else}
          <kbd>i</kbd> input
        {/if}
        <span class="hint-sep">·</span>
        <kbd>h</kbd> help
      </span>
    </div>
  {/if}

  {#if showGlobalHelp}
    <KeyboardShortcutOverlay onDismiss={() => { showGlobalHelp = false; }} />
  {/if}
</div>

<script module>
  import { truncate } from "@lightercore/ui/listTabFormat.js";

  function tabIcon(type) {
    const icons = {
      home: "⌂",
      detail: "📖",
      list: "📋",
      status: "📋",
      snippet: "❝",
      error: "⚠",
      loading: "⏳",
      form: "✏",
      help: "?",
    };
    return icons[type] || "•";
  }


</script>

<style>
  .tab-view {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }
  .tab-content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: none;
    flex-direction: column;
    background: #1a1a2e;
  }
  .tab-content.active {
    display: flex;
  }
  .tab-bar {
    display: flex;
    align-items: stretch;
    background: #16162a;
    border-top: 1px solid #333;
    overflow-x: auto;
    gap: 1px;
    min-height: 32px;
    flex-shrink: 0;
  }
  .tab {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background: #1a1a2e;
    border: none;
    border-right: 1px solid #333;
    color: #9292aa;
    font-family: monospace;
    font-size: 0.78rem;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.1s, color 0.1s;
    flex-shrink: 0;
  }
  .tab:hover {
    background: #22223a;
    color: #e0e0e0;
  }
  .tab.active {
    background: #1e1e32;
    color: #e0e0e0;
    border-bottom: 2px solid #7c7c9a;
  }
  .tab-icon { font-size: 0.7rem; opacity: 0.7; }
  .tab-label {
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tab-close {
    font-size: 0.65rem;
    padding: 1px 3px;
    border-radius: 3px;
    opacity: 0.5;
    transition: opacity 0.1s;
    line-height: 1;
  }
  .tab-close:hover { opacity: 1; background: #333; }
  .tab-bar-spacer { flex: 1; background: #1a1a2e; }
  .tab-hint {
    display: flex;
    align-items: center;
    gap: 3px;
    padding: 0 8px;
    font-size: 0.68rem;
    color: #888;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .tab-hint kbd {
    display: inline-block;
    padding: 1px 4px;
    font-size: 0.62rem;
    font-family: monospace;
    background: #222;
    border: 1px solid #444;
    border-radius: 3px;
    color: #999;
  }
  .hint-sep { color: #444; margin: 0 2px; }
  .home-hints {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px 0;
    background: #16162a;
    border-top: 1px solid #2a2a3e;
    flex-shrink: 0;
    min-height: 24px;
  }
</style>
