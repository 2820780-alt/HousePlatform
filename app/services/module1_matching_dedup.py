from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping

from app.services.module1_material_normalizer import NormalizedMaterialCandidate


DIMENSION_FIELDS = frozenset(
    {
        "dimensions_mm",
        "length_mm",
        "width_mm",
        "height_mm",
        "thickness_mm",
        "diameter_mm",
        "metal_thickness_mm",
        "sheet_area_m2",
        "roll_area_m2",
    }
)

EXACT_MATCH_THRESHOLD = Decimal("95")
STRONG_MATCH_THRESHOLD = Decimal("90")
MODERATION_MATCH_THRESHOLD = Decimal("70")
POSSIBLE_DUPLICATE_THRESHOLD = Decimal("55")


@dataclass(frozen=True)
class MatchComparison:
    score: Decimal
    matched_fields: tuple[str, ...] = ()
    conflicting_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    explanation: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaterialMatchScore:
    score: Decimal
    breakdown: Mapping[str, Decimal]
    conflicting_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    explanation: tuple[str, ...]


@dataclass(frozen=True)
class MaterialMatchCandidateDTO:
    candidate_id: str
    normalized_candidate_snapshot: Mapping[str, Any]
    matched_material_reference: Mapping[str, Any] | None
    confidence: Decimal
    decision_hint: str
    explanation: tuple[str, ...]
    conflicting_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    evidence_refs: Mapping[str, Any]
    source_refs: Mapping[str, Any]
    score_breakdown: Mapping[str, Decimal]


@dataclass(frozen=True)
class DedupCandidateDTO:
    candidate_id: str
    left_candidate_snapshot: Mapping[str, Any]
    right_candidate_snapshot: Mapping[str, Any]
    confidence: Decimal
    decision_hint: str
    explanation: tuple[str, ...]
    conflicting_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    score_breakdown: Mapping[str, Decimal]


@dataclass(frozen=True)
class DedupReport:
    checked_candidates: int
    duplicate_candidates: tuple[DedupCandidateDTO, ...]
    summary: Mapping[str, Any]


def build_match_candidate(
    normalized_candidate: NormalizedMaterialCandidate,
    existing_materials: Iterable[Mapping[str, Any] | Any],
) -> MaterialMatchCandidateDTO:
    best_material: Mapping[str, Any] | Any | None = None
    best_score: MaterialMatchScore | None = None

    for material in existing_materials:
        current_score = score_material_match(normalized_candidate, material)
        if best_score is None or current_score.score > best_score.score:
            best_material = material
            best_score = current_score

    if best_material is None or best_score is None:
        return _match_candidate_dto(
            normalized_candidate,
            material=None,
            match_score=MaterialMatchScore(
                score=Decimal("0.00"),
                breakdown={},
                conflicting_fields=(),
                missing_fields=tuple(normalized_candidate.missing_required_fields),
                explanation=("No existing material snapshots were provided.",),
            ),
            decision_hint="new_material_candidate",
        )

    decision_hint = classify_match_confidence(best_score.score)
    if _has_duplicate_signal(best_score):
        decision_hint = "possible_duplicate"

    return _match_candidate_dto(
        normalized_candidate,
        material=best_material,
        match_score=best_score,
        decision_hint=decision_hint,
    )


