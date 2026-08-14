/**
 * Form field definitions for FormTab.
 *
 * Each field def: `{name, label, type, required, help?, options?, ...}`.
 * Dynamic metadata fields (meta_<name>) are generated from the type
 * schemas served by `GET /api/v1/doi/types`.
 */

import { formatKey } from "./formatValue.js";
import { isTranslateableField } from "./doiForm.js";

/** Dynamic, type-specific metadata fields for the selected doi_type. */
export function metadataFields(typeSchemas, fieldValues) {
  const selected = fieldValues.doi_type || "";
  const schema = typeSchemas[selected];
  if (!schema || schema.length === 0) {
    // No guided schema (e.g. no type selected, or legacy "external").
    // Raw JSON entry is intentionally not offered — see issue #48.
    return [];
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
    translateable: isTranslateableField(f),
  }));
}

/**
 * @param {string} formType — FormTab's `data.form` value.
 * @param {string[]} typeOptions — DOI type names for the autocomplete.
 * @param {Record<string, object[]>} typeSchemas — per-type field schemas.
 * @param {Record<string, string>} fieldValues — current form values.
 * @returns {{ name: string, label: string, type: string, required: boolean, help?: string, options?: string[] }[]}
 */
export function getFields(formType, typeOptions, typeSchemas, fieldValues) {
  switch (formType) {
    case "doi-assign":
      return [
        { name: "url", label: "Target URL", type: "url", required: false, help: "The URL this DOI should resolve to (leave empty for entity DOIs)" },
        { name: "title", label: "Title", type: "text", required: false, translateable: true, help: "Human-readable title" },
        { name: "doi_type", label: "DOI Type", type: "autocomplete", required: false, help: "Select or type a type (book, film, person, …)", options: typeOptions },
        ...metadataFields(typeSchemas, fieldValues),
      ];
    case "doi-modify":
      return [
        { name: "doi", label: "DOI", type: "text", required: true, help: "The DOI to modify" },
        { name: "url", label: "New URL", type: "url", required: false, help: "Leave blank to keep current" },
        { name: "title", label: "Title", type: "text", required: false, translateable: true, help: "Leave blank to keep current" },
        { name: "doi_type", label: "DOI Type", type: "autocomplete", required: false, help: "Leave blank to keep current", options: typeOptions },
        ...metadataFields(typeSchemas, fieldValues),
      ];
    case "snippet-assign": {
      // Text/Code/Math toggle switches which fields are shown.
      const kind = fieldValues.type || "text";
      const fields = [
        { name: "type", label: "Content Type", type: "segmented", required: true, options: ["text", "code", "math"], help: "Text quotation, code snippet, or KaTeX math" },
        { name: "content", label: "Content", type: "textarea", required: true, help: kind === "code" ? "Paste the code snippet" : kind === "math" ? "KaTeX math source (e.g. \\frac{a}{b})" : "The quotation text" },
        { name: "title", label: "Title", type: "text", required: false, translateable: true, help: "Short human-readable title (optional)" },
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
