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
  import { getFields } from "./formFields.js";
  import FormFieldInput from "./FormFieldInput.svelte";
  import {
    buildTitle,
    fieldsToMetadata,
    metadataToFormValues,
    metadataToPrimaryLangs,
    metadataToTranslations,
    parseLanguageMap,
    parseMetadata,
    titleToFormValue,
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

  // ── Multilingual translations (doi + snippet forms) ────────────────
  // Per-field translation rows: `{fieldName: [{lang, title}]}` and
  // per-field primary language code (default "en", user-settable).
  let translationsByField = $state({});
  let primaryLangsByField = $state({});

  // Copy initial data on mount, then fetch the DOI type catalog for the
  // autocomplete dropdown and the type-specific metadata schemas (the
  // backend is the source of truth).  The $state only captures initial
  // values from props once, which is the correct behavior for form fields.
  onMount(async () => {
    fieldValues = { ...initialData };
    // Legacy multilingual title ({en: …}) → per-field translation rows.
    const parsedTitle = parseLanguageMap(initialData.title);
    if (parsedTitle.translations.length > 0) {
      translationsByField = { ...translationsByField, title: parsedTitle.translations };
      primaryLangsByField = {
        ...primaryLangsByField,
        title: parsedTitle.primaryLang,
      };
    }
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
        // Multilingual metadata values → translation rows keyed by the
        // form field name (meta_<schemaName>).
        const metaRows = metadataToTranslations(schema, existingMetadata);
        const metaLangs = metadataToPrimaryLangs(schema, existingMetadata);
        const byFormName = {};
        const langsByFormName = {};
        for (const f of schema) {
          if (metaRows[f.name]) byFormName[`meta_${f.name}`] = metaRows[f.name];
          if (metaLangs[f.name]) langsByFormName[`meta_${f.name}`] = metaLangs[f.name];
        }
        translationsByField = { ...translationsByField, ...byFormName };
        primaryLangsByField = { ...primaryLangsByField, ...langsByFormName };
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
  let fields = $derived(getFields(formType, typeOptions, typeSchemas, fieldValues));

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
        } else if (f.translateable && (translationsByField[f.name] || []).length > 0) {
          // Multilingual field → language map (JSON text for the flag).
          const primaryLang = primaryLangsByField[f.name] || "en";
          const value = buildTitle(val, translationsByField[f.name], primaryLang);
          flags[f.name] = typeof value === "object" ? JSON.stringify(value) : value;
        } else {
          flags[f.name] = val;
        }
      }
    }
    // Assemble type-specific metadata from the dynamic fields.
    const selectedType = fieldValues.doi_type || "";
    const schema = typeSchemas[selectedType];
    if (schema && schema.length > 0) {
      // Convert translations + primary langs keyed by form field
      // (meta_<name>) to the schema field names `fieldsToMetadata` expects.
      const schemaKeyed = {};
      const langsKeyed = {};
      for (const f of schema) {
        const rows = translationsByField[`meta_${f.name}`];
        if (rows) schemaKeyed[f.name] = rows;
        const lang = primaryLangsByField[`meta_${f.name}`];
        if (lang) langsKeyed[f.name] = lang;
      }
      const metadata = fieldsToMetadata(
        schema,
        metadataFieldValues(),
        schemaKeyed,
        langsKeyed,
      );
      if (Object.keys(metadata).length > 0) {
        flags.metadata = JSON.stringify(metadata);
      }
    }
    return flags;
  }

  // ── Multilingual editing ─────────────────────────────────────────────
  /** Set translation rows for a field (base field name or meta_<name>). */
  function setFieldTranslations(fieldName, rows) {
    translationsByField = { ...translationsByField, [fieldName]: rows };
  }

  /** Set the primary language code for a field. */
  function setFieldPrimaryLang(fieldName, lang) {
    primaryLangsByField = { ...primaryLangsByField, [fieldName]: lang };
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
        <FormFieldInput
          {field}
          value={fieldValues[field.name]}
          translations={translationsByField[field.name] || []}
          primaryLang={primaryLangsByField[field.name] || "en"}
          codeMode={fieldValues.type === "code" && field.name === "content"}
          onchange={(v) => setField(field.name, v)}
          onTranslationsChange={(rows) => setFieldTranslations(field.name, rows)}
          onPrimaryLangChange={(lang) => setFieldPrimaryLang(field.name, lang)}
        />
      </div>
    {/each}

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
  .form-actions {
    display: flex;
    gap: 0.5rem;
    padding-top: 0.5rem;
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
