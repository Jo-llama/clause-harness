# clause-harness

LLM harness for contract clause review, with an eval loop over a CUAD-derived golden set.

## Setup

```bash
conda create -n clause-harness python=3.12 -y
conda activate clause-harness
pip install -r requirements.txt

cp .env.example .env   # then add your Anthropic API key
python scripts/test_api.py   # smoke test
```
