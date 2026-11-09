"""Render the actual M2 home template with isolated, non-production categories."""
from __future__ import annotations

import ast
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


source = ast.parse(Path("app/services/module2_home.py").read_text(encoding="utf-8"))
constants = {
    target.id: ast.literal_eval(node.value)
    for node in source.body if isinstance(node, ast.Assign)
    for target in node.targets if isinstance(target, ast.Name)
    and target.id in {"HOUSE_ZONES", "ZONE_GROUPS"}
}
zones = [
    {"part": part, "category_code": code, "name": name, "description": description,
     "url": f"/api/v1/module2/encyclopedia/categories/{code}"}
    for part, code, name, description in constants["HOUSE_ZONES"]
]
by_part = {zone["part"]: zone for zone in zones}
env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape(("html",)))
print(env.get_template("module2_home.html").render(
    zones=zones, zones_by_part=by_part, zone_groups=constants["ZONE_GROUPS"],
    selected=by_part["foundations"], house_view="cutaway", can_workbench=True,
    m2_nav_active="home", atom_topbar_current_block="Модуль №2: Технологии",
))
