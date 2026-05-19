# Day-6 SEO Agent (Git-only fixer)

Crawl a **live website URL**, audit SEO issues, clone a **Git repository**, apply fixes with **`seo_fix`** (rules + optional OpenAI), verify build when applicable, and **commit** on a working branch.

## Setup

```bash
cd day-6/seo-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
```

Configure in `.env`:

- **`SEO_FIX_PROVIDER`**: `chain` (default), `rules`, or `openai`
- **`SEO_FIX_API_KEY`**: required for OpenAI-compatible fixes in `chain`/`openai` modes
- **`SEO_AGENT_GIT_BRANCH`**: branch after clone (default `seo-fixes`)
- **`SOP_RULES_ONLY=1`**: skip Ollama for SOP labels (recommended)

## Run API

```bash
uvicorn main:app --host 127.0.0.1 --port 8030
```

- UI: http://127.0.0.1:8030/ui/
- **Step 1:** Audit — URL + crawl limits (`apply_fixes: false`)
- **Step 2:** Apply — `repo_url` + optional re-audit / LLM review

The site you crawl must be built from the repo you clone (or redeploy after apply for the audit to clear).

## API example (apply)

```json
{
  "url": "https://example.com",
  "depth": 1,
  "max_pages": 5,
  "dry_run": false,
  "apply_fixes": true,
  "repo_url": "https://github.com/org/your-site.git",
  "git_branch": null,
  "reaudit_after_apply": false,
  "llm_apply_review": false
}
```

## Pipeline

`pre_validation` (clone) → `crawl` → `detect_stack` → `seo_audit` → `sop_validate` → **`seo_fix`** → post-build (if Node) → git commit → `format_results`

## Tests

```bash
pytest tests/ -q
```
