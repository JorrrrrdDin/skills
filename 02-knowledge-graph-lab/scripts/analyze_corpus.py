#!/usr/bin/env python
import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


TEXT_EXT = {".md", ".txt", ".rst"}
TOKEN_RE = re.compile(r"[A-Za-z0-9\uac00-\ud7a3_+-]{2,}")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9\uac00-\ud7a3_/-]+)")
HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
DEFAULT_SKIP_DIRS = {".obsidian", ".git", "node_modules", "07_Attachments", "99_Legacy_ANIMA_Nested", "copilot"}
BRIDGE_KINDS = {"moc", "template"}
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "via", "using", "based",
    "are", "was", "were", "has", "have", "had", "not", "but", "can", "may", "will",
    "to", "of", "in", "on", "as", "by", "or", "be", "is", "it",
    "system", "method", "paper", "note", "notes", "template", "status", "title", "tags",
    "type", "todo", "reference", "grade", "lane", "http", "https", "www", "com",
    "및", "또는", "대한", "으로", "에서", "하는",
}


def read_text(path):
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            pass
    return path.read_text(encoding="utf-8", errors="ignore")


def tokenize(text):
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if keep_token(token)
    ]


def keep_token(token):
    lowered = token.lower()
    if not (2 <= len(lowered) <= 42):
        return False
    if lowered.isdigit() or lowered in STOPWORDS:
        return False
    if all(ch in "-_+" for ch in lowered):
        return False
    if lowered.count("?") >= 2:
        return False
    return True


def title_from_text(path, text):
    for line in text.splitlines()[:40]:
        s = line.strip()
        if s.lower().startswith("title:"):
            return s.split(":", 1)[1].strip().strip("\"'") or path.stem
        if s.startswith("# "):
            return s[2:].strip() or path.stem
    return path.stem


def headings_from_text(text, limit=12):
    headings = []
    for line in text.splitlines():
        m = HEADING_RE.match(line.strip())
        if m:
            headings.append({"level": len(m.group(1)), "title": m.group(2).strip()})
        if len(headings) >= limit:
            break
    return headings


def note_kind(rel):
    s = str(rel).lower()
    if "paper" in s or "\ub17c\ubb38" in s:
        return "paper"
    if "invention" in s or "idea" in s or "\ud2b9\ud5c8" in s or re.search(r"\bt[-_ ]?\d{3}\b", s):
        return "invention"
    if "experiment" in s or "\uc2e4\ud5d8" in s:
        return "experiment"
    if "template" in s:
        return "template"
    if "moc" in s or "index" in s:
        return "moc"
    return "note"


def collect(input_dir, skip_dirs):
    input_dir = Path(input_dir).resolve()
    notes = []
    for path in input_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXT:
            continue
        rel_parts = path.relative_to(input_dir).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        if any(part in skip_dirs for part in rel_parts):
            continue
        text = read_text(path)
        tokens = tokenize(text)
        rel = path.relative_to(input_dir)
        stat = path.stat()
        notes.append(
            {
                "path": str(rel).replace("\\", "/"),
                "stem": path.stem,
                "title": title_from_text(path, text),
                "kind": note_kind(rel),
                "text_len": len(text),
                "tokens": tokens,
                "links": [x.strip() for x in WIKILINK_RE.findall(text)],
                "tags": sorted(set(TAG_RE.findall(text))),
                "headings": headings_from_text(text),
                "mtime": stat.st_mtime,
            }
        )
    return notes


def min_df_for_notes(notes):
    return 1 if len(notes) <= 5 else 2


def tfidf(notes, min_df=None):
    docs = [Counter(n["tokens"]) for n in notes]
    df = Counter()
    for doc in docs:
        df.update(doc.keys())
    vectors = []
    norms = []
    total = max(len(notes), 1)
    min_df = min_df_for_notes(notes) if min_df is None else min_df
    for doc in docs:
        vec = {}
        for token, count in doc.items():
            if df[token] < min_df:
                continue
            vec[token] = (1 + math.log(count)) * (math.log((1 + total) / (1 + df[token])) + 1)
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append(vec)
        norms.append(norm)
    return vectors, norms


def cosine(a, b, na, nb):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items()) / (na * nb)


