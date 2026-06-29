# skill-sanitizer

**English** | [한국어](README.ko.md)

> **The airport security checkpoint for your skills.** Scan before you share — catch the key, path, or client name *before* `git push`, not after.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT) ![Python](https://img.shields.io/badge/python-stdlib--only-blue.svg) ![Fail](https://img.shields.io/badge/mode-fail--closed-red.svg)

A skill that keeps your shared skills clean. You build a skill, you want to share it with the community — and you do *not* want to be the person who shipped a live API key, your home directory path, or a client's name in plaintext. skill-sanitizer is the metal detector you walk every skill through on the way out the door.

It's a Claude Code / AI-IDE skill **and** a standalone, stdlib-only Python CLI. No dependencies. No network. Just point it at a folder.

---

## The mental model

Think of it like airport security. Everything in your bag goes through the scanner before it's allowed past the gate. Most things sail through. A few get flagged for a second look. And the genuinely dangerous stuff — the live key, the private cert — gets a hard **STOP** at the checkpoint. Nothing leaks because nothing leaves un-scanned.

skill-sanitizer is **fail-closed**: when in doubt, it blocks. A scanner that quietly waves things through is worse than no scanner at all.

---

## What it catches

| Class | Severity | Examples |
|---|---|---|
| **🔑 Secrets** | BLOCK | API keys & tokens (`sk-`, `ghp_`, `AKIA…`, Stripe, Slack, JWT), private keys, DB connection strings, `.env` values |
| **🏠 Proprietary** | BLOCK / WARN | Local machine paths (`C:\Users\<you>\…`, `/home/<you>`, UNC, internal hostnames), internal project/skill names, client names (via a local private dictionary) |
| **📇 PII** | WARN | Emails, phone numbers |
| **🔌 Service code** | WARN | github / jira / slack / stripe / aws / notion / linear bindings that should be **split into a dedicated plugin** instead of baked into a generic skill |

There's also a **high-entropy backstop** to catch random-looking secrets that don't match a known prefix.

---

## Quick Start (10 seconds)

Install as a skill:

```bash
git clone https://github.com/animaresearch/skills
cp -r skills/04-skill-sanitizer <your-agent-skills-dir>/
```

Or just run the scanner directly on any folder:

```bash
python scanner.py <dir>
```

That's it. No config, no deps, no setup. Here's what a catch looks like:

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

Clean folder? You get a plain **`Safe to share`** and exit 0. Go ship it.

---

## Why this exists

Because the failure mode is *silent and permanent*.

You're moving fast, you copy a working skill out of your dev folder, you `git push` to share it — and now there's a live key in a public commit, or your username and an internal project name are sitting in someone's clone forever. Rotating a leaked secret is a bad afternoon. Un-leaking a client's name is impossible.

skill-sanitizer puts a checkpoint between "it works on my machine" and "it's on the internet." Run it once before you share. That's the whole pitch.

---

## Credible, because it's been attacked

This isn't a weekend regex script that trusts itself.

- **Adversarially audited** by an independent multi-agent review that hunted specifically for ways to sneak something past it — and found and **closed five fail-open paths.** Among them: a placeholder-substring bypass where a *live database connection string* containing the word `none` was passing as "Safe to share"; UTF-16-encoded files slipping under detection entirely; and a wholesale `.sanitizerignore` glob that could silently hide the whole tree from the scan.
- **Caught a real leak on its very first real run** against an actual skill collection: a hardcoded home-dir path (with a username) plus an internal project name embedded across two skills. Both were sanitized — and the scan *confirmed* that sensitive ID numbers in the same collection did **not** leak. It found the real thing and didn't cry wolf on the safe thing.

A scanner you can't trust is just decoration. This one earned trust the hard way.

---

## CI / pre-commit usage

The exit code is the integration point:

| Exit | Meaning |
|---|---|
| `0` | Clean — safe to share |
| `1` | **BLOCK** — must-fix leak found |
| `2` | **WARN** — review recommended |
| `3` | **Scan-integrity failure** — e.g. a dangerous wholesale `.sanitizerignore` glob trying to blind the scanner |

**pre-commit / pre-push hook:**

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

Note that exit `3` is its own signal on purpose — if someone tries to neuter the scanner with an over-broad ignore glob, that's treated as a failure, not a pass.

---

## Private dictionaries (kept out of the shipped skill)

Your client names and internal project names are themselves sensitive — so they don't live in the repo. skill-sanitizer reads an external, **gitignored** `.sanitizer.local.json` for your private dictionary. Copy the example and fill in your own:

```bash
cp .sanitizer.local.example.json .sanitizer.local.json
# add your client/project/codename strings — this file stays local
```

The shipped skill stays generic and shareable; your secret word-list never travels with it.

---

## Fail-closed philosophy

Three rules the scanner lives by:

1. **When in doubt, BLOCK.** A missed leak is unrecoverable; a false alarm costs you ten seconds.
2. **Don't trust the input to disarm you.** Encodings (UTF-16), placeholder-looking substrings, and ignore globs can't be used to slip past detection — those routes were specifically hunted and closed.
3. **Tampering with the scan is itself a failure** (exit 3), not a quiet pass.

---

## Limitations (honest)

- **The entropy backstop is soft.** It catches random-looking secrets that don't match a known prefix, but high-entropy heuristics inherently over-warn — expect the occasional false positive on hashes, UUIDs, or minified blobs. That's the fail-closed tax, and it's the right side to err on.
- **It is not a replacement for real secret rotation.** If a key was ever exposed, *rotate it.* This tool stops the *next* leak; it can't un-ring a bell that already rang.
- **It's skill-folder-scoped**, not a full-repo history scanner. It complements tools like git-secrets / trufflehog; it doesn't replace them.
- **Report-only by design.** It never edits your files — it tells you what to fix, you fix it.

---

## License

MIT. Use it, fork it, wire it into your release pipeline. Just don't ship the key.
