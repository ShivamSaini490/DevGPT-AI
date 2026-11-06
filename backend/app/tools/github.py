"""GitHub tools: triage pull requests and issues, check CI, publish issues/comments.

Reading public repositories works without a token (60 requests/hour);
set GITHUB_TOKEN for private repositories, higher limits and the write tools.
"""

import json
import re
from typing import Literal

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.config import EXTERNAL_API_TIMEOUT_SECONDS, GITHUB_API_URL, GITHUB_TOKEN


_REPO_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?(?:github\.com/)?([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?].*)?$"
)


class GitHubError(Exception):
    pass


def normalize_repo(repo: str) -> str:
    match = _REPO_PATTERN.match(repo.strip())
    if not match:
        raise GitHubError(
            f"'{repo}' is not a repository. Use the form owner/name or a GitHub URL."
        )
    return f"{match.group(1)}/{match.group(2)}"


def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevGPT",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def _request(method: str, path: str, **kwargs):
    response = httpx.request(
        method,
        f"{GITHUB_API_URL}{path}",
        headers=_headers(),
        timeout=EXTERNAL_API_TIMEOUT_SECONDS,
        **kwargs,
    )
    if response.status_code == 404:
        raise GitHubError(
            "Not found. Check the repository name"
            + ("" if GITHUB_TOKEN else ", or set GITHUB_TOKEN for private repositories")
            + "."
        )
    if response.status_code in (401, 403):
        detail = response.json().get("message", "") if response.content else ""
        raise GitHubError(f"GitHub refused the request ({response.status_code}): {detail}")
    response.raise_for_status()
    return response.json() if response.content else {}


def _run(callable_):
    try:
        return json.dumps(callable_(), ensure_ascii=False, default=str)
    except GitHubError as exc:
        return f"GitHub error: {exc}"
    except httpx.HTTPError as exc:
        return f"GitHub request failed: {exc}"


def _short(text: str | None, limit: int = 400) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


class RepoInput(BaseModel):
    repo: str = Field(description="Repository as owner/name or a github.com URL.")


class ListInput(RepoInput):
    state: Literal["open", "closed", "all"] = Field(default="open")
    limit: int = Field(default=10, ge=1, le=30)


class NumberInput(RepoInput):
    number: int = Field(description="Pull request or issue number.")


class CIInput(RepoInput):
    branch: str | None = Field(default=None, description="Branch to check; default branch when empty.")


class CreateIssueInput(RepoInput):
    title: str = Field(description="Issue title.")
    body: str = Field(default="", description="Issue body in Markdown.")
    labels: list[str] = Field(default_factory=list)


class CommentInput(NumberInput):
    body: str = Field(description="Comment text in Markdown.")


@tool(args_schema=RepoInput)
def github_repo_overview(repo: str) -> str:
    """Get a GitHub repository's description, stars, open issues, default branch and latest release."""

    def run():
        name = normalize_repo(repo)
        data = _request("GET", f"/repos/{name}")
        result = {
            "repo": data.get("full_name"),
            "url": data.get("html_url"),
            "description": data.get("description"),
            "language": data.get("language"),
            "stars": data.get("stargazers_count"),
            "forks": data.get("forks_count"),
            "open_issues_and_prs": data.get("open_issues_count"),
            "default_branch": data.get("default_branch"),
            "updated_at": data.get("pushed_at"),
            "private": data.get("private"),
        }
        try:
            release = _request("GET", f"/repos/{name}/releases/latest")
            result["latest_release"] = {
                "tag": release.get("tag_name"),
                "published_at": release.get("published_at"),
            }
        except GitHubError:
            result["latest_release"] = None
        return result

    return _run(run)


@tool(args_schema=ListInput)
def github_list_pull_requests(repo: str, state: str = "open", limit: int = 10) -> str:
    """List pull requests of a GitHub repository for triage (author, labels, draft, review state)."""

    def run():
        name = normalize_repo(repo)
        items = _request(
            "GET",
            f"/repos/{name}/pulls",
            params={"state": state, "per_page": limit, "sort": "updated", "direction": "desc"},
        )
        return [
            {
                "number": pr.get("number"),
                "title": pr.get("title"),
                "author": (pr.get("user") or {}).get("login"),
                "draft": pr.get("draft"),
                "labels": [label.get("name") for label in pr.get("labels", [])],
                "requested_reviewers": [r.get("login") for r in pr.get("requested_reviewers", [])],
                "head": (pr.get("head") or {}).get("ref"),
                "base": (pr.get("base") or {}).get("ref"),
                "updated_at": pr.get("updated_at"),
                "url": pr.get("html_url"),
            }
            for pr in items
        ]

    return _run(run)