def score_material_match(
    normalized_candidate: NormalizedMaterialCandidate,
    existing_material: Mapping[str, Any] | Any,
) -> MaterialMatchScore:
    title = compare_titles(
        normalized_candidate.normalized_title or normalized_candidate.source_title,
        _material_title(existing_material),
    )
    group = compare_group_code(
        normalized_candidate.suggested_group_code,
        _material_value(existing_material, "group_code", "suggested_group_code", "material_group", "category_code"),
    )
    dimensions = compare_dimensions(normalized_candidate.normalized_characteristics, _material_characteristics(existing_material))
    characteristics = compare_characteristics(
        normalized_candidate.normalized_characteristics,
        _material_characteristics(existing_material),
    )
    manufacturer = compare_manufacturer_brand(normalized_candidate, existing_material)
    unit = _compare_units(normalized_candidate.normalized_unit, _material_value(existing_material, "normalized_unit", "unit", "base_unit"))
    source_confidence = _decimal_0_1(normalized_candidate.confidence)

    breakdown = {
        "title": _points(title.score, Decimal("15")),
        "group_code": _points(group.score, Decimal("20")),
        "dimensions": _points(dimensions.score, Decimal("30")),
        "characteristics": _points(characteristics.score, Decimal("20")),
        "manufacturer_brand": _points(manufacturer.score, Decimal("5")),
        "unit": _points(unit.score, Decimal("5")),
        "source_confidence": _points(source_confidence, Decimal("5")),
    }
    raw_score = sum(breakdown.values(), Decimal("0.00"))

    conflicting_fields = _unique(
        title.conflicting_fields
        + group.conflicting_fields
        + dimensions.conflicting_fields
        + characteristics.conflicting_fields
        + manufacturer.conflicting_fields
        + unit.conflicting_fields
    )
    missing_fields = _unique(
        tuple(normalized_candidate.missing_required_fields)
        + title.missing_fields
        + group.missing_fields
        + dimensions.missing_fields
        + characteristics.missing_fields
        + manufacturer.missing_fields
        + unit.missing_fields
    )
    conflict_penalty = min(Decimal("16"), Decimal("4") * len(conflicting_fields))
    score = max(Decimal("0.00"), min(Decimal("100.00"), raw_score - conflict_penalty)).quantize(Decimal("0.01"))

    explanation = build_matching_explanation(
        normalized_candidate=normalized_candidate,
        existing_material=existing_material,
        score=score,
        breakdown=breakdown,
        conflicting_fields=conflicting_fields,
        missing_fields=missing_fields,
        comparisons=(title, group, dimensions, characteristics, manufacturer, unit),
    )
    return MaterialMatchScore(
        score=score,
        breakdown=breakdown,
        conflicting_fields=conflicting_fields,
        missing_fields=missing_fields,
        explanation=explanation,
    )


def compare_titles(left_title: str | None, right_title: str | None) -> MatchComparison:
    left = _normalize_title_for_match(left_title)
    right = _normalize_title_for_match(right_title)
    if not left or not right:
        return MatchComparison(score=Decimal("0.50"), missing_fields=("title",), explanation=("Title is missing on one side.",))

    ratio = Decimal(str(SequenceMatcher(None, left, right).ratio()))
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    token_score = Decimal("0")
    if left_tokens or right_tokens:
        token_score = Decimal(len(left_tokens & right_tokens)) / Decimal(len(left_tokens | right_tokens))
    score = max(ratio, token_score).quantize(Decimal("0.01"))
    explanation = (f"title similarity {score}",)
    return MatchComparison(score=score, matched_fields=("title",), explanation=explanation)


def compare_group_code(left_group_code: str | None, right_group_code: str | None) -> MatchComparison:
    if not left_group_code or not right_group_code:
        return MatchComparison(score=Decimal("0.50"), missing_fields=("group_code",), explanation=("Group code is missing on one side.",))
    if left_group_code == right_group_code:
        return MatchComparison(score=Decimal("1.00"), matched_fields=("group_code",), explanation=("Group code matches.",))
    return MatchComparison(
        score=Decimal("0.00"),
        conflicting_fields=("group_code",),
        explanation=(f"group_code differs: {left_group_code} != {right_group_code}",),
    )


def compare_characteristics(
    left_characteristics: Mapping[str, Any] | None,
    right_characteristics: Mapping[str, Any] | None,
) -> MatchComparison:
    left = {key: value for key, value in dict(left_characteristics or {}).items() if key not in DIMENSION_FIELDS}
    right = {key: value for key, value in dict(right_characteristics or {}).items() if key not in DIMENSION_FIELDS}
    if not left or not right:
        return MatchComparison(score=Decimal("0.60"), missing_fields=("characteristics",), explanation=("Characteristic set is incomplete.",))

    common_keys = sorted(set(left) & set(right))
    missing = tuple(sorted((set(left) ^ set(right)) - DIMENSION_FIELDS))
    if not common_keys:
        return MatchComparison(
            score=Decimal("0.50"),
            missing_fields=missing or ("characteristics",),
            explanation=("No common characteristics to compare.",),
        )

    matched: list[str] = []
    conflicts: list[str] = []
    for key in common_keys:
        if _same_value(left[key], right[key]):
            matched.append(key)
        else:
            conflicts.append(key)

    denominator = len(matched) + len(conflicts)
    score = (Decimal(len(matched)) / Decimal(denominator)).quantize(Decimal("0.01")) if denominator else Decimal("0.50")
    explanation = (f"matched characteristics: {', '.join(matched) or 'none'}",)
    return MatchComparison(
        score=score,
        matched_fields=tuple(matched),
        conflicting_fields=tuple(conflicts),
        missing_fields=missing,
        explanation=explanation,
    )


