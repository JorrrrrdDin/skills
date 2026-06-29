# Expected output — `examples/dirty-skill`

This is the verbatim report `skill-sanitizer` produces on the bundled
`dirty-skill` fixture. It exists so you can confirm your install behaves
identically. The four planted leaks (one fake secret, one home-dir path, one
personal email, one Jira marker block) make the scanner **BLOCK** with exit
code `1`.

## Command

```bash
cd examples/dirty-skill
python ../../scanner.py .
```

## Human report (stderr)

```
=== skill-sanitizer report ===
scanned: .../examples/dirty-skill
config:  (none; using generic defaults + auto-seeded identity)
files scanned: 2
BLOCK=2  WARN=4

[BLOCK] provider-api-key
    sync.py:5
    match: ghp_…Xy
    fix:   GitHub token. Remove and rotate; use a secret/env var.
[BLOCK] env-secret
    sync.py:5
    match: ghp_…Xy
    fix:   Secret value assigned to a credential-named variable. Move to env var / .env.example placeholder.
[WARN] plugin-split:atlassian-jira-confluence
    sync.py
    match: [atlassian-jira-confluence markers]
    fix:   Skill embeds atlassian-jira-confluence code (markers: /rest/api/[23]/, \.atlassian\.net, \bcustomfield_\d+). Extract it into a dedicated atlassian-jira-confluence service plugin and depend on it; keep this generic skill portable.
[WARN] high-entropy-secret
    sync.py:5
    match: ghp_…Xy
    fix:   High-entropy string of unknown format. Verify it is not a secret; if it is, remove and rotate.
[WARN] local-machine-path
    sync.py:8
    match: C:\U…oe
    fix:   Local path leaks username 'jdoe'. Replace with ~ / $HOME / %USERPROFILE% / <USER>.
[WARN] pii-email
    sync.py:11
    match: jane…om
    fix:   Email address. Replace with a reserved example.com address or allowlist if intentional.

plugin-split suggested for: atlassian-jira-confluence

exit: 1 (BLOCK present)
```

## Machine-readable line (last line of stdout)

```
RESULT_JSON={"version":"1.0","scanned_root":".../examples/dirty-skill","findings":[{"line":5,"col":17,"category":"provider-api-key","severity":"BLOCK","snippet":"ghp_…Xy","suggestion":"GitHub token. Remove and rotate; use a secret/env var.","file":"sync.py"},{"line":5,"col":17,"category":"env-secret","severity":"BLOCK","snippet":"ghp_…Xy","suggestion":"Secret value assigned to a credential-named variable. Move to env var / .env.example placeholder.","file":"sync.py"},{"file":"sync.py","line":0,"col":0,"category":"plugin-split:atlassian-jira-confluence","severity":"WARN","snippet":"[atlassian-jira-confluence markers]","suggestion":"..."},{"line":5,"col":17,"category":"high-entropy-secret","severity":"WARN","snippet":"ghp_…Xy","suggestion":"..."},{"line":8,"col":15,"category":"local-machine-path","severity":"WARN","snippet":"C:\\U…oe","suggestion":"..."},{"line":11,"col":21,"category":"pii-email","severity":"WARN","snippet":"jane…om","suggestion":"..."}],"counts":{"block":2,"warn":4,"files_scanned":2},"service_plugins_suggested":["atlassian-jira-confluence"],"suppression":{"suppressed_files":0,"ignore_patterns":[],"dangerous_ignore_globs":[],"ignore_file_suppressed_files":0,"ignore_line_suppressed_lines":0,"ignore_line_suppressed_findings":0},"scan_errors":[],"blocked":true,"exit_code":1}
```

## Verdict

```
Exit code: 1  (BLOCK — do NOT publish)
```

Notes:
- Every `snippet` is REDACTED (first 4 + last 2 chars) — the scanner never
  emits the full secret, even though it caught it.
- The same `ghp_` token is reported by THREE rules (provider-prefix BLOCK,
  credential-named env-var BLOCK, and the entropy backstop WARN) — overlapping
  detectors are the fail-closed design: removing the token clears all three.
- `suppression` is all-zero and `scan_errors` is empty, so this BLOCK is a
  genuine finding, not something a directive hid.
- After remediation (env-var the token, `~` for the path, an `example.com`
  email, Jira code moved to a plugin) the same folder scans to **exit 0**.
