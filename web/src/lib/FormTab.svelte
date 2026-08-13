<script>
  /** Form tab — interactive command form with dynamic fields.
   *
   * Props:
   *   data — { form: string, initialData: object }
   *   tabId — tab identifier
   */

  import { tabStore } from "@lightercore/ui/tabStore.svelte.js";
  import { banner } from "@lightercore/ui/bannerStore.svelte.js";
  import { execute, deriveIdKey } from "./commandExecutor.js";

  import { onMount } from "svelte";

  let { data = {}, tabId } = $props();
  let formType = $derived(data?.form || "");
  let initialData = $derived(data?.initialData || {});

  // ── Form state ────────────────────────────────────────────────────────
  let fieldValues = $state({});
  let submitting = $state(false);

  // Copy initial data on mount — the $state only captures initial values
  // from props once, which is the correct behavior for form fields.
  onMount(() => {
    fieldValues = { ...initialData };
  });
  let formError = $state("");

  // ── Field definitions per form type ───────────────────────────────────
  /** @returns {{ name: string, label: string, type: string, required: boolean, help?: string, options?: string[] }[]} */
  function getFields() {
    switch (formType) {
      case "doi-assign":
        return [
          { name: "url", label: "Target URL", type: "url", required: true, help: "The URL this DOI should resolve to" },
          { name: "title", label: "Title (JSON)", type: "json", required: false, help: '{\"en\": \"...\", \"fr\": \"...\"}' },
          { name: "doi_type", label: "DOI Type", type: "text", required: false, help: "external, internal, book, webpage, etc." },
          { name: "metadata", label: "Metadata (JSON)", type: "json", required: false, help: "Type-specific metadata as JSON" },
        ];
      case "doi-modify":
        return [
          { name: "doi", label: "DOI", type: "text", required: true, help: "The DOI to modify" },
          { name: "url", label: "New URL", type: "url", required: false, help: "Leave blank to keep current" },
          { name: "title", label: "Title (JSON)", type: "json", required: false, help: '{\"en\": \"...\"} or leave blank' },
          { name: "doi_type", label: "DOI Type", type: "text", required: false, help: "Leave blank to keep current" },
          { name: "metadata", label: "Metadata (JSON)", type: "json", required: false },
        ];
      case "snippet-assign": {
        // Text/Code/Math toggle switches which fields are shown.
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
      case "snippet-assign":
        return ["snippet", "assign"];
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

  function buildFlags() {
    const flags = {};
    for (const f of fields) {
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
    return flags;
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
    fieldValues = { ...fieldValues, [name]: value };
  }

  let displayTitle = $derived(
    formType === "doi-assign" ? "Assign DOI"
      : formType === "doi-modify" ? "Modify DOI"
      : formType === "snippet-assign" ? "Assign Snippet"
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
          />
        {/if}
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
