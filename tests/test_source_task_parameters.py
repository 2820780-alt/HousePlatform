from app.api.v1.dev_material_hub import _sanitize_task_parameters
from app.models.enums import SourceActionType


def test_full_scan_parameters_are_bounded():
    parameters = _sanitize_task_parameters(
        SourceActionType.INITIAL_MATERIAL_SCAN,
        {"scan_mode": "FULL", "max_pages": 100, "max_attempts": 400},
    )

    assert parameters["scan_mode"] == "FULL"
    assert parameters["max_pages"] == 100
    assert parameters["max_attempts"] == 300


def test_test_scan_parameters_are_small_by_default():
    parameters = _sanitize_task_parameters(SourceActionType.UPDATE_PRICES, {"scan_mode": "TEST"})

    assert parameters["scan_mode"] == "TEST"
    assert parameters["max_pages"] == 5
    assert parameters["max_attempts"] == 15
