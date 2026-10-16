"""Guard against documentation rot: links and images must point at files that exist."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
EXTERNAL = ("http://", "https://", "#", "mailto:")


def local_targets(markdown_path: Path):
    text = markdown_path.read_text(encoding="utf-8")
    for target in LINK.findall(text):
        if target.startswith(EXTERNAL):
            continue
        yield target.split("#")[0]


def missing_targets(markdown_path: Path):
    return [t for t in local_targets(markdown_path)
            if t and not (markdown_path.parent / t).exists()]


def test_readme_links_and_images_exist():
    assert missing_targets(ROOT / "README.md") == [], (
        "README points at missing files. Run `make all` and commit docs/ and benchmark/.")


def test_docs_folder_links_exist():
    for path in sorted((ROOT / "docs").glob("*.md")):
        assert missing_targets(path) == [], path.name


def test_licence_files_exist():
    assert (ROOT / "LICENSE").exists() and (ROOT / "DATA_LICENSE.md").exists()


def test_ci_workflow_runs_tests_and_benchmark_check():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pytest" in workflow
    assert "piikit.freeze verify benchmark" in workflow
    assert "piikit.validate_release" in workflow