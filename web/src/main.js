import App from "./App.svelte";
import { mount } from "svelte";
import { initCommandTree } from "./lib/commandTree.js";

// Fetch the command tree on startup for autocomplete.
// The tree is fetched asynchronously — the UI start rendering immediately
// and autocomplete activates when the response arrives.
initCommandTree();

const app = mount(App, { target: document.getElementById("app") });

export default app;
