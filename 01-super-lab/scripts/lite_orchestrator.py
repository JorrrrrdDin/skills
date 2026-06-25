"""Super Lab Lite — 1 Opus + 3 Sonnet + 3 Haiku 오케스트레이터.

독립 실행 (Claude Code 없이도):
  export ANTHROPIC_API_KEY=...
  python lite_orchestrator.py "이번 분기 한국 AI 스타트업 동향 분석"

구조:
  Phase 1  Opus   → 3 도메인 분할 + 각 Sonnet/Haiku 프롬프트 설계
  Phase 2  병렬   → 3 Haiku 리서치 동시 실행
  Phase 3  병렬   → 3 Sonnet 합성 동시 실행
  Phase 4  Opus   → 종합 + QA
  저장            → runs/{타임스탬프}_{작업명}/
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    print("pip install anthropic")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# 모델 설정
# ═══════════════════════════════════════════════════════════════
MODEL_OPUS   = os.environ.get("SLL_OPUS_MODEL",   "claude-opus-4-7")
MODEL_SONNET = os.environ.get("SLL_SONNET_MODEL", "claude-sonnet-4-6")
MODEL_HAIKU  = os.environ.get("SLL_HAIKU_MODEL",  "claude-haiku-4-5-20251001")

MAX_TOK_OPUS   = 4096
MAX_TOK_SONNET = 2048
MAX_TOK_HAIKU  = 1024

client = Anthropic()


# ═══════════════════════════════════════════════════════════════
# Tier 호출 래퍼
# ═══════════════════════════════════════════════════════════════
def _call(model: str, prompt: str, max_tokens: int, system: str = "") -> dict:
    t0 = time.time()
    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    r = client.messages.create(**kwargs)
    dt = time.time() - t0
    return {
        "text": r.content[0].text,
        "tokens_in": r.usage.input_tokens,
        "tokens_out": r.usage.output_tokens,
        "model": model,
        "elapsed_sec": round(dt, 2),
    }


def opus(prompt: str, system: str = "") -> dict:
    return _call(MODEL_OPUS, prompt, MAX_TOK_OPUS, system)


def sonnet(prompt: str, system: str = "") -> dict:
    return _call(MODEL_SONNET, prompt, MAX_TOK_SONNET, system)


def haiku(prompt: str, system: str = "") -> dict:
    return _call(MODEL_HAIKU, prompt, MAX_TOK_HAIKU, system)


# ═══════════════════════════════════════════════════════════════
# Phase 1: Opus 설계
# ═══════════════════════════════════════════════════════════════
PHASE1_SYSTEM = """당신은 연구 오케스트레이션 조율자(Coordinator)입니다.
사용자 요청을 서로 겹치지 않는 3개 하위 도메인으로 분할하고,
각 도메인별로 Sonnet(분석가)과 Haiku(리서처)에게 줄 프롬프트를 작성합니다.

