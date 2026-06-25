<p align="center">
  <img src="assets/knowledge-gravity-banner.svg" alt="Knowledge Gravity Lab banner" width="100%" />
</p>

<p align="center">
  <img src="assets/result-table-screenshot.png" alt="Rendered 80-point feedback loop table" width="100%" />
</p>

<p align="center">
  <img src="assets/workflow-demo.gif" alt="Knowledge Gravity command line workflow demo" width="100%" />
</p>

<h1 align="center">Knowledge Gravity Lab</h1>

<p align="center">
  <strong>Map the hidden gravity of your notes.</strong><br/>
  Point it at your Obsidian vault. Get back what's central, what's noise, and what to clean next.
</p>

<p align="center">
  <img alt="Knowledge map" src="https://img.shields.io/badge/knowledge-map-111827">
  <img alt="Markdown notes" src="https://img.shields.io/badge/notes-Markdown-2563EB">
  <img alt="Obsidian ready" src="https://img.shields.io/badge/Obsidian-ready-7C3AED">
  <img alt="Works with Codex and Claude" src="https://img.shields.io/badge/assistants-Codex%20%7C%20Claude%20%7C%20CLI-7C3AED">
  <img alt="No runtime API" src="https://img.shields.io/badge/runtime_API-none-16A34A">
</p>

<p align="center">
  English | <a href="README.ko.md">한국어</a>
</p>

---

Knowledge Gravity Lab is a tiny offline tool for a problem every serious note
taker eventually has: a vault full of notes and no idea what to clean first.

Point it at a Markdown or Obsidian folder and it tells you:

- what is central
- what is orphaned
- what looks like noise
- which clusters are getting too large
- the next cleanup action per note

One Python file. No API, no runtime LLM, deterministic.

It is built for:

- Obsidian vaults
- research notes
- invention logs
- paper cards
- memory exports
- worldbuilding or writing notebooks
- any messy Markdown folder that needs structure

It is not locked to one assistant. Use it directly from the command line, or
install the workflow files for Codex, Claude, or any assistant that can read a
local Markdown instruction file and run the bundled Python script.

## What It Produces

Running the bundled analyzer creates:

| Output | Purpose |
|---|---|
| `knowledge_gravity_report.md` | human-readable summary of centers, clusters, noise, and orphans |
| `knowledge_gravity_action_sheet.md` | temporary cleanup workspace with concrete next actions |
| `knowledge_gravity_nodes.csv` | note-level metrics |
| `knowledge_gravity_edges.csv` | inferred note-to-note links |
| `knowledge_gravity_data.json` | machine-readable analysis payload |

## Why It Feels Different

Most note tools show a graph. Knowledge Gravity asks a more useful question:

> Which notes are pulling the whole knowledge field, and which ones are just drifting?

It scores practical signals such as links, tags, headings, note size, repository
share, center score, orphan status, and review risk. The point is not to produce
a perfect graph. The point is to make the next cleanup action obvious.

## Install

Clone or download this repository:

```powershell
git clone https://github.com/JorrrrrdDin/knowledge-gravity-lab.git
cd knowledge-gravity-lab
```

Run the analyzer directly:

```powershell
python scripts\analyze_corpus.py --input "C:\path\to\vault" --output "D:\knowledge-gravity-output"
```

Optional: install it into a local assistant workflow folder. The same core files
can be used with Codex, Claude, or any compatible local-agent workflow:

```powershell
Copy-Item -Recurse . "<assistant-workflows>\knowledge-gravity-lab" -Force
```

The installed folder should look like this:

```text
knowledge-gravity-lab/
  SKILL.md
  agents/openai.yaml
  scripts/analyze_corpus.py
  references/public-boundary.md
  references/existing-rights-check.md
```

## Use

Run it from the command line:

```powershell
python scripts\analyze_corpus.py --input "C:\path\to\vault" --output "D:\knowledge-gravity-output"
```

Skip low-value folders when needed:

```powershell
python scripts\analyze_corpus.py --input "C:\path\to\vault" --output "D:\knowledge-gravity-output" --skip-dir "archive" --skip-dir "templates"
```

If installed into an assistant workflow folder, you can also ask:

```text
Use Knowledge Gravity Lab on my Obsidian vault and tell me what to clean first.
```

## Example Feedback Loop

The action sheet is designed to push note cleanup instead of just admiring a
score:

```text
This note is at 61/100.
Add 2 links, split the overgrown section, and connect it to the nearest cluster
to push it toward 80/100.
```

That makes the workflow simple:

1. Run the map.
2. Open the action sheet.
3. Fix the highest-leverage notes.
4. Run again.
5. Watch the knowledge field become cleaner.

## Public Boundary

This is a practical knowledge-hygiene workflow. It is not legal advice, not a
patent filing package, and not a guarantee that a note is true or false.

Knowledge Gravity uses heuristic analysis to help humans review their own
knowledge base. Treat its outputs as decision support, not ground truth.

## Repository Contents

```text
.
|-- SKILL.md
|-- agents/
|   `-- openai.yaml
|-- scripts/
|   `-- analyze_corpus.py
|-- references/
|   |-- public-boundary.md
|   `-- existing-rights-check.md
|-- tests/
|   `-- test_analyze_corpus.py
`-- assets/
    `-- knowledge-gravity-banner.svg
```

## Development Checks

```powershell
python -m pytest -q
python -m compileall -q scripts tests
```

## License

MIT License.
