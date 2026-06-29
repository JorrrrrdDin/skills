# AI Skills

바로 써먹을 수 있는 공개 AI 스킬 모음.

AI 에이전트에게 “더 잘 일하는 습관”을 폴더째로 주고 싶을 때 쓰는 컬렉션입니다. 각 스킬은 `SKILL.md`를 중심으로 구성되어 있고, 필요한 경우 스크립트, 예시, 에셋까지 함께 들어 있습니다.

[English README](./README.md)

## 왜 만들었나

좋은 AI 사용법은 긴 프롬프트 하나보다, 반복 가능한 작업 방식으로 남을 때 힘이 생깁니다.

이 저장소는 그런 작업 방식을 공개 가능한 형태로 모아둔 곳입니다. 연구, 노트 정리, 스킬 패키징처럼 실제로 자주 쓰는 워크플로우를 작게 나누고, 복사해서 바로 실험할 수 있게 만들었습니다.

## 들어있는 스킬

| # | 스킬 | 한 줄 설명 | 원본 |
|---|---|---|---|
| 01 | [Super Lab](./01-super-lab/) | 질문 하나를 여러 관점으로 쪼개고, 가볍게 병렬 연구해서 구조화된 결과로 합치는 스킬 | [RESEARCH_PAPERS](https://github.com/JorrrrrdDin/RESEARCH_PAPERS) |
| 02 | [Knowledge Graph Lab](./02-knowledge-graph-lab/) | Markdown/Obsidian 노트를 분석해서 중심 주제, 잡음, 고립 노트, 정리 우선순위를 찾아주는 스킬 | [knowledge-gravity-lab](https://github.com/JorrrrrdDin/knowledge-gravity-lab) |
| 03 | [Public Skill Launcher](./03-public-skill-launcher/) | 내부 스킬을 공개 가능한 형태로 포장하고, 훅/데모/예시/안전 스크럽까지 정리하는 스킬 | Original |
| 04 | [Skill Sanitizer](./04-skill-sanitizer/) | 스킬을 공개하기 *전에* 시크릿·개인정보·머신경로·클라이언트명 누출을 잡고, 서비스 코드는 plugin 분리를 권고하는 스캐너. fail-closed, 의존성 없음 | Original |

## 빠른 시작

```bash
git clone https://github.com/JorrrrrdDin/skills.git
```

원하는 스킬 폴더를 에이전트의 skills 디렉터리에 복사한 뒤 이렇게 요청하면 됩니다.

```text
Use the Knowledge Graph Lab skill to analyze this notes folder.
Use the Super Lab skill to structure this research question.
Use the Public Skill Launcher skill to package this workflow for GitHub.
```

## 이런 사람에게 좋습니다

- AI 에이전트용 스킬을 모아보고 싶은 사람
- Obsidian/Markdown 노트가 커져서 정리 우선순위가 필요한 사람
- 리서치 질문을 여러 관점으로 나누어 보고 싶은 사람
- 내부 프롬프트나 작업 방식을 공개용 스킬로 다듬고 싶은 사람
- “프롬프트 모음”보다 재사용 가능한 작업 폴더를 선호하는 사람

## 폴더 규칙

```text
01-super-lab/
02-knowledge-graph-lab/
03-public-skill-launcher/
04-skill-sanitizer/
05-next-skill/
```

번호를 붙여서 하나씩 늘려갑니다. 나중에 스킬이 많아져도 처음 온 사람이 어디서 시작할지 바로 알 수 있게 하기 위해서입니다.

## 별을 눌러두면 좋은 이유

- 새 공개 스킬이 추가될 때 바로 찾을 수 있습니다.
- 연구용, 노트용, 공개 패키징용 스킬을 한 곳에서 볼 수 있습니다.
- 각 스킬은 복사해서 바로 실험할 수 있는 폴더 단위입니다.
- 내부용 전체 버전이 아니라, 공개해도 안전한 핵심 워크플로우만 담습니다.

## 공개 경계

이 저장소는 공개용입니다. 그래서 각 스킬은 유용한 핵심만 담고, 비공개 데이터, 자격증명, 내부 튜닝값, 보호해야 할 구현 세부사항은 포함하지 않습니다.

## 라이선스

각 스킬 폴더의 라이선스를 따릅니다.

- `01-super-lab`: CC BY-NC 4.0, `RESEARCH_PAPERS`에서 상속
- `02-knowledge-graph-lab`: MIT, `knowledge-gravity-lab`에서 상속
- `03-public-skill-launcher`: 이 저장소 공개 컬렉션용 스킬
- `04-skill-sanitizer`: MIT

재사용 전 각 폴더의 `LICENSE`를 확인하세요.

## 관련 프로젝트

- [RESEARCH_PAPERS](https://github.com/JorrrrrdDin/RESEARCH_PAPERS)
- [knowledge-gravity-lab](https://github.com/JorrrrrdDin/knowledge-gravity-lab)
