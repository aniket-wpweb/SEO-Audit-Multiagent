# Day-6 SEO Agent

Run from this directory (`day-6/seo-agent`):

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
playwright install chromium
```

Copy `.env.example` to `.env` and adjust. For SOP labeling without Ollama, set `SOP_RULES_ONLY=1`.

**Auto-fix layout:** With `apply_fixes` and a repo path, `code_modify` resolves `file_hint` using the clone: prefers `src/app` over `app`, maps audited URLs to App Router `page.tsx` / `page.jsx` (or `pages/` / `src/pages/` when no App Router tree exists). It expands targets with a bounded relative-import walk and short evidence substring search so `missing_alt` / `duplicate_h1` can patch imported components, not only route files. `broken_link` gets a best-effort source `file_hint` via search; optional `SEO_AGENT_FIX_BROKEN_LINKS=1` enables a conservative internal-`href` replacement (see `.env.example`).

Embeddings use **sentence-transformers** (OSS). SOP vectors are stored as **JSON + numpy** under `CHROMA_PERSIST_DIR` (no separate ChromaDB server process; this avoids native build issues on Windows while keeping the same RAG-style workflow).

Start API:

```bash
uvicorn main:app --reload --port 8000
```

- Health: `GET http://127.0.0.1:8000/health`
- UI: `http://127.0.0.1:8000/ui/` — **two-step flow:**
  1. **Step 1 — Audit:** Enter **website URL**, **depth** (same-origin crawl depth), and **number of pages** (`max_pages`). Click **Run SEO audit** to see issues in a **table** (no code writes; `apply_fixes` is off).
  2. **Step 2 — Fix:** Enter a **Git clone URL** (`repo_url`, e.g. `https://github.com/org/repo.git` or `git@github.com:org/repo.git`). The server runs **`git clone`** into `.clones/<run-id>/`, checks out branch **`test`**, applies workshop patches, runs **`npm run build`** when files were touched, then **commits locally on `test`**. Set **`SEO_AGENT_GIT_AUTO_PUSH=1`** in `.env` to also run **`git push -u origin test`** after a successful commit (off by default). Requires **`git`** on the server `PATH` and **push-capable credentials** for the remote. For **legacy local paths** only, the API still accepts `repo_root` + `SEO_AGENT_REPO_ALLOWLIST` (not used by the default UI). Optionally check **Dry run** to skip writes. Step activity uses the async job API.
- Analyze (blocking, scripts): `POST http://127.0.0.1:8000/analyze` — same JSON body as below.
- Analyze async (UI): `POST http://127.0.0.1:8000/analyze/async` returns `202` with `{ "job_id", "poll_path" }`. Poll `GET http://127.0.0.1:8000/analyze/jobs/{job_id}?since=N` until `done: true`; append new `events` (pipeline step + state); when finished, `response` matches the blocking `/analyze` JSON and `http_status` is `200` / `400` / `500`. Unauthenticated job store is for **local workshop use only**.

Run `sample-site` for crawling (separate terminal):

```bash
cd sample-site && npm install && npm run dev
```

Example **audit-only** body (Step 1):

```json
{
  "url": "http://127.0.0.1:3000",
  "depth": 1,
  "max_pages": 5,
  "dry_run": false,
  "apply_fixes": false,
  "repo_root": null,
  "repo_url": null
}
```

Example **apply** body (Step 2 — same crawl params + **Git URL**):

```json
{
  "url": "http://127.0.0.1:3000",
  "depth": 1,
  "max_pages": 5,
  "dry_run": false,
  "apply_fixes": true,
  "repo_root": null,
  "repo_url": "https://github.com/org/your-repo.git"
}
```

Example **legacy apply** with local folder (`repo_root` only, mutually exclusive with `repo_url`):

```json
{
  "url": "http://127.0.0.1:3000",
  "depth": 1,
  "max_pages": 5,
  "dry_run": false,
  "apply_fixes": true,
  "repo_root": "sample-site",
  "repo_url": null
}
```

Tests:

```bash
pytest
```

See [../plan.md](../plan.md), [../tasks.md](../tasks.md), and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
