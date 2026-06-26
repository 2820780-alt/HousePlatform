from app.api.v1.admin_cabinet_view import _module_indicators


def test_module_indicators_keep_atom_card_compact():
    indicators = _module_indicators(
        number=1,
        metrics=[
            {"label": "Всего", "value": 394},
            {"label": "Без категории", "value": 7, "alert": True},
            {"label": "Без документов", "value": 12},
        ],
        events=[
            {"kind": "warning", "label": "на проверке", "value": 7},
            {"kind": "error", "label": "ошибки", "value": 2},
        ],
        atom_status="attention",
        fallback_status="Работает",
    )

    assert len(indicators) == 3
    assert indicators[0] == {"tone": "warn", "icon": "!", "text": "на проверке: 7"}
    assert indicators[1] == {"tone": "danger", "icon": "x", "text": "ошибки: 2"}
    assert indicators[2] == {"tone": "info", "icon": "+", "text": "Всего: 394"}


def test_module_indicators_mark_future_and_empty_states():
    indicators = _module_indicators(
        number=7,
        metrics=[],
        events=[],
        atom_status="planned",
        fallback_status="Планируется",
    )

    assert indicators[0] == {"tone": "future", "icon": "◇", "text": "планируется"}
    assert len(indicators) == 2
