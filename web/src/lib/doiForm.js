/**
 * DOI assign/modify form helpers.
 *
 * The assign form previously exposed `doi_type` as free text and
 * `metadata` as a raw JSON textarea.  These helpers back a
 * human-friendly replacement: a type dropdown (native `<datalist>`
 * autocomplete) and type-specific metadata inputs rendered from the
 * schemas served by `GET /api/v1/doi/types`.
 *
 * Person-list fields (authors, directors, …) are edited as a textarea
 * with one person per line — either a person DOI (`10.ronzz/...`) or an
 * inline name (`Given Family`).  `fieldsToMetadata()` converts the lines
 * to the canonical entry shapes the citation formatter understands.
 */

/** True when a schema field def declares the `list` type. */
export function isListField(fieldDef) {
  return (fieldDef.types || []).includes("list");
}

/** True when a schema field def declares the `int` type. */
export function isIntField(fieldDef) {
  return (fieldDef.types || []).includes("int");
}

/**
 * Convert a single person-list entry to its textarea line form.
 *
 * @param {*} entry — `{person_doi}` reference, `{given, family}` inline
 *   author, or a plain string.
 * @returns {string}
 */
export function entryToLine(entry) {
  if (!entry) return "";
  if (typeof entry === "string") return entry;
  if (entry.person_doi) return entry.person_doi;
  const given = entry.given || entry.first_name || "";
  const family = entry.family || entry.last_name || "";
  const name = [given, family].filter(Boolean).join(" ");
  return name || JSON.stringify(entry);
}

/**
 * Convert a textarea line to a canonical list entry.
 *
 * A line starting with a DOI prefix becomes `{person_doi: ...}`; a line
 * with multiple words becomes a CSL-style `{given, family}` inline
 * author; a single word is kept as-is.
 *
 * @param {string} line
 * @returns {*}
 */
export function lineToEntry(line) {
  const trimmed = line.trim();
  if (/^10\.\w+\//.test(trimmed)) {
    return { person_doi: trimmed };
  }
  const idx = trimmed.lastIndexOf(" ");
  if (idx > 0) {
    return {
      given: trimmed.slice(0, idx).trim(),
      family: trimmed.slice(idx + 1).trim(),
    };
  }
  return trimmed;
}

/**
 * Convert a person-list textarea value into a list of entries.
 *
 * @param {string} text — textarea content, one person per line.
 * @returns {*[]}
 */
export function linesToEntries(text) {
  return String(text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map(lineToEntry);
}

/**
 * Convert an existing list value (from a stored record) into textarea lines.
 *
 * @param {*} value — array of entries or a plain string.
 * @returns {string}
 */
export function entriesToLines(value) {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  if (!Array.isArray(value)) return JSON.stringify(value);
  return value.map(entryToLine).filter(Boolean).join("\n");
}

/**
 * Assemble a `metadata` dict from the dynamic per-field form values.
 *
 * List fields are parsed from textarea lines; integer-typed fields are
 * coerced to numbers when the input is numeric (plain strings are kept);
 * empty values are omitted.
 *
 * @param {object[]} schema — field defs from `/api/v1/doi/types`.
 * @param {Record<string, string>} values — form values keyed by field name.
 * @returns {Record<string, *>}
 */
export function fieldsToMetadata(schema, values) {
  const metadata = {};
  for (const fieldDef of schema || []) {
    const raw = values[fieldDef.name];
    if (raw === undefined || raw === null || String(raw).trim() === "") continue;
    if (isListField(fieldDef)) {
      const entries = linesToEntries(String(raw));
      if (entries.length > 0) metadata[fieldDef.name] = entries;
    } else if (isIntField(fieldDef) && String(raw).trim() !== "" && Number.isFinite(Number(raw))) {
      metadata[fieldDef.name] = Number(raw);
    } else {
      metadata[fieldDef.name] = raw;
    }
  }
  return metadata;
}

/**
 * Prefill dynamic per-field values from an existing metadata dict.
 *
 * @param {object[]} schema — field defs from `/api/v1/doi/types`.
 * @param {Record<string, *>} [metadata] — stored metadata dict.
 * @returns {Record<string, string>} form values keyed by field name.
 */
export function metadataToFormValues(schema, metadata) {
  const values = {};
  for (const fieldDef of schema || []) {
    const val = metadata?.[fieldDef.name];
    if (val === undefined || val === null) continue;
    if (isListField(fieldDef)) {
      values[fieldDef.name] = entriesToLines(val);
    } else if (typeof val === "object") {
      values[fieldDef.name] = JSON.stringify(val);
    } else {
      values[fieldDef.name] = String(val);
    }
  }
  return values;
}

/**
 * Parse the stored title into a plain-string prefill value.
 *
 * Titles are plain strings, but multilingual titles are language maps
 * (`{"en": "...", "fr": "..."}` — stored as JSON text).  Returns the
 * primary language (`en`, falling back to the first entry) as the plain
 * input value.
 *
 * @param {*} title — stored title (string or language map).
 * @returns {string}
 */
export function titleToFormValue(title) {
  if (title === undefined || title === null) return "";
  if (typeof title === "string") {
    try {
      const parsed = JSON.parse(title);
      if (isLanguageMap(parsed)) {
        return parsed.en || Object.values(parsed)[0] || "";
      }
    } catch {
      // Not JSON — plain title.
    }
    return title;
  }
  if (isLanguageMap(title)) {
    return title.en || Object.values(title)[0] || "";
  }
  return String(title);
}

/** True when *value* is a non-null, non-array object (a language map). */
function isLanguageMap(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Extract the non-primary translations from a multilingual title.
 *
 * @param {*} title — stored title (string, JSON string, or language map).
 * @returns {{ lang: string, title: string }[]}
 */
export function titleToTranslations(title) {
  let map = null;
  if (typeof title === "string") {
    try {
      const parsed = JSON.parse(title);
      if (isLanguageMap(parsed)) map = parsed;
    } catch {
      return [];
    }
  } else if (isLanguageMap(title)) {
    map = title;
  }
  if (!map) return [];
  return Object.entries(map)
    .filter(([lang, text]) => lang !== "en" && text !== undefined && text !== null)
    .map(([lang, text]) => ({ lang, title: String(text) }));
}

/**
 * Build the title value to submit: a plain string when there are no
 * translations, or a language map `{en: <primary>, <lang>: ...}` when
 * translations exist (the primary title is stored under "en").
 *
 * @param {string} primary — primary title text.
 * @param {{ lang: string, title: string }[]} translations
 * @returns {string|{en: string, [lang]: string}}
 */
export function buildTitle(primary, translations = []) {
  const primaryText = String(primary || "").trim();
  const extras = (translations || [])
    .filter((t) => t && String(t.lang || "").trim() && String(t.title || "").trim())
    .map((t) => ({ lang: t.lang.trim(), title: String(t.title).trim() }));

  if (extras.length === 0) {
    return primaryText;
  }
  const map = {};
  if (primaryText) map.en = primaryText;
  for (const { lang, title } of extras) {
    map[lang] = title;
  }
  return map;
}

/**
 * Parse a stored metadata value into a dict, handling string or dict.
 *
 * @param {*} metadata — stored metadata (dict or JSON string).
 * @returns {Record<string, *>}
 */
export function parseMetadata(metadata) {
  if (metadata === undefined || metadata === null) return {};
  if (typeof metadata === "object") return metadata;
  if (typeof metadata === "string") {
    try {
      const parsed = JSON.parse(metadata);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  }
  return {};
}