def score_notes(notes):
    now = datetime.now(timezone.utc).timestamp()
    incoming = Counter()
    for n in notes:
        for link in n["links"]:
            incoming[link.lower()] += 1

    for n in notes:
        age_days = max((now - n["mtime"]) / 86400, 0)
        recency = math.exp(-age_days / 180)
        kind_boost = {
            "invention": 1.8,
            "paper": 1.6,
            "experiment": 1.4,
            "moc": 1.3,
            "note": 1.0,
            "template": 0.2,
        }[n["kind"]]
        stem_key = n["stem"].lower()
        title_key = n["title"].lower()
        inlinks = incoming[stem_key]
        if title_key != stem_key:
            inlinks += incoming[title_key]
        outlinks = len(n["links"])
        inlink_score = math.log1p(inlinks) * 1.2
        outlink_score = math.log1p(outlinks) * 0.7
        size = min(math.log1p(n["text_len"]) / 7, 1.5)
        tag_score = min(len(n["tags"]) * 0.15, 1.0)
        boilerplate_penalty = 0.8 if n["kind"] == "template" else 0.0
        short_penalty = 0.6 if n["text_len"] < 240 else 0.0
        orphan_penalty = 0.6 if not n["links"] else 0.0
        n["center_score"] = round(kind_boost + inlink_score + outlink_score + size + tag_score + recency - boilerplate_penalty, 4)
        n["review_score"] = round(max(0, short_penalty + boilerplate_penalty + orphan_penalty - tag_score * 0.2), 4)
        reasons = []
        if short_penalty:
            reasons.append("short")
        if boilerplate_penalty:
            reasons.append("template")
        if orphan_penalty:
            reasons.append("orphan")
        if not n["tags"]:
            reasons.append("untagged")
        n["review_reasons"] = ", ".join(reasons)


def build_edges(notes, vectors=None, norms=None, max_edges_per_node=3, semantic_threshold=0.11):
    if vectors is None or norms is None:
        vectors, norms = tfidf(notes)
    edges = {}
    name_to_idx = {}
    for i, n in enumerate(notes):
        name_to_idx[n["stem"].lower()] = i
        name_to_idx[n["title"].lower()] = i

    for i, n in enumerate(notes):
        for link in n["links"]:
            j = name_to_idx.get(link.lower())
            if j is not None and j != i:
                key = tuple(sorted((i, j)))
                edges[key] = max(edges.get(key, 0.0), 2.0)

    for i in range(len(notes)):
        sims = []
        for j in range(i + 1, len(notes)):
            sim = cosine(vectors[i], vectors[j], norms[i], norms[j])
            if sim >= semantic_threshold:
                sims.append((sim, j))
        for sim, j in sorted(sims, reverse=True)[:max_edges_per_node]:
            key = tuple(sorted((i, j)))
            edges[key] = max(edges.get(key, 0.0), round(sim, 5))

    return [{"source": a, "target": b, "weight": w} for (a, b), w in edges.items()]


