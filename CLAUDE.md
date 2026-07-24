# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Collects data from public-data (OGD) REST APIs and MCP servers, stores it in a single Excel workbook, and shows it in a Streamlit dashboard. Currently focused on a real-estate location-analysis dashboard backed by a vendored MCP server plus a couple of directly-called public APIs.

`docs/implementation.md` is the authoritative, kept-up-to-date reference for how things actually work (feature flows, external API keys, known gotchas). `docs/architecture.md` and `docs/requirements.md` are the original design docs and are ahead of / aspirational relative to the code in places — prefer `implementation.md` and the code itself when they disagree. **When you change behavior described in `docs/implementation.md`, update that doc in the same change.**

## Commands

```bash
# install deps (uv-managed project, Python 3.14)
uv sync

# run the Streamlit dashboard
uv run streamlit run src/ogd_integrated_view/dashboard/app.py

# run the CLI batch collector (refreshes data/ogd_integrated.xlsx)
uv run python -m ogd_integrated_view.main
```

There is no lint/test tooling configured in this repo currently — don't assume `pytest`/`ruff` exist.

**Always run modules with `-m` (`python -m ogd_integrated_view.main`), never by file path (`python src/.../main.py`).** Running by path puts that file's own directory on `sys.path[0]`, and since `src/ogd_integrated_view/mcp/` is a local subpackage, a bare `from mcp import ClientSession` silently resolves to the local package instead of the third-party `mcp` SDK. The project is already installed editable into `.venv` (see `_editable_impl_ogd_integrated_view.pth`), so `-m` works out of the box.

## Architecture

```
[apis/definitions/*.py]  ─┐
                          ├→ collectors/collector.py → storage/repository.py (xlsx) → dashboard/app.py (Streamlit)
[mcp/definitions/*.py + data/mcp_servers.json]─┘
```

- **Definition-per-file, auto-registered.** Adding a new REST API or MCP server means adding one file under `apis/definitions/` or `mcp/definitions/` subclassing `ApiDefinition` / `McpServerDefinition` — never touch registration code. `apis/registry.py` / `mcp/registry.py` scan those packages with `pkgutil.iter_modules` and pick up every subclass. MCP servers registered at runtime through the Settings tab are stored in `data/mcp_servers.json` (git-ignored) and merged in by `mcp/registry.py:discover_mcp_servers()` alongside the hardcoded definitions — `mcp/definitions/` is currently empty in practice; the one MCP server actually used (A2A-MCP-RealEstate) is registered this way, matched by `role="location_analysis"`.
- **Storage is Excel only, no DB.** `storage/repository.py` wraps pandas read/write over `data/ogd_integrated.xlsx`, one sheet per source. Default write mode is append; `collectors/collector.py:refresh_api()` does a full sheet replace instead (used by the crosswalk "최신화" button).
- **Two independent entry points**, both driven by the same definitions/registries: `main.py` (CLI, batch collect via `collect_all()`) and `dashboard/app.py` (Streamlit, reads via `repository.py` and also calls MCP tools live for the location-analysis tab).
- **The real MCP work happens in a vendored, separate repo**: `vendor/A2A-MCP-RealEstate` (FastMCP stdio server, its own `.venv`, its own git history, excluded via `.gitignore`). Fixes to its tool logic (e.g. real-estate transaction lookup) live in that repo, not this one — check whether a change belongs there before editing wrapper code here. `mcp/client.py` is the generic stdio client (`call_tool`); `mcp/agent.py` (Claude) and `mcp/local_agent.py` (Ollama) are near-identical tool-use loop wrappers around it (max 6 rounds) used by the dashboard's free-form chat.
- **`mcp/location_pipeline.py:analyze_all()`** is a fixed, non-LLM pipeline (not tool-calling) used by the dashboard's address-search form: resolve address → `analyze_location` → `find_nearby_facilities` per category → `get_nearby_apartment_transactions` → `commercial_district.py` (public-data API, not an MCP tool) for 상권 counts. This is distinct from the chat path, which lets an LLM agent choose tools freely.
- **Small-model defensive sanitization**: `dashboard/backend.py` / the agent modules sanitize LLM-produced tool arguments (region codes, date ranges, dong names) before calling tools, because small local models frequently hallucinate plausible-looking but wrong values — see `docs/implementation.md` §3-2 before changing this logic, it encodes several found-in-production bugs.
- **`mcp/hogangnono_scraper.py`** is Playwright browser automation, not an MCP server — it drives real hogangnono.com pages to capture resident-review AI summaries. Login only ever captures session cookies from a real user-driven Kakao login (never handles credentials), and there's a documented headless-bot-detection workaround (`_stealth_user_agent`/`_STEALTH_INIT_SCRIPT`) that may need updating if hogangnono changes detection. Read `docs/implementation.md` §6 before touching this file — it lists several non-obvious failure modes (session expiry vs. "no review data" vs. transient timeout must be handled differently).
- **Region-name matching is exact-token, not substring** (`mcp/region_lookup.py`) — a previous substring-based version matched "강남구" inside "경상북도 포항시 남구" because "남구" is a substring of "강남구". Don't revert to substring matching.

## Secrets / config

- `.env` (git-ignored, see `.env.example`) holds API keys read via `python-dotenv`.
- `data/mcp_servers.json` and `data/app_settings.json` (both git-ignored) hold runtime-registered MCP servers and LLM/Kakao settings configured through the dashboard's Settings tab, not through code.
- The dashboard's location-analysis tab needs at least the A2A-MCP-RealEstate server registered (MOLIT key required; Naver/Kakao keys optional but disable related features if absent) — without it, the chat falls back to a mockup response.
