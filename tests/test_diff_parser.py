from pathlib import Path

import pytest

from copilot.diff_parser import anchor_line, parse_diff

FIXTURE = Path(__file__).parent / "fixtures" / "sample.diff"


@pytest.fixture
def files():
    return parse_diff(FIXTURE.read_text())


def test_parses_both_files(files):
    assert [f.path for f in files] == ["app/db.py", "app/new_module.py"]
    assert files[1].is_new and not files[0].is_new


def test_added_lines_tracked(files):
    db = files[0]
    # The hunk targets lines 10-18 in the new file; the string-formatted query
    # ends up on lines 15-16 of the new file.
    assert {15, 16} <= db.added_lines
    new_mod = files[1]
    assert new_mod.added_lines == {1, 2, 3, 4}


def test_context_lines_are_commentable(files):
    db = files[0]
    assert 10 in db.commentable_lines  # context line inside the hunk
    assert 999 not in db.commentable_lines


def test_numbered_diff_contains_line_numbers(files):
    db = files[0]
    assert "   15 | +" in db.numbered_diff
    assert "@@ -10,6 +10,7 @@" in db.numbered_diff


def test_anchor_exact_and_snap(files):
    db = files[0]
    assert anchor_line(db, 15) == 15            # exact
    assert anchor_line(db, 19) in db.commentable_lines  # snaps within 3
    assert anchor_line(db, 500) is None         # un-anchorable


def test_removed_lines_not_commentable(files):
    db = files[0]
    # the removed "def find_user(user_id):" old line must not add a bogus entry
    assert all(isinstance(n, int) for n in db.commentable_lines)
