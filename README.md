# ronzzdoi — In-house DOI & Citation Management

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

**ronzzdoi** is the in-house DOI (Digital Object Identifier) and citation management system at ronzz.org. It provides persistent identifiers for external resources (books, films, webpages) and internal documents (circulaire, rulebook, media files), with a citation formatting engine inspired by Zotero and native semantic web federation support.

Part of the [lighter ecosystem](https://github.com/Ron-RONZZ-org).

## Features (v0.1.0)

- **DOI assignment** — generate and assign persistent ronzzDOIs. Entity DOIs (person, abstract_entity, country) have no `target_url`.
- **DOI format** — identifiers follow the pattern `10.ronzz/<suffix>` (opaque by default; country DOIs use `10.ronzz/country/<ISO>` as documented exception)
- **Resolution & redirect** — HTTP redirect from `doi.ronzz.org/10.ronzz/<id>` to target URL with soft redirect support
- **Citation formatting** — read DOI metadata (`doi_type` + `metadata_json`) and produce styled citations in APA, Vancouver, or JSON format
- **Embeddable snippets** — host text quotations, code snippets, and KaTeX math as DOIs (separate `snippets` table); unified search finds them alongside DOIs; public content endpoint feeds HTML embeds on other ronzz sites (rendering in `ronzzdoi-public-web`)
- **17 doc_types** — book, bookSection, scientificPaper, conferencePaper, presentation, report, dataset, webpage, magazineArticle, newspaperArticle, film, podcast, song, media, circulaire, rulebook, document
- **Person/entity resolution** — authors reference person DOIs; formatters resolve names at format time with per-call caching
- **FTS5 full-text search** — search across DOI metadata via SQLite FTS5
- **Semantic search** (v0.2.0) — vector search via sqlite-vec + fastembed (optional `lightersearch` dependency)
- **CLI & Svelte 5 GUI** — dual interfaces following lighterbird patterns

## Planned (v0.2.0)

- Semantic web federation support with SPARQL query acceptance
- Linked data integration

## Architecture

ronzzdoi extends [lightercore](https://github.com/Ron-RONZZ-org/lightercore) for shared infrastructure (`LighterDB`, `CRUDService`, paths, exceptions) and uses [lightersearch](https://github.com/Ron-RONZZ-org/lightersearch) for optional semantic search. Interaction patterns follow [lighterbird](https://github.com/Ron-RONZZ-org/lighterbird).

```
                    ┌─────────────┐
                    │  ronzzdoi   │
                    │  (FastAPI)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │   CLI   │  │   GUI   │  │   LLM   │
        │ (!cmd)  │  │ (Svelte)│  │(natural) │
        └──────────┘ └──────────┘ └──────────┘
              │            │            │
              └────────────┼────────────┘
                           ▼
                    ┌─────────────┐
                    │ lightercore │
                    │ (DB, paths, │
                    │  CRUD, etc) │
                    └─────────────┘
```

## Authentication

ronzzdoi uses **key-only authentication** — no passwords or login forms. Every API request requires an `Authorization: Bearer <key>` header. Keys have three permission tiers:

| Tier | Read ops | Write ops | Auth mgmt |
|------|----------|-----------|-----------|
| `read_only` | ✅ | ❌ | ❌ |
| `edit` | ✅ | ✅ | ❌ |
| `admin` | ✅ | ✅ | ✅ |

## Quick Start

### Prerequisites

Sibling repos required alongside `ronzzdoi/`:

```bash
ls ../lightercore ../lighterauth   # must exist
```

### Install

```bash
uv pip install -e "../lightercore" -e "../lighterauth" -e ".[dev]"
```

### Activate the virtual environment

The install step above puts the `ronzzdoi`, `ronzzdoi-dev`, and `ronzzdoi-server` commands
into the project's `.venv/bin/` directory. Make them available on your PATH:

```bash
source .venv/bin/activate
```

Or run individual commands with `uv run` (no activation needed):

```bash
uv run ronzzdoi --help
```

### Start dev server with seed data

```bash
# With venv activated:
ronzzdoi-dev --seed

# Or without activation:
uv run ronzzdoi-dev --seed
```

This creates an admin API key, a read-only API key, and **8 sample DOIs** (external, book, webpage, film, person, country, circulaire, rulebook), then starts the servers — internal API on `http://127.0.0.1:8011`, public API on `http://127.0.0.1:8012`. Copy the admin key from the output — it's shown only once.

### Use the CLI

Open another terminal and ensure the venv is activated (`source .venv/bin/activate`) or use `uv run`:

```bash
export RONZZDOI_API_KEY="la_a_abc123..."   # the admin key from above

ronzzdoi --help               # show top-level usage
ronzzdoi doi search
ronzzdoi doi search quantum   # matches seeded "Quantum Computing" webpage
ronzzdoi doi assign https://example.com --title "My Example" --type external
ronzzdoi snippet add --type text --content "To be, or not to be…" \
    --source-doi 10.ronzz/<book> --page-start "Act 3"   # embeddable snippet
ronzzdoi snippet add --type code --content "print('hi')" --language python
ronzzdoi snippet view 10.ronzz/<snippet>
ronzzdoi snippet embed 10.ronzz/<snippet>   # prints a copy-paste <iframe> tag
ronzzdoi auth api_key list
ronzzdoi auth api_key create --name "CI key" --permission edit --owner "CI pipeline"
```

### Use the GUI

```bash
cd web && npm install && npm run dev
```

Open `http://127.0.0.1:6025` in your browser, paste your API key, then type `!help`, `!doi search`, etc.

The GUI's **Assign DOI** form offers a type dropdown (autocomplete),
type-specific metadata fields, and optional multilingual titles (an
"Add translations" section; the primary title is stored under `en`);
the **DOI detail** view renders metadata as a readable table (with a
"Copy JSON" button) and the **Copy DOI** button copies a
browser-resolvable URL (`<instance>/10.ronzz/<suffix>`) rather than the
bare identifier.

### Use the CLI against production

Two production API endpoints exist:

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `https://doi-api.ronzz.org` | **read-only** public API (search, resolve, citation, snippet content) | none (rate-limited) |
| `https://doi-admin.ronzz.org` | **write** API (assign/modify DOIs, snippets, API keys) | Bearer API key |

```bash
# Read-only queries (no key needed)
export RONZZDOI_SERVER=https://doi-api.ronzz.org
ronzzdoi doi search
ronzzdoi doi resolve 10.ronzz/<suffix>
ronzzdoi citation show 10.ronzz/<suffix> --style apa

# Writes — point at the admin API with a key from an admin
export RONZZDOI_SERVER=https://doi-admin.ronzz.org
export RONZZDOI_API_KEY="la_a_abc123..."
ronzzdoi doi assign https://example.com --title "My Book" --type book
ronzzdoi snippet add --type text --content "To be, or not to be…" \
    --source-doi 10.ronzz/<book> --page-start "Act 3"
ronzzdoi snippet embed 10.ronzz/<snippet>   # prints the <iframe> tag
```

If you have SSH access to the production server, you can also run the CLI
directly on the server against the local API:

```bash
ssh ronzz-linux-server-2
sudo -u ronzz HOME=/opt/ronzzdoi /opt/ronzzdoi/.venv/bin/ronzzdoi \
  --server http://127.0.0.1:8012 --api-key "la_a_..."    # read-only (public mode)
# or the write API:
sudo -u ronzz HOME=/opt/ronzzdoi /opt/ronzzdoi/.venv/bin/ronzzdoi \
  --server http://127.0.0.1:8011 --api-key "la_a_..."    # writes (internal mode)
```

The CLI reads its server URL from the `RONZZDOI_SERVER` environment variable
(default: `http://127.0.0.1:8011`). Pass `--server <url>` to override inline.

### Use the GUI against production

The Svelte GUI (dev tool) proxies `/api` to a backend. Point it at the
remote **write** API directly (no tunnel needed):

```bash
cd web
RONZZDOI_API_URL=https://doi-admin.ronzz.org npm run dev
# open http://127.0.0.1:6025, paste your API key, type !snippet add …
```

Or use an SSH tunnel against the server's loopback internal API:

```bash
ssh -L 8011:127.0.0.1:8011 ronzz-linux-server-2   # keep this terminal open
cd web && RONZZDOI_PORT=8011 npm run dev
```

### Use the public web

For **read-only** search, browsing, and citation formatting, visit
**[https://doi.ronzz.org](https://doi.ronzz.org)** — no API key required.
Snippet embeds live at `https://doi.ronzz.org/embed/10.ronzz/<suffix>` and
are frameable by any ronzz site. Snippet content is stored as written
(`$$`/`$` stripped for KaTeX math, ``` fences/backticks for code) and
text quotations are stored as raw markdown/HTML, rendered to rich HTML at
display time — re-editing shows exactly what you pasted.

### Canonical DOI URLs

A DOI resolves at **`https://doi.ronzz.org/<doi>`** (e.g.
`https://doi.ronzz.org/10.ronzz/<suffix>`): the public web redirects
external DOIs to their target URL and renders a record page otherwise.
This canonical base is used everywhere, regardless of the API origin that
served the record — so "Copy DOI" in the admin GUI (doi-admin.ronzz.org)
copies `https://doi.ronzz.org/10.ronzz/<suffix>`, never the admin host.

Override the canonical base if needed:

- Backend: `RONZZDOI_RESOLVE_BASE` (default `https://doi.ronzz.org`) —
  controls `resolve_url` in API responses.
- GUI dev: `VITE_RONZZDOI_RESOLVE_BASE` (default `https://doi.ronzz.org`).

### Obtain a production API key

Production API keys are managed by server administrators via the CLI.
The first admin key is created during initial server setup. Contact your
admin to request a key with the appropriate permission level.

## Testing

### Backend unit + integration tests

```bash
# Run all tests (437 backend tests)
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_doi_service.py -v
```

### Frontend component tests

```bash
cd web && npm run test
# 53 tests across 5 test files (parser, commandExecutor, formatValue, doiForm, resolveUrl)
```

### E2E browser smoke test (requires both servers running)

```bash
# Terminal 1: start backend (venv active or uv run)
ronzzdoi-dev
# or: uv run ronzzdoi-dev

# Terminal 2: start frontend
cd web && npm run dev

# Terminal 3: run smoke test
export RONZZDOI_API_KEY="la_..."   # admin key from the ronzzdoi-dev --seed output
cd web
CHROME_PATH=$(npx playwright install --list 2>/dev/null | grep chromium | head -1 | awk '{print $2}') \
  npm run test:e2e
```

The E2E test opens the GUI in headless Chromium, types `!help`, `!doi assign`, `!doi search`, `!citation show`, asserts tabs open with content, and fails on any JS console error. Command-based tests require an authenticated session, so the admin key from `ronzzdoi-dev --seed` must be passed via `RONZZDOI_API_KEY`; when set, the suite additionally verifies the assign-form type dropdown, the human-friendly metadata table, citation loading without auth errors, and resolvable DOI copy URLs.

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/

# Start dev server (full mode, both internal + public APIs)
ronzzdoi-dev            # with venv activated, or:
uv run ronzzdoi-dev     # without activation

# --seed starts dev servers with seed data (creates API keys automatically)

## Deployment

### Production server

| Aspect | Detail |
|--------|--------|
| Server | `ronzz-linux-server-2` (`158.178.193.231`, OCI Ubuntu 24.04) |
| Domain | `https://doi.ronzz.org` (Cloudflare proxied, TLS at edge) |
| User | `ronzz` (system user, no login) |
| Path | `/opt/ronzzdoi` |
| Data | `/opt/ronzzdoi/data/` (SQLite WAL) |
| Service | `ronzzdoi.service` — FastAPI public mode on `127.0.0.1:8012` |
| Dependencies | `lightercore`, `lighterauth`, `lightersearch` cloned to `/opt/` |

### Dependencies

On the server, sibling repos are cloned to `/opt/` alongside the main repo:

| Repo | Path |
|------|------|
| `ronzzdoi` | `/opt/ronzzdoi/` |
| `lightercore` | `/opt/lightercore/` |
| `lighterauth` | `/opt/lighterauth/` |
| `lightersearch` | `/opt/lightersearch/` |

Python dependencies are managed via **uv** and use local path overrides
(`[tool.uv.sources]` in `pyproject.toml`), so all four must be present.

### Reverse proxy

nginx on the server proxies `doi.ronzz.org` → `127.0.0.1:4321` (ronzzdoi-public-web),
which in turn calls the API at `http://127.0.0.1:8012`. Cloudflare handles
TLS termination at the edge (`proxied: true`). A fallback Let's Encrypt cert
is kept on port 443 for direct-IP access.

### Auto-deploy (GitHub Actions)

Every push to `main` triggers `.github/workflows/deploy.yml`:

1. SSH into the server as `ubuntu` (passwordless sudo)
2. `git pull` in `/opt/ronzzdoi`
3. `uv sync --extra public` (installs Python deps including slowapi)
4. `systemctl restart ronzzdoi`

The deploy key is stored as GitHub repo secret `DEPLOY_SSH_KEY` (shared with
ronzzdoi-public-web).

### SSL cert (fallback)

- Issued via acme.sh + Let's Encrypt (DNS-01 challenge via Cloudflare API)
- Auto-renewed daily via `sudo crontab`
- If renewal fails, the main Cloudflare-proxied path is unaffected — only
  direct-IP access over HTTPS breaks. Fix: `acme.sh --renew -d doi.ronzz.org`

## License

AGPL-3.0 — see [LICENSE](LICENSE).
