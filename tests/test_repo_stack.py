from pathlib import Path

from app.services.repo_stack import detect_repo_stack


def test_detect_next_app_router(tmp_path: Path) -> None:
    (tmp_path / "app" / "page.tsx").parent.mkdir(parents=True)
    (tmp_path / "package.json").write_text('{"scripts":{"build":"next build"}}', encoding="utf-8")
    s = detect_repo_stack(tmp_path)
    assert s.framework == "nextjs_app"
    assert s.is_node_project
    assert s.has_build_script


def test_detect_static_html(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    s = detect_repo_stack(tmp_path)
    assert s.framework in ("static", "unknown")
    assert not s.has_build_script
