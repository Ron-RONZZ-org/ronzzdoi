import { describe, it, expect } from "vitest";
import {
  buildTitle,
  lineToEntry,
  linesToEntries,
  entriesToLines,
  fieldsToMetadata,
  isTranslateableField,
  metadataToFormValues,
  metadataToPrimaryLangs,
  metadataToTranslations,
  parseLanguageMap,
  titleToFormValue,
  titleToTranslations,
  valueToTranslations,
  parseMetadata,
} from "../doiForm.js";

describe("lineToEntry", () => {
  it("maps DOI-prefixed lines to person_doi references", () => {
    expect(lineToEntry("10.ronzz/abc123")).toEqual({ person_doi: "10.ronzz/abc123" });
    expect(lineToEntry("10.9999/xyz")).toEqual({ person_doi: "10.9999/xyz" });
  });

  it("splits multi-word names into given/family", () => {
    expect(lineToEntry("Christopher Nolan")).toEqual({ given: "Christopher", family: "Nolan" });
  });

  it("keeps single-word lines as plain strings", () => {
    expect(lineToEntry("Ada")).toBe("Ada");
  });
});

describe("linesToEntries / entriesToLines", () => {
  it("round-trips person lists through textarea lines", () => {
    const lines = "10.ronzz/abc\nChristopher Nolan";
    const entries = linesToEntries(lines);
    expect(entries).toEqual([
      { person_doi: "10.ronzz/abc" },
      { given: "Christopher", family: "Nolan" },
    ]);
    expect(entriesToLines(entries)).toBe("10.ronzz/abc\nChristopher Nolan");
  });

  it("ignores blank lines", () => {
    expect(linesToEntries("a\n\nb\n")).toEqual(["a", "b"]);
  });

  it("serializes stored entries (person_doi / given-family / plain) to lines", () => {
    expect(entriesToLines([
      { person_doi: "10.ronzz/1" },
      { given: "Ada", family: "Lovelace" },
      "plain",
    ])).toBe("10.ronzz/1\nAda Lovelace\nplain");
  });
});

describe("fieldsToMetadata", () => {
  const bookSchema = [
    { name: "authors", types: ["list"], required: true },
    { name: "title", types: ["str"], required: true },
    { name: "year", types: ["int", "str"], required: true },
    { name: "publisher", types: ["str"], required: true },
    { name: "isbn", types: ["str"], required: false },
  ];

  it("converts list fields and coerces int fields", () => {
    const metadata = fieldsToMetadata(bookSchema, {
      authors: "10.ronzz/a\nAda Lovelace",
      title: "The Great Book",
      year: "2008",
      publisher: "Prentice Hall",
    });
    expect(metadata).toEqual({
      authors: [{ person_doi: "10.ronzz/a" }, { given: "Ada", family: "Lovelace" }],
      title: "The Great Book",
      year: 2008,
      publisher: "Prentice Hall",
    });
  });

  it("keeps non-numeric strings for int-typed fields", () => {
    const metadata = fieldsToMetadata(bookSchema, { year: "2nd ed." });
    expect(metadata).toEqual({ year: "2nd ed." });
  });

  it("omits empty values", () => {
    const metadata = fieldsToMetadata(bookSchema, { title: "Only Title", isbn: "" });
    expect(metadata).toEqual({ title: "Only Title" });
  });

  it("builds language maps for pure-text fields with translations (#47)", () => {
    const metadata = fieldsToMetadata(
      bookSchema,
      { title: "The Great Book", publisher: "Prentice Hall" },
      {
        title: [{ lang: "fr", title: "Le Grand Livre" }],
        publisher: [{ lang: "de", title: "Prentice Hall DE" }],
      },
    );
    expect(metadata).toEqual({
      title: { en: "The Great Book", fr: "Le Grand Livre" },
      publisher: { en: "Prentice Hall", de: "Prentice Hall DE" },
    });
  });

  it("keeps plain strings when translations are empty", () => {
    const metadata = fieldsToMetadata(
      bookSchema,
      { title: "The Great Book", publisher: "Prentice Hall" },
      {},
    );
    expect(metadata.title).toBe("The Great Book");
  });

  it("honours per-field primary languages (#47)", () => {
    const metadata = fieldsToMetadata(
      bookSchema,
      { title: "Le Grand Livre", publisher: "Prentice Hall" },
      { title: [{ lang: "en", title: "The Great Book" }] },
      { title: "fr" },
    );
    expect(metadata.title).toEqual({ fr: "Le Grand Livre", en: "The Great Book" });
  });
});

describe("isTranslateableField", () => {
  it("accepts str-only fields", () => {
    expect(isTranslateableField({ name: "title", types: ["str"] })).toBe(true);
  });

  it("rejects list and int fields", () => {
    expect(isTranslateableField({ name: "authors", types: ["list"] })).toBe(false);
    expect(isTranslateableField({ name: "year", types: ["int", "str"] })).toBe(false);
    expect(isTranslateableField({ name: "year", types: ["str", "int"] })).toBe(false);
  });

  it("rejects missing types", () => {
    expect(isTranslateableField({ name: "x" })).toBe(false);
    expect(isTranslateableField(undefined)).toBe(false);
  });
});

