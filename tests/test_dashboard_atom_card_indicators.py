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
    assert indicators[0] == {"tone": "info", "icon": "•", "text": "394 материалов"}
    assert indicators[1] == {"tone": "warn", "icon": "⚠", "text": "7 на проверке"}
    assert indicators[2] == {"tone": "danger", "icon": "✖", "text": "2 ошибки"}


def test_module_indicators_mark_future_and_empty_states():
    indicators = _module_indicators(
        number=7,
        metrics=[],
        events=[],
        atom_status="planned",
        fallback_status="Планируется",
    )

    assert indicators[0] == {"tone": "future", "icon": "◇", "text": "образ объекта планируется"}
    assert len(indicators) == 3


def test_module_indicators_use_mock_summary_for_analytics():
    indicators = _module_indicators(
        number=11,
        metrics=[
            {"label": "Динамика рынка", "value": "+3,8%"},
            {"label": "Категорий с динамикой", "value": 4},
        ],
        events=[],
        atom_status="active",
        fallback_status="Работает",
    )

    assert indicators == [
        {"tone": "info", "icon": "↗", "text": "стоимость +3,8%"},
        {"tone": "info", "icon": "•", "text": "4 категорий"},
        {"tone": "warn", "icon": "⚠", "text": "mock-аналитика"},
    ]
