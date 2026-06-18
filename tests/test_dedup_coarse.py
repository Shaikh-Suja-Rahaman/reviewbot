"""Fuzzy re-review dedup: skip a same file+severity finding with a similar title.

The exact fingerprint misses a finding when the model rephrases its title on a
re-review. These guard the title-similarity fallback in poster.py — which must
catch rewordings WITHOUT suppressing a genuinely distinct nearby finding.
"""

from copilot.models import Finding
from copilot.poster import extract_anchors, finding_to_comment_body, is_near_duplicate


def _finding(title, severity="bug", file="a.py", line=10):
    return Finding(
        file=file, line=line, severity=severity, title=title,
        issue="x", why_it_matters="y", suggested_fix="z", confidence="high",
    )


def _anchor_from(title, severity="bug", file="a.py", line=10):
    body = finding_to_comment_body(_finding(title, severity, file, line))
    return {"path": file, "line": line, "body": body}


def test_extract_anchors_parses_path_severity_title():
    anchors = extract_anchors([_anchor_from("SQL injection in query", severity="security")])
    assert anchors == [("a.py", "security", "SQL injection in query")]


def test_extract_anchors_skips_comments_without_severity_tag():
    assert extract_anchors([{"path": "a.py", "line": 3, "body": "just a human comment"}]) == []


def test_reworded_title_same_file_severity_is_duplicate():
    anchors = extract_anchors([_anchor_from("SQL injection via string-formatted query")])
    # reworded but shares the key tokens -> recognised as the same finding
    assert is_near_duplicate(_finding("SQL injection in the query string"), anchors) is True


def test_distinct_finding_is_not_duplicate_even_if_adjacent():
    # alpha vs beta: same file+severity, no shared title tokens -> NOT suppressed
    anchors = extract_anchors([_anchor_from("beta", line=2)])
    assert is_near_duplicate(_finding("alpha", line=4), anchors) is False


def test_not_duplicate_when_severity_differs():
    anchors = extract_anchors([_anchor_from("SQL injection in query", severity="bug")])
    assert is_near_duplicate(_finding("SQL injection in query", severity="security"), anchors) is False


def test_not_duplicate_when_file_differs():
    anchors = extract_anchors([_anchor_from("SQL injection in query", file="a.py")])
    assert is_near_duplicate(_finding("SQL injection in query", file="b.py"), anchors) is False