def compare_dimensions(
    left_characteristics: Mapping[str, Any] | None,
    right_characteristics: Mapping[str, Any] | None,
) -> MatchComparison:
    left = _dimension_map(left_characteristics)
    right = _dimension_map(right_characteristics)
    if not left or not right:
        return MatchComparison(score=Decimal("0.55"), missing_fields=("dimensions",), explanation=("Dimension data is incomplete.",))

    common_keys = sorted(set(left) & set(right))
    if not common_keys:
        return MatchComparison(score=Decimal("0.55"), missing_fields=("dimensions",), explanation=("No common dimensions to compare.",))

    matched: list[str] = []
    conflicts: list[str] = []
    for key in common_keys:
        if _same_value(left[key], right[key]):
            matched.append(key)
        else:
            conflicts.append(key)

    denominator = len(matched) + len(conflicts)
    score = (Decimal(len(matched)) / Decimal(denominator)).quantize(Decimal("0.01")) if denominator else Decimal("0.55")
    return MatchComparison(
        score=score,
        matched_fields=tuple(matched),
        conflicting_fields=tuple(conflicts),
        missing_fields=tuple(sorted(set(left) ^ set(right))),
        explanation=(f"matched dimensions: {', '.join(matched) or 'none'}",),
    )


def compare_manufacturer_brand(
    normalized_candidate: NormalizedMaterialCandidate,
    existing_material: Mapping[str, Any] | Any,
) -> MatchComparison:
    pairs = (
        ("manufacturer", normalized_candidate.manufacturer, _material_value(existing_material, "manufacturer", "raw_manufacturer")),
        ("brand", normalized_candidate.brand, _material_value(existing_material, "brand", "raw_brand")),
    )
    scores: list[Decimal] = []
    matched: list[str] = []
    conflicts: list[str] = []
    missing: list[str] = []

    for field, left, right in pairs:
        if not left and not right:
            continue
        if not left or not right:
            scores.append(Decimal("0.60"))
            missing.append(field)
            continue
        if _same_value(left, right):
            scores.append(Decimal("1.00"))
            matched.append(field)
        else:
            scores.append(Decimal("0.00"))
            conflicts.append(field)

    if not scores:
        return MatchComparison(score=Decimal("0.50"), missing_fields=("manufacturer_brand",), explanation=("Manufacturer and brand are not specified.",))
    return MatchComparison(
        score=(sum(scores, Decimal("0")) / Decimal(len(scores))).quantize(Decimal("0.01")),
        matched_fields=tuple(matched),
        conflicting_fields=tuple(conflicts),
        missing_fields=tuple(missing),
        explanation=(f"matched manufacturer/brand fields: {', '.join(matched) or 'none'}",),
    )


def classify_match_confidence(score: Decimal | int | float) -> str:
    value = Decimal(str(score))
    if value >= EXACT_MATCH_THRESHOLD:
        return "exact_match"
    if value >= STRONG_MATCH_THRESHOLD:
        return "strong_match"
    if value >= MODERATION_MATCH_THRESHOLD:
        return "needs_moderation"
    return "new_material_candidate"


def _has_duplicate_signal(match_score: MaterialMatchScore) -> bool:
    if not match_score.conflicting_fields:
        return False
    if match_score.score >= POSSIBLE_DUPLICATE_THRESHOLD:
        return True
    return (
        match_score.breakdown.get("group_code", Decimal("0")) >= Decimal("20")
        and match_score.breakdown.get("title", Decimal("0")) >= Decimal("7.50")
    )


def detect_duplicate_candidates(
    normalized_candidates: Iterable[NormalizedMaterialCandidate],
) -> tuple[DedupCandidateDTO, ...]:
    candidates = tuple(normalized_candidates)
    duplicate_candidates: list[DedupCandidateDTO] = []
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            score = score_material_match(left, _candidate_as_material_snapshot(right))
            if score.score < MODERATION_MATCH_THRESHOLD and not _has_duplicate_signal(score):
                continue
            decision_hint = classify_match_confidence(score.score)
            if score.conflicting_fields:
                decision_hint = "possible_duplicate"
            duplicate_candidates.append(
                DedupCandidateDTO(
                    candidate_id=_stable_key("dedup", _candidate_snapshot(left), _candidate_snapshot(right)),
                    left_candidate_snapshot=_candidate_snapshot(left),
                    right_candidate_snapshot=_candidate_snapshot(right),
                    confidence=score.score,
                    decision_hint=decision_hint,
                    explanation=score.explanation,
                    conflicting_fields=score.conflicting_fields,
                    missing_fields=score.missing_fields,
                    score_breakdown=score.breakdown,
                )
            )
    return tuple(duplicate_candidates)


