<script>
  /**
   * FormFieldInput.svelte — renders a single form field input.
   *
   * Extracted from FormTab.svelte to keep that file under the 500-line
   * convention.  Handles every input type FormTab supports: select,
   * segmented toggle, autocomplete combobox, meta-list textarea, JSON,
   * textarea, URL, and plain text.  Translateable fields get a
   * TranslationsEditor below the input.
   *
   * Props:
   *   field            — field def ({name, label, type, options, help, ...})
   *   value            — current field value
   *   translations     — translation rows for this field (translateable)
   *   onchange         — (value) => void
   *   onTranslationsChange — (rows) => void
   */

  import Autocomplete from "@lightercore/ui/Autocomplete.svelte";
  import TranslationsEditor from "./TranslationsEditor.svelte";

  let {
    field = {},
    value = "",
    translations = [],
    primaryLang = "en",
    codeMode = false,
    onchange = () => {},
    onTranslationsChange = () => {},
    onPrimaryLangChange = () => {},
  } = $props();

  function setValue(v) {
    onchange(v);
  }
</script>

<label class="field-label" for={field.name}>
  {field.label}
  {#if field.required}<span class="required-star">*</span>{/if}
</label>
{#if field.help}
  <p class="field-help">{field.help}</p>
{/if}

{#if field.type === "select"}
  <select
    id={field.name}
    class="field-input"
    value={value || ""}
    onchange={(e) => setValue(e.target.value)}
  >
    <option value="">— Select —</option>
    {#each field.options || [] as opt}
      <option value={opt}>{opt}</option>
    {/each}
  </select>
{:else if field.type === "segmented"}
  <div class="segmented" role="radiogroup" aria-label={field.label}>
    {#each field.options || [] as opt}
      <button
        type="button"
        class="segmented-option"
        class:active={value === opt}
        role="radio"
        aria-checked={value === opt}
        onclick={() => setValue(opt)}
      >
        {opt}
      </button>
    {/each}
  </div>
{:else if field.type === "autocomplete"}
  <Autocomplete
    id={field.name}
    value={value || ""}
    options={field.options || []}
    onchange={setValue}
    placeholder={field.help || ""}
    allowFreeText={true}
  />
{:else if field.type === "meta-list"}
  <textarea
    id={field.name}
    class="field-input field-textarea"
    value={value || ""}
    oninput={(e) => setValue(e.target.value)}
    placeholder="One person per line: DOI (10.ronzz/…) or 'Given Family'"
    rows="3"
  ></textarea>
{:else if field.type === "json"}
  <textarea
    id={field.name}
    class="field-input field-textarea"
    value={value || ""}
    oninput={(e) => setValue(e.target.value)}
    placeholder={field.help || ""}
    rows="4"
  ></textarea>
{:else if field.type === "textarea"}
  <textarea
    id={field.name}
    class="field-input field-textarea"
    class:code-input={codeMode}
    value={value || ""}
    oninput={(e) => setValue(e.target.value)}
    placeholder={field.help || ""}
    rows="6"
    spellcheck={false}
  ></textarea>
{:else if field.type === "url"}
  <input
    id={field.name}
    type="url"
    class="field-input"
    value={value || ""}
    oninput={(e) => setValue(e.target.value)}
    placeholder={field.help || ""}
  />
{:else}
  <input
    id={field.name}
    type="text"
    class="field-input"
    value={value || ""}
    oninput={(e) => setValue(e.target.value)}
    placeholder={field.help || ""}
  />
{/if}

{#if field.translateable}
  <TranslationsEditor
    {primaryLang}
    translations={translations || []}
    onPrimaryLangChange={onPrimaryLangChange}
    onchange={onTranslationsChange}
  />
{/if}

<style>
  .field-label {
    font-family: monospace;
    font-size: 0.85rem;
    color: #c0c0d0;
    font-weight: 600;
  }
  .required-star { color: #da6a6a; margin-left: 0.15rem; }
  .field-help {
    font-family: monospace;
    font-size: 0.72rem;
    color: #7c7c9a;
    margin: 0;
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
    transition: border-color 0.15s;
    width: 100%;
    box-sizing: border-box;
  }
  .field-input:focus { border-color: #5a5a8a; }
  .field-textarea {
    resize: vertical;
    min-height: 80px;
  }
  select.field-input { cursor: pointer; }
  .segmented {
    display: flex;
    gap: 0.25rem;
  }
  .segmented-option {
    flex: 1;
    padding: 0.4rem 0.6rem;
    background: #16213e;
    border: 1px solid #555;
    color: #c0c0d0;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.82rem;
    cursor: pointer;
    text-transform: capitalize;
    transition: all 0.15s;
  }
  .segmented-option:hover { border-color: #5a5a8a; }
  .segmented-option.active {
    background: #2a4a3a;
    border-color: #3a7a4a;
    color: #8fdb9f;
    font-weight: 600;
  }
  .field-textarea.code-input {
    background: #101526;
    font-family: monospace;
    tab-size: 4;
  }
</style>