def cluster(notes, edges):
    parent = list(range(len(notes)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for e in edges:
        a = notes[e["source"]]
        b = notes[e["target"]]
        semantic_link = e["weight"] < 2.0 and e["weight"] >= 0.35
        direct_content_link = e["weight"] >= 2.0 and a["kind"] not in BRIDGE_KINDS and b["kind"] not in BRIDGE_KINDS
        if semantic_link or direct_content_link:
            union(e["source"], e["target"])

    groups = defaultdict(list)
    for i in range(len(notes)):
        groups[find(i)].append(i)
    return sorted(groups.values(), key=len, reverse=True)


def cluster_profile(notes, group):
    kind_counts = Counter(notes[i]["kind"] for i in group)
    tokens = Counter()
    for i in group:
        tokens.update(notes[i]["tokens"])
    top_terms = [token for token, _ in tokens.most_common(8)]
    examples = sorted((notes[i] for i in group), key=lambda n: n["center_score"], reverse=True)[:5]
    return {
        "size": len(group),
        "kinds": ", ".join(f"{k}:{v}" for k, v in kind_counts.most_common()),
        "top_terms": ", ".join(top_terms) or "-",
        "examples": ", ".join(n["title"] for n in examples),
    }


def organization_score(note, total_text_len):
    share = note["text_len"] / total_text_len if total_text_len else 0
    score = 45
    score += min(len(note["links"]) * 8, 24)
    score += min(len(note["tags"]) * 6, 18)
    score += min(len(note["headings"]) * 3, 12)
    if note["text_len"] >= 600:
        score += 6
    if share >= 0.08 and len(note["links"]) < 2:
        score -= 12
    if note["text_len"] < 240:
        score -= 10
    if note["kind"] in BRIDGE_KINDS:
        score -= 8
    return max(15, min(100, int(round(score))))


def split_suggestions(notes, limit=10):
    candidates = []
    for n in notes:
        if len(n["headings"]) < 3 or n["text_len"] < 1200:
            continue
        score = n["text_len"] + len(n["headings"]) * 180
        candidates.append((score, n))
    return [n for _, n in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]]


def unlinked_twin_suggestions(notes, edges, vectors=None, norms=None, limit=12):
    existing_pairs = {
        tuple(sorted((e["source"], e["target"])))
        for e in edges
    }
    if vectors is None or norms is None:
        vectors, norms = tfidf(notes)
    suggestions = []
    for i in range(len(notes)):
        if notes[i]["kind"] in BRIDGE_KINDS:
            continue
        for j in range(i + 1, len(notes)):
            if notes[j]["kind"] in BRIDGE_KINDS or (i, j) in existing_pairs:
                continue
            shared_terms = sorted(set(vectors[i]) & set(vectors[j]))
            if len(shared_terms) < 4:
                continue
            sim = cosine(vectors[i], vectors[j], norms[i], norms[j])
            if sim < 0.14:
                continue
            suggestions.append((sim, shared_terms[:8], notes[i], notes[j]))
    return sorted(suggestions, key=lambda x: x[0], reverse=True)[:limit]


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(out, notes, edges, groups):
    top = sorted(notes, key=lambda n: n["center_score"], reverse=True)[:20]
    review = sorted(notes, key=lambda n: n["review_score"], reverse=True)[:20]
    orphan = [n for n in notes if not n["links"]]
    overgrown = [g for g in groups if len(g) >= max(8, len(notes) * 0.18)]

    lines = [
        "# Knowledge Gravity Report",
        "",
        f"- notes: {len(notes)}",
        f"- edges: {len(edges)}",
        f"- clusters: {len(groups)}",
        f"- generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Center Notes",
        "",
        "| rank | title | kind | center | links | path |",
        "|---:|---|---|---:|---:|---|",
    ]
    for i, n in enumerate(top, 1):
        lines.append(f"| {i} | {n['title']} | {n['kind']} | {n['center_score']:.3f} | {len(n['links'])} | `{n['path']}` |")

    lines += [
        "",
        "## Review Queue",
        "",
        "| rank | title | review | reasons | path |",
        "|---:|---|---:|---|---|",
    ]
    for i, n in enumerate(review, 1):
        if n["review_score"] <= 0:
            continue
        lines.append(f"| {i} | {n['title']} | {n['review_score']:.3f} | {n['review_reasons']} | `{n['path']}` |")

    lines += [
        "",
        "## Topic Groups",
        "",
        "| group | size | kind mix | top terms | examples |",
        "|---:|---:|---|---|---|",
    ]
    for idx, group in enumerate(groups[:12], 1):
        profile = cluster_profile(notes, group)
        lines.append(
            f"| {idx} | {profile['size']} | {profile['kinds']} | {profile['top_terms']} | {profile['examples']} |"
        )

    lines += [
        "",
        "## Overgrown Topic Groups",
        "",
    ]
    if not overgrown:
        lines.append("- No overgrown cluster found by the current heuristic.")
    for idx, group in enumerate(overgrown, 1):
        titles = ", ".join(notes[i]["title"] for i in group[:8])
        lines.append(f"- cluster {idx}: {len(group)} notes. Examples: {titles}")

    lines += [
        "",
        "## Orphan Notes",
        "",
        f"- orphan count: {len(orphan)}",
        "",
        "## Suggested Actions",
        "",
        "1. Review the top review-queue items before using them as retrieval sources.",
        "2. Split any overgrown topic group into smaller topic notes or MOCs.",
        "3. Add links/tags to important orphan notes.",
        "4. Promote the top center notes into an index or map-of-content.",
        "5. Archive templates, fragments, and low-signal notes that remain unlinked.",
        "",
        "> Experimental note: this report is a heuristic knowledge-hygiene map, not a truth detector.",
    ]
    (out / "knowledge_gravity_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_action_sheet(out, notes, edges, groups, vectors=None, norms=None):
    total_text_len = sum(n["text_len"] for n in notes) or 1
    scored = sorted(
        ((organization_score(n, total_text_len), n) for n in notes),
        key=lambda item: (item[0], item[1]["center_score"]),
    )
    heavy = sorted(notes, key=lambda n: n["text_len"], reverse=True)[:12]
    split_candidates = split_suggestions(notes)
    twin_candidates = unlinked_twin_suggestions(notes, edges, vectors, norms)

    lines = [
        "# Knowledge Gravity Action Sheet",
        "",
        "> This temporary markdown is for cleanup decisions. Edit it freely, then move useful pieces back into the vault.",
        "",
        "## 80-Point Feedback Loop",
        "",
        "| title | current | next action | path |",
        "|---|---:|---|---|",
    ]
    for score, n in scored[:15]:
        actions = []
        if len(n["links"]) < 2:
            actions.append("add 1-2 links")
        if not n["tags"]:
            actions.append("add tags")
        if len(n["headings"]) < 2 and n["text_len"] >= 800:
            actions.append("add headings")
        if n["text_len"] < 240:
            actions.append("merge or archive")
        action = ", ".join(actions) or "review manually"
        lines.append(f"| {n['title']} | {score} | {action} | `{n['path']}` |")

    lines += [
        "",
        "## Repository Share",
        "",
        "| title | share | size | links | path |",
        "|---|---:|---:|---:|---|",
    ]
    for n in heavy:
        share = n["text_len"] / total_text_len * 100
        lines.append(f"| {n['title']} | {share:.2f}% | {n['text_len']} | {len(n['links'])} | `{n['path']}` |")

    lines += [
        "",
        "## Whitening Template",
        "",
        "```markdown",
        "# {{note_title}}",
        "",
        "## One-line claim",
        "- ",
        "",
        "## Keep",
        "- ",
        "",
        "## Split out",
        "- ",
        "",
        "## Link targets",
        "- [[ ]]",
        "",
        "## Tags",
        "- #",
        "",
        "## Next cleanup action",
        "- [ ] ",
        "```",
        "",
        "## Split By Headings",
        "",
    ]
    if not split_candidates:
        lines.append("- No heading-based split candidate found by the current heuristic.")
    for n in split_candidates:
        lines.append(f"### {n['title']}")
        lines.append(f"- path: `{n['path']}`")
        lines.append("- proposed child notes:")
        for h in n["headings"][:8]:
            lines.append(f"  - {h['title']}")
        lines.append("")

    lines += [
        "## Link Suggestions",
        "",
    ]
    if not twin_candidates:
        lines.append("- No strong unlinked pair found by the current heuristic.")
    for sim, terms, a, b in twin_candidates:
        lines.append(
            f"- {a['title']} <-> {b['title']} ({sim:.3f}): "
            f"shared terms: {', '.join(terms)}. "
            "These two notes look like fraternal twins; consider linking them."
        )

    lines += [
        "",
        "## Quick Cleanup Rules",
        "",
        "- Raise a note toward 80 by adding links, tags, and headings before rewriting its body.",
        "- If a note takes a large repository share but has few links, split it or turn it into a map-of-content.",
        "- If two notes share many nouns but have no direct link, add one link or merge the weaker note.",
        "",
        "> Experimental note: this action sheet is a heuristic prompt for human cleanup, not an automatic truth judgment.",
    ]
    (out / "knowledge_gravity_action_sheet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Folder containing .md/.txt/.rst files")
    parser.add_argument("--output", required=True, help="Output folder")
    parser.add_argument("--skip-dir", action="append", default=[], help="Directory name to skip. Can be repeated.")
    args = parser.parse_args()

    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    notes = collect(args.input, DEFAULT_SKIP_DIRS | set(args.skip_dir))
    if not notes:
        raise SystemExit("No Markdown/text notes found.")

    score_notes(notes)
    vectors, norms = tfidf(notes)
    edges = build_edges(notes, vectors, norms)
    groups = cluster(notes, edges)

    node_rows = [
        {
            "id": i,
            "title": n["title"],
            "path": n["path"],
            "kind": n["kind"],
            "center_score": n["center_score"],
            "review_score": n["review_score"],
            "review_reasons": n["review_reasons"],
            "links": len(n["links"]),
            "tags": " ".join(n["tags"]),
            "text_len": n["text_len"],
        }
        for i, n in enumerate(notes)
    ]
    write_csv(out / "knowledge_gravity_nodes.csv", node_rows, list(node_rows[0].keys()))

    edge_rows = [
        {
            "source": e["source"],
            "target": e["target"],
            "weight": e["weight"],
            "source_title": notes[e["source"]]["title"],
            "target_title": notes[e["target"]]["title"],
        }
        for e in edges
    ]
    if edge_rows:
        write_csv(out / "knowledge_gravity_edges.csv", edge_rows, list(edge_rows[0].keys()))
    else:
        (out / "knowledge_gravity_edges.csv").write_text("source,target,weight,source_title,target_title\n", encoding="utf-8")

    data = {
        "notes": node_rows,
        "edges": edge_rows,
        "clusters": [[notes[i]["title"] for i in group] for group in groups],
        "generated": datetime.now().isoformat(timespec="seconds"),
    }
    (out / "knowledge_gravity_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out, notes, edges, groups)
    write_action_sheet(out, notes, edges, groups, vectors, norms)

    print(f"notes={len(notes)}")
    print(f"edges={len(edges)}")
    print(f"clusters={len(groups)}")
    print(f"stem_title_same={sum(1 for n in notes if n['stem'].lower() == n['title'].lower())}")
    print("inlink_title_fallback=distinct-title-only")
    print(f"tfidf_min_df={min_df_for_notes(notes)}")
    print(f"report={out / 'knowledge_gravity_report.md'}")
    print(f"action_sheet={out / 'knowledge_gravity_action_sheet.md'}")


if __name__ == "__main__":
    main()
