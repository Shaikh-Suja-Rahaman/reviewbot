"""Fetch context beyond the changed lines: the full file at the PR head.

The rubric asks the reviewer to "understand file context beyond the changed
lines — imports, class definitions, dependencies". The simplest robust way is
to ship the whole current file alongside the numbered diff (1M-token context
makes this cheap); we cap per-file size so a vendored bundle can't blow up
the prompt.
"""

from .config import get_settings
from .diff_parser import FileDiff
from .github_client import GitHubClient, PullRequest


def build_file_context(client: GitHubClient, pr: PullRequest, file_diff: FileDiff) -> str:
    settings = get_settings()
    if file_diff.is_deleted:
        return "(file deleted in this PR)"
    content = client.get_file_content(pr.owner, pr.repo, file_diff.path, pr.head_sha)
    if content is None:
        return "(file content unavailable — binary or too large)"
    if len(content) > settings.max_context_chars:
        head = content[: settings.max_context_chars]
        return f"{head}\n... (truncated, file is {len(content)} chars)"
    return content
