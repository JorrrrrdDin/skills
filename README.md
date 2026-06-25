# AI Skills

Small, useful agent skills you can try today.

This repo collects public AI workflow skills from my research projects into one place. Each skill is packaged as a folder with a `SKILL.md`, examples, and any scripts or assets it needs.

## Skills

| # | Skill | What it does | Source |
|---|---|---|---|
| 01 | [Super Lab](./01-super-lab/) | Lightweight multi-agent research orchestration for turning a question into structured outputs. | [RESEARCH_PAPERS](https://github.com/JorrrrrdDin/RESEARCH_PAPERS) |
| 02 | [Knowledge Graph Lab](./02-knowledge-graph-lab/) | Maps Markdown/Obsidian notes into center topics, noisy notes, orphans, and cleanup actions. | [knowledge-gravity-lab](https://github.com/JorrrrrdDin/knowledge-gravity-lab) |

## Quick Start

Clone this repo and copy a skill folder into your agent's skills directory.

```bash
git clone https://github.com/JorrrrrdDin/skills.git
```

Then use the skill by name in your agent workflow:

```text
Use the Knowledge Graph Lab skill to analyze this notes folder.
Use the Super Lab skill to structure this research question.
```

## Folder Pattern

New skills will follow this style:

```text
01-super-lab/
02-knowledge-graph-lab/
03-next-skill/
```

The numbering keeps the collection easy to browse as it grows.

## Why Star This Repo

- Practical skills, not abstract prompt theory.
- Public-safe versions of research workflows.
- Copyable folders you can adapt quickly.
- More skills will be added over time.

## License

Licenses are preserved per skill folder:

- `01-super-lab`: CC BY-NC 4.0, inherited from `RESEARCH_PAPERS`.
- `02-knowledge-graph-lab`: MIT, inherited from `knowledge-gravity-lab`.

Check each folder's `LICENSE` before reuse.

## Related Projects

- [RESEARCH_PAPERS](https://github.com/JorrrrrdDin/RESEARCH_PAPERS)
- [knowledge-gravity-lab](https://github.com/JorrrrrdDin/knowledge-gravity-lab)
