import { describe, it, expect } from "vitest";
import {
  lineToEntry,
  linesToEntries,
  entriesToLines,
  fieldsToMetadata,
  metadataToFormValues,
  titleToFormValue,
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
