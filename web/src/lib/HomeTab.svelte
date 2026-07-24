<script>
  import { tabStore } from "@lightercore/ui/tabStore.svelte.js";
  import { popup } from "@lightercore/ui/popupStore.svelte.js";
  import { execute, deriveIdKey } from "./commandExecutor.js";
  import ChatInput from "./ChatInput.svelte";
  import { hasAuthKey } from "./api.js";

  // Track auth state
  let isAuthenticated = $state(hasAuthKey());

  async function handleSubmit(input) {
    const trimmed = input.trim();
    if (!trimmed) return;

    // Show loading indicator
    popup.showLoading("Executing…");

    try {
      const result = await execute(trimmed);

      if (result.type === "error") {
        popup.show("error", result.title, result.data);
        return;
      }

      // Handle form type — open interactive form tab
      if (result.type === "form") {
        const formData = result.data || {};
        tabStore.open("form", result.title || "Complete Form", {
          form: formData.form,
          initialData: formData.initialData || {},
        }, { idKey: `form-${formData.form}` });
        return;
      }

      // Derive id_key locally from type + data + tokens
      const { tokens, flags } = parseSimple(trimmed);
      const idKey = deriveIdKey(result.type, result.data, tokens, flags);

      if (idKey) {
        // Dedup by idKey: detail or list tabs
        tabStore.open(result.type, result.title, result.data, { idKey });
      } else {
        // Transient: success/status/error
        popup.show(result.type, result.title, result.data);
      }
    } catch (err) {
      popup.show("error", "Error", {
        message: err.message || String(err),
      });
    }
  }

  function parseSimple(input) {
    const trimmed = input.trim();
    if (!trimmed.startsWith("!")) return { tokens: [], flags: {} };
    const withoutBang = trimmed.slice(1).trimStart();
    const parts = withoutBang.split(/\s+/);
    const tokens = [];
    const flags = {};
    let inFlag = null;
    for (const p of parts) {
      if (p.startsWith("--")) {
        if (inFlag) flags[inFlag] = "";
        inFlag = p.slice(2);
      } else if (inFlag) {
        flags[inFlag] = p;
        inFlag = null;
      } else {
        tokens.push(p);
      }
    }
    if (inFlag) flags[inFlag] = "";
    return { tokens, flags };
  }

  // Listen for auth changes (e.g. after !auth api_key create)
  function checkAuth() {
    isAuthenticated = hasAuthKey();
  }

  // Poll for auth changes on mount
  $effect(() => {
    const interval = setInterval(checkAuth, 2000);
    return () => clearInterval(interval);
  });
</script>

<div class="home-tab">
  <div class="brand">
    <h1 class="logo">ronzzdoi</h1>
    <p class="tagline">DOI &amp; Citation Management</p>

    {#if !isAuthenticated}
      <div class="auth-warning">
        <p class="auth-message">
          No API key configured. You need a valid API key to interact with the backend.
        </p>
        <p class="auth-hint">
          Run <code>!auth api_key create --name &lt;name&gt; --permission read_only|edit|admin</code>
          to create a key. You need an existing admin key to create new keys.
        </p>
        <p class="auth-hint">
          Once you have a key, paste it below:
        </p>
        <div class="key-input-row">
          <input
            type="password"
            class="key-input"
            placeholder="Paste your API key (la_...) here"
            onkeydown={(e) => {
              if (e.key === "Enter") {
                const val = e.target.value.trim();
                if (val) {
                  localStorage.setItem("ronzzdoi_api_key", val);
                  isAuthenticated = true;
                }
              }
            }}
          />
          <button
            class="key-set-btn"
            onclick={(e) => {
              const input = e.target.previousElementSibling;
              if (input && input.value.trim()) {
                localStorage.setItem("ronzzdoi_api_key", input.value.trim());
                isAuthenticated = true;
              }
            }}
          >
            Set Key
          </button>
        </div>
      </div>
    {/if}
  </div>

  <!-- Input area -->
  <div class="input-container">
    <ChatInput centered={false} onSubmit={handleSubmit} />
  </div>
</div>

<style>
  .home-tab {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    position: relative;
  }
  .brand {
    text-align: center;
    padding: 2rem 1rem 0.5rem;
    flex-shrink: 0;
  }
  .logo {
    font-size: 1.6rem;
    font-weight: 300;
    color: #7c7c9a;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-family: monospace;
  }
  .tagline {
    font-size: 0.8rem;
    color: #5a5a7a;
    font-family: monospace;
    margin-top: 0.4rem;
  }

  /* ── Auth status ───────────────────────────── */
  .auth-warning {
    max-width: 500px;
    margin: 1rem auto;
    padding: 0.75rem 1rem;
    background: #2a2a1a;
    border: 1px solid #5a5a3a;
    border-radius: 6px;
    text-align: left;
  }
  .auth-message {
    color: #dbdb8f;
    font-size: 0.82rem;
    margin-bottom: 0.5rem;
  }
  .auth-hint {
    color: #999;
    font-size: 0.78rem;
    margin-bottom: 0.4rem;
  }
  .auth-hint code {
    background: #222;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 0.75rem;
    color: #c8c8e8;
  }
  .key-input-row {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .key-input {
    flex: 1;
    padding: 0.5rem 0.6rem;
    background: #16213e;
    border: 1px solid #555;
    color: #e0e0e0;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.82rem;
    outline: none;
  }
  .key-input:focus { border-color: #7c7c9a; }
  .key-set-btn {
    padding: 0.4rem 0.8rem;
    border: 1px solid #4a8a4a;
    border-radius: 4px;
    background: #2a4a3a;
    color: #8fdb9f;
    font-family: monospace;
    font-size: 0.82rem;
    cursor: pointer;
    white-space: nowrap;
  }
  .key-set-btn:hover { background: #3a6a4a; }

  .input-container {
    padding: 0.5rem 1rem 1rem;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    border-top: 1px solid #333;
    background: #1a1a2e;
  }
</style>