반드시 아래 JSON 스키마로만 응답하세요:
{
  "goal": "전체 목표 한 문장",
  "domains": [
    {
      "name": "도메인 A 이름 (한글)",
      "haiku_prompt": "Haiku에게 줄 팩트/데이터 수집 지시. 판단·평가 금지. 구조화(bullet/JSON)로 반환 요청.",
      "sonnet_prompt": "Sonnet에게 줄 분석 지시. Haiku 결과를 받아 분석·권고 작성."
    },
    // 총 3개
  ],
  "final_schema": "최종 산출물 구조 명세 (예: '1) 요약 2) 도메인별 분석 3) 교차 통찰 4) 권고')"
}"""


def phase1_design(user_request: str) -> dict:
    prompt = f"사용자 요청:\n{user_request}\n\n위를 3 도메인으로 분할해 JSON으로 응답."
    result = opus(prompt, system=PHASE1_SYSTEM)
    # JSON 추출
    text = result["text"]
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise RuntimeError(f"Phase 1 JSON 파싱 실패:\n{text[:500]}")
    plan = json.loads(m.group(0))
    result["plan"] = plan
    return result


# ═══════════════════════════════════════════════════════════════
# Phase 2: Haiku 병렬 리서치
# ═══════════════════════════════════════════════════════════════
HAIKU_SYSTEM = """당신은 연구 보조자(Researcher)입니다.
팩트·데이터 수집에만 집중하세요. 판단·결론·추천 금지.
응답은 구조화된 bullet 또는 JSON으로. 출처 있으면 명시."""


def phase2_research_parallel(domains: list) -> dict:
    results = {}
    with ThreadPoolExecutor(max_workers=3) as exe:
        futures = {
            exe.submit(haiku, d["haiku_prompt"], HAIKU_SYSTEM): d["name"]
            for d in domains
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as e:
                results[name] = {"error": str(e), "text": ""}
    return results


# ═══════════════════════════════════════════════════════════════
# Phase 3: Sonnet 병렬 합성
# ═══════════════════════════════════════════════════════════════
SONNET_SYSTEM = """당신은 도메인 분석가(Analyst)입니다.
Haiku가 수집한 원본 데이터를 받아 분석하고, 근거·한계·권고를 정리합니다.
마크다운 리포트로 응답하세요. 섹션: ## 요약 / ## 분석 / ## 근거 / ## 한계 / ## 권고"""


def phase3_analyze_parallel(domains: list, haiku_results: dict) -> dict:
    results = {}
    with ThreadPoolExecutor(max_workers=3) as exe:
        futures = {}
        for d in domains:
            haiku_text = haiku_results.get(d["name"], {}).get("text", "(데이터 없음)")
            combined = f"{d['sonnet_prompt']}\n\n## Haiku 리서치 데이터\n{haiku_text}"
            fut = exe.submit(sonnet, combined, SONNET_SYSTEM)
            futures[fut] = d["name"]
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as e:
                results[name] = {"error": str(e), "text": ""}
    return results


# ═══════════════════════════════════════════════════════════════
# Phase 4: Opus 종합
# ═══════════════════════════════════════════════════════════════
SYNTHESIS_SYSTEM = """당신은 연구 오케스트레이션 조율자(Coordinator)의 최종 QA 단계입니다.
3 도메인 리포트를 받아:
1. 교차 통찰(각 도메인 상호 영향) 추출
2. 모순·공백 지적
3. 최종 사용자 응답 작성 (요약 → 상세 → 부록)

원본 Haiku 데이터와 Sonnet 분석이 모두 제공됩니다.
결론은 근거 기반으로만. 확신 없으면 '추가 조사 필요' 명시."""


def phase4_synthesize(user_request: str, plan: dict, sonnet_reports: dict) -> dict:
    parts = [f"# 사용자 원 요청\n{user_request}\n",
             f"# 설계 (Phase 1)\n```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```\n",
             "# 도메인별 분석 (Sonnet 리포트)"]
    for name, r in sonnet_reports.items():
        parts.append(f"\n## 도메인: {name}\n{r.get('text', '(실패)')}")
    parts.append(f"\n# 요구 스키마\n{plan.get('final_schema', '자유')}")
    return opus("\n".join(parts), system=SYNTHESIS_SYSTEM)


