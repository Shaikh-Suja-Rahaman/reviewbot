"""Render findings + risk summary into GitHub review payloads and markdown."""

import hashlib
import re
from typing import Any

from .models import SEVERITY_EMOJI, Finding, RiskSummary

# Hidden marker embedded in every inline comment so re-reviews of the same PR
# (webhook `synchronize`) can detect what's already posted and skip it.
FP_MARKER_RE = re.compile(r"<!-- copilot-fp:([0-9a-f]{12}) -->")


def fingerprint(f: Finding) -> str:
    """Stable identity for a finding across re-reviews.

    Line numbers shift between pushes, so the fingerprint is built from the
    file, severity and normalised title instead.
    """
    norm_title = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]", " ", f.title.lower())).strip()
    raw = f"{f.file}|{f.severity}|{norm_title}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def extract_fingerprints(comment_bodies: list[str]) -> set[str]:
    found: set[str] = set()
    for body in comment_bodies:
        found.update(FP_MARKER_RE.findall(body))
    return found


# First line of every comment body: "{emoji} **[SEVERITY]** {title}".
COMMENT_HEAD_RE = re.compile(r"\*\*\[([A-Z]+)\]\*\*\s*(.+)")


def _title_tokens(title: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9]+", " ", title.lower()).split())


def extract_anchors(comments: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """(path, severity, title) for existing inline comments, for fuzzy dedup."""
    anchors: list[tuple[str, str, str]] = []
    for c in comments:
        body = c.get("body") or ""
        path = c.get("path")
        m = COMMENT_HEAD_RE.search(body)
        if m and path:
            anchors.append((path, m.group(1).lower(), m.group(2).strip()))
    return anchors


def is_near_duplicate(
    f: Finding, anchors: list[tuple[str, str, str]], sim_threshold: float = 0.5
) -> bool:
    """True if an existing comment on the same file+severity has a similar title.

    The exact fingerprint misses a finding when the model rephrases its title on a
    re-review. Title-token similarity catches those rewordings WITHOUT suppressing
    a genuinely different finding (distinct titles share no tokens), and is robust
    to line shifts (unlike a file+severity+line key, which drops nearby findings).
    """
    f_tokens = _title_tokens(f.title)
    if not f_tokens:
        return False
    for path, severity, title in anchors:
        if path != f.file or severity != f.severity:
            continue
        a_tokens = _title_tokens(title)
        if not a_tokens:
            continue
        jaccard = len(f_tokens & a_tokens) / len(f_tokens | a_tokens)
        if jaccard >= sim_threshold:
            return True
    return False

RECOMMENDATION_LABEL = {
    "approve": "✅ Approve",
    "approve_with_nits": "✅ Approve (with nits)",
    "request_changes": "🔶 Request changes",
    "block": "⛔ Block",
}


def finding_to_comment_body(f: Finding) -> str:
    emoji = SEVERITY_EMOJI[f.severity]
    parts = [
        f"{emoji} **[{f.severity.upper()}]** {f.title}",
        "",
        f"**Issue:** {f.issue}",
        "",
        f"**Why it matters:** {f.why_it_matters}",
    ]
    if f.suggested_fix.strip():
        parts += ["", "**Suggested fix:**", "```suggestion", f.suggested_fix.rstrip(), "```"]
    parts += [
        "",
        f"<sub>confidence: {f.confidence} · by Code Review Copilot</sub>",
        f"<!-- copilot-fp:{fingerprint(f)} -->",
    ]
    return "\n".join(parts)


def findings_to_github_comments(findings: list[Finding]) -> list[dict[str, Any]]:
    return [
        {"path": f.file, "line": f.line, "side": "RIGHT", "body": finding_to_comment_body(f)}
        for f in findings
    ]


def summary_to_markdown(summary: RiskSummary, findings: list[Finding]) -> str:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    severity_line = " · ".join(
        f"{SEVERITY_EMOJI[s]} {s}: {n}" for s, n in sorted(counts.items(), key=lambda kv: -kv[1])
    ) or "no issues found"

    risks = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(summary.highest_risk_changes)) or "—"

    return f"""## 🔍 Code Review Copilot

**Quality score: {summary.quality_score}/100** · **{RECOMMENDATION_LABEL[summary.merge_recommendation]}**

{summary.overall_assessment}

### Highest-risk changes
{risks}

### Rationale
{summary.rationale}

### Findings ({len(findings)})
{severity_line}

<sub>Inline comments below explain each finding and how to fix it.</sub>
"""
