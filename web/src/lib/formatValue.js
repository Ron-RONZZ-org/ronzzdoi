/**
 * Human-friendly rendering helpers for DOI metadata.
 *
 * DOI metadata is stored as free-form JSON (e.g. a film's
 * `{"director": {"name": "Christopher Nolan", "type": "person"}, ...}`).
 * `flattenValue()` turns that nested structure into a flat list of leaf
 * rows — each with a humanized path and depth for indentation — so the
 * detail view can render a readable table instead of raw JSON.
 */

/** True for plain objects (not arrays, not null). */
function isObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Depth of a flattened path: number of `.` and `[` separators. */
export function pathDepth(path) {
  if (!path) return 0;
  return (String(path).match(/[.[]/g) || []).length;
}

/**
 * Humanize a metadata key: `snake_case` and `camelCase` → Title Case.
 *
 * @param {string} key
 * @returns {string}
 */
export function formatKey(key) {
  return String(key)
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Flatten a nested metadata value into a list of leaf rows.
 *
 * Each row is `{ path, depth, value }` where:
 *   - `path` is the dotted/indexed path from the root (e.g. `director.name`).
 *   - `depth` is the nesting level (indentation hint).
 *   - `value` is the scalar leaf value (always a string for null/empty).
 *
 * Objects are walked recursively; arrays of scalars become one row per
 * item (`authors[0]`, `authors[1]`), arrays of objects are nested.
 *
 * @param {*} value — metadata value (object, array, or scalar).
 * @param {string} [prefix=""] — path prefix for nested calls.
 * @returns {{ path: string, depth: number, value: * }[]}
 */
export function flattenValue(value, prefix = "") {
  const rows = [];

  function walk(val, path) {
    if (val === null || val === undefined) {
      rows.push({ path, depth: pathDepth(path), value: "" });
    } else if (Array.isArray(val)) {
      if (val.length === 0) {
        rows.push({ path, depth: pathDepth(path), value: "" });
      } else if (val.every((item) => !isObject(item))) {
        // Array of scalars — one row per item.
        val.forEach((item, i) => {
          walk(item, `${path}[${i}]`);
        });
      } else {
        // Array of objects — nested under each index.
        val.forEach((item, i) => {
          walk(item, `${path}[${i}]`);
        });
      }
    } else if (isObject(val)) {
      const entries = Object.entries(val);
      if (entries.length === 0) {
        rows.push({ path, depth: pathDepth(path), value: "" });
      }
      for (const [key, child] of entries) {
        walk(child, path ? `${path}.${key}` : key);
      }
    } else {
      rows.push({ path, depth: pathDepth(path), value: val });
    }
  }

  walk(value, prefix);
  return rows;
}
