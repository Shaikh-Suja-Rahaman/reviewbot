"""Parse unified diffs and guarantee correct line attribution.

Two jobs:
1. Build a *commentable-line map* per file — the set of new-file line numbers
   GitHub will accept an inline comment on (lines that appear in a hunk).
   Findings outside this set are re-anchored or dropped before posting.
2. Render the diff with explicit line numbers so the model reads the number
   off the page instead of counting — the main trick for accurate anchoring.
"""

from dataclasses import dataclass, field

from unidiff import PatchSet


@dataclass
class FileDiff:
    path: str
    is_new: bool
    is_deleted: bool
    commentable_lines: set[int] = field(default_factory=set)  # new-file line numbers
    added_lines: set[int] = field(default_factory=set)
    numbered_diff: str = ""  # diff text with " 42 | + code" style line prefixes


def parse_diff(diff_text: str) -> list[FileDiff]:
    patch = PatchSet.from_string(diff_text)
    files: list[FileDiff] = []
    for pf in patch:
        fd = FileDiff(
            path=pf.path,
            is_new=pf.is_added_file,
            is_deleted=pf.is_removed_file,
        )
        rendered: list[str] = [f"--- {pf.source_file}", f"+++ {pf.target_file}"]
        for hunk in pf:
            rendered.append(
                f"@@ -{hunk.source_start},{hunk.source_length} "
                f"+{hunk.target_start},{hunk.target_length} @@"
            )
            for line in hunk:
                if line.is_added:
                    fd.commentable_lines.add(line.target_line_no)
                    fd.added_lines.add(line.target_line_no)
                    rendered.append(f"{line.target_line_no:>5} | +{line.value.rstrip()}")
                elif line.is_context:
                    fd.commentable_lines.add(line.target_line_no)
                    rendered.append(f"{line.target_line_no:>5} |  {line.value.rstrip()}")
                else:  # removed — exists only in the old file, not commentable by new line no
                    rendered.append(f"      | -{line.value.rstrip()}")
        fd.numbered_diff = "\n".join(rendered)
        files.append(fd)
    return files


def anchor_line(file_diff: FileDiff, line: int) -> int | None:
    """Validate/repair a finding's line number against the commentable map.

    Exact match wins; otherwise snap to the nearest commentable line within
    3 lines (models are occasionally off by one); otherwise None (un-anchorable).
    """
    if line in file_diff.commentable_lines:
        return line
    candidates = [n for n in file_diff.commentable_lines if abs(n - line) <= 3]
    if candidates:
        return min(candidates, key=lambda n: abs(n - line))
    return None