# ═══════════════════════════════════════════════════════════════
# 오케스트레이터
# ═══════════════════════════════════════════════════════════════
def run(user_request: str, out_root: Path) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    slug = re.sub(r"[^가-힣a-zA-Z0-9]+", "_", user_request)[:40].strip("_")
    run_dir = out_root / f"{ts}_{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)

    audit = {"started_at": datetime.now().isoformat(), "user_request": user_request,
             "phases": {}, "total_tokens": {"in": 0, "out": 0}}

    # Phase 1
    print(f"[Phase 1] Opus 설계 중...")
    p1 = phase1_design(user_request)
    (run_dir / "phase1_opus_plan.md").write_text(
        f"# Phase 1 — Opus 설계\n\n{p1['text']}", encoding="utf-8")
    (run_dir / "phase1_plan.json").write_text(
        json.dumps(p1["plan"], ensure_ascii=False, indent=2), encoding="utf-8")
    audit["phases"]["phase1"] = {k: v for k, v in p1.items() if k != "plan"}
    audit["total_tokens"]["in"] += p1["tokens_in"]
    audit["total_tokens"]["out"] += p1["tokens_out"]

    domains = p1["plan"]["domains"]
    assert len(domains) == 3, f"도메인 3개 아님: {len(domains)}"

    # Phase 2
    print(f"[Phase 2] Haiku 3 병렬 리서치...")
    haiku_results = phase2_research_parallel(domains)
    audit["phases"]["phase2"] = {}
    for name, r in haiku_results.items():
        d_dir = run_dir / f"domain_{name}"
        d_dir.mkdir(exist_ok=True)
        (d_dir / "haiku_research.md").write_text(r.get("text", ""), encoding="utf-8")
        audit["phases"]["phase2"][name] = {k: v for k, v in r.items() if k != "text"}
        audit["total_tokens"]["in"] += r.get("tokens_in", 0)
        audit["total_tokens"]["out"] += r.get("tokens_out", 0)

    # Phase 3
    print(f"[Phase 3] Sonnet 3 병렬 분석...")
    sonnet_reports = phase3_analyze_parallel(domains, haiku_results)
    audit["phases"]["phase3"] = {}
    for name, r in sonnet_reports.items():
        d_dir = run_dir / f"domain_{name}"
        (d_dir / "sonnet_report.md").write_text(r.get("text", ""), encoding="utf-8")
        audit["phases"]["phase3"][name] = {k: v for k, v in r.items() if k != "text"}
        audit["total_tokens"]["in"] += r.get("tokens_in", 0)
        audit["total_tokens"]["out"] += r.get("tokens_out", 0)

    # Phase 4
    print(f"[Phase 4] Opus 종합...")
    p4 = phase4_synthesize(user_request, p1["plan"], sonnet_reports)
    (run_dir / "phase4_opus_synthesis.md").write_text(
        f"# Phase 4 — Opus 종합\n\n{p4['text']}", encoding="utf-8")
    audit["phases"]["phase4"] = {k: v for k, v in p4.items() if k != "text"}
    audit["total_tokens"]["in"] += p4["tokens_in"]
    audit["total_tokens"]["out"] += p4["tokens_out"]

    # Audit
    audit["finished_at"] = datetime.now().isoformat()
    cost_usd = (
        audit["total_tokens"]["in"] / 1e6 * 15 +  # Opus 평균 (rough)
        audit["total_tokens"]["out"] / 1e6 * 5
    )  # 실제론 모델별로 분리 계산해야 정확
    audit["cost_estimate_usd"] = round(cost_usd, 4)
    (run_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    # 최종 사용자 응답
    final_md = (run_dir / "FINAL.md")
    final_md.write_text(
        f"# Super Lab Lite — 최종 응답\n\n"
        f"**원 요청:** {user_request}\n\n"
        f"**토큰:** in={audit['total_tokens']['in']}, out={audit['total_tokens']['out']}\n"
        f"**비용 추정:** ~${audit['cost_estimate_usd']}\n\n"
        f"---\n\n{p4['text']}",
        encoding="utf-8",
    )

    print(f"\n✓ 완료: {run_dir}")
    print(f"  최종 응답: {final_md}")
    print(f"  토큰: {audit['total_tokens']}")
    print(f"  비용: ~${audit['cost_estimate_usd']}")
    return run_dir


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description="Super Lab Lite orchestrator")
    ap.add_argument("request", help="연구/분석 요청 (한글/영문)")
    ap.add_argument("--out", default="./super_lab_lite_runs",
                    help="결과 저장 루트 (기본: ./super_lab_lite_runs)")
    args = ap.parse_args()

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY 환경변수 필요")
        sys.exit(1)

    run(args.request, out_root)


if __name__ == "__main__":
    main()
