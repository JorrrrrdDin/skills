# Knowledge Gravity Lab Launch Kit

Drop-in copy for repo settings and launch channels.

## GitHub Repo Description

```text
Offline tool that maps a Markdown/Obsidian vault and tells you which notes to fix first — center topics, orphans, noise, and a per-note next action. No API, no LLM, deterministic.
```

Shorter alternative:

```text
Point it at your Obsidian vault. Get back what's central, what's noise, and what to clean next — fully offline, no API.
```

## GitHub Topics

```text
obsidian, obsidian-plugin-adjacent, markdown, note-taking,
knowledge-management, pkm, second-brain, knowledge-graph,
zettelkasten, python, offline-first, cli
```

## X / Twitter

Attach `assets/result-table-screenshot.png` or `assets/workflow-demo.gif`.

```text
Built a tiny tool for a problem every Obsidian user has: a vault full of notes and
no idea what to clean first.

Point it at your Markdown folder -> it tells you the center topics, the orphans, the
noise, and the next action per note.

One Python file. No API, no LLM, runs 100% offline.

https://github.com/JorrrrrdDin/knowledge-gravity-lab
```

Follow-up:

```text
The part I actually use: an "80-point loop." Every note gets a score and a concrete
next move — "add 2 links, archive this, split that." Cleanup becomes a to-do list,
not a vibe.
```

## Reddit

Post the screenshot in the comments or use the GIF as the lead asset.

Title:

```text
I made a free offline tool that scans your vault and tells you which notes to fix first
```

Body:

```text
My vault got to a few hundred notes and I lost the plot — couldn't tell which notes
were actually load-bearing vs. dead fragments I'd never link again.

So I wrote a small Python script (no plugins, no API, nothing leaves your machine)
that reads the relationships between notes and spits out:

- center notes (your real hubs)
- a review queue (short / orphan / untagged / template noise)
- orphan notes drifting with no links
- overgrown topic clusters to split
- an action sheet with a per-note "next move" and an 80-point target

It's deterministic — same vault, same answer — and runs fully offline.
MIT licensed. Feedback welcome, especially on the scoring heuristics.

https://github.com/JorrrrrdDin/knowledge-gravity-lab
```

## Show HN

Use the README screenshot/GIF as the visual proof when cross-posting elsewhere.

Title:

```text
Show HN: Offline tool that maps a Markdown vault and ranks what to clean first
```

First comment:

```text
Author here. This started as a way to keep my own research/invention notes from
rotting. It's a single dependency-free Python file: it tokenizes a folder of
Markdown, builds TF-IDF + wikilink edges, does union-find clustering, and scores
each note for centrality and "needs review."

The deliberate constraint is no runtime LLM and no network — it's a deterministic
heuristic, so the same vault always produces the same map, and your notes stay
local. The output I actually use day to day is an action sheet that names the next
move per note (add links, split, merge, archive) toward an 80-point target.

It's explicitly not a truth detector — the "review queue" means "a human should
look," not "this is wrong." Happy to talk about the scoring choices.
```

## Visual Assets

- `assets/result-table-screenshot.png`: rendered 80-point feedback loop table.
- `assets/action-sheet-screenshot.png`: larger rendered action sheet screenshot.
- `assets/workflow-demo.gif`: 10-second command -> generated files -> result table demo.
