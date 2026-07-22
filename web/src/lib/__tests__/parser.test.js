import { describe, it, expect } from "vitest";
import { parseCommand, hasTrailingSpace } from "../parser.js";

describe("parseCommand", () => {
  it("parses command with no trailing space — last token is partial", () => {
    const result = parseCommand("!doi search");
    // Without trailing space, "search" is treated as partial (still being typed)
    expect(result.tokens).toEqual(["doi"]);
    expect(result.partial).toBe("search");
    expect(result.flags).toEqual({});
  });

  it("parses command with trailing space — last token is complete", () => {
    const result = parseCommand("!doi search ");
    expect(result.tokens).toEqual(["doi", "search"]);
    expect(result.partial).toBe("");
    expect(result.flags).toEqual({});
  });

  it("parses command with flag value", () => {
    const result = parseCommand('!doi assign --title "hello world"');
    expect(result.tokens).toEqual(["doi", "assign"]);
    expect(result.flags.title).toBe("hello world");
  });

  it("parses flag without value with trailing space", () => {
    const result = parseCommand("!auth api_key list --include-expired ");
    expect(result.tokens).toEqual(["auth", "api_key", "list"]);
    expect(result.flags["include-expired"]).toBe("");
  });

  it("treats flag without trailing space as partial", () => {
    const result = parseCommand("!auth api_key list --include-expired");
    expect(result.tokens).toEqual(["auth", "api_key", "list"]);
    expect(result.partial).toBe("--include-expired");
  });

  it("returns partial for incomplete command", () => {
    const result = parseCommand("!do");
    expect(result.tokens).toEqual([]);
    expect(result.partial).toBe("do");
  });

  it("handles trailing space as complete token", () => {
    const result = parseCommand("!doi ");
    expect(result.tokens).toEqual(["doi"]);
    expect(result.partial).toBe("");
  });

  it("returns empty for non-command input", () => {
    const result = parseCommand("plain text");
    expect(result).toEqual({ tokens: [], flags: {}, partial: "plain text" });
  });

  it("handles quoted values with double quotes", () => {
    const result = parseCommand('!doi assign --title "My Title"');
    expect(result.tokens).toEqual(["doi", "assign"]);
    expect(result.flags.title).toBe("My Title");
  });

  it('handles --flag=value syntax', () => {
    const result = parseCommand("!doi search --limit=20");
    expect(result.tokens).toEqual(["doi", "search"]);
    expect(result.flags.limit).toBe("20");
  });

  it("parses multiple flags", () => {
    const result = parseCommand("!doi search --query test --limit 10 ");
    expect(result.tokens).toEqual(["doi", "search"]);
    expect(result.flags.query).toBe("test");
    expect(result.flags.limit).toBe("10");
  });
});

describe("hasTrailingSpace", () => {
  it("detects trailing space", () => {
    expect(hasTrailingSpace("!doi ")).toBe(true);
    expect(hasTrailingSpace("!doi")).toBe(false);
  });
});
