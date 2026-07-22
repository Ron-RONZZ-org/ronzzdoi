<script>
  import { commandTree } from "./commandTree.js";
  import { getCompletions } from "./commandEngine.js";
  import { parseCommand } from "./parser.js";
  import { createCommandHistory } from "@lightercore/ui/commandHistory.svelte.js";
  import ChatSuggestions from "./ChatSuggestions.svelte";

  const history = createCommandHistory("ronzzdoi:commandHistory");

  let {
    onSubmit,
    placeholder = "Type !command (e.g. !doi search, !auth api_key list)",
    centered = true,
  } = $props();

  let value = $state("");
  let suggestions = $state([]);
  let hints = $state([]);
  let positionals = $state([]);
  let selectedSuggestion = $state(-1);
  let isCommandMode = $state(false);
  let textareaEl = $state(null);

  let hasInteractiveItems = $derived(suggestions.length > 0);
  let showSuggestions = $derived(
    (isCommandMode && hasInteractiveItems) || positionals.length > 0,
  );

  function checkCommandMode() {
    isCommandMode = value.startsWith("!");
    if (!isCommandMode) {
      suggestions = [];
      hints = [];
      positionals = [];
    }
  }

  function updateSuggestions() {
    if (!isCommandMode) {
      suggestions = [];
      hints = [];
      positionals = [];
      selectedSuggestion = -1;
      return;
    }
    const result = getCompletions(value);
    suggestions = result.completions;
    hints = result.hints;
    positionals = result.positionals;
    selectedSuggestion = -1;
  }

  function autoResize() {
    if (!textareaEl) return;
    textareaEl.style.height = "auto";
    textareaEl.style.height = Math.min(textareaEl.scrollHeight, 200) + "px";
  }

  function handleInput() {
    autoResize();
    checkCommandMode();
    if (isCommandMode) updateSuggestions();
  }

  function applyCompletion(completion) {
    if (!completion) return;
    if (value.endsWith(" ")) {
      value = value + completion + " ";
    } else if (completion.startsWith("!") && value.startsWith("!")) {
      value = completion + " ";
    } else {
      const parts = value.split(/\s+/);
      parts[parts.length - 1] = completion;
      value = parts.join(" ") + " ";
    }
    suggestions = [];
    hints = [];
    positionals = [];
    selectedSuggestion = -1;
    requestAnimationFrame(() => updateSuggestions());
  }

  function handleKeydown(e) {
    // Escape: close suggestions
    if (e.key === "Escape") {
      if (showSuggestions) {
        suggestions = [];
        hints = [];
        positionals = [];
        return;
      }
      textareaEl?.blur();
      e.stopPropagation();
      return;
    }

    // Tab: autocomplete
    if (e.key === "Tab" && hasInteractiveItems) {
      e.preventDefault();
      if (suggestions.length > 0) {
        const idx = selectedSuggestion >= 0 ? selectedSuggestion : 0;
        applyCompletion(suggestions[idx]);
      }
      return;
    }

    // Arrow keys: navigate suggestions OR command history
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      if (hasInteractiveItems) {
        e.preventDefault();
        if (e.key === "ArrowUp") {
          selectedSuggestion = Math.max(0, selectedSuggestion - 1);
        } else {
          selectedSuggestion = Math.min(suggestions.length - 1, selectedSuggestion + 1);
        }
        return;
      }
      // No suggestions → navigate command history
      e.preventDefault();
      const cmd = e.key === "ArrowUp" ? history.back() : history.forward();
      if (cmd) {
        value = cmd;
        checkCommandMode();
        requestAnimationFrame(() => updateSuggestions());
      }
      return;
    }

    // Enter: submit (Shift+Enter = newline)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const cmd = value.trim();
      if (!cmd) return;

      // If in command mode and suggestions exist, complete instead
      if (isCommandMode && suggestions.length > 0) {
        const lastToken = cmd.split(/\s+/).pop() || "";
        const isPartial = suggestions.some(
          (s) =>
            s.toLowerCase().startsWith(lastToken.toLowerCase()) &&
            s !== lastToken &&
            !s.startsWith("<") &&
            !s.startsWith("["),
        );
        if (isPartial) {
          const idx = selectedSuggestion >= 0 ? selectedSuggestion : 0;
          applyCompletion(suggestions[idx]);
          return;
        }
      }

      // Submit — save to history
      history.push(cmd);
      value = "";
      suggestions = [];
      hints = [];
      positionals = [];
      if (onSubmit) onSubmit(cmd);
    }
  }

  function handleFocus() {
    window.dispatchEvent(new CustomEvent("input-focus-changed", { detail: { focused: true } }));
  }

  function handleBlur() {
    window.dispatchEvent(new CustomEvent("input-focus-changed", { detail: { focused: false } }));
  }
</script>

<div class="chat-input" class:centered>
  <div class="input-area">
    <!-- svelte-ignore a11y_autofocus -->
    <textarea
      bind:this={textareaEl}
      class="input-field"
      class:command-mode={isCommandMode}
      {placeholder}
      bind:value
      oninput={handleInput}
      onkeydown={handleKeydown}
      onfocus={handleFocus}
      onblur={handleBlur}
      aria-label="Command input"
      autofocus
    ></textarea>
  </div>

  <ChatSuggestions
    {suggestions}
    dataCompletions={[]}
    {hints}
    {positionals}
    {selectedSuggestion}
    selectedDataIndex={-1}
    {isCommandMode}
    {showSuggestions}
    onSelect={applyCompletion}
  />
</div>

<style>
  .chat-input {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    width: 100%;
    max-width: 720px;
    margin: 0 auto;
    transition: all 0.3s ease;
  }
  .chat-input.centered {
    justify-content: center;
    flex: 1;
  }
  .input-area {
    position: relative;
    width: 100%;
    display: flex;
    align-items: flex-end;
    gap: 0.5rem;
  }
  .input-field {
    flex: 1;
    background: #1e1e32;
    border: 1px solid #555;
    border-radius: 14px;
    color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 0.95rem;
    padding: 0.85rem 1rem;
    outline: none;
    resize: none;
    line-height: 1.6;
    min-height: 52px;
    max-height: 200px;
    overflow-y: auto;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .input-field:focus {
    border-color: #7c7c9a;
    box-shadow: 0 0 0 2px rgba(124, 124, 154, 0.2);
  }
  .input-field.command-mode {
    border-color: #5a8a5a;
    box-shadow: 0 0 0 2px rgba(90, 138, 90, 0.15);
  }
  .input-field::placeholder {
    color: #555;
  }
</style>
