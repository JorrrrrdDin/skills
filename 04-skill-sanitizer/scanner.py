#!/usr/bin/env python3
# sanitizer: ignore-file
"""skill-sanitizer: pre-share leak scanner for Claude Code skills.

Stdlib-only (os, sys, re, json, math, argparse, pathlib). Cross-platform.
Scans a target directory recursively for:
  - secrets (provider API keys, private keys, .env values, high-entropy strings)
  - PII (emails, phones)
  - local machine paths (C:\\Users\\<name>, /home/<name>, /Users/<name>, UNC, internal hosts)
  - client/proper-noun names (from an EXTERNAL local config dictionary)
  - service-specific code markers (jira/github/gitlab/slack/salesforce/notion/linear/stripe/aws/...)

Prints a human-readable report, then a final line exactly:
    RESULT_JSON={...}
Exits nonzero IFF any BLOCK finding exists. Fail-closed: ambiguous => flag.
"""

import os
import sys
import re
import json
import math
import fnmatch
import argparse
from pathlib import Path

VERSION = "1.0"

# ---------------------------------------------------------------------------
# Placeholder / allowlist set (always on). Suppresses entropy, env-value and
# connection-string password matches. NEVER suppresses a known-prefix BLOCK.
# ---------------------------------------------------------------------------
# Whole-value placeholder tokens. A value is a placeholder ONLY when the ENTIRE
# value is one of these (re.fullmatch) -- a mere substring NEVER suppresses.
# The alternation is wrapped so common decorations (your_..._here, leading/
# trailing separators, repeated placeholder words) still fullmatch.
_PLACEHOLDER_WORDS = [
    r"x{3,}", r"X{3,}", r"0{3,}", r"\*{3,}", r"\.{3,}", r"_{3,}", r"-{3,}",
    r"change[-_]?me", r"your[-_]?(?:api[-_]?key|token|secret|password|value|name|here)?",
    r"my[-_]?secret", r"placeholder", r"redacted", r"dummy", r"sample",
    r"example", r"foobar", r"test123?", r"todo", r"fixme", r"fake", r"none",
    r"here", r"insert", r"replace", r"pw", r"password", r"secret", r"token",
    r"<[^>]+>",            # <angle templates>
    r"\$\{[^}]+\}",        # ${shell vars}
    r"\{\{[^}]+\}\}",      # {{mustache}}
    r"%[A-Za-z_]+%",       # %ENVVAR%
]
_PLACEHOLDER_ALT = "|".join(_PLACEHOLDER_WORDS)
# Full-value placeholder: one or more placeholder words joined by separators,
# optionally wrapped in quotes/brackets. The WHOLE value must be consumed.
PLACEHOLDER_FULL_RE = re.compile(
    r"(?i)^[\"'`<>\[\]{}()]*"
    r"(?:" + _PLACEHOLDER_ALT + r")"
    r"(?:[-_. ]*(?:" + _PLACEHOLDER_ALT + r"))*"
    r"[\"'`<>\[\]{}()]*$"
)
# Template-style markers (angle/shell/mustache/env) anywhere => placeholder,
# since these can never be a real literal secret.
PLACEHOLDER_TEMPLATE_RE = re.compile(
    r"<[^>]+>|\$\{[^}]+\}|\{\{[^}]+\}\}|%[A-Za-z_]+%"
)

GENERIC_USERNAMES = {
    "user", "username", "youruser", "your-user", "me", "example", "runner",
    "vscode", "root", "administrator", "public", "default", "all users",
    "name", "yourname", "test", "ci", "build", "home",
}

EXAMPLE_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net", "test", "localhost",
    "email.com", "domain.com", "yourcompany.com", "your-company.com",
    "acme.example", "company.com",
}
EXAMPLE_LOCALPARTS = {"noreply", "no-reply", "support", "hello", "admin", "your-email", "you"}

# Binary / skip file extensions
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".pdf",
    ".zip", ".gz", ".tar", ".tgz", ".7z", ".rar", ".exe", ".dll", ".so",
    ".dylib", ".class", ".jar", ".pyc", ".woff", ".woff2", ".ttf", ".otf",
    ".mp3", ".mp4", ".mov", ".avi", ".wav", ".bin", ".dat", ".db", ".sqlite",
}
# Filenames/dirs to skip entirely
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}
# Glob-ish basenames that are noisy for entropy (still get prefix BLOCK scan)
ENTROPY_SKIP_BASENAMES = re.compile(
    r"(?i)(package-lock\.json|yarn\.lock|poetry\.lock|Cargo\.lock|.*\.min\.(js|css)|.*\.map|.*\.svg)$"
)

MAX_FILE_BYTES = 2 * 1024 * 1024  # skip files larger than 2MB for text scan


# ---------------------------------------------------------------------------
# Leak category regexes
# ---------------------------------------------------------------------------
# (name, severity, compiled_regex, remediation)
PREFIX_RULES = [
    ("provider-api-key", "BLOCK", re.compile(r"\bsk-ant-(?:api03|admin01)-[A-Za-z0-9_-]{80,}\b"),
     "Anthropic API key. Remove and rotate; reference via env var."),
    ("provider-api-key", "BLOCK", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
     "OpenAI-style API key. Remove and rotate; use os.environ."),
    ("provider-api-key", "BLOCK", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
     "GitHub token. Remove and rotate; use a secret/env var."),
    ("provider-api-key", "BLOCK", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
     "GitHub fine-grained PAT. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
     "GitLab token. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
     "Slack token. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"),
     "Slack incoming webhook URL. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{24,}\b"),
     "Stripe key. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
     "Google API key. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"),
     "SendGrid API key. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
     "npm token. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"\bhf_[A-Za-z0-9]{34,}\b"),
     "HuggingFace token. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"\bdckr_pat_[A-Za-z0-9_-]{20,}\b"),
     "Docker PAT. Remove and rotate."),
    ("provider-api-key", "BLOCK", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
     "JWT. If it carries real claims/signature, remove and rotate."),
    ("aws-access-key-id", "BLOCK", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA)[0-9A-Z]{16}\b"),
     "AWS access key id. Remove and rotate immediately."),
]

# Generic / medium-confidence prefixes: subject to the placeholder downgrade.
# (Bare OpenAI-style sk-…, and JWT.) High-specificity prefixes stay BLOCK.
GENERIC_PREFIX_PATTERNS = {
    r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b",
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
}

PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
    r"|PuTTY-User-Key-File-\d"
    r"|\bAGE-SECRET-KEY-1[0-9A-Z]{50,}\b"
)

AWS_SECRET_CTX_RE = re.compile(r"(?i)aws_?secret_?access_?key['\"\s:=]+([A-Za-z0-9/+]{40})")

CONN_STRING_RE = re.compile(
    r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:([^/\s:@]{3,})@[^/\s]+"
)

