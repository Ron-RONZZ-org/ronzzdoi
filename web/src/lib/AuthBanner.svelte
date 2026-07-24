<script>
  /**
   * AuthBanner — thin dismissable banner showing authenticated status
   * with a "Clear Key" button.
   *
   * Positioned below the app header, above all content.
   * Only visible when an API key is stored. Dispatches a custom event
   * when the key is cleared so other components can react.
   */
  import { getAuthKey, clearAuthKey } from "./api.js";

  let hasKey = $state(!!getAuthKey());

  function handleClear() {
    clearAuthKey();
    hasKey = false;
    window.dispatchEvent(new CustomEvent("auth-cleared"));
  }

  // React to auth changes from other sources (e.g. key set in HomeTab)
  function checkAuth() {
    hasKey = !!getAuthKey();
  }

  $effect(() => {
    const interval = setInterval(checkAuth, 2000);
    return () => clearInterval(interval);
  });
</script>

{#if hasKey}
  <div class="auth-banner" role="status">
    <span class="auth-banner-icon">✓</span>
    <span class="auth-banner-text">Authenticated</span>
    <button class="auth-clear-btn" onclick={handleClear} title="Remove API key">
      Clear Key
    </button>
  </div>
{/if}

<style>
  .auth-banner {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-family: monospace;
    font-size: 0.7rem;
    flex-shrink: 0;
  }
  .auth-banner-icon {
    color: #8fdb9f;
    font-size: 0.72rem;
  }
  .auth-banner-text {
    color: #8fdb9f;
  }
  .auth-clear-btn {
    background: transparent;
    border: 1px solid #5a3a3a;
    border-radius: 3px;
    color: #db8f8f;
    font-family: monospace;
    font-size: 0.65rem;
    padding: 0.05rem 0.35rem;
    cursor: pointer;
    transition: background 0.1s;
  }
  .auth-clear-btn:hover {
    background: #3a1e1e;
  }
</style>
