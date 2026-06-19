from decimal import Decimal

from app.services.unit_conversion_rules import convert_quantity


def test_board_piece_to_volume_requires_dimensions():
    result = convert_quantity(
        10,
        from_unit="шт",
        to_unit="м3",
        formula_type="PIECE_TO_VOLUME",
        specifications={"thickness": 50, "width": 150},
    )

    assert result.can_convert is False
    assert result.missing_specifications == ("length",)


def test_board_piece_to_volume_from_millimeters():
    result = convert_quantity(
        10,
        from_unit="шт",
        to_unit="м3",
        formula_type="PIECE_TO_VOLUME",
        specifications={"thickness": 50, "width": 150, "length": 6000},
    )

    assert result.can_convert is True
    assert result.value == Decimal("0.450000000")
    assert result.unit == "м3"


def test_osb_sheet_to_area():
    result = convert_quantity(
        3,
        from_unit="лист",
        to_unit="м2",
        formula_type="PIECE_TO_AREA",
        specifications={"width": 1220, "length": 2440},
    )

    assert result.can_convert is True
    assert result.value == Decimal("8.930400")


def test_dry_mix_bag_to_kg_uses_package_weight():
    result = convert_quantity(
        4,
        from_unit="мешок",
        to_unit="кг",
        formula_type="PACKAGE_TO_UNIT",
        specifications={"package_weight": 25},
    )

    assert result.can_convert is True
    assert result.value == Decimal("100")


def test_fasteners_weight_to_pieces_does_not_guess_without_piece_weight():
    result = convert_quantity(
        1,
        from_unit="кг",
        to_unit="шт",
        formula_type="WEIGHT_TO_PIECE",
        specifications={},
    )

    assert result.can_convert is False
    assert result.missing_specifications == ("single_piece_weight",)


def test_fasteners_weight_to_pieces_with_piece_weight():
    result = convert_quantity(
        1,
        from_unit="кг",
        to_unit="шт",
        formula_type="WEIGHT_TO_PIECE",
        specifications={"single_piece_weight": Decimal("0.005")},
    )

    assert result.can_convert is True
    assert result.value == Decimal("2E+2")
