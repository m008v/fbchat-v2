"""Offline checks for the split user documentation."""

from __future__ import annotations

import ast
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = (
    "docs/getting-started/quickstart.md",
    "docs/messaging/standard.md",
    "docs/messaging/e2ee.md",
    "docs/features/facebook-actions.md",
    "docs/recipes/cheatsheet.md",
)
FENCES = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)
MAIN_URL = "https://github.com/m008v/fbchat-v2/blob/main/"


def _anchors(text: str) -> set[str]:
    anchors = set()
    counts: dict[str, int] = {}
    for heading in re.findall(r"(?m)^#{1,6} (.+)$", FENCES.sub("", text)):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        anchors.add(f"{slug}-{count}" if count else slug)
    return anchors


def _check_links(source: Path, *, docs_only: bool = False) -> None:
    text = FENCES.sub("", source.read_text(encoding="utf-8"))
    for target in re.findall(r"\]\(([^)\n]+)\)", text):
        if target.startswith(MAIN_URL):
            target = "/" + target.removeprefix(MAIN_URL)
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        relative = unquote(parsed.path)
        destination = (
            ROOT / relative.lstrip("/")
            if relative.startswith("/")
            else source.parent / relative if relative else source
        )
        if docs_only and "docs" not in destination.parts:
            continue
        assert destination.exists(), (source, target)
        if parsed.fragment and destination.suffix == ".md":
            assert unquote(parsed.fragment) in _anchors(
                destination.read_text(encoding="utf-8")
            ), (source, target)


def test_documentation_has_five_topic_pages() -> None:
    assert not (ROOT / "DOCS.md").exists()
    assert set(ROOT.joinpath("docs").rglob("*.md")) == {ROOT / p for p in PAGES}
    assert f'Documentation = "{MAIN_URL}{PAGES[0]}"' in (
        ROOT / "pyproject.toml"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize("page", PAGES)
def test_documentation_links_and_python_examples(page: str) -> None:
    source = ROOT / page
    _check_links(source)
    text = source.read_text(encoding="utf-8")
    assert text.count("```") % 2 == 0
    for language, code in FENCES.findall(text):
        if language.strip() == "python":
            compile(code, page, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)


def test_readmes_link_to_existing_topic_pages() -> None:
    for name in ("README.md", "README_EN.md"):
        source = ROOT / name
        _check_links(source, docs_only=True)
        text = source.read_text(encoding="utf-8")
        assert all(MAIN_URL + page in text for page in PAGES)
    entrypoints = [
        ROOT / "CLAUDE.md",
        ROOT / "FLOWCHART.md",
        ROOT / "mindmap-mermaid.md",
        ROOT / "language/README.md",
        ROOT / "bridge-e2ee/README.md",
        *ROOT.joinpath("src").rglob("README*.md"),
        *ROOT.joinpath(".github").glob("RELEASE_NOTES*.md"),
    ]
    for source in entrypoints:
        _check_links(source, docs_only=True)
        for target in re.findall(
            r"\]\(([^)\n]+)\)", source.read_text(encoding="utf-8")
        ):
            parsed = urlsplit(target)
            if not parsed.scheme:
                assert not parsed.path.endswith("DOCS.md"), (source, target)