def build_dedup_report(candidates: Iterable[NormalizedMaterialCandidate]) -> DedupReport:
    candidate_tuple = tuple(candidates)
    duplicate_candidates = detect_duplicate_candidates(candidate_tuple)
    by_decision: dict[str, int] = {}
    for candidate in duplicate_candidates:
        by_decision[candidate.decision_hint] = by_decision.get(candidate.decision_hint, 0) + 1
    return DedupReport(
        checked_candidates=len(candidate_tuple),
        duplicate_candidates=duplicate_candidates,
        summary={
            "duplicate_count": len(duplicate_candidates),
            "decision_hints": by_decision,
            "auto_merge_allowed": False,
        },
    )


def build_matching_explanation(
    *,
    normalized_candidate: NormalizedMaterialCandidate,
    existing_material: Mapping[str, Any] | Any,
    score: Decimal,
    breakdown: Mapping[str, Decimal],
    conflicting_fields: tuple[str, ...],
    missing_fields: tuple[str, ...],
    comparisons: tuple[MatchComparison, ...],
) -> tuple[str, ...]:
    messages = [
        f"Match confidence: {score}.",
        f"Candidate group: {normalized_candidate.suggested_group_code or 'unknown'}.",
        f"Existing material: {_material_title(existing_material) or 'unknown'}.",
        "Breakdown: "
        + ", ".join(f"{key}={value}" for key, value in sorted(breakdown.items())),
    ]
    if conflicting_fields:
        messages.append("Conflicts: " + ", ".join(conflicting_fields) + ".")
    if missing_fields:
        messages.append("Missing or partial fields: " + ", ".join(missing_fields) + ".")
    for comparison in comparisons:
        messages.extend(comparison.explanation)
    messages.append("No automatic merge or alias creation is performed.")
    return tuple(messages)


def _match_candidate_dto(
    normalized_candidate: NormalizedMaterialCandidate,
    *,
    material: Mapping[str, Any] | Any | None,
    match_score: MaterialMatchScore,
    decision_hint: str,
) -> MaterialMatchCandidateDTO:
    return MaterialMatchCandidateDTO(
        candidate_id=_stable_key("match", _candidate_snapshot(normalized_candidate), _material_reference(material)),
        normalized_candidate_snapshot=_candidate_snapshot(normalized_candidate),
        matched_material_reference=_material_reference(material),
        confidence=match_score.score,
        decision_hint=decision_hint,
        explanation=match_score.explanation,
        conflicting_fields=match_score.conflicting_fields,
        missing_fields=match_score.missing_fields,
        evidence_refs=_evidence_refs(normalized_candidate),
        source_refs=_source_refs(normalized_candidate),
        score_breakdown=match_score.breakdown,
    )


def _candidate_as_material_snapshot(candidate: NormalizedMaterialCandidate) -> Mapping[str, Any]:
    return {
        "id": _stable_key("candidate", _candidate_snapshot(candidate)),
        "normalized_title": candidate.normalized_title,
        "group_code": candidate.suggested_group_code,
        "normalized_characteristics": candidate.normalized_characteristics,
        "normalized_unit": candidate.normalized_unit,
        "manufacturer": candidate.manufacturer,
        "brand": candidate.brand,
        "source_refs": _source_refs(candidate),
    }


def _candidate_snapshot(candidate: NormalizedMaterialCandidate) -> Mapping[str, Any]:
    return _jsonable(asdict(candidate))


def _material_reference(material: Mapping[str, Any] | Any | None) -> Mapping[str, Any] | None:
    if material is None:
        return None
    return {
        "id": _material_value(material, "id", "material_id", "code"),
        "title": _material_title(material),
        "group_code": _material_value(material, "group_code", "suggested_group_code", "material_group", "category_code"),
    }


def _material_title(material: Mapping[str, Any] | Any) -> str | None:
    value = _material_value(material, "normalized_title", "canonical_name", "name", "title", "raw_name")
    return str(value) if value not in (None, "") else None


