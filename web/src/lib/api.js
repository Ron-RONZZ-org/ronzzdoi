/** Thin fetch() wrapper for ronzzdoi REST API with Auth header injection. */

const BASE = "/api/v1";

const BACKEND_HELP =
  "Is the Python backend running? Run `uv run python -m ronzzdoi` in another terminal.";

// ── Auth key management (localStorage) ──────────────────────────────────

const AUTH_KEY_STORAGE = "ronzzdoi_api_key";

export function getAuthKey() {
  return localStorage.getItem(AUTH_KEY_STORAGE) || "";
}

export function setAuthKey(key) {
  localStorage.setItem(AUTH_KEY_STORAGE, key);
}

export function clearAuthKey() {
  localStorage.removeItem(AUTH_KEY_STORAGE);
}

export function hasAuthKey() {
  return !!getAuthKey();
}

// ── API request helper ───────────────────────────────────────────────────

async function request(method, path, body = null, opts = {}) {
  const apiKey = getAuthKey();
  const headers = { "Content-Type": "application/json" };
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }

  const fetchOpts = { method, headers };
  if (body !== null) {
    fetchOpts.body = JSON.stringify(body);
  }
  if (opts.signal) {
    fetchOpts.signal = opts.signal;
  }

  // GET requests get retry with backoff for transient failures
  let resp;
  try {
    if (method === "GET" && opts.retry !== false) {
      resp = await fetchWithRetry(`${BASE}${path}`, fetchOpts);
    } else {
      resp = await fetch(`${BASE}${path}`, fetchOpts);
    }
  } catch (err) {
    const msg =
      err.cause?.code === "ECONNREFUSED"
        ? `Cannot connect to the backend server. ${BACKEND_HELP}`
        : `Network error: ${err.message}. ${BACKEND_HELP}`;
    const e = new Error(msg);
    e.code = "CONNECTION_REFUSED";
    e.status = 0;
    throw e;
  }

  if (resp.status === 204) return null;

  let data;
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    try {
      data = await resp.json();
    } catch {
      data = null;
    }
  } else {
    const text = await resp.text();
    if (resp.status === 502 || resp.status === 504) {
      const e = new Error(
        `Backend server not reachable (HTTP ${resp.status}). ${BACKEND_HELP}`,
      );
      e.code = "BACKEND_UNREACHABLE";
      e.status = resp.status;
      throw e;
    }
    data = {
      error: text
        ? `Server returned ${ct || "unknown"} content (HTTP ${resp.status})`
        : `Server returned empty response (HTTP ${resp.status}). ${BACKEND_HELP}`,
    };
  }

  if (!resp.ok) {
    let msg;
    if (Array.isArray(data?.detail)) {
      msg = data.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    } else if (typeof data?.detail === "object" && data?.detail !== null) {
      msg = data.detail.error || data.detail.message || JSON.stringify(data.detail);
    } else {
      msg = data?.detail;
    }
    const err = new Error(data?.error || msg || `HTTP ${resp.status}`);
    err.code = data?.code || "UNKNOWN";
    err.suggestion = data?.suggestion || BACKEND_HELP;
    err.status = resp.status;
    throw err;
  }

  return data;
}

async function fetchWithRetry(url, options, retries = 3, baseBackoff = 500) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const resp = await fetch(url, options);
      if (resp.status >= 500 && resp.status < 600 && attempt < retries) {
        await sleep(baseBackoff * 2 ** attempt);
        continue;
      }
      return resp;
    } catch (err) {
      if (attempt < retries) {
        await sleep(baseBackoff * 2 ** attempt);
        continue;
      }
      throw err;
    }
  }
  throw new Error("Request failed after retries");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Domain-specific API wrappers ───────────────────────────────────────

export const doiApi = {
  assign: (data) => request("POST", "/doi", data, { retry: false }),

  resolve: (doi) => request("GET", `/doi/${encodeURIComponent(doi)}`),

  modify: (doi, data) =>
    request("PATCH", `/doi/${encodeURIComponent(doi)}`, data, { retry: false }),

  merge: (source, target) =>
    request("POST", `/doi/${encodeURIComponent(source)}/merge`, { target_doi: target }, { retry: false }),

  delete: (doi) =>
    request("DELETE", `/doi/${encodeURIComponent(doi)}`, null, { retry: false }),

  search: (params = {}) => {
    const q = new URLSearchParams();
    if (params.query) q.set("query", params.query);
    if (params.limit) q.set("limit", String(params.limit));
    if (params.offset) q.set("offset", String(params.offset));
    if (params.mode) q.set("mode", params.mode);
    return request("GET", `/doi/search?${q}`);
  },
};

export const citationApi = {
  show: (doi, style = "apa") =>
    request("GET", `/citation/${encodeURIComponent(doi)}?style=${style}`),

  styles: (doi) => request("GET", `/citation/${encodeURIComponent(doi)}/styles`),
};

export const authApi = {
  health: () => request("GET", "/health"),
};

// ── Command dispatch ────────────────────────────────────────────────────

/**
 * Execute a !command via POST /api/v1/command.
 * This is the universal command endpoint used by the command executor.
 */
export async function executeCommand(tokens, flags = {}, rawInput = "") {
  return request("POST", "/command", { tokens, flags, raw_input: rawInput });
}
