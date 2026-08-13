<script>
  /** Form tab — interactive command form with dynamic fields.
   *
   * Props:
   *   data — { form: string, initialData: object }
   *   tabId — tab identifier
   */

  import { tabStore } from "@lightercore/ui/tabStore.svelte.js";
  import { banner } from "@lightercore/ui/bannerStore.svelte.js";
  import { deriveIdKey } from "./commandExecutor.js";
  import { doiApi } from "./api.js";
  import { formatKey } from "./formatValue.js";
  import {
    buildTitle,
    fieldsToMetadata,
    metadataToFormValues,
    parseMetadata,
    titleToFormValue,
    titleToTranslations,
  } from "./doiForm.js";

  import { onMount } from "svelte";

  let { data = {}, tabId } = $props();
  let formType = $derived(data?.form || "");
  let initialData = $derived(data?.initialData || {});

  // ── Form state ────────────────────────────────────────────────────────
  let fieldValues = $state({});
  let submitting = $state(false);
  let formError = $state("");

  // ── DOI type catalog (from GET /api/v1/doi/types) ─────────────────────
  let typeOptions = $state([]);
  let typeSchemas = $state({});

  // ── Multilingual title translations (doi forms) ───────────────────────
  let titleTranslations = $state([]);
  let titleI18nOpen = $state(false);

  // Copy initial data on mount, then fetch the DOI type catalog for the
  // autocomplete dropdown and the type-specific metadata schemas (the
  // backend is the source of truth).  The $state only captures initial
  // values from props once, which is the correct behavior for form fields.
  onMount(async () => {
    fieldValues = { ...initialData };
    titleTranslations = titleToTranslations(initialData.title);
    try {
      const catalog = await doiApi.types();
      typeOptions = catalog.types || [];
      typeSchemas = catalog.schemas || {};

      // Prefill dynamic metadata fields (modify form) from the record.
      const selectedType = fieldValues.doi_type || "";
      const schema = typeSchemas[selectedType];
      const existingMetadata = parseMetadata(fieldValues.metadata);
      if (schema && Object.keys(existingMetadata).length > 0) {
        fieldValues = {
          ...fieldValues,
          ...metadataToFormValues(schema, existingMetadata),
        };
      }

      // Legacy multilingual titles ({en: …}) → plain string for the input.
      const title = titleToFormValue(fieldValues.title);
      if (title !== fieldValues.title) {
        fieldValues = { ...fieldValues, title };
      }
    } catch {
      // Type catalog unavailable — form falls back to free-text + JSON.
    }
  });

  // ── Field definitions per form type ───────────────────────────────────

  /** Dynamic, type-specific metadata fields for the selected doi_type. */
  function metadataFields() {
    const selected = fieldValues.doi_type || "";
    const schema = typeSchemas[selected];
    if (!schema || schema.length === 0) {
      return [{
        name: "metadata",
        label: "Metadata (JSON)",
        type: "json",
        required: false,
        help: "Type-specific metadata as JSON (advanced). Pick a DOI type above for a guided form.",
      }];
    }
    return schema.map((f) => ({
      name: `meta_${f.name}`,
      schemaName: f.name,
      label: formatKey(f.name),
      type: f.types.includes("list")
        ? "meta-list"
        : f.types.includes("int")
          ? "meta-int"
          : "meta-str",
      required: false,
      help: f.description || "",
    }));
  }

  /**
   * Shared snippet form fields (used by snippet-add and snippet-edit).
   * The Text/Code/Math toggle switches which fields are shown.
   */
  function snippetFields() {
    const kind = fieldValues.type || "text";
    const fields = [
      { name: "type", label: "Content Type", type: "segmented", required: true, options: ["text", "code", "math"], help: "Text quotation, code snippet, or KaTeX math" },
      { name: "content", label: "Content", type: "textarea", required: true, help: kind === "code" ? "Paste the code snippet" : kind === "math" ? "KaTeX math source (e.g. \\frac{a}{b})" : "The quotation text" },
      { name: "title", label: "Title", type: "text", required: false, help: "Short human-readable title (optional)" },
    ];
    if (kind === "code") {
      fields.push({ name: "language", label: "Language", type: "text", required: false, help: "python, javascript, bash, …" });
    } else if (kind === "text") {
      fields.push(
        { name: "source_doi", label: "Source DOI", type: "text", required: false, help: "The book/document DOI this quote is from (optional)" },
        { name: "page_start", label: "Page Start", type: "text", required: false },
        { name: "page_end", label: "Page End", type: "text", required: false },
      );
    }
    return fields;
  }

  /** @returns {{ name: string, label: string, type: string, required: boolean, help?: string, options?: string[] }[]} */
  function getFields() {
    switch (formType) {
      case "doi-assign":
        return [
          { name: "url", label: "Target URL", type: "url", required: true, help: "The URL this DOI should resolve to (leave empty for entity DOIs)" },
          { name: "title", label: "Title", type: "text", required: false, help: "Human-readable title" },
          { name: "doi_type", label: "DOI Type", type: "autocomplete", required: false, help: "Select or type a type (book, film, person, …)", options: typeOptions },
          ...metadataFields(),
        ];
      case "doi-modify":
        return [
          { name: "doi", label: "DOI", type: "text", required: true, help: "The DOI to modify" },
          { name: "url", label: "New URL", type: "url", required: false, help: "Leave blank to keep current" },
          { name: "title", label: "Title", type: "text", required: false, help: "Leave blank to keep current" },
          { name: "doi_type", label: "DOI Type", type: "autocomplete", required: false, help: "Leave blank to keep current", options: typeOptions },
          ...metadataFields(),
        ];
      case "snippet-add":
        return snippetFields();
      case "snippet-edit":
        // Edit reuses the assign fields, prefilled, plus a read-only DOI.
        return [
          { name: "doi", label: "DOI", type: "text", required: true, readonly: true, help: "The snippet DOI (read-only)" },
          ...snippetFields(),
        ];
      case "auth-key-create":
        return [
          { name: "name", label: "Key Name", type: "text", required: true },
          { name: "permission", label: "Permission", type: "select", required: true, options: ["read_only", "edit", "admin"] },
          { name: "expires_at", label: "Expires At (ISO)", type: "text", required: false, help: "e.g. 2027-01-01T00:00:00" },
        ];
      case "auth-key-update":
        return [
          { name: "key_id", label: "Key ID", type: "text", required: true },
          { name: "name", label: "New Name", type: "text", required: false },
          { name: "permission", label: "New Permission", type: "select", required: false, options: ["read_only", "edit", "admin"] },
          { name: "expires_at", label: "Expires At (ISO)", type: "text", required: false, help: 'Empty string to clear' },
        ];
      case "auth-key-delete":
        return [
          { name: "key_id", label: "Key ID", type: "text", required: true },
        ];
      default:
        return [];
    }
  }

  let fields = $derived(getFields());

  function buildTokens() {
    switch (formType) {
      case "doi-assign":
        return ["doi", "assign"];
      case "doi-modify":
        return ["doi", "modify"];
      case "snippet-add":
        return ["snippet", "add"];
      case "snippet-edit":
        return ["snippet", "modify"];
      case "auth-key-create":
        return ["auth", "api_key", "create"];
      case "auth-key-update":
        return ["auth", "api_key", "update"];
      case "auth-key-delete":
        return ["auth", "api_key", "delete"];
      default:
        return [];
    }
  }

  /** Extract dynamic metadata field values keyed by schema field name. */
  function metadataFieldValues() {
    const out = {};
    for (const f of fields) {
      if (f.schemaName && fieldValues[`meta_${f.schemaName}`] !== undefined) {
        out[f.schemaName] = fieldValues[`meta_${f.schemaName}`];
      }
    }
    return out;
  }

  function buildFlags() {
    const flags = {};
    for (const f of fields) {
      if (f.schemaName) continue; // dynamic metadata assembled below
      const val = fieldValues[f.name];
      if (val !== undefined && val !== null && val !== "") {
        if (f.type === "json") {
          try {
            JSON.parse(val); // Validate JSON
            flags[f.name] = val;
          } catch {
            // Let submit handle the error
            flags[f.name] = val;
          }
        } else {
          flags[f.name] = val;
        }
      }
    }
    // Multilingual titles: a language map when translations exist.
    if (isDoiForm && fieldValues.title !== undefined && titleTranslations.length > 0) {
      const title = buildTitle(fieldValues.title, titleTranslations);
      if (typeof title === "object") {
        flags.title = JSON.stringify(title);
      }
    }
    // Assemble type-specific metadata from the dynamic fields.
    const selectedType = fieldValues.doi_type || "";
    const schema = typeSchemas[selectedType];
    if (schema && schema.length > 0) {
      const metadata = fieldsToMetadata(schema, metadataFieldValues());
      if (Object.keys(metadata).length > 0) {
        flags.metadata = JSON.stringify(metadata);
      }
    }
    return flags;
  }

  // ── Multilingual title editing ────────────────────────────────────────
  let isDoiForm = $derived(formType === "doi-assign" || formType === "doi-modify");

  function addTitleTranslation() {
    titleTranslations = [...titleTranslations, { lang: "", title: "" }];
  }

  function updateTitleTranslation(index, field, value) {
    const next = titleTranslations.map((t, i) => (i === index ? { ...t, [field]: value } : t));
    titleTranslations = next;
  }

  function removeTitleTranslation(index) {
    titleTranslations = titleTranslations.filter((_, i) => i !== index);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;

    // Validate required fields
    for (const f of fields) {
      if (f.required && !fieldValues[f.name]) {
        formError = `${f.label} is required.`;
        return;
      }
      if (f.type === "json" && fieldValues[f.name]) {
        try {
          JSON.parse(fieldValues[f.name]);
        } catch {
          formError = `${f.label} is not valid JSON.`;
          return;
        }
      }
    }

    submitting = true;
    formError = "";

    const tokens = buildTokens();
    const flags = buildFlags();
    const rawInput = "!" + tokens.join(" ") + " " + Object.entries(flags).map(([k, v]) => `--${k} ${v}`).join(" ");

    try {
      const apiKey = localStorage.getItem("ronzzdoi_api_key") || "";
      const resp = await fetch("/api/v1/command", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
        },
        body: JSON.stringify({ tokens, flags, raw_input: rawInput }),
      });

      const result = await resp.json();

      if (!resp.ok) {
        const detail = result.detail || {};
        const msg = typeof detail === "string" ? detail : detail.error || `HTTP ${resp.status}`;
        formError = msg;
        return;
      }

      if (result.type === "error") {
        formError = result.data?.message || "Command failed";
        return;
      }

      // Close form tab
      if (tabId) tabStore.close(tabId);

      // Open result tab
      const idKey = deriveIdKey(result.type, result.data, tokens, flags);
      tabStore.open(result.type || "status", result.title || "Done", result.data || {}, { idKey });

      // For key creation, show the raw key in a banner
      if (formType === "auth-key-create" && result.data?.raw_key) {
        banner.show("Raw key (copy now): " + result.data.raw_key, "info", 0);
      }
    } catch (err) {
      formError = err.message || "Network error";
    } finally {
      submitting = false;
    }
  }

  function handleCancel() {
    if (tabId) tabStore.close(tabId);
  }

  function setField(name, value) {
    if (name === "doi_type") {
      // Drop stale dynamic metadata fields when the type changes.
      const cleaned = {};
      for (const k of Object.keys(fieldValues)) {
        if (!k.startsWith("meta_")) cleaned[k] = fieldValues[k];
      }
      fieldValues = { ...cleaned, [name]: value };
      return;
    }
    fieldValues = { ...fieldValues, [name]: value };
  }

  let displayTitle = $derived(
    formType === "doi-assign" ? "Assign DOI"
      : formType === "doi-modify" ? "Modify DOI"
      : formType === "snippet-add" ? "Add Snippet"
      : formType === "snippet-edit" ? "Edit Snippet"
      : formType === "auth-key-create" ? "Create API Key"
      : formType === "auth-key-update" ? "Update API Key"
      : formType === "auth-key-delete" ? "Delete API Key"
      : formType.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
  );
