<script>
  /**
   * TranslationsEditor.svelte — multilingual translation rows for a field.
   *
   * Renders a primary-language input plus an "Add translations" toggle
   * under a pure-text field.  When open, shows one row per translation:
   * language code + translated text, with remove buttons and an "Add
   * language" action.
   *
   * The primary language defaults to "en" but is user-settable — e.g. a
   * French song title can keep `fr` as the primary key.
   *
   * Controlled component: the parent owns the rows array.
   *
   * Props:
   *   primaryLang          — primary language code (default "en").
   *   translations         — `{lang, title}[]` rows for this field.
   *   onPrimaryLangChange  — `(lang) => void`
   *   onchange             — `(rows) => void` called with the next rows array.
   */

  let {
    primaryLang = "en",
    translations = [],
    onPrimaryLangChange = () => {},
    onchange = () => {},
  } = $props();

  let open = $state(false);

  function add() {
    onchange([...translations, { lang: "", title: "" }]);
  }

  function update(index, field, value) {
    onchange(
      translations.map((t, i) => (i === index ? { ...t, [field]: value } : t)),
    );
  }

  function remove(index) {
    onchange(translations.filter((_, i) => i !== index));
  }
</script>

<div class="translations-editor">
  <div class="i18n-bar">
    <span class="i18n-primary-label">Primary lang</span>
    <input
      type="text"
      class="field-input i18n-primary"
      value={primaryLang}
      oninput={(e) => onPrimaryLangChange(e.target.value)}
      placeholder="en"
      aria-label="Primary language"
    />
    <button
      type="button"
      class="i18n-toggle"
      onclick={() => { open = !open; }}
    >
      🌐 {open ? "Hide" : "Add"} translations
    </button>
  </div>
  {#if open}
    <div class="i18n-rows">
      {#each translations as t, i (i)}
        <div class="i18n-row">
          <input
            type="text"
            class="field-input i18n-lang"
            value={t.lang}
            oninput={(e) => update(i, "lang", e.target.value)}
            placeholder="lang (fr, de, …)"
          />
          <input
            type="text"
            class="field-input i18n-text"
            value={t.title}
            oninput={(e) => update(i, "title", e.target.value)}
            placeholder="Translated text"
          />
          <button
            type="button"
            class="i18n-remove"
            aria-label="Remove translation"
            onclick={() => remove(i)}
          >✕</button>
        </div>
      {/each}
      <button type="button" class="btn-small" onclick={add}>+ Add language</button>
      <p class="field-help">
        The primary text is stored under the language above (default
        <code>en</code>); translations add other languages (e.g.
        <code>fr</code>, <code>de</code>).
      </p>
    </div>
  {/if}
</div>

<style>
  .translations-editor {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-top: 0.25rem;
  }
  .i18n-bar {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .i18n-primary-label {
    font-family: monospace;
    font-size: 0.72rem;
    color: #7c7c9a;
    white-space: nowrap;
  }
  .i18n-primary {
    width: 4.5rem;
    flex-shrink: 0;
  }
  .i18n-toggle {
    flex: 1;
    background: none;
    border: 1px dashed #4a4a6a;
    color: #7c9ad4;
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.78rem;
    cursor: pointer;
    text-align: left;
    white-space: nowrap;
  }
  .i18n-toggle:hover {
    border-color: #7c9ad4;
    background: #1e1e3a;
  }
  .i18n-rows {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .i18n-row {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }
  .i18n-lang {
    width: 8rem;
    flex-shrink: 0;
  }
  .i18n-text {
    flex: 1;
    min-width: 0;
  }
  .i18n-remove {
    background: none;
    border: none;
    color: #7c7c9a;
    cursor: pointer;
    font-size: 0.85rem;
    padding: 0.2rem 0.4rem;
    border-radius: 3px;
    flex-shrink: 0;
  }
  .i18n-remove:hover {
    color: #f77;
    background: #3a1e1e;
  }
  .i18n-rows .btn-small {
    align-self: flex-start;
  }
  .field-input {
    padding: 0.5rem 0.6rem;
    background: #16213e;
    border: 1px solid #555;
    color: #e0e0e0;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.85rem;
    outline: none;
  }
  .field-help {
    font-family: monospace;
    font-size: 0.72rem;
    color: #7c7c9a;
    margin: 0;
  }
</style>
