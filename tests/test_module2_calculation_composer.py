from decimal import Decimal
from dataclasses import replace

import pytest

from app.services.module2_calculation_blocks import decode_definition, encode_definition
from app.services.module2_calculation_composer import ComposerStep, compose_block, composer_form_data, recompose_block
from app.services.module2_calculation_graph import evaluate_block
from app.services.module5_calculation_preview import StatementBinding, calculate_statement_preview


def test_composed_volume_uses_named_steps_and_persists_without_code():
    steps = (
        ComposerStep("Длина", "INPUT", "m", source="geometry.length"),
        ComposerStep("Ширина", "INPUT", "m", source="geometry.width"),
        ComposerStep("Высота", "INPUT", "m", source="PARAMETER"),
        ComposerStep("Площадь", "MULTIPLY", "m2", (1, 2)),
        ComposerStep("Объём", "MULTIPLY", "m3", (4, 3)),
    )
    graph = compose_block("Лента", steps, material_step=5, work_step=5, rule_source="Проект")
    assert graph.rule_status == "PRELIMINARY" and graph.parameters[0].status == "UNCONFIRMED"
    inputs = {"geometry.length": ("10", "m"), "geometry.width": ("0.4", "m"),
              graph.parameters[0].input_key: ("0.6", "m")}
    assert evaluate_block(graph, inputs)[graph.outputs[0]].value == Decimal("2.4")
    restored = decode_definition(encode_definition(graph), block_id=graph.id, name=graph.name)
    assert restored == graph and restored.nodes[-1].label == "Объём"


def test_composer_rejects_future_reference_wrong_units_and_unsourced_constants():
    with pytest.raises(ValueError, match="earlier"):
        compose_block("Ошибка", (ComposerStep("Шаг", "ADD", "m", (1, 1)),),
                      material_step=1, work_step=None)
    with pytest.raises(ValueError, match="dimensions"):
        compose_block("Ошибка", (ComposerStep("Длина", "INPUT", "m", source="geometry.length"),
                                 ComposerStep("Число", "INPUT", "1", source="PARAMETER"),
                                 ComposerStep("Сумма", "ADD", "m", (1, 2))), material_step=3, work_step=None)
    with pytest.raises(ValueError, match="source"):
        compose_block("Ошибка", (ComposerStep("Постоянная", "CONSTANT", "1", constant=Decimal("2")),),
                      material_step=1, work_step=None)
    with pytest.raises(ValueError, match="length unit"):
        compose_block("Ошибка", (ComposerStep("Длина", "INPUT", "kg", source="geometry.length"),),
                      material_step=1, work_step=None)
    with pytest.raises(ValueError, match="geometry input"):
        compose_block("Ошибка", (ComposerStep("Площадь", "INPUT", "m2", source="geometry.area"),),
                      material_step=1, work_step=None)


def test_composer_does_not_accept_arbitrary_operations_or_missing_output():
    with pytest.raises(ValueError, match="supported"):
        compose_block("Ошибка", (ComposerStep("Код", "EVAL", "1"),), material_step=1, work_step=None)
    with pytest.raises(ValueError, match="output"):
        compose_block("Ошибка", (ComposerStep("Длина", "INPUT", "m", source="geometry.length"),),
                      material_step=None, work_step=None)


def test_preview_accepts_block_parameters_but_never_overrides_m7_geometry():
    steps = (ComposerStep("Длина", "INPUT", "m", source="geometry.length"),
             ComposerStep("Ширина", "INPUT", "m", source="PARAMETER"),
             ComposerStep("Площадь", "MULTIPLY", "m2", (1, 2)))
    graph = compose_block("Площадь", steps, material_step=3, work_step=None)
    binding = StatementBinding("line", graph.id, "MATERIAL", "material", graph.outputs[0], "area")
    key = graph.parameters[0].input_key
    result = calculate_statement_preview((graph,), (binding,), {"geometry.length": ("10", "m")}, {},
                                         parameter_values={(graph.id, key): ("0.4", "m")})
    assert result.materials[0].quantity == Decimal("4")
    with pytest.raises(ValueError, match="parameter values"):
        calculate_statement_preview((graph,), (binding,), {"geometry.length": ("10", "m")}, {},
                                    parameter_values={(graph.id, "geometry.length"): ("100", "m")})


def test_editing_supported_scheme_preserves_unchanged_parameter_and_requires_review():
    steps = (ComposerStep("Длина", "INPUT", "m", source="geometry.length"),
             ComposerStep("Толщина", "INPUT", "m", source="PARAMETER"),
             ComposerStep("Площадь", "MULTIPLY", "m2", (1, 2)))
    old = compose_block("Расчёт", steps, material_step=3, work_step=None, rule_source="Проект")
    old = replace(old, rule_status="VERIFIED", parameters=(replace(old.parameters[0], default=Decimal("0.2"),
                          source="Проект", status="VERIFIED", auto_apply=True),))
    assert composer_form_data(old)["steps"][2]["references"] == [1, 2]
    changed = compose_block("Расчёт", (*steps[:2], ComposerStep("Сумма", "ADD", "m", (1, 2))),
                            material_step=3, work_step=None, rule_source="Проект")
    edited = recompose_block(old, changed)
    assert edited.id == old.id and edited.rule_status == "PRELIMINARY"
    assert edited.parameters[0].input_key == old.parameters[0].input_key
    assert edited.parameters[0].default == Decimal("0.2") and edited.parameters[0].source == "Проект"
    assert edited.nodes[2].operation == "ADD"
