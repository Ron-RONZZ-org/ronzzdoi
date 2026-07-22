/** Command executor — sends parsed commands to POST /api/v1/command.
 *
 * The frontend parses input tokens and sends them to the backend.
 * The backend owns validation, alias resolution, and execution.
 * The frontend only handles autocomplete (local, instant).
 */

import { parseCommand } from "./parser.js";

const COMMAND_ENDPOINT = "/api/v1/command";

/**
 * Derive a dedup id_key from the command response.
 * The backend is stateless regarding UI state — no id_key in the response.
 * See: https://github.com/Ron-RONZZ-org/ronzzdoi/issues/8
 */
export function deriveIdKey(type, data, tokens, flags) {
  if (type === "detail" && data?.doi) return `detail-${data.doi}`;
  if (type === "detail" && data?.citation) return `detail-citation-${tokens[2] || ""}`;
  if (type === "list" && tokens[0] === "doi" && tokens[1] === "search")
    return `list-doi-search-${tokens[2] || ""}-${flags.mode || "semantical"}`;
  if (type === "list" && tokens[0] === "auth") return "list-auth-api-key";
  if (type === "success") return null;
  if (type === "error") return null;
  return null;
}

/**
 * Get auth key from localStorage for API calls.
 */
function getAuthKey() {
  return localStorage.getItem("ronzzdoi_api_key") || "";
}

/**
 * Execute a user !command.
 *
 * @param {string} input — raw user input (e.g. "!doi search --query foo")
 * @returns {{ type: string, title: string, data: any }}
 */
export async function execute(input) {
  const trimmed = input.trim();

  // Only !commands are supported in v0.1.0
  if (!trimmed.startsWith("!")) {
    return {
      type: "error",
      title: "Invalid Input",
      data: {
        message:
          "Type a !command to interact with ronzzdoi. "
          + "Natural language chat is not available in v0.1.0.",
      },
    };
  }

  const { tokens, flags, partial } = parseCommand(trimmed);
  const effectiveTokens = partial ? [...tokens, partial] : tokens;

  if (effectiveTokens.length === 0) {
    return {
      type: "error",
      title: "Error",
      data: { message: "No command specified." },
    };
  }

  try {
    const apiKey = getAuthKey();
    const headers = { "Content-Type": "application/json" };
    if (apiKey) {
      headers["Authorization"] = `Bearer ${apiKey}`;
    }

    const resp = await fetch(COMMAND_ENDPOINT, {
      method: "POST",
      headers,
      body: JSON.stringify({
        tokens: effectiveTokens,
        flags,
        raw_input: input,
      }),
    });

    const ct = resp.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
      const text = await resp.text().catch(() => "");
      return {
        type: "error",
        title: "Backend Error",
        data: {
          message: text
            ? `Backend returned ${ct || "unknown"} content (HTTP ${resp.status})`
            : `Backend returned empty response (HTTP ${resp.status}). Is the backend running?`,
        },
      };
    }

    const data = await resp.json();

    if (!resp.ok) {
      const detail = data.detail || {};
      const msg = typeof detail === "string" ? detail : detail.error || `HTTP ${resp.status}`;
      const suggestion = detail.suggestion || "";
      return {
        type: "error",
        title: "Command Failed",
        data: { message: msg, suggestion },
      };
    }

    return data;
  } catch (err) {
    const msg =
      err.cause?.code === "ECONNREFUSED"
        ? "Cannot connect to the backend. Is the backend running?"
        : `Network error: ${err.message}`;
    return {
      type: "error",
      title: "Connection Error",
      data: { message: msg },
    };
  }
}