def _material_characteristics(material: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    value = _material_value(material, "normalized_characteristics", "characteristics", "attributes", "technical_profile")
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _material_value(material: Mapping[str, Any] | Any, *keys: str) -> Any:
    for key in keys:
        if isinstance(material, Mapping) and key in material:
            return material[key]
        if not isinstance(material, Mapping) and hasattr(material, key):
            return getattr(material, key)
    return None


def _compare_units(left_unit: str | None, right_unit: str | None) -> MatchComparison:
    if not left_unit or not right_unit:
        return MatchComparison(score=Decimal("0.50"), missing_fields=("unit",), explanation=("Unit is missing on one side.",))
    if _same_value(left_unit, right_unit):
        return MatchComparison(score=Decimal("1.00"), matched_fields=("unit",), explanation=("Unit matches.",))
    return MatchComparison(score=Decimal("0.00"), conflicting_fields=("unit",), explanation=(f"unit differs: {left_unit} != {right_unit}",))


def _dimension_map(characteristics: Mapping[str, Any] | None) -> Mapping[str, Any]:
    result: dict[str, Any] = {}
    source = dict(characteristics or {})
    dimensions = source.get("dimensions_mm")
    if isinstance(dimensions, (list, tuple)):
        for index, value in enumerate(dimensions):
            result[f"dimension_{index + 1}_mm"] = value
    for key, value in source.items():
        if key in DIMENSION_FIELDS and key != "dimensions_mm":
            result[key] = value
    return result


def _normalize_title_for_match(value: str | None) -> str:
    text = _normalize_text(value)
    replacements = {
        "газобетонный блок": "aerated_concrete_block",
        "газобетон блок": "aerated_concrete_block",
        "газоблок": "aerated_concrete_block",
        "газобетон": "aerated_concrete_block",
        "арматура": "rebar",
        "бетон": "concrete",
        "доска обрезная": "board",
        "доска": "board",
        "металлочерепица": "metal_tile",
        "гклв": "gypsum_board",
        "гкл": "gypsum_board",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return _collapse_spaces(text)


def _normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("×", "x").replace("х", "x").replace("*", "x").replace("ø", "")
    text = text.replace("d ", "d").replace("а ", "а")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = re.sub(r"[^0-9a-zа-яё._ -]+", " ", text)
    return _collapse_spaces(text)


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _same_value(left: Any, right: Any) -> bool:
    left_decimal = _decimal_or_none(left)
    right_decimal = _decimal_or_none(right)
    if left_decimal is not None and right_decimal is not None:
        return left_decimal == right_decimal
    return _normalize_scalar(left) == _normalize_scalar(right)


def _normalize_scalar(value: Any) -> str:
    text = _normalize_text(value)
    translation = str.maketrans(
        {
            "а": "a",
            "в": "b",
            "с": "c",
            "е": "e",
            "к": "k",
            "м": "m",
            "н": "h",
            "о": "o",
            "п": "p",
            "р": "p",
            "т": "t",
            "х": "x",
        }
    )
    return text.translate(translation).replace(" ", "")


def _decimal_or_none(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    try:
        if value in (None, ""):
            return None
        return Decimal(str(value).replace(",", "."))
    except Exception:
        return None


def _decimal_0_1(value: Any) -> Decimal:
    decimal = _decimal_or_none(value)
    if decimal is None:
        return Decimal("0.50")
    if decimal > 1:
        decimal = decimal / Decimal("100")
    return max(Decimal("0.00"), min(Decimal("1.00"), decimal))


def _points(score_0_1: Decimal, weight: Decimal) -> Decimal:
    return (score_0_1 * weight).quantize(Decimal("0.01"))


def _source_refs(candidate: NormalizedMaterialCandidate) -> Mapping[str, Any]:
    keys = ("source_id", "source_code", "source_type", "source_url", "legacy_source", "captured_at", "observed_at")
    return {key: _jsonable(candidate.source_metadata.get(key)) for key in keys if candidate.source_metadata.get(key) not in (None, "")}


def _evidence_refs(candidate: NormalizedMaterialCandidate) -> Mapping[str, Any]:
    keys = ("raw_title", "raw_category", "raw_documents", "raw_images", "extraction_profile_reference")
    return {key: _jsonable(candidate.evidence.get(key)) for key in keys if candidate.evidence.get(key) not in (None, "", [], {})}


def _stable_key(prefix: str, *parts: Any) -> str:
    payload = repr(_jsonable(parts)).encode("utf-8")
    return f"{prefix}_{hashlib.sha1(payload).hexdigest()[:16]}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_jsonable(item) for item in value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return tuple(result)
