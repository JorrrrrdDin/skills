# AI Skills

Small, useful agent skills you can try today.

**한국어로 보기:** [README.ko.md](./README.ko.md)

> 바로 써먹을 수 있는 공개 AI 스킬 모음입니다. 연구, 노트 정리, 스킬 공개 패키징처럼 반복되는 AI 작업 방식을 `SKILL.md` 폴더 단위로 모았습니다.

This repo collects public AI workflow skills from my research projects into one place. Each skill is packaged as a folder with a `SKILL.md`, examples, and any scripts or assets it needs.

## Skills

| # | Skill | What it does | Source |
|---|---|---|---|
| 01 | [Super Lab](./01-super-lab/) | Lightweight multi-agent research orchestration for turning a question into structured outputs. | [RESEARCH_PAPERS](https://github.com/JorrrrrdDin/RESEARCH_PAPERS) |
| 02 | [Knowledge Graph Lab](./02-knowledge-graph-lab/) | Maps Markdown/Obsidian notes into center topics, noisy notes, orphans, and cleanup actions. | [knowledge-gravity-lab](https://github.com/JorrrrrdDin/knowledge-gravity-lab) |
| 03 | [Public Skill Launcher](./03-public-skill-launcher/) | Packages an internal skill into a public-ready release with hooks, demos, examples, and safety scrub. | Original |
| 04 | [Skill Sanitizer](./04-skill-sanitizer/) | Pre-share leak scanner — catches secrets, PII, machine paths, and client names *before* you publish a skill, and flags service code to split into plugins. Fail-closed, stdlib-only. | Original |

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
03-public-skill-launcher/
04-skill-sanitizer/
05-next-skill/
```

The numbering keeps the collection easy to browse as it grows.

## Why Star This Repo

- Practical skills, not abstract prompt theory.
- Public-safe versions of research workflows.
- Copyable folders you can adapt quickly.
- More skills will be added over time.

## 한국어 요약

이 저장소는 AI 에이전트에게 바로 복사해서 줄 수 있는 공개 스킬 컬렉션입니다.

- `01-super-lab`: 질문을 여러 관점으로 나누어 가볍게 병렬 연구합니다.
- `02-knowledge-graph-lab`: Markdown/Obsidian 노트를 분석해 중심 주제와 정리 우선순위를 찾습니다.
- `03-public-skill-launcher`: 내부 스킬을 공개 가능한 형태로 포장합니다.
- `04-skill-sanitizer`: 공유 전 누출 스캐너 — 시크릿·개인정보·머신경로·클라이언트명을 공개 *전에* 잡고, 서비스 코드는 plugin 분리를 권고합니다.

한국어 설명은 [README.ko.md](./README.ko.md)에 따로 정리해두었습니다.

## License

Licenses are preserved per skill folder:

- `01-super-lab`: CC BY-NC 4.0, inherited from `RESEARCH_PAPERS`.
- `02-knowledge-graph-lab`: MIT, inherited from `knowledge-gravity-lab`.
- `04-skill-sanitizer`: MIT.

Check each folder's `LICENSE` before reuse.

## Related Projects

- [RESEARCH_PAPERS](https://github.com/JorrrrrdDin/RESEARCH_PAPERS)
- [knowledge-gravity-lab](https://github.com/JorrrrrdDin/knowledge-gravity-lab)
