# Super Lab Lite

> Low-cost multi-model orchestration skill — **1 Opus + 3 Sonnet + 3 Haiku**, 7 agents in parallel. Standalone, no external framework required.

A lightweight 7-agent orchestration for everyday research and analysis. Model tiering brings the cost down to roughly **1/5** of a full-Opus orchestration.

## What it does

| Phase | Tier | Work |
|---|---|---|
| 1 | Opus | Split the request into 3 disjoint domains + design each agent's prompt |
| 2–3 | Haiku ×3 | Gather facts/data per domain, in parallel |
| 4 | Sonnet ×3 | Analyze each domain, in parallel |
| 5 | Opus | Synthesize + QA → final answer |

## Requirements

- Python 3.9+
- `pip install anthropic`
- `ANTHROPIC_API_KEY` environment variable

## Install

### As a Claude Code skill

Copy the `super-lab-lite` folder into your skills directory:

```bash
# macOS / Linux
cp -r super-lab-lite ~/.claude/skills/

# Windows (PowerShell)
Copy-Item -Recurse super-lab-lite "$env:USERPROFILE\.claude\skills\"
```

Or pull it straight from this repo:

```bash
git clone https://github.com/JorrrrrdDin/RESEARCH_PAPERS
cp -r RESEARCH_PAPERS/skills/super-lab-lite ~/.claude/skills/
```

Restart Claude Code → the skill is auto-detected.

### Standalone (plain Python, no Claude Code)

```bash
export ANTHROPIC_API_KEY=your_api_key_here
python scripts/lite_orchestrator.py "Analyze Q1 Korean AI startup trends"
```

Results are written to `./super_lab_lite_runs/{timestamp}_{task}/` (plan, per-domain research/analysis, final synthesis, and a token/cost audit).

## Files

- `SKILL.md` — full skill spec (workflow, model tiering, cost guide)
- `scripts/lite_orchestrator.py` — standalone Python orchestrator
- `scripts/claude_code_runner.md` — Claude Code Agent-tool usage pattern

## Cost (rough)

| Scenario | Cost | vs full-Opus |
|---|---|---|
| Simple (~3K tok/agent) | ~$0.06 | ~1/5 |
| Medium (~10K tok/agent) | ~$0.25 | ~1/5 |
| Large (~30K tok/agent) | ~$0.80 | ~1/5 |

Actual cost scales with prompt/response length.

## License

See the repository `LICENSE`.

---
*v1.0 · standalone multi-model orchestration skill*
