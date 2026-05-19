from __future__ import annotations

from pathlib import Path

from app.services.repo_layout import (
    analyze_repo_layout,
    app_router_page_candidates,
    layout_file_candidates,
    normalize_audit_file_hint,
    pages_router_page_candidates,
    resolve_page_source_file,
)


def test_analyze_repo_layout_prefers_src_app(tmp_path: Path) -> None:
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "app").mkdir()
    lay = analyze_repo_layout(tmp_path)
    assert lay.app_dir == "src/app"


def test_analyze_repo_layout_app_only(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir(parents=True)
    lay = analyze_repo_layout(tmp_path)
    assert lay.app_dir == "app"
    assert lay.pages_dir is None


def test_analyze_repo_layout_components_dir(tmp_path: Path) -> None:
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "components").mkdir(parents=True)
    lay = analyze_repo_layout(tmp_path)
    assert lay.components_dir == "src/components"


def test_app_router_page_candidates(tmp_path: Path) -> None:
    from app.services.repo_layout import RepoLayout

    (tmp_path / "app" / "blog").mkdir(parents=True)
    page = tmp_path / "app" / "blog" / "page.tsx"
    page.write_text("export default function Page() {}", encoding="utf-8")
    lay = RepoLayout(app_dir="app", pages_dir=None, components_dir=None)
    c = app_router_page_candidates(tmp_path, lay, "http://x/blog/")
    assert c == ["app/blog/page.tsx"]


def test_normalize_audit_hint_src_app(tmp_path: Path) -> None:
    from app.services.repo_layout import RepoLayout

    p = tmp_path / "src" / "app" / "blog" / "page.tsx"
    p.parent.mkdir(parents=True)
    p.write_text("x", encoding="utf-8")
    lay = RepoLayout(app_dir="src/app", pages_dir=None, components_dir=None)
    assert normalize_audit_file_hint(tmp_path, lay, "app/blog/page.tsx") == "src/app/blog/page.tsx"


def test_pages_router_index(tmp_path: Path) -> None:
    from app.services.repo_layout import RepoLayout

    (tmp_path / "pages").mkdir()
    idx = tmp_path / "pages" / "index.tsx"
    idx.write_text("export default function Home() {}", encoding="utf-8")
    lay = RepoLayout(app_dir=None, pages_dir="pages", components_dir=None)
    c = pages_router_page_candidates(tmp_path, lay, "http://x/")
    assert "pages/index.tsx" in c


def test_layout_file_candidates(tmp_path: Path) -> None:
    from app.services.repo_layout import RepoLayout

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "layout.tsx").write_text("export default function RootLayout() {}", encoding="utf-8")
    lay = RepoLayout(app_dir="app", pages_dir=None, components_dir=None)
    assert layout_file_candidates(tmp_path, lay) == ["app/layout.tsx"]


def test_resolve_page_source_app_over_pages(tmp_path: Path) -> None:
    from app.services.repo_layout import RepoLayout

    (tmp_path / "app" / "about").mkdir(parents=True)
    (tmp_path / "app" / "about" / "page.tsx").write_text("x", encoding="utf-8")
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "about.tsx").write_text("y", encoding="utf-8")
    lay = RepoLayout(app_dir="app", pages_dir="pages", components_dir=None)
    r = resolve_page_source_file(tmp_path, lay, "nextjs", "http://x/about")
    assert r == "app/about/page.tsx"
