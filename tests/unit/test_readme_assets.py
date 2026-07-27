from __future__ import annotations

import re
from xml.etree import ElementTree

from sbfp_platform.config import repo_root

IMAGE = re.compile(r"!\[([^]]+)]\((docs/images/[^)]+\.svg)\)")
SVG = "{http://www.w3.org/2000/svg}"


def test_readme_graphics_exist_and_are_accessible_svg() -> None:
    root = repo_root()
    references = IMAGE.findall((root / "README.md").read_text(encoding="utf-8"))
    assert len(references) >= 2

    for alt_text, relative_path in references:
        assert alt_text.strip()
        svg = ElementTree.parse(root / relative_path).getroot()
        assert svg.tag == f"{SVG}svg"
        assert svg.find(f"{SVG}title") is not None
        assert svg.find(f"{SVG}desc") is not None
        assert svg.get("viewBox")
