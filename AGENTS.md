# Repository Guidelines

## Project Structure & Module Organization
- Frontend (`src/`): React + TypeScript via Vite. Components in `src/components/*`, state in `src/store`, data mocks in `src/data`, shared types in `src/types`, utilities in `src/utils`, entrypoints `src/main.tsx` and `App.medievalgame.tsx`.
- Backend (`backend/`): Flask API (`backend/app.py`), agents under `backend/agents/*`, game loop scripts (`backend/run_game_loop.py`), Socket.IO/SSE helpers, and SQLite DBs (`backend/game.db`, `game_memory.db`).
- Scripts: `run_dev.sh`, `run_prod.sh` (frontend), `backend/run_api.sh` (backend). Static assets live alongside `index.html` and `index.css`.

## Build, Test, and Development Commands
- Install: `pnpm install`
- Dev (frontend): `pnpm dev` (Vite on `http://localhost:5173`)
- Build: `pnpm build` (TypeScript compile + Vite build)
- Preview: `pnpm preview -- --port 5173`
- Dev (backend): `cd backend && ./run_api.sh` (creates venv, installs `requirements.txt`, serves Flask on `API_PORT` default `8000`)
- Run both during development so the frontend can call `http://localhost:8000/api/*` (CORS is preconfigured for `5173`).

## Coding Style & Naming Conventions
- TypeScript/React: 2‑space indent, strict TS. Components use PascalCase files (e.g., `NPCPanel.tsx`); hooks start with `use*`; stores end with `*Store.ts`; enums/types in `src/types`.
- Python: PEP8 with 4‑space indent; prefer type hints and `@dataclass`. Keep modules small and focused.
- Lint/format: No enforced linters here—use your editor’s formatter. Keep imports ordered and avoid unused code.

## Testing Guidelines
- Backend integration tests: `python test_memory_system.py` and `python test_llm_summarization.py` (ensure `cd backend && pip install -r requirements.txt` first, or run `backend/run_api.sh` once to set up venv).
- Test naming: Python tests follow `test_*.py`. Place new tests in `backend/tests` or repo root consistently.
- Expectations: Include edge cases and ensure deterministic outputs (seed randomness where applicable).

## Commit & Pull Request Guidelines
- Commits: Use Conventional Commits (e.g., `feat(ui): add AgentNetworkBuilder`, `fix(api): handle CORS preflight`). Keep messages imperative and scoped.
- PRs: Clear summary, linked issues, UI screenshots/GIFs when relevant, reproduction steps, and notes on env vars/migrations. Keep diffs focused and include before/after for API or schema changes.

## Security & Configuration Tips
- Copy `backend/.env.example` to `.env` as needed. Important vars: `API_PORT`, `AUTO_REPUTATION_UPDATE`, `REPUTATION_UPDATE_TIMEOUT`, `GAME_AGENT_LLM_CONFIGS`.
- SQLite files are checked in for convenience; avoid committing large local DBs. Prefer new test DBs for experiments.
