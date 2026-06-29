<!-- sanitizer: ignore-file — 탐지 패턴을 예시로 문서화한 파일. 실제 누출 아님 -->
# skill-sanitizer

[English](README.md) | **한국어**

> **스킬을 위한 공항 보안검색대.** 공유하기 전에 훑어서, 키·경로·클라이언트명을 `git push` *전에* 잡는다 — 후가 아니라.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT) ![Python](https://img.shields.io/badge/python-stdlib--only-blue.svg) ![Fail](https://img.shields.io/badge/mode-fail--closed-red.svg)

스킬을 만들었고, 커뮤니티에 공유하고 싶다. 근데 **라이브 API 키, 홈 디렉터리 경로, 클라이언트 이름**을 평문으로 흘린 사람이 되고 싶진 않다. skill-sanitizer는 스킬을 문 밖으로 내보내기 직전에 통과시키는 금속탐지기다.

Claude Code / AI-IDE 스킬이자 독립 실행 가능한 **stdlib-only 파이썬 CLI**. 의존성 0, 네트워크 0. 폴더만 가리키면 된다.

---

## 멘탈 모델

공항 보안검색대라고 생각해라. 가방 속 모든 게 게이트를 지나기 전에 스캐너를 통과한다. 대부분은 그냥 통과한다. 몇 개는 2차 검토 대상으로 표시된다. 그리고 진짜 위험한 것 — 라이브 키, 개인 인증서 — 은 검색대에서 강하게 **STOP**. 안 훑은 채로 나가는 게 없으니 아무것도 새지 않는다.

skill-sanitizer는 **fail-closed**다: 애매하면 막는다. 조용히 통과시키는 스캐너는 없느니만 못하다.

---

## 무엇을 잡나

| 분류 | 심각도 | 예시 |
|---|---|---|
| **🔑 시크릿** | BLOCK | API 키·토큰(`sk-`, `ghp_`, `AKIA…`, Stripe, Slack, JWT), 개인키, DB 연결 문자열, `.env` 값 |
| **🏠 기밀/독점** | BLOCK / WARN | 로컬 머신 경로(`C:\Users\<you>\…`, `/home/<you>`, UNC, 내부 호스트명), 내부 프로젝트/스킬 이름, 클라이언트명(로컬 비공개 사전 기반) |
| **📇 개인정보(PII)** | WARN | 이메일, 전화번호 |
| **🔌 서비스 코드** | WARN | github / jira / slack / stripe / aws / notion / linear 바인딩 → 범용 스킬에 박지 말고 **전용 plugin으로 분리** 권고 |

알려진 prefix에 안 걸리는 무작위형 시크릿을 잡는 **고-엔트로피 백스톱**도 있다.

---

## 빠른 시작 (10초)

스킬로 설치:

```bash
git clone https://github.com/animaresearch/skills
cp -r skills/04-skill-sanitizer <your-agent-skills-dir>/
```

아니면 아무 폴더에 스캐너를 직접 실행:

```bash
python scanner.py <dir>
```

끝. 설정·의존성·셋업 없음. 걸렸을 때 모습:

```
$ python scanner.py ./my-cool-skill

  SCAN  ./my-cool-skill  (7 files)

  ✗ BLOCK  skill.md:42          SECRET / api-key
           sk-live-4eC39H...     OpenAI-style live key
  ✗ BLOCK  helper.py:13         PROPRIETARY / local-path
           C:\Users\jdoe\dev\…   home-dir path leaks your username
  ⚠ WARN   README.md:8          PII / email
           jdoe@example.com

  RESULT: BLOCK — 2 must-fix, 1 to review.  Not safe to share.
```

깨끗하면? 그냥 **`Safe to share`** + exit 0. 바로 배포해라.

---

## 왜 필요한가

실패 모드가 *조용하고 영구적*이기 때문이다.

빠르게 움직이다가 dev 폴더에서 동작하는 스킬을 복사하고, 공유하려고 `git push` — 그 순간 공개 커밋에 라이브 키가 박히거나, 네 유저명과 내부 프로젝트명이 누군가의 클론에 영원히 남는다. 새어나간 시크릿 교체는 하루 망치는 일이고, 클라이언트 이름은 *되돌릴 수 없다*.

skill-sanitizer는 "내 머신에선 돌아감"과 "인터넷에 올라감" 사이에 검문소를 둔다. 공유 전 한 번만 돌려라. 그게 전부다.

---

## 공격당해봐서 믿을 만하다

자기 자신을 믿는 주말 정규식 스크립트가 아니다.

- **적대적 감사 완료** — 독립 멀티에이전트 리뷰가 *뚫을 방법만* 노려 찾았고 **fail-open 경로 5개를 닫았다.** 그중엔: `none`이라는 단어가 들어간 *라이브 DB 연결 문자열*이 "Safe to share"로 통과하던 placeholder-부분일치 우회; UTF-16 인코딩 파일이 탐지를 통째로 빠져나가던 것; 전체 트리를 조용히 숨기던 무차별 `.sanitizerignore` 글롭.
- **첫 실전 실행에서 진짜 누출을 잡았다** — 실제 스킬 모음에서, 유저명이 든 하드코딩 홈 디렉터리 경로 + 두 스킬에 박힌 내부 프로젝트명. 둘 다 정리됐고, 같은 모음의 민감한 ID 번호는 새지 *않았다*고 확인까지 했다. 진짜는 잡고, 안전한 건 오버하지 않았다.

믿을 수 없는 스캐너는 장식일 뿐이다. 이건 신뢰를 어렵게 벌었다.

---

## CI / pre-commit 사용

연동 지점은 exit 코드다:

| Exit | 의미 |
|---|---|
| `0` | 깨끗 — 공유 안전 |
| `1` | **BLOCK** — 반드시 고칠 누출 발견 |
| `2` | **WARN** — 검토 권장 |
| `3` | **스캔 무결성 실패** — 예: 스캐너를 멀게 하려는 무차별 `.sanitizerignore` 글롭 |

**pre-commit / pre-push 훅:**

```bash
python scanner.py . || {
  echo "skill-sanitizer blocked the push. Fix the leaks above."
  exit 1
}
```

**GitHub Actions:**

```yaml
- name: Sanitize skill before release
  run: python scanner.py ./skills
```

exit `3`이 별도 신호인 건 의도적이다 — 누가 과도하게 넓은 ignore 글롭으로 스캐너를 무력화하려 하면, 그건 통과가 아니라 실패로 본다.

---

## 비공개 사전 (배포 스킬에서 분리)

클라이언트명·내부 프로젝트명은 그 자체가 민감하다 — 그래서 repo에 두지 않는다. skill-sanitizer는 외부의 **gitignore된** `.sanitizer.local.json`에서 네 비공개 사전을 읽는다. 예시를 복사해 채워라:

```bash
cp .sanitizer.local.example.json .sanitizer.local.json
# 네 클라이언트/프로젝트/코드네임 문자열 추가 — 이 파일은 로컬에만 남는다
```

배포되는 스킬은 범용·공유 가능한 채로 유지되고, 네 비밀 단어목록은 함께 따라가지 않는다.

---

## fail-closed 철학

스캐너가 지키는 세 규칙:

1. **애매하면 BLOCK.** 놓친 누출은 복구 불가, 오탐은 10초 비용.
2. **입력이 너를 무장해제하게 두지 마라.** 인코딩(UTF-16), placeholder처럼 보이는 부분일치, ignore 글롭 — 이걸로 탐지를 빠져나갈 수 없다. 그 경로들은 일부러 노려 닫았다.
3. **스캔을 조작하는 것 자체가 실패**(exit 3)지, 조용한 통과가 아니다.

---

## 한계 (정직하게)

- **엔트로피 백스톱은 soft하다.** 알려진 prefix에 안 걸리는 무작위형 시크릿을 잡지만, 고-엔트로피 휴리스틱은 본질적으로 과하게 경고한다 — 해시·UUID·minified 덩어리에서 가끔 오탐이 난다. 그게 fail-closed의 세금이고, 틀려도 이쪽으로 틀리는 게 맞다.
- **진짜 시크릿 교체의 대체재가 아니다.** 키가 한 번이라도 노출됐으면 *교체해라.* 이 도구는 *다음* 누출을 막지, 이미 울린 종을 되돌리진 못한다.
- **스킬 폴더 단위**지, 전체 repo 히스토리 스캐너가 아니다. git-secrets / trufflehog 같은 도구를 보완하지 대체하지 않는다.
- **설계상 보고 전용.** 파일을 절대 수정하지 않는다 — 뭘 고칠지 알려주고, 고치는 건 너다.

---

## 라이선스

MIT. 쓰고, 포크하고, 릴리스 파이프라인에 엮어라. 키만 안 넣으면 된다.
