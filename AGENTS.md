# AGENTS.md

## Repository Expectations

- This is a Python CLI project for `NovelWriter Agent`.
- Keep the default workflow runnable in mock mode without network access or an API key.
- Do not commit `.env`, local state, cache files, generated logs, or exported novels.
- `.env.example` is safe to commit and must not contain real credentials.
- Prefer small, focused modules under `novelwriter/` instead of putting orchestration into `main.py`.

## Useful Commands

- Smoke test: `python scripts/smoke_test.py`
- CLI help: `python main.py --help`
- List projects: `python main.py list`
- Run sample quality check: `python main.py --project sample-cyber-mystery check 1`

## Validation

Before finishing code changes, run:

```bash
python scripts/smoke_test.py
```

If Python is only available as `python3`, use:

```bash
python3 scripts/smoke_test.py
```

The smoke test creates a temporary project and should not modify committed sample novels.

## Safety Notes

- Real API keys belong in `.env` locally or in Codex/GitHub secret settings, never in tracked files.
- `novels/**/logs/*` and `novels/**/exported_novel.md` are generated outputs and are intentionally ignored.
- Sample project files under `novels/sample-cyber-mystery/` are test fixtures and documentation examples.

