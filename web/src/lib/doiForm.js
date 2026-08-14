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
 * True when a schema field is a pure text field — one that accepts a
 * plain string and nothing else (no list, no int).  These fields are
 * eligible for multilingual translation maps.
 *
 * @param {object} fieldDef — schema field def from `/api/v1/doi/types`.
 * @returns {boolean}
 */
export function isTranslateableField(fieldDef) {
  const types = fieldDef?.types || [];
  return types.includes("str") && !types.includes("list") && !types.includes("int");
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
 * empty values are omitted.  Pure-text fields with translations become
 * language maps with the configured primary language first.
 *
 * @param {object[]} schema — field defs from `/api/v1/doi/types`.
 * @param {Record<string, string>} values — form values keyed by field name.
 * @param {Record<string, {lang: string, title: string}[]>} [translations]
 *   per-field translation rows (language maps for pure-text fields).
 * @param {Record<string, string>} [primaryLangs] — per-field primary
 *   language code (default "en").
 * @returns {Record<string, *>}
 */
export function fieldsToMetadata(schema, values, translations = {}, primaryLangs = {}) {
  const metadata = {};
  for (const fieldDef of schema || []) {
    const raw = values[fieldDef.name];
    if (raw === undefined || raw === null || String(raw).trim() === "") continue;
    if (isListField(fieldDef)) {
      const entries = linesToEntries(String(raw));
      if (entries.length > 0) metadata[fieldDef.name] = entries;
    } else if (isIntField(fieldDef) && String(raw).trim() !== "" && Number.isFinite(Number(raw))) {
      metadata[fieldDef.name] = Number(raw);
    } else if (isTranslateableField(fieldDef) && (translations[fieldDef.name] || []).length > 0) {
      // Multilingual pure-text field → language map (or plain string when
      // only the primary is filled).  Primary language is the first key.
      const primaryLang = primaryLangs?.[fieldDef.name] || "en";
      metadata[fieldDef.name] = buildTitle(
        String(raw),
        translations[fieldDef.name],
        primaryLang,
      );
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
    } else if (isTranslateableField(fieldDef) && isLanguageMap(val)) {
      // Multilingual field → primary language into the input.
      values[fieldDef.name] = languageMapPrimary(val);
    } else if (typeof val === "object") {
      values[fieldDef.name] = JSON.stringify(val);
    } else {
      values[fieldDef.name] = String(val);
    }
  }
  return values;
}

/**
 * Extract per-field translation rows from an existing metadata dict.
 *
 * @param {object[]} schema — field defs from `/api/v1/doi/types`.
 * @param {Record<string, *>} [metadata] — stored metadata dict.
 * @returns {Record<string, {lang: string, title: string}[]>}
 *   translation rows keyed by field name (empty arrays for plain values).
 */
export function metadataToTranslations(schema, metadata) {
  const translations = {};
  for (const fieldDef of schema || []) {
    const val = metadata?.[fieldDef.name];
    if (isTranslateableField(fieldDef) && isLanguageMap(val)) {
      translations[fieldDef.name] = valueToTranslations(val);
    }
  }
  return translations;
}

/**
 * Extract per-field primary language codes from an existing metadata dict.
 *
 * @param {object[]} schema — field defs from `/api/v1/doi/types`.
 * @param {Record<string, *>} [metadata] — stored metadata dict.
 * @returns {Record<string, string>} primary language keyed by field name
 *   (only fields whose stored value is a language map).
 */
export function metadataToPrimaryLangs(schema, metadata) {
  const langs = {};
  for (const fieldDef of schema || []) {
    const val = metadata?.[fieldDef.name];
    if (isTranslateableField(fieldDef) && isLanguageMap(val)) {
      langs[fieldDef.name] = languageMapPrimaryLang(val);
    }
  }
  return langs;
}

/**
 * Parse a stored value into a plain-string prefill value.
 *
 * Multilingual values are language maps (stored as JSON text in the DB);
 * returns the primary language (first key) as the plain input value.
 *
 * @param {*} value — stored value (string or language map).
 * @returns {string}
 */
export function titleToFormValue(value) {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (isLanguageMap(parsed)) {
        return languageMapPrimary(parsed);
      }
    } catch {
      // Not JSON — plain string.
    }
    return value;
  }
  if (isLanguageMap(value)) {
    return languageMapPrimary(value);
  }
  return String(value);
}