@tool(args_schema=NumberInput)
def github_pull_request_details(repo: str, number: int) -> str:
    """Get one pull request's description, changed files, review status and CI check results."""

    def run():
        name = normalize_repo(repo)
        pr = _request("GET", f"/repos/{name}/pulls/{number}")
        files = _request("GET", f"/repos/{name}/pulls/{number}/files", params={"per_page": 50})
        reviews = _request("GET", f"/repos/{name}/pulls/{number}/reviews")
        sha = (pr.get("head") or {}).get("sha")
        checks = []
        if sha:
            runs = _request("GET", f"/repos/{name}/commits/{sha}/check-runs", params={"per_page": 30})
            checks = [
                {"name": c.get("name"), "status": c.get("status"), "conclusion": c.get("conclusion")}
                for c in runs.get("check_runs", [])
            ]
        return {
            "number": pr.get("number"),
            "title": pr.get("title"),
            "author": (pr.get("user") or {}).get("login"),
            "state": pr.get("state"),
            "merged": pr.get("merged"),
            "mergeable_state": pr.get("mergeable_state"),
            "body": _short(pr.get("body"), 1200),
            "additions": pr.get("additions"),
            "deletions": pr.get("deletions"),
            "files": [
                {
                    "file": f.get("filename"),
                    "status": f.get("status"),
                    "changes": f.get("changes"),
                    "patch": _short(f.get("patch"), 300),
                }
                for f in files[:25]
            ],
            "reviews": [
                {"reviewer": (r.get("user") or {}).get("login"), "state": r.get("state")}
                for r in reviews
            ],
            "checks": checks,
            "url": pr.get("html_url"),
        }

    return _run(run)


@tool(args_schema=ListInput)
def github_list_issues(repo: str, state: str = "open", limit: int = 10) -> str:
    """List issues (not pull requests) of a GitHub repository for triage."""

    def run():
        name = normalize_repo(repo)
        items = _request(
            "GET",
            f"/repos/{name}/issues",
            params={"state": state, "per_page": min(limit * 2, 60), "sort": "updated"},
        )
        issues = [item for item in items if "pull_request" not in item][:limit]
        return [
            {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "author": (issue.get("user") or {}).get("login"),
                "labels": [label.get("name") for label in issue.get("labels", [])],
                "assignees": [a.get("login") for a in issue.get("assignees", [])],
                "comments": issue.get("comments"),
                "body": _short(issue.get("body"), 300),
                "updated_at": issue.get("updated_at"),
                "url": issue.get("html_url"),
            }
            for issue in issues
        ]

    return _run(run)


@tool(args_schema=CIInput)
def github_ci_status(repo: str, branch: str | None = None) -> str:
    """Get recent GitHub Actions workflow runs (CI status) for a repository or branch."""

    def run():
        name = normalize_repo(repo)
        params = {"per_page": 10}
        if branch:
            params["branch"] = branch
        data = _request("GET", f"/repos/{name}/actions/runs", params=params)
        return [
            {
                "workflow": run.get("name"),
                "branch": run.get("head_branch"),
                "event": run.get("event"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "commit": _short((run.get("head_commit") or {}).get("message"), 80),
                "started_at": run.get("run_started_at"),
                "url": run.get("html_url"),
            }
            for run in data.get("workflow_runs", [])
        ]

    return _run(run)


def _require_token():
    if not GITHUB_TOKEN:
        raise GitHubError("Publishing needs GITHUB_TOKEN in backend/.env.")


@tool(args_schema=CreateIssueInput)
def github_create_issue(repo: str, title: str, body: str = "", labels: list[str] | None = None) -> str:
    """Publish a new issue to a GitHub repository. Only call when the user explicitly asks to create it."""

    def run():
        _require_token()
        name = normalize_repo(repo)
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        issue = _request("POST", f"/repos/{name}/issues", json=payload)
        return {"created": True, "number": issue.get("number"), "url": issue.get("html_url")}

    return _run(run)


@tool(args_schema=CommentInput)
def github_add_comment(repo: str, number: int, body: str) -> str:
    """Publish a comment on a GitHub issue or pull request. Only call when the user explicitly asks to post it."""

    def run():
        _require_token()
        name = normalize_repo(repo)
        comment = _request("POST", f"/repos/{name}/issues/{number}/comments", json={"body": body})
        return {"posted": True, "url": comment.get("html_url")}

    return _run(run)


github_tools = [
    github_repo_overview,
    github_list_pull_requests,
    github_pull_request_details,
    github_list_issues,
    github_ci_status,
    github_create_issue,
    github_add_comment,
]