describe("metadataToFormValues", () => {
  const bookSchema = [
    { name: "authors", types: ["list"] },
    { name: "year", types: ["int", "str"] },
    { name: "publisher", types: ["str"] },
  ];

  it("prefills list fields as lines and scalars as strings", () => {
    expect(metadataToFormValues(bookSchema, {
      authors: [{ person_doi: "10.ronzz/1" }],
      year: 2010,
      publisher: "Test Press",
    })).toEqual({
      authors: "10.ronzz/1",
      year: "2010",
      publisher: "Test Press",
    });
  });

  it("returns empty object for missing metadata", () => {
    expect(metadataToFormValues(bookSchema, undefined)).toEqual({});
  });
});

describe("metadataToTranslations", () => {
  const filmSchema = [
    { name: "title", types: ["str"] },
    { name: "directors", types: ["list"] },
    { name: "studio", types: ["str"] },
  ];

  it("extracts per-field translation rows from stored language maps (#47)", () => {
    expect(metadataToTranslations(filmSchema, {
      title: { en: "Inception", fr: "Inception (FR)" },
      studio: "Warner Bros.",
    })).toEqual({
      title: [{ lang: "fr", title: "Inception (FR)" }],
    });
  });

  it("returns empty for plain values", () => {
    expect(metadataToTranslations(filmSchema, { title: "Inception" })).toEqual({});
  });
});

describe("parseLanguageMap / primary language", () => {
  it("treats the first key as primary (default en for legacy data)", () => {
    expect(parseLanguageMap({ en: "Inception", fr: "Inception (FR)" })).toEqual({
      primaryLang: "en",
      primary: "Inception",
      translations: [{ lang: "fr", title: "Inception (FR)" }],
    });
  });

  it("supports non-en primary languages (fr-first maps)", () => {
    expect(parseLanguageMap({ fr: "La Vie en Rose", en: "La Vie en Rose" })).toEqual({
      primaryLang: "fr",
      primary: "La Vie en Rose",
      translations: [{ lang: "en", title: "La Vie en Rose" }],
    });
  });

  it("handles JSON-string and plain-string values", () => {
    expect(parseLanguageMap('{"fr": "Bonjour", "de": "Hallo"}')).toEqual({
      primaryLang: "fr",
      primary: "Bonjour",
      translations: [{ lang: "de", title: "Hallo" }],
    });
    expect(parseLanguageMap("plain title")).toEqual({
      primaryLang: "en",
      primary: "",
      translations: [],
    });
    expect(parseLanguageMap(undefined)).toEqual({
      primaryLang: "en",
      primary: "",
      translations: [],
    });
  });
});

describe("metadataToPrimaryLangs", () => {
  const filmSchema = [
    { name: "title", types: ["str"] },
    { name: "studio", types: ["str"] },
  ];

  it("extracts primary language per field", () => {
    expect(metadataToPrimaryLangs(filmSchema, {
      title: { fr: "La Vie en Rose", en: "La Vie en Rose" },
      studio: "Warner Bros.",
    })).toEqual({ title: "fr" });
  });
});

describe("titleToFormValue", () => {
  it("passes plain titles through", () => {
    expect(titleToFormValue("Inception (2010)")).toBe("Inception (2010)");
  });

  it("extracts the en value from a JSON language map", () => {
    expect(titleToFormValue('{"en": "Inception", "fr": "Inception"}')).toBe("Inception");
  });

  it("handles object titles", () => {
    expect(titleToFormValue({ en: "Inception" })).toBe("Inception");
  });
});

describe("titleToTranslations", () => {
  it("extracts non-primary languages from a language map", () => {
    expect(titleToTranslations({ en: "Inception", fr: "Inception", de: "Inception" })).toEqual([
      { lang: "fr", title: "Inception" },
      { lang: "de", title: "Inception" },
    ]);
  });

  it("handles JSON-string titles", () => {
    expect(titleToTranslations('{"en": "Inception", "fr": "Inception"}')).toEqual([
      { lang: "fr", title: "Inception" },
    ]);
  });

  it("returns empty for plain titles", () => {
    expect(titleToTranslations("Inception")).toEqual([]);
    expect(titleToTranslations(undefined)).toEqual([]);
  });
});

describe("valueToTranslations", () => {
  it("is the generic alias of titleToTranslations for any field (#47)", () => {
    expect(valueToTranslations({ en: "WB", fr: "WB (FR)" })).toEqual([
      { lang: "fr", title: "WB (FR)" },
    ]);
    expect(valueToTranslations("plain")).toEqual([]);
  });
});

describe("buildTitle", () => {
  it("returns a plain string when there are no translations", () => {
    expect(buildTitle("Inception (2010)", [])).toBe("Inception (2010)");
    expect(buildTitle("  Inception  ", [])).toBe("Inception");
  });

  it("builds a language map when translations exist", () => {
    expect(buildTitle("Inception", [
      { lang: "fr", title: "Inception" },
      { lang: "de", title: "Inception" },
    ])).toEqual({ en: "Inception", fr: "Inception", de: "Inception" });
  });

  it("ignores empty translation rows and allows en-less maps", () => {
    expect(buildTitle("", [{ lang: "fr", title: "Inception" }])).toEqual({ fr: "Inception" });
    expect(buildTitle("Inception", [{ lang: " ", title: "" }])).toBe("Inception");
  });
});

describe("parseMetadata", () => {
  it("parses JSON strings into dicts", () => {
    expect(parseMetadata('{"director": {"name": "Nolan"}}')).toEqual({
      director: { name: "Nolan" },
    });
  });

  it("passes dicts through and tolerates bad JSON", () => {
    expect(parseMetadata({ year: 2010 })).toEqual({ year: 2010 });
    expect(parseMetadata("not json")).toEqual({});
    expect(parseMetadata(undefined)).toEqual({});
  });
});
