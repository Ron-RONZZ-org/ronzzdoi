import { describe, it, expect } from "vitest";
import { flattenValue, formatKey, pathDepth } from "../formatValue.js";

describe("formatKey", () => {
  it("title-cases snake_case keys", () => {
    expect(formatKey("duration_minutes")).toBe("Duration Minutes");
    expect(formatKey("website_name")).toBe("Website Name");
  });

  it("splits camelCase keys", () => {
    expect(formatKey("accessDate")).toBe("Access Date");
  });

  it("leaves plain words intact", () => {
    expect(formatKey("title")).toBe("Title");
  });
});

describe("pathDepth", () => {
  it("counts dot and bracket separators", () => {
    expect(pathDepth("year")).toBe(0);
    expect(pathDepth("director.name")).toBe(1);
    expect(pathDepth("authors[0].given")).toBe(2);
  });
});

describe("flattenValue", () => {
  it("flattens nested objects into leaf rows", () => {
    const rows = flattenValue({
      director: { name: "Christopher Nolan", type: "person" },
      year: 2010,
      duration_minutes: 148,
    });
    expect(rows).toEqual([
      { path: "director.name", depth: 1, value: "Christopher Nolan" },
      { path: "director.type", depth: 1, value: "person" },
      { path: "year", depth: 0, value: 2010 },
      { path: "duration_minutes", depth: 0, value: 148 },
    ]);
  });

  it("renders arrays of scalars as indexed rows", () => {
    const rows = flattenValue({ languages: ["French", "English"] });
    expect(rows).toEqual([
      { path: "languages[0]", depth: 1, value: "French" },
      { path: "languages[1]", depth: 1, value: "English" },
    ]);
  });

  it("nests arrays of objects", () => {
    const rows = flattenValue({
      authors: [
        { given: "Ada", family: "Lovelace" },
        { person_doi: "10.ronzz/abc" },
      ],
    });
    expect(rows).toEqual([
      { path: "authors[0].given", depth: 2, value: "Ada" },
      { path: "authors[0].family", depth: 2, value: "Lovelace" },
      { path: "authors[1].person_doi", depth: 2, value: "10.ronzz/abc" },
    ]);
  });

  it("renders null/empty values as empty strings", () => {
    expect(flattenValue({ note: null, extra: {} })).toEqual([
      { path: "note", depth: 0, value: "" },
      { path: "extra", depth: 0, value: "" },
    ]);
  });

  it("handles scalar root values", () => {
    expect(flattenValue("plain")).toEqual([{ path: "", depth: 0, value: "plain" }]);
  });
});
