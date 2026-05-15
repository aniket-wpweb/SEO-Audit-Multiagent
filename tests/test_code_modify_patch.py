"""Unit tests for code_modify string patch helpers."""

from __future__ import annotations

import app.tools.code_modify as code_modify


def test_patch_page_img_alt_empty_string_alt() -> None:
    s = '<img alt="" src="/_next/image?url=%2Fx.jpg" />'
    out = code_modify._patch_page_img_alt(s)
    assert out is not None
    assert 'alt="Workshop image"' in out
    assert 'alt=""' not in out


def test_patch_page_img_alt_jsx_empty_literal() -> None:
    s = 'export default function P() { return <Image src="/a.jpg" alt={""} />; }'
    out = code_modify._patch_page_img_alt(s)
    assert out is not None
    assert "Workshop image" in out
