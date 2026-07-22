/** Parse user input into tokens, flags, and cursor position.
 *
 * Handles:
 *   "!doi search"            → { tokens:["doi","search"], flags:{}, partial:"" }
 *   "!doi assign --title ..." → { tokens:["doi","assign"], flags:{title:"..."}, partial:"" }
 *   "!doi"                   → { tokens:["doi"], flags:{}, partial:"" }
 *   "!doi "                  → { tokens:["doi"], flags:{}, partial:"" }
 *   "!ac"                    → { tokens:[], flags:{}, partial:"ac" }
 */

/**
 * @param {string} input — the raw input string
 * @returns {{ tokens:string[], flags:Record<string,string>, partial:string }}
 */
export function parseCommand(input) {
  const trimmed = input.trim();
  if (!trimmed || !trimmed.startsWith("!")) {
    return { tokens: [], flags: {}, partial: trimmed.replace(/^!/, "") };
  }

  const withoutBang = trimmed.slice(1).trimStart();
  const tokens = [];
  const flags = {};
  let partial = "";
  let inFlag = null;
  let inQuote = false;
  let current = "";
  let i = 0;

  const trailing = input.endsWith(" ");

  function flush() {
    if (current === "") return;
    if (current.startsWith("--") && inFlag === null) {
      inFlag = current.slice(2);
      current = "";
    } else if (inFlag !== null) {
      flags[inFlag] = current;
      inFlag = null;
      current = "";
    } else {
      tokens.push(current);
      current = "";
    }
  }

  while (i < withoutBang.length) {
    const ch = withoutBang[i];
    const isLast = i === withoutBang.length - 1;

    if (ch === '"') {
      if (inQuote) {
        inQuote = false;
        flush();
      } else {
        inQuote = true;
        if (current !== "") {
          const eqIdx = current.indexOf("=");
          if (current.startsWith("--") && eqIdx > 0) {
            inFlag = current.slice(2, eqIdx);
            current = "";
          } else {
            flush();
          }
        }
      }
    } else if (inQuote) {
      current += ch;
    } else if (ch === " " || ch === "\t") {
      flush();
    } else if (ch === "=" && current.startsWith("--")) {
      inFlag = current.slice(2);
      current = "";
    } else {
      current += ch;
    }
    i++;
  }

  if (inQuote) {
    partial = current;
  } else if (current !== "") {
    if (inFlag !== null) {
      flags[inFlag] = current;
      } else if (current.startsWith("--") && current.length > 2 && trailing) {
        // Complete flag: "--include-expired " (trailing space → no value)
        flags[current.slice(2)] = "";
      } else if (current.startsWith("--")) {
        // Incomplete flag: "--include-expired" (no trailing space)
        partial = current;
    } else if (trailing) {
      tokens.push(current);
    } else {
      partial = current;
    }
  } else if (inFlag !== null) {
    flags[inFlag] = "";
  }

  return { tokens, flags, partial };
}

/**
 * Check if the input has a trailing space.
 */
export function hasTrailingSpace(input) {
  return input.endsWith(" ");
}
