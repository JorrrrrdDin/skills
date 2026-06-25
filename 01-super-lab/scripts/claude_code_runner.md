# Claude Code에서 Super Lab Lite 돌리는 법

Python 스크립트 없이 Claude Code 세션 안에서 바로 실행.

## 패턴 A — 한 세션 안에서 메인 Claude가 직접 오케스트

사용자 요청을 받으면 메인 Claude(Opus)가 직접 Phase 1/4를 수행하고, Phase 2/3는 `Agent` tool로 병렬 서브에이전트를 띄운다.

### Phase 1: 메인 Opus가 설계
```
사용자: "이번 분기 한국 AI 스타트업 동향 분석해"

메인 Opus:
  내부에서 3 도메인 분할:
    A: 주요 딜·투자·펀딩
    B: 기술 트렌드 (생성AI/에이전트/인프라)
    C: 정책·규제·정부 지원
  
  각 도메인별 Sonnet 프롬프트 + Haiku 프롬프트 작성
  (머릿속 or 임시 파일로)
```

### Phase 2-3: Agent tool 병렬 호출
```
Agent(
  subagent_type='general-purpose',
  model='sonnet',
  description='도메인 A 분석',
  prompt='''
  당신은 도메인 A(주요 딜·투자·펀딩) 분석가입니다.
  
  먼저 리서치 서브에이전트를 호출하세요:
    Agent(
      subagent_type='general-purpose',
      model='haiku',
      prompt='2026 Q1-Q2 한국 AI 스타트업 시리즈A 이상 투자 딜 리스트. 회사명, 라운드, 금액, VC, 일자만. 구조화된 bullet.'
    )
  
  리서치 결과 받으면 분석 리포트 작성:
  ## 요약 / ## 분석 / ## 근거 / ## 한계 / ## 권고
  '''
)

Agent(subagent_type='general-purpose', model='sonnet', ... 도메인 B)
Agent(subagent_type='general-purpose', model='sonnet', ... 도메인 C)
```

**병렬 실행**: 세 Agent tool 호출을 **단일 메시지**에 넣으면 Claude Code가 자동 병렬 처리.

### Phase 4: 메인 Opus 종합
```
3 Sonnet 결과 → 메인 세션으로 수합 → 메인 Opus가 교차 통찰/모순/공백 검사 → 최종 응답
```

## 패턴 B — Python 스크립트 호출 (CLI 자동화)

```bash
export ANTHROPIC_API_KEY=your_api_key_here
cd ~/.claude/skills/super-lab-lite/scripts/
python lite_orchestrator.py "이번 분기 한국 AI 스타트업 동향 분석" --out ~/super_lab_runs
```

결과:
```
~/super_lab_runs/
└── 2026-04-24_164500_이번_분기_한국_AI_스타트업_동향_분석/
    ├── FINAL.md                         ← 최종 응답
    ├── phase1_opus_plan.md
    ├── phase1_plan.json
    ├── phase4_opus_synthesis.md
    ├── audit.json                       ← 토큰·비용·시간
    └── domain_주요_딜·투자·펀딩/
        ├── haiku_research.md
        └── sonnet_report.md
```

## 언제 어느 패턴?

| 상황 | 패턴 |
|------|------|
| 인터랙티브 대화 중 연구 위임 | A (Agent tool) |
| 결과 저장·감사·재현 필요 | B (Python CLI) |
| 회의 중 "30초 안에" 필요 | A, 다만 도메인 2~3개로 축소 |
| 주간/월간 자동 리포트 | B + 스케줄러 |
| 토큰 비용 엄격 관리 | B (audit.json에 정확 기록됨) |

## Tips

- **Sonnet의 Haiku 재호출 보장**: Agent tool 프롬프트에 "리서치가 필요하면 Haiku 모델로 서브에이전트를 호출하세요" 명시. 없으면 Sonnet이 자기가 다 해버림.
- **도메인 개수 조정**: 기본 3개지만 2개/4개로 바꿔도 됨. Phase 1 프롬프트에서 "N개로 분할" 지시.
- **결과 언어 통일**: Phase 1 설계 단계에서 "모든 응답 한국어" 명시 → 섞이지 않음.
- **토큰 절감**: Haiku에게 "결과는 bullet 최대 10개, 200 토큰 이내" 같은 상한 명시.
