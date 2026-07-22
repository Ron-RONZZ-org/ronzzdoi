/** Command hierarchy — fetched from the backend at startup.
 *
 * The authoritative tree lives in the backend (via @command() decorators)
 * and is served via ``GET /api/v1/command/tree``.
 *
 * There is NO hardcoded fallback — the only source of truth is the backend.
 */

/** @type {CommandNode[]} */
export let commandTree = [];

/**
 * Fetch the authoritative command tree from the backend.
 * Call this once on app startup.
 */
export async function initCommandTree() {
  try {
    const resp = await fetch("/api/v1/command/tree");
    if (resp.ok) {
      commandTree = await resp.json();
    }
  } catch {
    // Tree stays empty until next page load.
    // The app degrades gracefully.
  }
}

/** Build a flat list of all root-level command names. */
export function getRootNames() {
  return commandTree.map((n) => n.name);
}

/** Find the deepest node matching a path of tokens (case-insensitive). */
export function findNode(tokens) {
  let current = commandTree;
  let node = null;
  for (const token of tokens) {
    const matched = current.find(
      (n) => n.name.toLowerCase() === token.toLowerCase(),
    );
    if (!matched) return node;
    node = matched;
    if (!node.children || node.children.length === 0) return node;
    current = node.children;
  }
  return node;
}

/** Get all children that match a prefix (case-insensitive). */
export function matchChildren(nodes, prefix) {
  const p = prefix.toLowerCase();
  return nodes.filter((n) => n.name.toLowerCase().startsWith(p));
}
