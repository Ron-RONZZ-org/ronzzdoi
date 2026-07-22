<script>
  let { message = "Loading…" } = $props();
</script>

<div class="loading">
  <div class="spinner"></div>
  <p class="message">{message}</p>
</div>

<style>
  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    gap: 1rem;
  }
  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid #333;
    border-top-color: #7c7c9a;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .message {
    color: #7c7c9a;
    font-family: monospace;
    font-size: 0.85rem;
  }
</style>
