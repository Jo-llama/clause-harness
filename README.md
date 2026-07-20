# clause-harness

LLM harness for contract clause review, with an eval loop over a CUAD-derived golden set.

## Setup

```bash
uv sync

cp .env.example .env   # then add your Anthropic API key
uv run scripts/test_api.py   # smoke test
```
