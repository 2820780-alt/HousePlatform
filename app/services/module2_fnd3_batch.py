"""Prepare the reviewed FND-3 draft blocks as one caller-controlled transaction."""
from __future__ import annotations

from functools import partial

from app.services.module2_fnd3_base_preparation import SCOPES, add_base_preparation_blocks
from app.services.module2_fnd3_bored_pile_blocks import add_bored_pile_blocks, add_bored_pile_reinforcement_blocks
from app.services.module2_fnd3_coating_blocks import add_coating_blocks, add_coating_primer_work
from app.services.module2_fnd3_column_wall_blocks import (
    add_column_wall_concrete, add_column_wall_formwork, add_column_wall_reinforcement,
)
from app.services.module2_fnd3_driven_pile_blocks import add_driven_pile_blocks, add_driven_head_treatment_block
from app.services.module2_fnd3_grillage_blocks import add_grillage_blocks
from app.services.module2_fnd3_membrane_blocks import add_membrane_blocks
from app.services.module2_fnd3_precast_blocks import add_precast_blocks
from app.services.module2_fnd3_ribbed_slab_blocks import USHP_CODE, add_ribbed_slab_blocks, add_ribbed_slab_detail_blocks
from app.services.module2_fnd3_screw_pile_blocks import add_screw_pile_blocks, add_screw_optional_work_blocks
from app.services.module2_fnd3_slab_blocks import add_slab_concrete_block, add_slab_formwork_block, add_slab_reinforcement_blocks
from app.services.module2_fnd3_strip_blocks import add_strip_blocks
from app.services.module2_fnd3_strip_auxiliary import add_strip_auxiliary_blocks
from app.services.module2_fnd3_uff_blocks import add_uff_blocks
from app.services.module2_fnd3_ushp_blocks import add_ushp_blocks, add_ushp_geotextile_block, add_ushp_preparation_blocks
from app.services.module2_fnd3_xps_blocks import add_xps_blocks
from app.services.module2_fnd3_work_details import add_foundation_work_details


def _steps():
    steps = [add_strip_blocks, add_strip_auxiliary_blocks, add_precast_blocks, add_slab_concrete_block, add_slab_reinforcement_blocks,
             add_slab_formwork_block, add_ribbed_slab_blocks, add_ribbed_slab_detail_blocks,
             partial(add_ribbed_slab_blocks, technology_code=USHP_CODE), add_ushp_blocks,
             add_ushp_preparation_blocks, add_ushp_geotextile_block, add_uff_blocks,
             add_bored_pile_blocks, add_bored_pile_reinforcement_blocks, add_driven_pile_blocks, add_driven_head_treatment_block,
             add_screw_pile_blocks, add_screw_optional_work_blocks, add_grillage_blocks, add_coating_blocks, add_coating_primer_work,
             add_membrane_blocks, add_xps_blocks]
    for code in ("FND_COLUMN_CONCRETE_RC", "FND_BASEMENT_WALL_MONOLITHIC"):
        steps.extend(partial(fn, technology_code=code) for fn in (
            add_column_wall_concrete, add_column_wall_reinforcement, add_column_wall_formwork))
    steps.extend(partial(add_base_preparation_blocks, technology_code=code) for code in SCOPES)
    return steps


async def prepare_foundation_drafts(db, *, actor: object) -> list[dict]:
    """Stage reviewed blocks atomically; the caller retains responsibility for commit."""
    results = []
    async with db.begin_nested():
        await add_foundation_work_details(db)
        for step in _steps():
            result = await step(db, actor=actor)
            if result.get("edited"):
                conflicts = ", ".join(str(name) for name in result["edited"])
                raise ValueError(f"Existing calculation blocks were changed ({conflicts}); no batch changes applied")
            results.append(result)
        await db.flush()
    return results
