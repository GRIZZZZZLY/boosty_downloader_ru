"""Guard against Flet properties that are scheduled for removal.

`flet run` hides these warnings, and the built app only shows them at runtime,
which is a bad place to find out. A source scan catches them at test time.
"""

import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

# Property -> the version of Flet that removes it.
REMOVED_IN = {
    "border_color": "1.3.0",
    "focused_border_color": "1.3.0",
    "focused_border_width": "1.3.0",
}


def _uses(name: str):
    """Every place the source passes or assigns `name`, as file:line."""
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == name:
                        yield f"{path.relative_to(SRC)}:{keyword.value.lineno}"
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == name:
                        yield f"{path.relative_to(SRC)}:{node.lineno}"


@pytest.mark.parametrize("name, removed_in", sorted(REMOVED_IN.items()))
def test_deprecated_property_is_not_used(name, removed_in):
    used = sorted(set(_uses(name)))
    assert (
        used == []
    ), f"{name} is removed in Flet {removed_in}; used at: {', '.join(used)}"


def test_flet_still_considers_border_color_deprecated():
    """If Flet ever un-deprecates it, this test says so instead of guessing."""
    import flet as ft
    from flet.controls.material.form_field_control import FormFieldControl

    annotation = FormFieldControl.__annotations__["border_color"]
    assert "deprecated" in str(annotation).lower()
    # The replacement used across the app has to keep working.
    assert ft.OutlineInputBorder(side=ft.BorderSide(color=ft.Colors.TRANSPARENT))