</script>

<div class="form-tab">
  <div class="form-header">
    <span class="form-title">{displayTitle}</span>
    <button class="cancel-btn" onclick={handleCancel} aria-label="Cancel">✕</button>
  </div>

  {#if formError}
    <div class="form-error-banner" role="alert">
      <span class="form-error-icon">✗</span>
      <span class="form-error-text">{formError}</span>
      <button class="form-error-dismiss" onclick={() => { formError = ''; }} aria-label="Dismiss">✕</button>
    </div>
  {/if}

  <form onsubmit={handleSubmit} class="form-body">
    {#each fields as field}
      <div class="form-field">
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
            value={fieldValues[field.name] || ""}
            onchange={(e) => setField(field.name, e.target.value)}
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
                class:active={fieldValues[field.name] === opt}
                role="radio"
                aria-checked={fieldValues[field.name] === opt}
                onclick={() => setField(field.name, opt)}
              >
                {opt}
              </button>
            {/each}
          </div>
        {:else if field.type === "autocomplete"}
          <input
            id={field.name}
            type="text"
            class="field-input"
            value={fieldValues[field.name] || ""}
            oninput={(e) => setField(field.name, e.target.value)}
            placeholder={field.help || ""}
            list={field.name + "-options"}
          />
          <datalist id={field.name + "-options"}>
            {#each field.options || [] as opt}
              <option value={opt}></option>
            {/each}
          </datalist>
        {:else if field.type === "meta-list"}
          <textarea
            id={field.name}
            class="field-input field-textarea"
            value={fieldValues[field.name] || ""}
            oninput={(e) => setField(field.name, e.target.value)}
            placeholder="One person per line: DOI (10.ronzz/…) or 'Given Family'"
            rows="3"
          ></textarea>
        {:else if field.type === "json"}
          <textarea
            id={field.name}
            class="field-input field-textarea"
            value={fieldValues[field.name] || ""}
            oninput={(e) => setField(field.name, e.target.value)}
            placeholder={field.help || ""}
            rows="4"
          ></textarea>
        {:else if field.type === "textarea"}
          <textarea
            id={field.name}
            class="field-input field-textarea"
            class:code-input={fieldValues.type === "code"}
            value={fieldValues[field.name] || ""}
            oninput={(e) => setField(field.name, e.target.value)}
            placeholder={field.help || ""}
            rows="6"
            spellcheck={false}
          ></textarea>
        {:else if field.type === "url"}
          <input
            id={field.name}
            type="url"
            class="field-input"
            value={fieldValues[field.name] || ""}
            oninput={(e) => setField(field.name, e.target.value)}
            placeholder={field.help || ""}
          />
        {:else}
          <input
            id={field.name}
            type="text"
            class="field-input"
            value={fieldValues[field.name] || ""}
            oninput={(e) => setField(field.name, e.target.value)}
            placeholder={field.help || ""}
            disabled={field.readonly}
          />
        {/if}
      </div>
    {/each}

    {#if isDoiForm}
      <div class="form-field">
        <button
          type="button"
          class="i18n-toggle"
          onclick={() => { titleI18nOpen = !titleI18nOpen; }}
        >
          🌐 {titleI18nOpen ? "Hide" : "Add"} translations (multilingual title)
        </button>
        {#if titleI18nOpen}
          <div class="i18n-rows">
            {#each titleTranslations as t, i (i)}
              <div class="i18n-row">
                <input
                  type="text"
                  class="field-input i18n-lang"
                  value={t.lang}
                  oninput={(e) => updateTitleTranslation(i, "lang", e.target.value)}
                  placeholder="lang (fr, de, …)"
                />
                <input
                  type="text"
                  class="field-input i18n-text"
                  value={t.title}
                  oninput={(e) => updateTitleTranslation(i, "title", e.target.value)}
                  placeholder="Translated title"
                />
                <button
                  type="button"
                  class="i18n-remove"
                  aria-label="Remove translation"
                  onclick={() => removeTitleTranslation(i)}
                >✕</button>
              </div>
            {/each}
            <button type="button" class="btn-small" onclick={addTitleTranslation}>+ Add language</button>
            <p class="field-help">
              The primary title is stored as <code>en</code>; translations
              above add other languages (e.g. <code>fr</code>, <code>de</code>).
            </p>
          </div>
        {/if}
      </div>
    {/if}

    <div class="form-actions">
      <button type="submit" class="btn-submit" disabled={submitting}>
        {submitting ? "Submitting…" : "Submit"}
      </button>
      <button type="button" class="btn-cancel" onclick={handleCancel}>Cancel</button>
    </div>
  </form>
</div>

<style>
  .form-tab {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow-y: auto;
  }
  .form-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 1rem;
    border-bottom: 1px solid #333;
    background: #16162a;
    flex-shrink: 0;
  }
  .form-title {
    font-family: monospace;
    font-size: 0.9rem;
    color: #e0e0e0;
    font-weight: 600;
  }
  .cancel-btn {
    background: none;
    border: none;
    color: #7c7c9a;
    font-size: 1rem;
    cursor: pointer;
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
  }
  .cancel-btn:hover { background: #2a2a44; color: #e0e0e0; }
  .form-error-banner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    background: #3a1e1e;
    border-bottom: 1px solid #7a3a3a;
    color: #db8f8f;
    font-family: monospace;
    font-size: 0.82rem;
    flex-shrink: 0;
  }
  .form-error-icon { font-size: 0.9rem; flex-shrink: 0; }
  .form-error-text { flex: 1; min-width: 0; }
  .form-error-dismiss {
    background: none; border: none; color: #db8f8f;
    opacity: 0.6; cursor: pointer; font-size: 0.85rem;
    padding: 0.1rem 0.3rem; flex-shrink: 0;
  }
  .form-error-dismiss:hover { opacity: 1; }
  .form-body {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .form-field {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
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
  }
  .field-input:focus { border-color: #5a5a8a; }
  .field-input:disabled {
    opacity: 0.6;
    background: #12182a;
    cursor: not-allowed;
  }
  .field-textarea {
    resize: vertical;
    min-height: 80px;
  }
  select.field-input {
    cursor: pointer;
  }
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
  .segmented-option:hover {
    border-color: #5a5a8a;
  }
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
  .form-actions {
    display: flex;
    gap: 0.5rem;
    padding-top: 0.5rem;
  }
  .i18n-toggle {
    background: none;
    border: 1px dashed #4a4a6a;
    color: #7c9ad4;
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.78rem;
    cursor: pointer;
    text-align: left;
  }
  .i18n-toggle:hover {
    border-color: #7c9ad4;
    background: #1e1e3a;
  }
  .i18n-rows {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-top: 0.4rem;
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
  .btn-submit {
    padding: 0.5rem 1rem;
    background: #2a4a3a;
    border: 1px solid #3a7a4a;
    border-radius: 4px;
    color: #8fdb9f;
    font-family: monospace;
    font-size: 0.85rem;
    cursor: pointer;
    font-weight: 600;
  }
  .btn-submit:hover { background: #3a6a4a; }
  .btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-cancel {
    padding: 0.5rem 1rem;
    background: #2a2a3e;
    border: 1px solid #555;
    border-radius: 4px;
    color: #e0e0e0;
    font-family: monospace;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .btn-cancel:hover { background: #3a3a5a; }
</style>