ENV_SECRET_RE = re.compile(
    r"(?im)^\s*(?:export\s+)?([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|APIKEY|API_KEY|"
    r"ACCESS_KEY|PRIVATE_KEY|CLIENT_SECRET|AUTH|CREDENTIAL|PASSPHRASE|DSN)[A-Z0-9_]*)"
    r"\s*[:=]\s*['\"]?([^'\"\s#]{6,})['\"]?"
)

# ---------------------------------------------------------------------------
# Group C: high-value secret context rules (escalate to BLOCK)
# ---------------------------------------------------------------------------
# HTTP auth headers: Authorization / Proxy-Authorization / X-Api-Key.
AUTH_HEADER_RE = re.compile(
    r"(?i)\b(?:proxy-)?authorization\s*[:=]\s*['\"]?\s*"
    r"(?:(bearer|basic)\s+)?([A-Za-z0-9+/._=~-]{16,})"
)
APIKEY_HEADER_RE = re.compile(
    r"(?i)\bx-api-key\s*[:=]\s*['\"]?\s*([A-Za-z0-9+/._=~-]{16,})"
)
# GCP service-account private_key JSON value (long high-entropy base64 body).
GCP_PRIVATE_KEY_RE = re.compile(
    r"(?i)\"?private_key\"?\s*[:=]\s*['\"]([^'\"]{100,})['\"]"
)
GCP_SA_CONTEXT_RE = re.compile(
    r"(?i)\"type\"\s*:\s*\"service_account\"|client_email|private_key_id"
)
# Headerless PEM/key body: contiguous 60-65 char pure-base64 lines.
PEM_BODY_LINE_RE = re.compile(r"^[A-Za-z0-9+/]{60,65}={0,2}$")
KEY_MATERIAL_CTX_RE = re.compile(r"(?i)private_key|id_rsa|BEGIN [A-Z ]*PRIVATE KEY")

# Secret-store REFERENCES (best-practice non-secrets) -> exempt to WARN.
SECRET_REF_VALUE_RE = re.compile(
    r"(?i)^['\"]?(?:/run/secrets/[\w./-]+"
    r"|vault://[\w./:-]+"
    r"|arn:aws:secretsmanager:[\w:/-]+"
    r"|secret://[\w./-]+"
    r"|file://[\w./-]+)['\"]?$"
)
SECRET_REF_NAME_RE = re.compile(r"(?i)_(?:FILE|REF|PATH|NAME|ID)$")


def is_secret_reference(key, val):
    """True if (key, val) is a pointer to a secret store, not a literal secret."""
    v = (val or "").strip()
    if SECRET_REF_VALUE_RE.match(v):
        return True
    if key and SECRET_REF_NAME_RE.search(key):
        return True
    return False


ENTROPY_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_-]{20,}")
HEX_RE = re.compile(r"^[0-9a-fA-F]{32,}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?:(?<![\w.])\+\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]\d{3,4}[\s.-]\d{3,4}\b"
)
KR_PHONE_RE = re.compile(r"\b01[016-9][-.]?\d{3,4}[-.]?\d{4}\b")
SEMVER_RE = re.compile(r"\bv?\d+\.\d+\.\d+\b")

WIN_PATH_RE = re.compile(r"(?i)[A-Z]:[\\/]Users[\\/]([^\\/\r\n:*?\"<>|]+)")
POSIX_HOME_RE = re.compile(r"/home/([^/\s]+)")
MAC_HOME_RE = re.compile(r"/Users/([^/\s]+)")
WSL_PATH_RE = re.compile(r"/mnt/[a-z]/Users/([^/\s]+)")

UNC_RE = re.compile(r"\\\\[A-Za-z0-9._-]+\\[^\\\s]+")
INTERNAL_HOST_RE = re.compile(r"\b[a-z0-9-]+\.(?:internal|local|lan|corp|intranet|localdomain)\b", re.I)
PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)

