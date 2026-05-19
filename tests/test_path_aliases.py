from __future__ import annotations

import json
from pathlib import Path

from app.services.path_aliases import load_path_mappings, resolve_alias_spec


def test_resolve_alias_spec_src_app(tmp_path: Path) -> None:
    (tmp_path / "src" / "components" / "Blog").mkdir(parents=True)
    target = tmp_path / "src" / "components" / "Blog" / "SingleBlog.tsx"
    target.write_text("export default function SB() {}", encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "baseUrl": ".",
                    "paths": {"@/*": ["./src/*"]},
                }
            }
        ),
        encoding="utf-8",
    )
    load_path_mappings.cache_clear()
    rel = resolve_alias_spec(tmp_path, "@/components/Blog/SingleBlog")
    assert rel == "src/components/Blog/SingleBlog.tsx"


def test_load_path_mappings_from_jsconfig(tmp_path: Path) -> None:
    (tmp_path / "src" / "lib").mkdir(parents=True)
    (tmp_path / "src" / "lib" / "util.ts").write_text("export const x = 1", encoding="utf-8")
    (tmp_path / "jsconfig.json").write_text(
        json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"]}}}),
        encoding="utf-8",
    )
    load_path_mappings.cache_clear()
    mappings = load_path_mappings(str(tmp_path.resolve()))
    assert mappings
    assert resolve_alias_spec(tmp_path, "@/lib/util") == "src/lib/util.ts"
