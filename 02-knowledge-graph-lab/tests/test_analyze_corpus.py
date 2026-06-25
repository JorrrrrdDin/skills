import csv
import math
import subprocess
import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_corpus.py"
SPEC = spec_from_file_location("analyze_corpus", SCRIPT)
kg = module_from_spec(SPEC)
SPEC.loader.exec_module(kg)


def make_note(title, *, stem=None, links=None, tokens=None, text_len=320, tags=None):
    return {
        "title": title,
        "stem": stem or title,
        "links": links or [],
        "tokens": tokens or ["shared", "gravity", "cleanup", "notes"],
        "kind": "note",
        "mtime": datetime.now(timezone.utc).timestamp(),
        "text_len": text_len,
        "tags": tags or [],
        "headings": [],
        "path": f"{stem or title}.md",
    }


def test_small_corpus_uses_min_df_one():
    assert kg.min_df_for_notes([{}] * 5) == 1
    assert kg.min_df_for_notes([{}] * 6) == 2


def test_edges_and_twins_reuse_supplied_tfidf(monkeypatch):
    notes = [
        make_note("A", tokens=["alpha", "beta", "gamma", "delta"]),
        make_note("B", tokens=["alpha", "beta", "gamma", "delta"]),
    ]
    vectors = [{"alpha": 1.0, "beta": 1.0}, {"alpha": 1.0, "beta": 1.0}]
    norms = [math.sqrt(2), math.sqrt(2)]

    def fail_tfidf(_notes):
        raise AssertionError("tfidf should be computed once and injected")

    monkeypatch.setattr(kg, "tfidf", fail_tfidf)

    edges = kg.build_edges(notes, vectors, norms, semantic_threshold=0.1)
    assert edges
    assert kg.unlinked_twin_suggestions(notes, edges, vectors, norms) == []


def test_semantic_edges_are_not_recommended_as_unlinked_twins():
    notes = [
        make_note("A", tokens=["alpha", "beta", "gamma", "delta", "epsilon"]),
        make_note("B", tokens=["alpha", "beta", "gamma", "delta", "epsilon"]),
    ]
    vectors = [{"alpha": 1.0, "beta": 1.0, "gamma": 1.0, "delta": 1.0}, {"alpha": 1.0, "beta": 1.0, "gamma": 1.0, "delta": 1.0}]
    norms = [2.0, 2.0]
    semantic_edges = [{"source": 0, "target": 1, "weight": 0.5}]

    assert kg.unlinked_twin_suggestions(notes, semantic_edges, vectors, norms) == []


def test_inlink_count_does_not_double_count_matching_stem_and_title():
    target = make_note("Hub", stem="Hub", links=[], text_len=320)
    source = make_note("Source", links=["Hub"], text_len=320)
    kg.score_notes([target, source])

    size = min(math.log1p(target["text_len"]) / 7, 1.5)
    expected = 1.0 + math.log1p(1) * 1.2 + size + 1.0
    assert abs(target["center_score"] - expected) < 0.05


def test_cli_smoke_outputs_collision_stats_and_no_check_fallback(tmp_path):
    vault = tmp_path / "vault"
    out = tmp_path / "out"
    vault.mkdir()
    (vault / "Hub.md").write_text("# Hub\n#core\nLinks to [[Leaf A]] and [[Leaf B]].\n", encoding="utf-8")
    (vault / "Leaf A.md").write_text("# Leaf A\nShared gravity cleanup token.\n", encoding="utf-8")
    (vault / "Leaf B.md").write_text("# Leaf B\nShared gravity cleanup token.\n", encoding="utf-8")
    (vault / "Loose.md").write_text("# Loose\nTiny fragment.\n", encoding="utf-8")
    (vault / "Template.md").write_text("# Template\nTODO\nTODO\nTODO\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(vault), "--output", str(out)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert "stem_title_same=" in result.stdout
    assert "inlink_title_fallback=distinct-title-only" in result.stdout
    assert "tfidf_min_df=1" in result.stdout

    with (out / "knowledge_gravity_nodes.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert all(row["review_reasons"] != "check" for row in rows)