/** True when *value* is a non-null, non-array object (a language map). */
export function isLanguageMap(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Primary language code of a language map (first key, else "en"). */
export function languageMapPrimaryLang(map) {
  if (!map) return "en";
  const keys = Object.keys(map);
  return keys.length > 0 ? keys[0] : "en";
}

/** Primary language text of a language map (first entry). */
export function languageMapPrimary(map) {
  return Object.values(map || {})[0] || "";
}

/**
 * Parse a stored multilingual value into `{primaryLang, primary, translations}`.
 *
 * The primary language is the FIRST key of the map (JSON insertion order
 * is preserved) — default "en" when absent.  Legacy maps like
 * `{"en": ..., "fr": ...}` still work (en stays primary).
 *
 * @param {*} value — stored value (string, JSON string, or language map).
 * @returns {{ primaryLang: string, primary: string, translations: {lang: string, title: string}[] }}
 */
export function parseLanguageMap(value) {
  let map = null;
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (isLanguageMap(parsed)) map = parsed;
    } catch {
      // Not JSON — plain string.
    }
  } else if (isLanguageMap(value)) {
    map = value;
  }
  if (!map || Object.keys(map).length === 0) {
    return { primaryLang: "en", primary: "", translations: [] };
  }
  const primaryLang = languageMapPrimaryLang(map);
  const primary = String(languageMapPrimary(map) ?? "");
  const translations = Object.entries(map)
    .filter(([lang]) => lang !== primaryLang)
    .filter(([, text]) => text !== undefined && text !== null)
    .map(([lang, text]) => ({ lang, title: String(text) }));
  return { primaryLang, primary, translations };
}

/**
 * Extract the non-primary translations from a multilingual value.
 *
 * @param {*} value — stored value (string, JSON string, or language map).
 * @returns {{ lang: string, title: string }[]}
 */
export function titleToTranslations(value) {
  return valueToTranslations(value);
}

/**
 * Extract the non-primary translations from a multilingual value.
 *
 * Generic version of `titleToTranslations` for any language-map field.
 * The primary language (first key) is excluded.
 *
 * @param {*} value — stored value (string, JSON string, or language map).
 * @returns {{ lang: string, title: string }[]}
 */
export function valueToTranslations(value) {
  return parseLanguageMap(value).translations;
}

/**
 * Build a field value to submit: a plain string when there are no
 * translations, or a language map `{<primaryLang>: <primary>, <lang>: ...}`
 * when translations exist (the primary text is stored under the first
 * key — default "en", overridable per field).
 *
 * @param {string} primary — primary field text.
 * @param {{ lang: string, title: string }[]} translations
 * @param {string} [primaryLang] — language code of the primary text
 *   (default "en").
 * @returns {string|{en: string, [lang]: string}}
 */
export function buildTitle(primary, translations = [], primaryLang = "en") {
  const primaryText = String(primary || "").trim();
  const extras = (translations || [])
    .filter((t) => t && String(t.lang || "").trim() && String(t.title || "").trim())
    .map((t) => ({ lang: t.lang.trim(), title: String(t.title).trim() }));

  if (extras.length === 0) {
    return primaryText;
  }
  const map = {};
  const lang = String(primaryLang || "en").trim() || "en";
  if (primaryText) map[lang] = primaryText;
  for (const { lang: extraLang, title } of extras) {
    map[extraLang] = title;
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
