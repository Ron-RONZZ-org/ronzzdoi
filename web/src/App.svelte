<script>
  import { tabStore } from "@lightercore/ui/tabStore.svelte.js";
  import { popup } from "@lightercore/ui/popupStore.svelte.js";
  import BannerContainer from "@lightercore/ui/BannerContainer.svelte";
  import { banner } from "@lightercore/ui/bannerStore.svelte.js";
  import TabView from "./lib/TabView.svelte";
  import LoadingPopup from "./lib/LoadingPopup.svelte";
  import AuthBanner from "./lib/AuthBanner.svelte";

  // ── Loading state for command execution ───────────────────────────────
  // Managed via popup.showLoading / popup.close — no separate isLoading.

  // ── Global keyboard shortcuts (handled in TabView) ──────────────────
</script>

<svelte:window onbeforeunload={(e) => {
  // No dirty form guard in v0.1.0
}} />

<main>
  <header class="app-header">
    <span class="app-title">ronzzdoi</span>
    <span class="header-spacer"></span>
  </header>

  <AuthBanner />
  <BannerContainer />
  <TabView />
</main>

<style>
  :global(*) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  :global(:root) {
    --clr-muted: #82829a;
    --clr-sub: #9292aa;
    --clr-dim: #888;
    --clr-kbd: #999;
    --clr-accent: #7c7c9a;
  }
  :global(body) {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  main {
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100%;
  }
  .app-header {
    display: flex;
    align-items: center;
    padding: 0.35rem 0.75rem;
    background: #16162a;
    border-bottom: 1px solid #2a2a3e;
    flex-shrink: 0;
    gap: 0.5rem;
  }
  .app-title {
    font-family: monospace;
    font-size: 0.78rem;
    color: #7c7c9a;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .header-spacer { flex: 1; }
</style>
