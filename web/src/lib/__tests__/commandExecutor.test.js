import { describe, it, expect } from "vitest";
import { deriveIdKey } from "../commandExecutor.js";

describe("deriveIdKey", () => {
  it("derives idKey for detail with doi", () => {
    const key = deriveIdKey("detail", { doi: "10.ronzz/abc123" }, ["doi", "resolve"], {});
    expect(key).toBe("detail-10.ronzz/abc123");
  });

  it("derives idKey for citation detail", () => {
    const key = deriveIdKey("detail", { citation: true }, ["citation", "show", "10.ronzz/abc"], {});
    expect(key).toBe("detail-citation-10.ronzz/abc");
  });

  it("derives idKey for doi search list", () => {
    const key = deriveIdKey("doi-list", { results: [] }, ["doi", "search", "test"], { mode: "semantical" });
    expect(key).toBe("doi-list-search-test-semantical");
  });

  it("derives idKey for auth list", () => {
    const key = deriveIdKey("list", { keys: [] }, ["auth", "api_key", "list"], {});
    expect(key).toBe("list-auth-api-key");
  });

  it("returns null for success type", () => {
    const key = deriveIdKey("success", { message: "Done" }, [], {});
    expect(key).toBeNull();
  });

  it("returns null for error type", () => {
    const key = deriveIdKey("error", { message: "Failed" }, [], {});
    expect(key).toBeNull();
  });

  it("uses default mode when not specified for doi search", () => {
    const key = deriveIdKey("doi-list", { results: [] }, ["doi", "search"], {});
    expect(key).toBe("doi-list-search--semantical");
  });
});
