"""Tests for package_collector — no LLM required."""
from pathlib import Path

import pytest

from cmdop_claude.services.package_collector import (
    CollectedPackage,
    collect,
    iter_package_dirs,
    _extract_export_lines,
    _compute_fingerprint,
)


def _make_pkg(tmp_path: Path, name: str = "@test/pkg", extra_files: dict | None = None) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "package.json").write_text(f'{{"name": "{name}", "version": "1.2.3"}}')
    src = pkg / "src"
    src.mkdir()
    (src / "index.ts").write_text(
        'export { Button } from "./button";\n'
        'export type { ButtonProps } from "./button";\n'
        'export { useAuth } from "./hooks";\n'
    )
    (src / "button.tsx").write_text("export const Button = () => null;\n")
    (src / "button.story.tsx").write_text(
        "import { Button } from './button';\n"
        "export const Basic = () => <Button>Click</Button>;\n"
    )
    (pkg / "README.md").write_text("# @test/pkg\n\nA test package.\n")
    if extra_files:
        for rel, content in extra_files.items():
            p = pkg / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
    return pkg


def test_collect_basic(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path)
    result = collect(pkg)

    assert isinstance(result, CollectedPackage)
    assert result.package_name == "@test/pkg"
    assert result.version == "1.2.3"
    assert result.pkg_dir == "pkg"
    assert "A test package" in result.readme
    assert len(result.stories) == 1
    assert result.stories[0][0] == "button.story.tsx"
    assert "Button" in result.stories[0][1]
    assert any("Button" in line for line in result.export_lines)
    assert result.fingerprint != ""


def test_collect_excludes_skip_dirs(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path, extra_files={
        "src/@refactoring/PLAN.md": "# Plan",
        "src/@refactoring/old.story.tsx": "export const Old = () => null;",
        "src/node_modules/foo/index.ts": "export const x = 1;",
    })
    result = collect(pkg, extra_exclude=["@refactoring"])
    # Stories from @refactoring should be excluded
    assert not any("@refactoring" in s[0] for s in result.stories)
    # node_modules always excluded
    assert not any("node_modules" in s[0] for s in result.stories)


def test_collect_sub_readmes(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path, extra_files={
        "src/components/Button/README.md": "# Button\n\nA button component.",
        "src/@dev/notes.md": "# Dev notes",  # should be excluded
    })
    result = collect(pkg, extra_exclude=["@dev"])
    assert any("README.md" in r[0] and "Button" in r[0] for r in result.sub_readmes)
    assert not any("@dev" in r[0] for r in result.sub_readmes)


def test_extract_export_lines() -> None:
    text = """\
export { Button, ButtonLink } from './button';
export type { ButtonProps } from './button';
export const VERSION = '1.0';
import { something } from 'somewhere';
export function createClient() {}
"""
    lines = _extract_export_lines(text)
    assert any("Button" in l for l in lines)
    assert any("ButtonProps" in l for l in lines)
    assert any("createClient" in l for l in lines)
    # imports not included
    assert not any("import" in l for l in lines)


def test_fingerprint_changes_with_file(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path)
    fp1 = _compute_fingerprint(pkg, [])
    # Modify README
    (pkg / "README.md").write_text("# Changed\n")
    fp2 = _compute_fingerprint(pkg, [])
    assert fp1 != fp2


def test_iter_package_dirs(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    packages.mkdir()

    # valid packages
    for name in ["ui-core", "api", "llm"]:
        p = packages / name
        p.mkdir()
        (p / "package.json").write_text(f'{{"name": "@test/{name}"}}')

    # not a package (no package.json, no src/)
    (packages / "not-a-pkg").mkdir()

    # hidden dir — should be skipped
    (packages / ".hidden").mkdir()

    result = iter_package_dirs(packages)
    names = [p.name for p in result]
    assert "ui-core" in names
    assert "api" in names
    assert "llm" in names
    assert "not-a-pkg" not in names
    assert ".hidden" not in names


def test_collect_no_readme(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "package.json").write_text('{"name": "@test/minimal"}')
    src = pkg / "src"
    src.mkdir()
    result = collect(pkg)
    assert result.readme == ""
    assert result.package_name == "@test/minimal"
    assert result.fingerprint != ""


def test_collect_stories_recursive(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path, extra_files={
        "src/components/deep/nested/Widget.story.tsx": "export const Foo = () => null;",
        "src/hooks/useAuth.story.ts": "export const AuthStory = () => null;",
    })
    result = collect(pkg)
    paths = [s[0] for s in result.stories]
    assert any("Widget.story.tsx" in p for p in paths)
    assert any("useAuth.story.ts" in p for p in paths)
