#!/usr/bin/env python3
"""Demo helper for dirty-skill. PLANTED leaks below — never ship this file.

Every sensitive-looking value here is a deliberately FAKE fixture used only to
demonstrate skill-sanitizer. Do not copy these patterns into real code.
"""

# PLANTED SECRET (fake, realistic-length GitHub token: ghp_ + 36 chars) -> BLOCK
GITHUB_TOKEN = "ghp_0a1B2c3D4e5F6g7H8i9J0kLmNoPqRsTuVwXy"

# PLANTED PROPRIETARY: hardcoded home-dir path with a username -> WARN
CACHE_DIR = r"C:\Users\jdoe\AppData\Local\dirty-skill\cache"

# PLANTED PII: a personal contact email -> WARN
MAINTAINER_EMAIL = "jane.doe.personal@gmail.com"


def push_issue(title):
    # PLANTED service code: internal Jira markers -> plugin-split:atlassian-jira-confluence
    base = "https://mycompany.atlassian.net/rest/api/3/issue"
    field = "customfield_10042"  # internal custom-field id
    return base, field, title


if __name__ == "__main__":
    print("token loaded from", CACHE_DIR, "for", MAINTAINER_EMAIL)