# ---------------------------------------------------------------------------
# Service signatures (plugin-split detection)
# ---------------------------------------------------------------------------
SERVICE_SIGNATURES = {
    "atlassian-jira-confluence": [
        r"\.atlassian\.net", r"/rest/api/[23]/", r"/wiki/rest/api",
        r"from\s+jira\s+import", r"atlassian[_-]python[-_]api",
        r"JIRA_API_TOKEN", r"CONFLUENCE_", r"\bcustomfield_\d+",
    ],
    "github": [
        r"api\.github\.com", r"from\s+github\s+import\s+Github", r"octokit",
        r"GITHUB_TOKEN", r"GH_TOKEN", r"X-GitHub-Event",
        r"/repos/\{?owner\}?/", r"actions/checkout",
    ],
    "gitlab": [
        r"gitlab\.com/api/v4", r"/api/v4/projects", r"python-gitlab",
        r"\bimport\s+gitlab\b", r"CI_JOB_TOKEN", r"GITLAB_TOKEN", r"\.gitlab-ci\.yml",
    ],
    "slack": [
        r"slack_sdk", r"slack_bolt", r"@slack/web-api", r"hooks\.slack\.com/services",
        r"chat\.postMessage", r"conversations\.list", r"SLACK_BOT_TOKEN",
        r"SLACK_SIGNING_SECRET",
    ],
    "salesforce": [
        r"\.salesforce\.com", r"\.force\.com", r"/services/data/v\d",
        r"simple_salesforce", r"\bSELECT\b.+\bFROM\s+(?:Account|Contact|Lead|Opportunity)\b",
        r"SF_SECURITY_TOKEN", r"__c\b",
    ],
    "notion": [
        r"api\.notion\.com/v1", r"Notion-Version", r"notion[_-]client",
        r"@notionhq/client", r"NOTION_API_KEY", r"NOTION_TOKEN", r"NOTION_DATABASE_ID",
    ],
    "linear": [
        r"api\.linear\.app/graphql", r"@linear/sdk", r"LINEAR_API_KEY",
        r"\blin_api_", r"issueCreate", r"teamId",
    ],
    "stripe": [
        r"api\.stripe\.com", r"\bimport\s+stripe\b", r"STRIPE_SECRET_KEY",
        r"STRIPE_WEBHOOK_SECRET", r"\bwhsec_", r"PaymentIntent", r"/v1/charges",
    ],
    "aws": [
        r"\bimport\s+boto3\b", r"\bbotocore\b", r"\.amazonaws\.com",
        r"AWS_ACCESS_KEY_ID", r"AWS_SECRET_ACCESS_KEY", r"\barn:aws:",
        r"boto3\.client\(",
    ],
    "google-workspace": [
        r"googleapis\.com/(?:gmail|drive|calendar|sheets)", r"googleapiclient",
        r"google\.oauth2", r"GOOGLE_APPLICATION_CREDENTIALS",
        r"\"type\":\s*\"service_account\"", r"\"private_key\":",
    ],
}
SERVICE_ADVICE = (
    "Skill embeds {svc} code (markers: {markers}). Extract it into a dedicated "
    "{svc} service plugin and depend on it; keep this generic skill portable."
)
SERVICE_COMPILED = {
    svc: [re.compile(p, re.I) for p in pats] for svc, pats in SERVICE_SIGNATURES.items()
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def shannon_entropy(s):
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def is_placeholder(value):
    """A value is a placeholder ONLY if the WHOLE value is placeholder-shaped.

    Substring matches NEVER suppress (closes the substring-evasion fail-open).
    Template markers (<...>, ${...}, {{...}}, %ENV%) spanning the whole value,
    or a single template token equal to the whole value, also count.
    """
    v = value.strip()
    if not v:
        return True
    # all same char (e.g. "xxxxx", "00000")
    if len(set(v)) <= 1:
        return True
    if PLACEHOLDER_FULL_RE.fullmatch(v):
        return True
    # A pure template token as the entire value (e.g. "<password>", "${PW}").
    stripped = v.strip("\"'`")
    m = PLACEHOLDER_TEMPLATE_RE.fullmatch(stripped)
    if m:
        return True
    return False


# Documentation-placeholder vocabulary. A *segment* of a value (split on
# -_. and spaces) is "wordy/benign" if it is one of these, a provider scheme
# fragment, a pure-digit run, or a short low-entropy alpha word. This is the
# basis for DOWNGRADING (BLOCK->WARN) doc placeholders like
# `ghp_your_github_token` / `xoxp-new-token-here` WITHOUT ever downgrading a
# real, high-entropy secret -- a single random high-entropy segment (e.g. the
# 40-hex body of a real ghp_ token, or `noneSecretRealP4ssw0rd99`) makes the
# whole value NON-placeholder, so it keeps its BLOCK severity.
_DOC_PLACEHOLDER_WORDS = {
    "your", "my", "our", "the", "a", "an", "new", "old", "some",
    "example", "examples", "sample", "samples", "demo", "test", "tests",
    "testing", "dummy", "fake", "mock", "placeholder", "redacted", "hidden",
    "token", "tokens", "secret", "secrets", "key", "keys", "apikey", "api",
    "password", "passwd", "pass", "pwd", "credential", "credentials", "auth",
    "here", "there", "value", "val", "name", "id", "string", "goes", "go",
    "insert", "replace", "put", "enter", "add", "set", "use", "paste",
    "changeme", "change", "me", "todo", "fixme", "foo", "bar", "baz", "foobar",
    "xxx", "abc", "abcdef", "none", "null", "nil", "real", "actual", "valid",
    "github", "gitlab", "slack", "stripe", "google", "aws", "openai", "anthropic",
    "personal", "access", "bearer", "user", "username", "client", "app",
}
# Provider scheme / prefix fragments that legitimately lead a placeholder.
_DOC_PLACEHOLDER_PREFIXES = {
    "ghp", "gho", "ghu", "ghs", "ghr", "gh", "sk", "pk", "rk", "xox", "xoxp",
    "xoxb", "xoxa", "xoxr", "xoxs", "glpat", "hf", "npm", "dckr", "pat", "live",
    "test", "proj", "sg", "aiza", "akia", "asia", "sk-ant", "api03",
}
# A segment is "obviously random secret material" (and therefore makes the whole
# value a real secret, not a placeholder) when it is long AND high-entropy.
_RANDOM_SEGMENT_MINLEN = 16
_RANDOM_SEGMENT_MINENT = 3.5
_SEGMENT_SPLIT_RE = re.compile(r"[-_. ]+")


def looks_like_doc_placeholder(value):
    """True for low-entropy, dictionary-wordy documentation placeholders.

    Unlike is_placeholder() (which requires the WHOLE value to be a placeholder
    template and is intentionally strict), this recognizes *composed* doc
    placeholders such as `ghp_your_github_token` or `xoxp-new-token-here` so
    they can be DOWNGRADED from BLOCK to WARN.

    Fail-closed guard: returns False (=> keep BLOCK) if ANY segment looks like
    random secret material (>= 16 chars AND entropy >= 3.5). That single guard
    keeps real high-entropy secrets blocking even when they contain a word like
    "none"/"example" as a substring (e.g. `noneSecretRealP4ssw0rd99`), closing
    the audited substring-evasion path.
    """
    v = (value or "").strip().strip("\"'`")
    if not v:
        return False
    segs = [s for s in _SEGMENT_SPLIT_RE.split(v) if s]
    if not segs:
        return False
    saw_placeholder_word = False
    for seg in segs:
        low = seg.lower()
        # Any long, high-entropy segment => treat as real secret material.
        if len(seg) >= _RANDOM_SEGMENT_MINLEN and shannon_entropy(seg) >= _RANDOM_SEGMENT_MINENT:
            return False
        if low in _DOC_PLACEHOLDER_WORDS:
            saw_placeholder_word = True
            continue
        if low in _DOC_PLACEHOLDER_PREFIXES:
            continue
        if seg.isdigit():
            continue
        # Short, low-entropy alpha-ish word (e.g. "github", "newtoken"): benign.
        if (len(seg) <= 12 and shannon_entropy(seg) < 3.0
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", seg)):
            continue
        # Any other segment (long/random/mixed) is NOT benign -> not a placeholder.
        return False
    return saw_placeholder_word


def redact(s):
    s = s.strip()
    if len(s) <= 8:
        return s[0] + "…" if s else ""
    return s[:4] + "…" + s[-2:]


def mixed_classes(s):
    return (any(c.islower() for c in s) + any(c.isupper() for c in s)
            + any(c.isdigit() for c in s)) >= 2


def load_config(start_dir, explicit=None):
    """Find and load .sanitizer.local.json walking up from start_dir, then $HOME."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    cur = Path(start_dir).resolve()
    for parent in [cur] + list(cur.parents):
        candidates.append(parent / ".sanitizer.local.json")
    home = Path(os.path.expanduser("~"))
    candidates.append(home / ".sanitizer.local.json")

    for c in candidates:
        try:
            if c.is_file():
                with open(c, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return str(c), data
        except (OSError, ValueError):
            # malformed config => fail-closed usage error handled by caller
            if explicit and Path(explicit) == c:
                raise
            continue
    return None, {}


def auto_seed_terms():
    """Derive author identity at runtime (in-memory only). Never written out."""
    seeds = set()
    for var in ("USERNAME", "USER"):
        v = os.environ.get(var)
        if v and len(v) >= 2:
            seeds.add(v)
    try:
        import socket
        h = socket.gethostname()
        if h and len(h) >= 2:
            seeds.add(h)
    except Exception:
        pass
    # git identity (best-effort)
    try:
        import subprocess
        for key in ("user.name", "user.email"):
            try:
                out = subprocess.run(
                    ["git", "config", "--get", key],
                    capture_output=True, text=True, timeout=3,
                )
                val = (out.stdout or "").strip()
                if val and len(val) >= 3:
                    seeds.add(val)
            except Exception:
                pass
    except Exception:
        pass
    return {s for s in seeds if s.lower() not in GENERIC_USERNAMES}


def build_dictionary(config):
    block_terms = list(config.get("block_terms", []) or [])
    block_terms += list(config.get("client_names", []) or [])
    block_terms += list(config.get("project_codenames", []) or [])
    warn_terms = list(config.get("warn_terms", []) or [])
    own_user = config.get("own_username")
    if own_user:
        block_terms.append(own_user)
    block_re = None
    warn_re = None
    if block_terms:
        block_re = re.compile(
            r"(?i)\b(?:" + "|".join(re.escape(t) for t in block_terms) + r")\b"
        )
    if warn_terms:
        warn_re = re.compile(
            r"(?i)\b(?:" + "|".join(re.escape(t) for t in warn_terms) + r")\b"
        )
    return block_re, warn_re, len(block_terms) + len(warn_terms)


def is_text_file(path):
    ext = path.suffix.lower()
    if ext in BINARY_EXTS:
        return False
    return True


# ---------------------------------------------------------------------------
# Suppression directives (stdlib-only; do not affect detection regexes)
# ---------------------------------------------------------------------------
IGNORE_FILE_TOKEN = "sanitizer: ignore-file"
IGNORE_LINE_TOKEN = "sanitizer: ignore-line"
SANITIZERIGNORE_NAME = ".sanitizerignore"


def load_sanitizerignore(root):
    """Read .sanitizerignore at the scan root -> list of gitignore-style globs."""
    patterns = []
    try:
        p = Path(root) / SANITIZERIGNORE_NAME
        if p.is_file():
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    s = raw.strip()
                    if not s or s.startswith("#"):
                        continue
                    patterns.append(s)
    except OSError:
        pass
    return patterns


def matches_ignore(rel_posix, patterns):
    """True if a POSIX-normalized relative path matches any gitignore-style glob."""
    base = rel_posix.rsplit("/", 1)[-1]
    for pat in patterns:
        p = pat.lstrip("/")
        if p.endswith("/"):
            p = p.rstrip("/")
            if rel_posix == p or rel_posix.startswith(p + "/") or fnmatch.fnmatch(rel_posix, p + "/*"):
                return True
            continue
        if fnmatch.fnmatch(rel_posix, p):
            return True
        # bare pattern with no slash also matches by basename at any depth
        if "/" not in p and fnmatch.fnmatch(base, p):
            return True
        if fnmatch.fnmatch(rel_posix, p + "/*"):
            return True
    return False


def has_ignore_file_directive(content):
    """True only for an ANCHORED standalone comment containing the token.

    The whole (stripped) line must be a comment line whose content is the
    ignore-file token (optionally with surrounding parenthetical note). A bare
    substring buried inside code/data does NOT count (closes #4/#15 fail-open).
    """
    for line in content.splitlines()[:10]:
        s = line.strip()
        if IGNORE_FILE_TOKEN not in s:
            continue
        # Strip a leading comment marker; the remainder must START with token.
        body = re.sub(r"^(?:#|//|;|--|/\*|\*|<!--|%)\s*", "", s)
        if body.startswith(IGNORE_FILE_TOKEN):
            return True
    return False


def scan_file_level(rel, fname, content, lines):
    """File-scope findings that need whole-file context (Group C #6/#7).

    Detects headerless PEM/private-key bodies: a .pem/.key file, or contiguous
    60-65 char base64 blocks, treated as BLOCK when context indicates key
    material (filename, private_key/id_rsa, or a BEGIN banner seen anywhere).
    """
    out = []
    ext = Path(fname).suffix.lower()
    key_ext = ext in (".pem", ".key")
    ctx_key = key_ext or bool(KEY_MATERIAL_CTX_RE.search(content))
    has_begin = "BEGIN" in content and "PRIVATE KEY" in content

    # Contiguous run of pure-base64 PEM-width lines.
    run = 0
    run_start = 0
    longest = 0
    longest_start = 0
    for idx, ln in enumerate(lines, 1):
        if PEM_BODY_LINE_RE.match(ln.strip()):
            if run == 0:
                run_start = idx
            run += 1
            if run > longest:
                longest = run
                longest_start = run_start
        else:
            run = 0
    # A real key body is several such lines; a lone 64-char token is not enough
    # unless this is a .pem/.key file or explicit key context with the banner.
    body_is_key = (longest >= 3 and ctx_key) or (longest >= 2 and has_begin) \
        or (key_ext and longest >= 1)
    if body_is_key:
        out.append({
            "file": rel, "line": longest_start, "col": 1,
            "category": "private-key-body", "severity": "BLOCK",
            "snippet": "[PEM/base64 key body x{0} lines]".format(longest),
            "suggestion": "Private key material (headerless PEM body). Remove the "
                          "file from the share and rotate the key.",
        })
    return out


# ---------------------------------------------------------------------------
# Core scan of a single line
# ---------------------------------------------------------------------------
def scan_line(line, lineno, ctx):
    """Return list of finding dicts for this line."""
    out = []
    allow_emails = ctx["allow_emails"]
    seed_re = ctx["seed_re"]
    block_dict_re = ctx["block_dict_re"]
    warn_dict_re = ctx["warn_dict_re"]
    entropy_ok = ctx["entropy_enabled"] and ctx["entropy_for_file"]

    def add(category, severity, match, suggestion, col=0):
        out.append({
            "line": lineno,
            "col": col + 1,
            "category": category,
            "severity": severity,
            "snippet": redact(match),
            "suggestion": suggestion,
        })

    # 1. Known-prefix provider keys.
    # High-specificity prefixes (AKIA, ghp_, sk-ant, sk_live, etc.) -> BLOCK
    # unconditionally. Generic/medium-confidence prefixes (bare sk-…, JWT) run
    # the FULL-value placeholder filter and downgrade obvious placeholders to
    # WARN (never suppressed to nothing).
    for name, sev, rgx, suggestion in PREFIX_RULES:
        for m in rgx.finditer(line):
            tok = m.group(0)
            if rgx.pattern in GENERIC_PREFIX_PATTERNS:
                # strip a leading "sk-"/"sk-proj-" so the body is placeholder-tested
                body = re.sub(r"(?i)^sk-(?:proj-)?", "", tok)
                if is_placeholder(tok) or is_placeholder(body):
                    add(name, "WARN", tok,
                        "Generic-prefixed token that looks like a placeholder. "
                        "Confirm it is not a real credential.", m.start())
                    continue
            # Doc-placeholder downgrade (applies even to known prefixes): a
            # low-entropy, dictionary-wordy value like `xoxp-new-token-here`
            # is a documentation placeholder, NOT a live key -> WARN. A real,
            # high-entropy key (ghp_+36 random, sk_live_..., AKIA...) is never
            # wordy, so looks_like_doc_placeholder() returns False -> stays BLOCK.
            if sev == "BLOCK" and looks_like_doc_placeholder(tok):
                add(name, "WARN", tok,
                    "Known-prefix token but the value is a low-entropy "
                    "documentation placeholder. Confirm it is not a real "
                    "credential; if real, remove and rotate.", m.start())
                continue
            add(name, sev, tok, suggestion, m.start())

    # 2. Private keys
    for m in PRIVATE_KEY_RE.finditer(line):
        add("private-key", "BLOCK", m.group(0),
            "Private key material. Remove the file from the share; rotate the key.", m.start())

    # 3. AWS secret access key (contextual) -- placeholder suppression NEVER
    # applies here unless the WHOLE value is a template marker (<...>/${...}).
    for m in AWS_SECRET_CTX_RE.finditer(line):
        val = m.group(1)
        whole_template = bool(PLACEHOLDER_TEMPLATE_RE.fullmatch(val.strip("\"'`")))
        if not whole_template and shannon_entropy(val) >= 3.0:
            add("aws-secret-access-key", "BLOCK", val,
                "AWS secret access key. Remove and rotate; use env vars.", m.start(1))

    # 3b. HTTP auth headers (Authorization / Proxy-Authorization / X-Api-Key)
    # with a high-entropy value -> BLOCK (exempt only FULL-match placeholders).
    for m in AUTH_HEADER_RE.finditer(line):
        val = m.group(2)
        if is_placeholder(val):
            continue
        # Basic creds are base64(user:pass); accept lower entropy there.
        scheme = (m.group(1) or "").lower()
        ent = shannon_entropy(val)
        if scheme == "basic" or ent >= 3.0 or len(val) >= 20:
            add("auth-header-secret", "BLOCK", val,
                "Authorization/Proxy-Authorization header carries a live token. "
                "Remove and rotate; inject via env var at runtime.", m.start(2))
    for m in APIKEY_HEADER_RE.finditer(line):
        val = m.group(1)
        if is_placeholder(val):
            continue
        if shannon_entropy(val) >= 3.0 or len(val) >= 20:
            add("auth-header-secret", "BLOCK", val,
                "X-Api-Key header carries a live key. Remove and rotate; "
                "inject via env var at runtime.", m.start(1))

    # 3c. GCP service-account private_key JSON value (long high-entropy base64).
    for m in GCP_PRIVATE_KEY_RE.finditer(line):
        val = m.group(1)
        # unescape \n so an inlined PEM body's entropy is measured on the body
        body = val.replace("\\n", "").replace("\n", "")
        if is_placeholder(body):
            continue
        if len(body) >= 100 and shannon_entropy(body) >= 4.0:
            add("gcp-service-account-key", "BLOCK", val,
                "GCP service-account private_key value. Remove the key JSON from "
                "the share and rotate the service account key.", m.start(1))

    # 4. Connection string with credentials
    for m in CONN_STRING_RE.finditer(line):
        pw = m.group(1)
        if pw.lower() in ("password", "user", "pass") or is_placeholder(pw):
            continue
        sev = "BLOCK"
        if re.search(r"localhost|127\.0\.0\.1", m.group(0)):
            sev = "WARN"
        add("connection-string-credentials", sev, m.group(0),
            "URI embeds a password. Move credentials to env vars.", m.start())

    # 5. Env-assignment secret
    for m in ENV_SECRET_RE.finditer(line):
        key, val = m.group(1), m.group(2)
        # Skip code expressions: a value that references env/getenv or is a call
        # is NOT a hardcoded secret (e.g. token=os.environ.get("X")).
        val_is_code = bool(re.search(
            r"(?i)(os\.environ|getenv|process\.env|environ\[|\.get\(|^[A-Za-z_][\w.]*\()", val
        )) or "(" in val
        if val_is_code:
            continue
        # Secret-store REFERENCES (e.g. /run/secrets/..., vault://..., *_FILE)
        # are best practice, not literal secrets -> WARN not BLOCK.
        if is_secret_reference(key, val):
            add("env-secret-reference", "WARN", key + "=" + val,
                "Looks like a secret-store reference / pointer, not a literal "
                "secret. Confirm it resolves to a real secret only at runtime.",
                m.start())
            continue
        if is_placeholder(val):
            add("env-secret", "WARN", key + "=" + val,
                "Secret-named var present (value looks like a placeholder). "
                "Confirm no real value ships.", m.start())
        elif looks_like_doc_placeholder(val):
            # Low-entropy, dictionary-wordy value (e.g. ghp_your_github_token,
            # xoxp-new-token-here) -> documentation placeholder. WARN, never
            # BLOCK. A high-entropy real secret is not wordy and falls through
            # to BLOCK below (audited evasion stays blocked).
            add("env-secret", "WARN", key + "=" + val,
                "Secret-named var with a low-entropy, placeholder-like value. "
                "Confirm it is not a real credential before shipping.", m.start())
        elif len(val) >= 12 and len(set(val)) > 2:
            add("env-secret", "BLOCK", val,
                "Secret value assigned to a credential-named variable. "
                "Move to env var / .env.example placeholder.", m.start(2))
        # else: too short / low signal -> skip

    # 6. High-entropy unknown secret (WARN backstop)
    if entropy_ok:
        lower_line = line.lower()
        sha_ctx = any(w in lower_line for w in ("commit", "sha", "revision", "integrity", "sha512-", "sha256-"))
        for m in ENTROPY_TOKEN_RE.finditer(line):
            tok = m.group(0)
            if len(tok) < ctx["entropy_min_len"]:
                continue
            if is_placeholder(tok):
                continue
            if UUID_RE.match(tok):
                continue
            if sha_ctx and HEX_RE.match(tok):
                continue
            ent = shannon_entropy(tok)
            is_hex = bool(HEX_RE.match(tok))
            hit = False
            if is_hex and ent >= ctx["entropy_hex_bits"]:
                hit = True
            elif (not is_hex) and ent >= ctx["entropy_b64_bits"] and mixed_classes(tok):
                hit = True
            if hit:
                add("high-entropy-secret", "WARN", tok,
                    "High-entropy string of unknown format. Verify it is not a secret; "
                    "if it is, remove and rotate.", m.start())

    # 7. PII email
    for m in EMAIL_RE.finditer(line):
        email = m.group(0)
        low = email.lower()
        if low in allow_emails:
            continue
        domain = low.split("@", 1)[1]
        localpart = low.split("@", 1)[0]
        if domain in EXAMPLE_EMAIL_DOMAINS or localpart in EXAMPLE_LOCALPARTS:
            continue
        if domain.endswith(".example") or domain.endswith(".test"):
            continue
        add("pii-email", "WARN", email,
            "Email address. Replace with a reserved example.com address or allowlist if intentional.",
            m.start())

    # 8. PII phone
    for rgx in (PHONE_RE, KR_PHONE_RE):
        for m in rgx.finditer(line):
            span = m.group(0)
            digits = re.sub(r"\D", "", span)
            if len(digits) < 9:
                continue
            if SEMVER_RE.search(span):
                continue
            # reserved fictional US 555-01xx
            if re.search(r"555[\s.-]?01\d\d", span):
                continue
            before = line[max(0, m.start()-1):m.start()]
            if before in ("v", "#", ":"):
                continue
            add("pii-phone", "WARN", span,
                "Possible phone number. Genericize or allowlist if intentional.", m.start())

    # 9. Local machine paths with username
    for rgx in (WIN_PATH_RE, WSL_PATH_RE, POSIX_HOME_RE, MAC_HOME_RE):
        for m in rgx.finditer(line):
            uname = m.group(1)
            if uname.lower() in GENERIC_USERNAMES:
                continue
            add("local-machine-path", "WARN", m.group(0),
                "Local path leaks username '{0}'. Replace with ~ / $HOME / %USERPROFILE% / <USER>.".format(uname),
                m.start())

    # 10. Internal host / network
    for m in UNC_RE.finditer(line):
        add("internal-host", "WARN", m.group(0),
            "UNC path leaks an internal host/share. Genericize.", m.start())
    for m in INTERNAL_HOST_RE.finditer(line):
        add("internal-host", "WARN", m.group(0),
            "Internal hostname. Replace with a generic placeholder host.", m.start())
    for m in PRIVATE_IP_RE.finditer(line):
        if re.search(r"(?i)example|e\.g\.", line):
            continue
        add("internal-network", "WARN", m.group(0),
            "Private/internal IP address. Genericize if it identifies your network.", m.start())

    # 11. Client / proper-noun dictionary (from config) -> BLOCK
    if block_dict_re:
        for m in block_dict_re.finditer(line):
            add("client-proper-noun", "BLOCK", m.group(0),
                "Client/proper-noun term from your private dictionary. Genericize before sharing.",
                m.start())
    if warn_dict_re:
        for m in warn_dict_re.finditer(line):
            add("client-proper-noun", "WARN", m.group(0),
                "Term from your private warn dictionary. Review before sharing.", m.start())

    # 12. Auto-seeded author identity -> BLOCK (self-leak)
    if seed_re:
        for m in seed_re.finditer(line):
            add("self-identity", "BLOCK", m.group(0),
                "This matches YOUR own identity (username/email/hostname/git name). "
                "Remove self-identifying info before sharing.", m.start())

    return out


# ---------------------------------------------------------------------------
# Robust text decoding (closes the UTF-16 bypass #2)
# ---------------------------------------------------------------------------
def decode_bytes(raw):
    """Decode bytes to text, handling UTF-16 BOM / NUL-interleaving.

    Returns text with NUL bytes stripped so that \\b-anchored regexes match.
    A latin-1 fallback used to interleave NULs from UTF-16 data and silently
    defeat every \\b regex -- this detects BOMs and a high NUL ratio and decodes
    utf-16 properly; any remaining NULs are stripped before regex.
    """
    if raw.startswith(b"\xff\xfe"):
        try:
            return raw.decode("utf-16-le", errors="ignore").replace("\x00", "")
        except Exception:
            pass
    if raw.startswith(b"\xfe\xff"):
        try:
            return raw.decode("utf-16-be", errors="ignore").replace("\x00", "")
        except Exception:
            pass
    if raw.startswith(b"\xef\xbb\xbf"):
        try:
            return raw.decode("utf-8-sig", errors="ignore").replace("\x00", "")
        except Exception:
            pass
    # No BOM: detect heavy NUL interleaving (UTF-16 without BOM).
    sample = raw[:4096]
    if sample:
        nul_ratio = sample.count(0) / len(sample)
        if nul_ratio > 0.20:
            # Guess endianness from which byte position carries the NULs.
            even_nul = sample[0::2].count(0)
            odd_nul = sample[1::2].count(0)
            enc = "utf-16-le" if odd_nul >= even_nul else "utf-16-be"
            try:
                return raw.decode(enc, errors="ignore").replace("\x00", "")
            except Exception:
                pass
    try:
        return raw.decode("utf-8").replace("\x00", "")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="ignore").replace("\x00", "")


# Dangerous .sanitizerignore globs that could mask code/secret files wholesale.
DANGEROUS_IGNORE_GLOBS = re.compile(r"^\*(?:\.\*|\.[A-Za-z0-9]+)?$|^\*\*?$")


# ---------------------------------------------------------------------------
# Directory walk
# ---------------------------------------------------------------------------
def scan_dir(root, ctx):
    findings = []
    files_scanned = 0
    service_hits = {svc: {"count": 0, "files": set(), "markers": set()} for svc in SERVICE_COMPILED}
    root = Path(root)

    ignore_patterns = load_sanitizerignore(root)
    dangerous_globs = [p for p in ignore_patterns if DANGEROUS_IGNORE_GLOBS.match(p)]
    # Suppression telemetry (closes #3/#4/#15: suppression must be VISIBLE).
    telemetry = {
        "suppressed_files": 0,          # files dropped by .sanitizerignore
        "ignore_patterns": list(ignore_patterns),
        "dangerous_ignore_globs": dangerous_globs,
        "ignore_file_suppressed_files": 0,   # files dropped by ignore-file directive
        "ignore_line_suppressed_lines": 0,   # lines dropped by ignore-line directive
        "ignore_line_suppressed_findings": 0,  # findings dropped by ignore-line
        "scan_errors": [],              # paths that could not be scanned (#10)
    }

    # By default skip the currently-running scanner file (by realpath).
    try:
        self_realpath = os.path.realpath(os.path.abspath(__file__))
    except (NameError, OSError):
        self_realpath = None

    def long_path(p):
        """Apply the Windows extended-length prefix to dodge MAX_PATH (#10)."""
        if os.name == "nt":
            ap = os.path.abspath(p)
            if not ap.startswith("\\\\?\\"):
                if ap.startswith("\\\\"):
                    return "\\\\?\\UNC\\" + ap.lstrip("\\")
                return "\\\\?\\" + ap
        return p

    walk_errors = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=walk_errors.append):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            fpath = Path(dirpath) / fn
            try:
                rel = fpath.relative_to(root).as_posix()
            except ValueError:
                rel = str(fpath)
            try:
                if fpath.is_symlink():
                    continue
                size = fpath.stat().st_size
            except OSError:
                # MAX_PATH / permission: surface as a scan error, do NOT skip silently.
                try:
                    size = os.stat(long_path(str(fpath))).st_size
                except OSError as e:
                    telemetry["scan_errors"].append({"path": rel, "error": str(e)})
                    continue

            # Suppression: .sanitizerignore globs (relative-to-root, POSIX)
            if ignore_patterns and matches_ignore(rel, ignore_patterns):
                telemetry["suppressed_files"] += 1
                continue
            # Suppression: skip the running scanner file itself (by realpath)
            if self_realpath is not None:
                try:
                    if os.path.realpath(str(fpath)) == self_realpath:
                        continue
                except OSError:
                    pass

            # entropy noise files: still get prefix scan, skip entropy
            entropy_for_file = not bool(ENTROPY_SKIP_BASENAMES.search(fn))

            open_path = str(fpath)

            if not is_text_file(fpath) or size > MAX_FILE_BYTES:
                # binary or huge: still scan bytes for prefix BLOCK patterns
                try:
                    try:
                        with open(open_path, "rb") as f:
                            raw = f.read(MAX_FILE_BYTES)
                    except OSError:
                        with open(long_path(open_path), "rb") as f:
                            raw = f.read(MAX_FILE_BYTES)
                    text = decode_bytes(raw)
                    files_scanned += 1
                    for name, sev, rgx, suggestion in PREFIX_RULES + [
                        ("private-key", "BLOCK", PRIVATE_KEY_RE, "Private key material; remove from share.")
                    ]:
                        for m in rgx.finditer(text):
                            findings.append({
                                "file": rel, "line": 0, "col": 0,
                                "category": name, "severity": sev,
                                "snippet": redact(m.group(0)), "suggestion": suggestion,
                            })
                except OSError as e:
                    telemetry["scan_errors"].append({"path": rel, "error": str(e)})
                continue

            # Read as bytes then decode robustly (UTF-16 BOM / NUL-strip).
            try:
                try:
                    with open(open_path, "rb") as f:
                        raw = f.read(MAX_FILE_BYTES)
                except OSError:
                    with open(long_path(open_path), "rb") as f:
                        raw = f.read(MAX_FILE_BYTES)
            except OSError as e:
                telemetry["scan_errors"].append({"path": rel, "error": str(e)})
                continue
            content = decode_bytes(raw)

            # Suppression: inline file directive in first ~10 lines (anchored).
            if has_ignore_file_directive(content):
                telemetry["ignore_file_suppressed_files"] += 1
                continue

            files_scanned += 1
            file_ctx = dict(ctx)
            file_ctx["entropy_for_file"] = entropy_for_file

            # service markers
            for svc, pats in SERVICE_COMPILED.items():
                for p in pats:
                    if p.search(content):
                        service_hits[svc]["count"] += 1
                        service_hits[svc]["files"].add(rel)
                        service_hits[svc]["markers"].add(p.pattern)

            lines = content.splitlines()
            for i, line in enumerate(lines, 1):
                if len(line) > 5000:
                    line = line[:5000]
                # Suppression: inline line directive drops all findings on this line
                if IGNORE_LINE_TOKEN in line:
                    telemetry["ignore_line_suppressed_lines"] += 1
                    dropped = scan_line(line, i, file_ctx)
                    telemetry["ignore_line_suppressed_findings"] += len(dropped)
                    continue
                for fnd in scan_line(line, i, file_ctx):
                    fnd["file"] = rel
                    findings.append(fnd)

            # File-scope detection (headerless PEM / key body).
            for fnd in scan_file_level(rel, fn, content, lines):
                findings.append(fnd)

    for err in walk_errors:
        telemetry["scan_errors"].append({
            "path": getattr(err, "filename", str(err)) or str(err),
            "error": str(err),
        })

    # build plugin-split findings (WARN)
    for svc, info in service_hits.items():
        if info["count"] >= 2 and len(info["markers"]) >= 1:
            markers = ", ".join(sorted(info["markers"])[:4])
            for f in sorted(info["files"]):
                findings.append({
                    "file": f, "line": 0, "col": 0,
                    "category": "plugin-split:" + svc, "severity": "WARN",
                    "snippet": "[{0} markers]".format(svc),
                    "suggestion": SERVICE_ADVICE.format(svc=svc, markers=markers),
                })

    return findings, files_scanned, service_hits, telemetry


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(description="skill-sanitizer: pre-share leak scanner.")
    parser.add_argument("target", help="directory (or file) to scan")
    parser.add_argument("--config", default=None, help="path to .sanitizer.local.json")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--warn-ok", action="store_true",
                        help="WARN-only runs exit 0 (still nonzero on BLOCK)")
    parser.add_argument("--no-entropy", action="store_true", help="disable entropy backstop")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="list every WARN finding per-line (default: summarize "
                             "WARNs as a per-category count). BLOCK findings are "
                             "always listed in full. Does not affect RESULT_JSON.")
    args = parser.parse_args(argv)

    target = Path(args.target)
    if not target.exists():
        sys.stderr.write("ERROR: target does not exist: {0}\n".format(target))
        print("RESULT_JSON=" + json.dumps({
            "version": VERSION, "error": "target-not-found",
            "findings": [], "counts": {}, "blocked": False, "exit_code": 3,
        }))
        return 3

    try:
        cfg_path, config = load_config(str(target if target.is_dir() else target.parent), args.config)
    except ValueError as e:
        sys.stderr.write("ERROR: malformed config: {0}\n".format(e))
        print("RESULT_JSON=" + json.dumps({
            "version": VERSION, "error": "bad-config",
            "findings": [], "counts": {}, "blocked": False, "exit_code": 3,
        }))
        return 3

    entropy_cfg = config.get("entropy", {}) or {}
    block_dict_re, warn_dict_re, dict_count = build_dictionary(config)

    allowlist = config.get("allowlist", {}) or {}
    allow_emails = set(e.lower() for e in (allowlist.get("emails", []) or []))
    allow_emails |= set(e.lower() for e in (config.get("own_emails", []) or []))

    seeds = auto_seed_terms()
    seed_re = None
    if seeds and any(len(s) >= 3 for s in seeds):
        seed_re = re.compile(
            r"(?i)\b(?:" + "|".join(re.escape(s) for s in seeds if len(s) >= 3) + r")\b"
        )

    ctx = {
        "allow_emails": allow_emails,
        "seed_re": seed_re,
        "block_dict_re": block_dict_re,
        "warn_dict_re": warn_dict_re,
        "entropy_enabled": (not args.no_entropy) and entropy_cfg.get("enabled", True),
        "entropy_for_file": True,
        "entropy_min_len": int(entropy_cfg.get("min_len", 20)),
        "entropy_b64_bits": float(entropy_cfg.get("base64_bits", 4.0)),
        "entropy_hex_bits": float(entropy_cfg.get("hex_bits", 3.0)),
    }

    try:
        scan_root = target if target.is_dir() else target.parent
        findings, files_scanned, service_hits, telemetry = scan_dir(scan_root, ctx)
    except Exception as e:  # fail-closed: any crash -> usage error, never silent pass
        sys.stderr.write("ERROR: scan failed: {0}\n".format(e))
        print("RESULT_JSON=" + json.dumps({
            "version": VERSION, "error": "scan-failed",
            "findings": [], "counts": {}, "blocked": False, "exit_code": 3,
        }))
        return 3

    counts = {"BLOCK": 0, "WARN": 0, "INFO": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    blocked = counts["BLOCK"] > 0
    scan_errored = bool(telemetry.get("scan_errors"))

    order = {"BLOCK": 0, "WARN": 1, "INFO": 2}
    findings_sorted = sorted(findings, key=lambda x: (order.get(x["severity"], 3), x["file"], x["line"]))

    # ---- human report (stderr) ----
    w = sys.stderr.write
    w("\n=== skill-sanitizer report ===\n")
    w("scanned: {0}\n".format(os.path.abspath(str(scan_root))))
    w("config:  {0}\n".format(cfg_path or "(none; using generic defaults + auto-seeded identity)"))
    w("files scanned: {0}\n".format(files_scanned))
    w("BLOCK={0}  WARN={1}\n\n".format(counts["BLOCK"], counts["WARN"]))

    # Suppression telemetry: NEVER let suppression hide behind a green verdict.
    supp_files = telemetry.get("suppressed_files", 0)
    supp_ifile = telemetry.get("ignore_file_suppressed_files", 0)
    supp_ifind = telemetry.get("ignore_line_suppressed_findings", 0)
    supp_iline = telemetry.get("ignore_line_suppressed_lines", 0)
    dangerous = telemetry.get("dangerous_ignore_globs", [])
    ipat = telemetry.get("ignore_patterns", [])
    any_suppression = bool(supp_files or supp_ifile or supp_ifind or ipat)
    # "risky" suppression = something that could plausibly hide a real leak:
    # a dangerous wholesale glob, findings actually dropped by ignore-line, or
    # a scan error. Benign named-file ignores (a skill excluding its own docs)
    # are reported but do NOT void a clean verdict.
    risky_suppression = bool(dangerous or supp_ifind or scan_errored)

    if not findings_sorted:
        if risky_suppression:
            w("No reported findings -- but RISKY suppression/errors are active "
              "(see SUPPRESSION below). Do NOT treat as 'Safe to share' "
              "without reviewing what was hidden.\n")
        elif any_suppression:
            w("No findings. Safe to share. "
              "(Some files were suppressed -- see SUPPRESSION below; "
              "all are explicit named excludes, not wholesale globs.)\n")
        else:
            w("No findings. Safe to share.\n")
    # BLOCK findings: ALWAYS listed in full and first (must-fix, prominent).
    # WARN findings: summarized per-category by default to keep the demo output
    # clean; --verbose restores the full per-line listing. RESULT_JSON (stdout)
    # always carries every finding regardless of --verbose (machine output is
    # unchanged), so this only affects the human report.
    block_findings = [f for f in findings_sorted if f["severity"] == "BLOCK"]
    warn_findings = [f for f in findings_sorted if f["severity"] == "WARN"]
    other_findings = [f for f in findings_sorted
                      if f["severity"] not in ("BLOCK", "WARN")]

    def _emit(f):
        loc = "{0}:{1}".format(f["file"], f["line"]) if f["line"] else f["file"]
        w("[{0}] {1}\n    {2}\n    match: {3}\n    fix:   {4}\n".format(
            f["severity"], f["category"], loc, f["snippet"], f["suggestion"]))

    for f in block_findings:
        _emit(f)

    if warn_findings:
        if args.verbose:
            for f in warn_findings:
                _emit(f)
        else:
            # Summarize WARNs as a count per category (stable, sorted order).
            cat_counts = {}
            for f in warn_findings:
                cat_counts[f["category"]] = cat_counts.get(f["category"], 0) + 1
            w("WARN findings ({0} total) -- summarized by category "
              "(use --verbose to list each):\n".format(len(warn_findings)))
            for cat in sorted(cat_counts):
                w("    WARN: {0} x{1}\n".format(cat, cat_counts[cat]))

    # Any non-BLOCK/non-WARN findings (e.g. future INFO) are always listed.
    for f in other_findings:
        _emit(f)

    plugin_suggested = sorted(
        svc for svc, info in service_hits.items()
        if info["count"] >= 2 and len(info["markers"]) >= 1
    )
    if plugin_suggested:
        w("\nplugin-split suggested for: {0}\n".format(", ".join(plugin_suggested)))

    # ---- SUPPRESSION section (always printed when anything was suppressed) ----
    if any_suppression or supp_iline:
        w("\n--- SUPPRESSION (review before trusting any clean verdict) ---\n")
        w("  .sanitizerignore patterns: {0}\n".format(ipat or "(none)"))
        w("  files hidden by .sanitizerignore: {0}\n".format(supp_files))
        w("  files hidden by ignore-file directive: {0}\n".format(supp_ifile))
        w("  lines hidden by ignore-line directive: {0} "
          "(findings suppressed: {1})\n".format(supp_iline, supp_ifind))
        if dangerous:
            w("  *** WARNING: dangerous .sanitizerignore glob(s) {0} can mask "
              "code/secret files wholesale -- a green verdict here is NOT "
              "trustworthy. ***\n".format(dangerous))

    # ---- SCAN ERRORS (unscanned paths -> exit 3, never 'clean') ----
    if scan_errored:
        w("\n--- SCAN ERRORS (paths could NOT be scanned; result is incomplete) ---\n")
        for e in telemetry["scan_errors"][:20]:
            w("  {0}: {1}\n".format(e.get("path"), e.get("error")))
        more = len(telemetry["scan_errors"]) - 20
        if more > 0:
            w("  ... and {0} more\n".format(more))

    # A dangerous wholesale .sanitizerignore glob (e.g. *, *.*, *.py, **) is a
    # scan-integrity failure: it can hide everything, so a clean verdict is
    # untrustworthy. Fail-closed -> exit 3 (same class as scan_errors) so a naive
    # `if scanner exits 0: pass` CI gate cannot silently greenlight it. Explicit
    # NAMED-file excludes are benign and do NOT trip this.
    integrity_failed = scan_errored or bool(dangerous)

    # Exit-code contract: 1 BLOCK > 3 scan-integrity > 2 WARN > 0 clean.
    if blocked:
        exit_code = 1
    elif integrity_failed:
        exit_code = 3
    elif counts["WARN"] > 0 and not args.warn_ok:
        exit_code = 2
    else:
        exit_code = 0
    if exit_code == 3:
        reason3 = "scan error (incomplete)" if scan_errored else \
                  "dangerous .sanitizerignore glob (scan integrity)"
    else:
        reason3 = ""
    exit_reason = {1: "BLOCK present", 3: reason3,
                   2: "WARN present", 0: "clean"}[exit_code]
    w("\nexit: {0} ({1})\n".format(exit_code, exit_reason))

    # ---- machine line (stdout) ----
    result = {
        "version": VERSION,
        "scanned_root": os.path.abspath(str(scan_root)),
        "findings": findings_sorted,
        "counts": {"block": counts["BLOCK"], "warn": counts["WARN"],
                   "files_scanned": files_scanned},
        "service_plugins_suggested": plugin_suggested,
        "suppression": {
            "suppressed_files": supp_files,
            "ignore_patterns": ipat,
            "dangerous_ignore_globs": dangerous,
            "ignore_file_suppressed_files": supp_ifile,
            "ignore_line_suppressed_lines": supp_iline,
            "ignore_line_suppressed_findings": supp_ifind,
        },
        "scan_errors": telemetry.get("scan_errors", []),
        "blocked": blocked,
        "exit_code": exit_code,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2))
    print("RESULT_JSON=" + json.dumps(result))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
