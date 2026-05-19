from __future__ import annotations

import json
from pathlib import Path

from app.orchestrator.context import Issue
from app.services.fix_provider.rules import RulesProvider
from app.services.repo_hints import (
    _evidence_substrings_for_grep,
    collect_import_neighbors,
    expand_patch_targets,
)
from app.services.repo_layout import RepoLayout, analyze_repo_layout, scan_roots_for_grep


def _write_blog_fixture(repo: Path) -> None:
    (repo / "src" / "app" / "blog").mkdir(parents=True)
    (repo / "src" / "components" / "Blog").mkdir(parents=True)
    (repo / "src" / "app" / "blog" / "page.tsx").write_text(
        'import SingleBlog from "@/components/Blog/SingleBlog";\n'
        "export default function Blog() { return <SingleBlog blog={{}} />; }\n",
        encoding="utf-8",
    )
    (repo / "src" / "components" / "Blog" / "SingleBlog.tsx").write_text(
        'import Image from "next/image";\n'
        'export default function SingleBlog({ blog }: { blog: { image: string } }) {\n'
        '  return <Image src={blog.image} alt="" fill />;\n'
        "}\n",
        encoding="utf-8",
    )
    (repo / "src" / "components" / "Blog" / "blogData.tsx").write_text(
        'export default [{ image: "/images/blog/blog-01.jpg" }];\n',
        encoding="utf-8",
    )
    (repo / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"]}}}),
        encoding="utf-8",
    )


def test_collect_import_neighbors_follows_alias(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    _write_blog_fixture(repo)
    neighbors = collect_import_neighbors(repo, "src/app/blog/page.tsx")
    assert "src/components/Blog/SingleBlog.tsx" in neighbors


def test_expand_patch_targets_includes_single_blog(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    _write_blog_fixture(repo)
    layout = analyze_repo_layout(repo)
    evidence = (
        '<img alt="" data-nimg="fill" src="/_next/image?url=%2Fimages%2Fblog%2Fblog-01.jpg&w=1920&q=75">'
    )
    issue = Issue(
        issue_id="1",
        rule_id="missing_alt",
        severity="medium",
        page_url="http://localhost:3000/blog",
        evidence=evidence,
        suggested_fix="Add alt",
        file_hint="src/app/blog/page.tsx",
    )
    targets = expand_patch_targets(repo, layout, "src/app/blog/page.tsx", [issue])
    assert "src/components/Blog/SingleBlog.tsx" in targets


def test_evidence_substrings_decodes_next_image_url() -> None:
    evidence = 'src="/_next/image?url=%2Fimages%2Fblog%2Fblog-01.jpg&w=100"'
    needles = _evidence_substrings_for_grep(evidence)
    assert "/images/blog/blog-01.jpg" in needles
    assert "/images/blog/" in needles


def test_scan_roots_includes_components(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    _write_blog_fixture(repo)
    layout = analyze_repo_layout(repo)
    roots = scan_roots_for_grep(layout)
    assert layout.components_dir == "src/components"
    assert "src/components" in roots


def test_rules_provider_patches_image_alt_empty(tmp_path: Path) -> None:
    content = '<Image src={image} alt="" fill />'
    from app.services.repo_stack import RepoStackInfo

    p = RulesProvider("http://localhost:3000")
    stack = RepoStackInfo(
        framework="nextjs_app",
        package_manager="npm",
        has_build_script=True,
        build_script="next build",
    )
    issues = [
        Issue(
            issue_id="1",
            rule_id="missing_alt",
            severity="medium",
            page_url="http://localhost:3000/blog",
            evidence="",
            suggested_fix="",
        )
    ]
    r = p.fix_file(
        rel_path="src/components/Blog/SingleBlog.tsx",
        content=content,
        issues=issues,
        repo_stack=stack,
        site_url="http://localhost:3000",
    )
    assert r.content is not None
    assert 'alt=""' not in r.content
    assert 'alt="Page image"' in r.content


def test_rules_provider_patches_image_without_alt() -> None:
    from app.services.repo_stack import RepoStackInfo

    content = "<Image src={image} fill />"
    p = RulesProvider("http://example.com")
    stack = RepoStackInfo(framework="nextjs_app", package_manager="npm", has_build_script=False, build_script=None)
    issues = [
        Issue(
            issue_id="1",
            rule_id="missing_alt",
            severity="medium",
            page_url="http://example.com",
            evidence="",
            suggested_fix="",
        )
    ]
    r = p.fix_file(
        rel_path="x.tsx",
        content=content,
        issues=issues,
        repo_stack=stack,
        site_url="http://example.com",
    )
    assert r.content is not None
    assert 'alt="Page image"' in r.content
