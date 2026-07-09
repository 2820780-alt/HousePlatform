
# Module №2 Technology Engine — Codex-ready implementation plan for VSCode

Версия: 1.0  
Назначение: план реализации скрытого расчетного ядра Модуля №2 для ИЖС и ремонта квартир.  
Формат: один Markdown-файл, который можно положить в репозиторий и использовать как рабочую спецификацию для Codex в VSCode.

---

## 0. Короткий ответ на вопрос про спринты

Предыдущие спринты были больше похожи на архитектурно-продуктовые этапы. Для Codex в VSCode этого недостаточно.

Для Codex нужна другая нарезка:

```text
Большой реализационный спринт = этап сборки модуля.
Codex task card = маленькая исполняемая задача внутри спринта.
```

То есть спринты не должны быть слишком короткими и хаотичными. Но задачи для Codex должны быть короткими, конкретными и проверяемыми тестами.

Правильная структура:

```text
Спринт: 3–7 рабочих дней / один законченный технический блок.
Codex task: 30–120 минут / один ограниченный PR или commit.
```

Codex нельзя давать задачу вида:

```text
Сделай весь Модуль №2.
```

Нужно давать так:

```text
Создай Quantity и UnitConversion Engine.
Файлы: packages/module2/src/core/quantity.ts, packages/module2/src/core/unitConversion.ts.
Добавь тесты: packages/module2/tests/unitConversion.test.ts.
Acceptance: конвертация m -> kg для арматуры работает через kg_per_meter, нет конверсии -> warning.
```

---

## 1. Исправление после проверки: кровельные саморезы

Ошибка, которую нужно исправить в логике дефолтов:

```text
Нельзя считать кровельные саморезы как характеристику самого самореза: screws_per_m2.
```

Правильно:

```text
Количество кровельного крепежа задается схемой крепления кровельного покрытия и технологией монтажа.
```

То есть `screws_per_m2` не является свойством самореза. Это свойство:

```text
roof_covering_profile.fastening_pattern
roof_technology.fastening_rule
batten_step
sheet_profile
overlap_rule
edge_zone_rule
additional_elements_rule
```

Правильная модель:

```ts
interface RoofFasteningPattern {
  patternCode: string;
  baseFastenersPerSheet?: number;
  baseFastenersPerM2Fallback?: number;
  fastenersPerBattenCrossing?: number;
  overlapFastenersPerMeter?: number;
  edgeZoneMultiplier?: number;
  ridgeFastenersPerMeter?: number;
  eaveFastenersPerMeter?: number;
  valleyFastenersPerMeter?: number;
  additionalWastePercent?: number;
  source: 'module_1_covering_profile' | 'technology_default' | 'admin_override';
}
```

Расчет:

```text
roof_fasteners =
  main_field_fasteners
  + overlap_fasteners
  + edge_zone_fasteners
  + additional_element_fasteners
  + waste
```

Для простого предварительного расчета допустим fallback, но он должен быть помечен:

```json
{
  "used_default_value": true,
  "warning": "Крепеж кровли рассчитан по fallback-схеме покрытия, а не по точной раскладке листов."
}
```

---

## 2. Главная архитектурная цель

Модуль №2 — это скрытый Technology Engine.

Он не является пользовательским модулем, не является сметами, не хранит цены и не рассчитывает стоимость.

Он делает только это:

```text
параметры объекта / работы
        ↓
технология + формулы + правила + данные из Material Hub
        ↓
техническая ресурсная спецификация
        ↓
Модуль №5 превращает спецификацию в смету
```

---

## 3. Нерушимые правила runtime

Эти правила Codex должен соблюдать во всех задачах.

```text
1. В runtime Модуля №2 нет LLM/AI-вызовов.
2. Все расчеты детерминированные.
3. Один и тот же input + одна и та же версия технологии = один и тот же output.
4. Модуль №2 не берет цены.
5. Модуль №2 не округляет до закупочных упаковок как финальное действие.
6. Модуль №2 возвращает техническое количество.
7. Модуль №5 выбирает конкретные материалы, упаковки, цены и считает стоимость.
8. Модуль №1 дает технические профили материалов, характеристики, единицы и цены.
9. Любой fallback должен быть явно отражен в assumptions/warnings.
10. Каждая технология должна иметь version и calculation_trace.
11. Старая смета должна хранить snapshot расчета.
12. Изменение технологии не меняет старую смету автоматически.
```

---

## 4. Рекомендуемая структура репозитория

Ниже структура, под которую удобно давать задания Codex. Если текущий стек другой, имена можно адаптировать, но логические слои лучше сохранить.

```text
packages/
  module1-material-hub/
    src/
      contracts/
      technicalProfiles/
      unitConversions/
      prices/

  module2-technology-engine/
    src/
      contracts/
        calculateRequest.ts
        calculateResponse.ts
        materialTechnicalProfile.ts
        module5Handoff.ts

      core/
        quantity.ts
        units.ts
        unitConversion.ts
        formulaEngine.ts
        ruleEngine.ts
        warnings.ts
        assumptions.ts
        trace.ts
        rounding.ts
        validation.ts

      materialResolver/
        materialResolver.interface.ts
        materialResolver.mock.ts
        materialResolver.http.ts
        technicalProfileValidator.ts

      registry/
        technologyRegistry.ts
        technologyPack.ts
        technologyStatus.ts
        technologyVersion.ts

      technologies/
        foundation/
          stripFoundation.ts
          slabFoundation.ts
          pileGrillageFoundation.ts
          screwPiles.ts
          foundationWaterproofing.ts
          blindArea.ts
        walls/
          gasBlockWall.ts
          brickWall.ts
          ceramicBlockWall.ts
          frameWall.ts
          sipWall.ts
          lintels.ts
          bondBeam.ts
          gklPartition.ts
        roof/
          roofGeometry.ts
          shedRoof.ts
          gableRoof.ts
          hipRoof.ts
          rafters.ts
          metalTileRoof.ts
          softRoof.ts
          mansardInsulation.ts
          gutters.ts
          snowGuards.ts
          soffits.ts
        facade/
          wetFacade.ts
          siding.ts
          ventilatedFacade.ts
          plinthFinish.ts
        floors/
          screed.ts
          selfLevelingFloor.ts
          laminate.ts
          vinyl.ts
          waterHeatedFloor.ts
          electricHeatedFloor.ts
        interior/
          primer.ts
          plaster.ts
          putty.ts
          paint.ts
          wallpaper.ts
          tile.ts
          stretchCeiling.ts
          gklCeiling.ts
          doors.ts
          windowsAndSlopes.ts
        bathroom/
          waterproofing.ts
          bathroomTile.ts
          sanitaryBoxes.ts
          showerTray.ts
        mep/
          electrical.ts
          waterSupply.ts
          sewerage.ts
          heating.ts
          ventilation.ts
          septic.ts
          waterEntry.ts
        landscaping/
          fenceProfiledSheet.ts
          fence3dMesh.ts
          gates.ts
          pavingSlabs.ts
          concretePaths.ts
          drainage.ts
          lawn.ts
          porch.ts
          terrace.ts
        demolition/
          tileDemolition.ts
          screedDemolition.ts
          partitionDemolition.ts
          plasterDemolition.ts
          wasteCalculation.ts

      admin/
        dto/
        moderation/
        formulaEditor/
        mappingInspector/
        testCaseManager/

    tests/
      unit/
      integration/
      golden/
      fixtures/

  module5-estimates/
    src/
      module2Bridge/
      widgets/
      materialSelection/
      recalculation/
```

---

## 5. Контракты между Модулями №1, №2 и №5

### 5.1. Запрос из Модуля №5 в Модуль №2

```ts
interface TechnologyCalculationRequest {
  sourceModule: 'module_5_estimates' | 'house_model' | 'plan_2d' | 'constructor_3d';
  sourceEntityId?: string;
  technologyCode: string;
  technologyVersion?: string;
  input: Record<string, unknown>;
  selectedMaterials?: Record<string, string>;
  options?: {
    useDefaults?: boolean;
    returnTrace?: boolean;
    returnReferenceLinks?: boolean;
    strictMode?: boolean;
  };
}
```

### 5.2. Запрос технического профиля из Модуля №2 в Модуль №1

```ts
interface MaterialTechnicalProfileRequest {
  materialGroup: string;
  materialId?: string;
  filters?: Record<string, unknown>;
  requiredFields: string[];
  allowGenericProfile: boolean;
}
```

### 5.3. Ответ Модуля №1

```ts
interface MaterialTechnicalProfileResponse {
  status: 'found' | 'generic_found' | 'missing' | 'incomplete';
  materialGroup: string;
  materialId?: string;
  profile: Record<string, unknown>;
  unitConversions?: UnitConversionRule[];
  missingFields?: string[];
  warnings?: string[];
  profileVersion?: string;
}
```

### 5.4. Ответ Модуля №2 в Модуль №5

```ts
interface TechnologyCalculationResponse {
  calculationId: string;
  status: 'success' | 'success_with_assumptions' | 'blocked' | 'failed';
  technology: {
    code: string;
    name: string;
    version: string;
  };
  inputSnapshot: Record<string, unknown>;
  materialProfileSnapshot?: Record<string, unknown>;
  calculatedValues: Record<string, Quantity>;
  resources: ResourceRequirement[];
  assumptions: Assumption[];
  warnings: Warning[];
  trace: CalculationTraceStep[];
  referenceLinks?: ReferenceLink[];
}
```

### 5.5. ResourceRequirement

```ts
interface ResourceRequirement {
  resourceKey: string;
  resourceType: 'material' | 'labor_hint' | 'equipment_hint' | 'waste';
  materialGroup?: string;
  technicalRequirement: string;
  quantity: number;
  unit: string;
  required: boolean;
  conditionApplied?: string;
  wastePercent?: number;
  overlapPercent?: number;
  materialSelector?: {
    group: string;
    filters?: Record<string, unknown>;
    requiredTechnicalFields?: string[];
  };
  calculationExplanation: string;
  referenceArticleCode?: string;
}
```

---

## 6. Как использовать этот файл с Codex в VSCode

### 6.1. Рекомендуемый режим

1. Положить этот файл в репозиторий:

```text
docs/module2_codex_vscode_implementation_plan.md
```

2. Создать отдельную ветку:

```bash
git checkout -b feature/module2-technology-engine
```

3. Давать Codex не весь файл целиком, а одну task card за раз.

4. После каждой task card:

```bash
npm test
npm run lint
npm run typecheck
```

или команды вашего стека.

5. После каждой рабочей задачи делать commit.

---

## 7. Общий шаблон task card для Codex

```text
TASK: <номер и название>

Context:
You are working on Module №2 Technology Engine. It is a deterministic calculation engine for private house construction and apartment renovation. Runtime must not use AI or LLM calls. Module №2 returns technical resource quantities only. It does not calculate prices.

Goal:
<четкая цель задачи>

Files to create/edit:
<конкретные файлы>

Implementation requirements:
<что именно сделать>

Do not:
<что запрещено>

Tests:
<какие тесты добавить>

Acceptance criteria:
<как понять, что задача готова>
```

---

# IMPLEMENTATION SPRINTS FOR CODEX

Ниже спринты именно по мере реализации. Это не продуктовые этапы, а инженерный порядок сборки.

---

## Sprint 0 — Repository scaffolding and architectural guardrails

Цель: подготовить структуру Модуля №2 так, чтобы Codex не смешивал технологии, сметы, цены и Material Hub.

### Task 0.1 — Create Module №2 package skeleton

```text
TASK 0.1: Create module2-technology-engine package skeleton

Goal:
Create the package/folder structure for Module №2 without implementing business algorithms yet.

Files to create/edit:
packages/module2-technology-engine/src/contracts/*
packages/module2-technology-engine/src/core/*
packages/module2-technology-engine/src/materialResolver/*
packages/module2-technology-engine/src/registry/*
packages/module2-technology-engine/src/technologies/*
packages/module2-technology-engine/tests/*

Implementation requirements:
- Add index exports.
- Add placeholders only where needed.
- Add README explaining Module №2 boundaries.
- Add a runtime guard note: no AI/LLM calls.

Do not:
- Do not add pricing logic.
- Do not add UI.
- Do not connect to live Module №1 yet.

Tests:
- Add a smoke test importing the package root.

Acceptance criteria:
- Package compiles.
- Smoke test passes.
- Folder structure matches the plan.
```

### Task 0.2 — Add runtime invariants test

```text
TASK 0.2: Add runtime invariants

Goal:
Add code-level invariants documenting what Module №2 is not allowed to do.

Files:
packages/module2-technology-engine/src/core/runtimeInvariants.ts
packages/module2-technology-engine/tests/unit/runtimeInvariants.test.ts

Implementation:
- Export constants or functions describing forbidden runtime capabilities.
- Add test asserting no pricing fields are present in calculation response resources.
- Add test asserting calculation response has quantity, unit, trace, warnings, assumptions.

Acceptance:
- Tests pass.
- Future developers see that prices belong to Module №5/Module №1, not Module №2.
```

---

## Sprint 1 — Core domain types: Quantity, Units, Warnings, Trace

Цель: создать фундамент для всех расчетов.

### Task 1.1 — Quantity and unit model

```text
TASK 1.1: Implement Quantity and Unit model

Goal:
Create a safe model for all calculated quantities.

Files:
src/core/quantity.ts
src/core/units.ts
tests/unit/quantity.test.ts

Implementation:
- Quantity = { value: number; unit: UnitCode; precision?: number; source?: string }
- UnitCode includes: m, m2, m3, mm, cm, kg, ton, l, pcs, roll, pack, hour, day.
- Add helpers: q(value, unit), addSameUnit, multiply, divide, roundQuantity.
- Reject adding incompatible units.

Acceptance:
- addSameUnit(q(2,'m'), q(3,'m')) = 5 m.
- addSameUnit(q(2,'m'), q(3,'kg')) throws or returns error.
- multiply(q(10,'m'), q(2,'m')) returns 20 m2 if dimensional mode is enabled or returns a composed unit if simple mode.
```

### Task 1.2 — Warning, Assumption, Trace models

```text
TASK 1.2: Implement warnings, assumptions, calculation trace

Files:
src/core/warnings.ts
src/core/assumptions.ts
src/core/trace.ts
tests/unit/trace.test.ts

Implementation:
- Warning severity: info, warning, blocking.
- Assumption source: technology_default, module_1_generic_profile, admin_override, user_input.
- Trace step contains key, expression, inputs, result, unit, explanation.

Acceptance:
- Trace can be appended step-by-step.
- Warnings can be filtered by severity.
- Assumptions expose source clearly.
```

---

## Sprint 2 — Unit Conversion Engine

Цель: надежно пересчитывать технические единицы без цен и без упаковочного финального округления.

### Task 2.1 — UnitConversion Engine

```text
TASK 2.1: Implement UnitConversion Engine

Files:
src/core/unitConversion.ts
tests/unit/unitConversion.test.ts

Implementation:
- Support static factor conversions: ton <-> kg, cm <-> m, mm <-> m.
- Support profile-based conversions: m -> kg for rebar using kg_per_meter.
- Support area/volume conversions for boards only if dimensions exist.
- Return warning if conversion is impossible.

Examples:
- rebar 512 m × 0.888 kg/m = 454.656 kg.
- 300 kg = 0.3 ton.
- board m2 -> m3 requires thickness. Without thickness return blocking warning.

Acceptance:
- No silent conversion failures.
- Every profile-based conversion includes trace.
```

---

## Sprint 3 — Formula Engine

Цель: готовый механизм формул для алгоритмов.

### Task 3.1 — Safe expression evaluator

```text
TASK 3.1: Implement safe Formula Engine

Files:
src/core/formulaEngine.ts
tests/unit/formulaEngine.test.ts

Implementation:
- Evaluate arithmetic expressions using a controlled parser/evaluator.
- Allow variables only from provided context.
- Allow functions: ceil, floor, round, min, max, sqrt, sin, cos, tan, pi.
- Do not use eval/new Function.
- Return trace with expression, inputs and result.

Acceptance:
- total_strip_length = 2*(building_width + building_length) + internal_walls works.
- Unknown variable returns blocking error.
- No arbitrary JS execution is possible.
```

### Task 3.2 — Formula graph execution

```text
TASK 3.2: Implement formula dependency graph

Goal:
Some formulas depend on previous calculated values.

Implementation:
- FormulaNode has key, expression, unit, dependsOn, condition.
- Execute in dependency order.
- Detect cycles.

Acceptance:
- concrete_volume can depend on total_strip_length.
- Cyclic formulas fail with clear error.
```

---

## Sprint 4 — Rule Engine

Цель: добавлять ресурсы по условиям, а не только по формулам.

### Task 4.1 — Conditional Rule Engine

```text
TASK 4.1: Implement Rule Engine

Files:
src/core/ruleEngine.ts
tests/unit/ruleEngine.test.ts

Implementation:
- Support conditions: equals, notEquals, gt, gte, lt, lte, includes, and/or.
- Rules can add resources, warnings, assumptions.
- Rules must be deterministic.

Examples:
- substrate_type = gas_block -> add deep_penetration_primer.
- plaster_layer_mm > mesh_threshold -> add mesh.
- formwork_type = wooden -> add boards, fasteners, braces.

Acceptance:
- Same input always returns same rule results.
- Missing condition variable creates warning or blocking error based on rule config.
```

---

## Sprint 5 — Material Hub Resolver

Цель: связать Модуль №2 с техническими данными Модуля №1.

### Task 5.1 — Resolver interface and mock

```text
TASK 5.1: Implement MaterialTechnicalProfileResolver interface and mock

Files:
src/materialResolver/materialResolver.interface.ts
src/materialResolver/materialResolver.mock.ts
tests/unit/materialResolver.mock.test.ts

Implementation:
- Define request/response interfaces.
- Mock resolver returns generic profiles for rebar, plaster, primer, gas_block, osb, metal_tile, soft_roof, tile, paint.
- Missing fields must be explicit.

Acceptance:
- Request rebar Ø12 returns kg_per_meter 0.888 from mock.
- Request gypsum_plaster returns consumption_kg_m2_mm from mock.
- Unknown group returns missing status.
```

### Task 5.2 — Technical profile validator

```text
TASK 5.2: Validate required fields from Module №1

Files:
src/materialResolver/technicalProfileValidator.ts
tests/unit/technicalProfileValidator.test.ts

Implementation:
- Given required fields, check profile completeness.
- Return status: complete, incomplete, missing.
- Convert incomplete profile into warnings/blockers depending on strictMode.

Acceptance:
- Missing kg_per_meter for rebar blocks weight conversion.
- Missing pack size does not block Module №2 because packaging is Module №5.
```

---

## Sprint 6 — Calculation Orchestrator and Resource Specification Builder

Цель: единый вход для Модуля №5.

### Task 6.1 — calculateTechnology orchestrator

```text
TASK 6.1: Implement calculateTechnology orchestrator

Files:
src/calculateTechnology.ts
src/contracts/calculateRequest.ts
src/contracts/calculateResponse.ts
tests/integration/calculateTechnology.test.ts

Implementation:
- Receive TechnologyCalculationRequest.
- Find technology in registry.
- Validate parameters.
- Resolve material profiles if needed.
- Execute formulas.
- Execute rules.
- Build resource specification.
- Return response with trace.

Acceptance:
- Unknown technology returns blocked response.
- Known technology returns resources, calculatedValues, trace, warnings.
- No price fields appear.
```

### Task 6.2 — Resource Specification Builder

```text
TASK 6.2: Implement ResourceSpecificationBuilder

Files:
src/core/resourceSpecificationBuilder.ts
tests/unit/resourceSpecificationBuilder.test.ts

Implementation:
- Convert resource rules into ResourceRequirement objects.
- Attach materialSelector for Module №5.
- Attach required technical fields for Module №1.
- Attach calculationExplanation.

Acceptance:
- concrete resource has group concrete, quantity m3, selector filters.
- plaster resource has group gypsum_plaster, quantity kg, selector filters.
```

---

## Sprint 7 — Technology Registry and Moderation Statuses

Цель: сразу завести полный каркас технологий, чтобы ничего не потерялось.

### Task 7.1 — Technology Pack Registry

```text
TASK 7.1: Implement Technology Pack Registry

Files:
src/registry/technologyPack.ts
src/registry/technologyRegistry.ts
tests/unit/technologyRegistry.test.ts

Implementation:
- Add packs: foundation, earthworks, walls, roof, mansard, facade, floors, interior, bathroom, mep, landscaping, fences, demolition, waste, reference.
- Add statuses: draft, needs_mapping, testing, active, deprecated.
- Registry must support list, getByCode, filterByPack, filterByStatus.

Acceptance:
- All packs exist.
- Registry can include draft technologies without enabling calculation.
```

### Task 7.2 — Full Technology Registry shell

```text
TASK 7.2: Create full technology shell list

Goal:
Add every planned technology as a registry entry, even if algorithms are not implemented yet.

Implementation:
- Add codes for all ИЖС and apartment renovation technologies.
- Mark not-yet-implemented technologies as draft or needs_mapping.
- Implemented technologies can move to testing/active later.

Acceptance:
- Registry has no missing major sections: foundations, walls, roof, mansard, facade, floors, interior, bathroom, MEP, fences, landscaping, demolition, waste.
```

---

## Sprint 8 — Foundations Pack

Цель: реализовать ключевые алгоритмы фундаментов.

### Task 8.1 — Strip foundation algorithm

```text
TASK 8.1: Implement strip foundation algorithm

Files:
src/technologies/foundation/stripFoundation.ts
tests/golden/foundation/stripFoundation.golden.test.ts

Inputs:
building_length, building_width, internal_bearing_walls_total_length, strip_width, strip_height, concrete_waste_percent, formwork_type, longitudinal_bar_count, rebar_diameter_mm, stirrup_diameter_mm, stirrup_step_m, protective_cover_m.

Formulas:
outer_perimeter = 2 * (building_length + building_width)
total_strip_length = outer_perimeter + internal_bearing_walls_total_length
concrete_volume_raw = total_strip_length * strip_width * strip_height
concrete_volume = concrete_volume_raw * (1 + concrete_waste_percent / 100)
formwork_area = 2 * total_strip_length * strip_height
stirrups_count = ceil(total_strip_length / stirrup_step_m)

Rebar:
- longitudinal_rebar_length = total_strip_length * longitudinal_bar_count + laps + corner reinforcement.
- rebar_weight uses kg_per_meter from Module №1 profile or fallback formula diameter²/162 with warning.

Golden test:
Input: 10x8 house, internal wall 8 m, strip 0.4 x 0.8, waste 3%.
Expected:
outer_perimeter = 36 m
total_strip_length = 44 m
concrete_volume_raw = 14.08 m3
concrete_volume = 14.50 m3 rounded to 2 decimals
formwork_area = 70.4 m2

Acceptance:
- Test passes.
- Trace explains every value.
- No price fields.
```

### Task 8.2 — Slab foundation algorithm

```text
TASK 8.2: Implement slab foundation algorithm

Formulas:
slab_area = slab_length * slab_width
concrete_volume = slab_area * slab_thickness * waste_factor
sand_volume = slab_area * sand_layer_thickness * compaction_factor
gravel_volume = slab_area * gravel_layer_thickness * compaction_factor
edge_formwork_area = slab_perimeter * edge_formwork_height
rebar bars by X/Y grid:
bars_x_count = ceil(slab_width / rebar_step_y) + 1
bars_y_count = ceil(slab_length / rebar_step_x) + 1
rebar_total_length = (bars_x_count*slab_length + bars_y_count*slab_width) * mesh_layers + laps

Acceptance:
- Returns concrete, sand, gravel, formwork, rebar, spacers, waterproofing/insulation if enabled.
```

### Task 8.3 — Pile-grillage, screw piles, waterproofing, blind area

```text
TASK 8.3: Implement remaining foundation algorithms

Files:
pileGrillageFoundation.ts
screwPiles.ts
foundationWaterproofing.ts
blindArea.ts

Key formulas:
pile_volume = pi * (pile_diameter/2)^2 * pile_depth
total_pile_concrete = pile_volume * pile_count * waste_factor
grillage_concrete = grillage_length * grillage_width * grillage_height
horizontal_waterproofing_area = foundation_contact_area * overlap_factor
vertical_waterproofing_area = foundation_perimeter * waterproofing_height * layers_count * overlap_factor
blind_area = house_perimeter * blind_area_width
blind_concrete = blind_area * concrete_thickness * waste_factor

Acceptance:
- Each technology has at least 3 golden tests.
```

---

## Sprint 9 — Walls, openings, lintels, bond beams

### Task 9.1 — Gas block wall algorithm

```text
TASK 9.1: Implement gas block wall algorithm

Formulas:
wall_area_net = wall_length * wall_height - openings_area
wall_volume = wall_area_net * wall_thickness
blocks_count = wall_volume * blocks_per_m3 * waste_factor
or blocks_count = wall_area_net / block_face_area * waste_factor
glue_quantity = wall_area_net * glue_consumption_per_m2 * waste_factor
rows_count = ceil(wall_height / (block_height + joint_thickness))
reinforced_rows_count = floor(rows_count / reinforcement_every_n_rows)
wall_reinforcement_length = wall_length * reinforced_rows_count * bars_per_row + laps

Acceptance:
- Supports area-based and volume-based block calculation.
- Uses Module №1 block dimensions when selected.
```

### Task 9.2 — Brick, ceramic block, frame wall, SIP, GKL partition

```text
TASK 9.2: Implement wall variants

Algorithms:
brickWall.ts: bricks_count by bricks_per_m2_by_wall_thickness or geometry fallback.
ceramicBlockWall.ts: similar to gas block with ceramic block profile.
frameWall.ts: studs, plates, insulation, sheathing, membrane, fasteners.
sipWall.ts: panel area, panel count, joint timber, foam, screws.
gklPartition.ts: sheets, guide profile, stud profile, insulation, screws, joint tape, putty.

Acceptance:
- Each technology has resources and tests.
- Openings reduce wall area.
```

### Task 9.3 — Lintels and bond beam

```text
TASK 9.3: Implement lintels and bond beam

Formulas:
lintel_length = opening_width + bearing_left + bearing_right
lintel_concrete = lintel_length * lintel_width * lintel_height
bond_beam_length = outer_wall_perimeter + internal_bearing_walls_length
bond_beam_concrete = bond_beam_length * bond_beam_width * bond_beam_height
stirrups_count = ceil(bond_beam_length / stirrup_step)

Acceptance:
- Openings can generate lintel requirements.
- Bond beam can be called from gas block/brick house model later.
```

---

## Sprint 10 — Roof and Mansard Pack

Это критически важный спринт для ИЖС. Он должен учитывать односкатную, двускатную, вальмовую кровлю и утепление по стропилам.

### Task 10.1 — Roof geometry core

```text
TASK 10.1: Implement roofGeometry core

Files:
src/technologies/roof/roofGeometry.ts
tests/unit/roofGeometry.test.ts

Functions:
- calculateShedRoofGeometry
- calculateGableRoofGeometry
- calculateHipRoofGeometry
- calculateRoofCommonLengths

Acceptance:
- Functions return area, slope length, eave length, ridge length where applicable.
- Units are explicit.
- Invalid geometry returns blocking warning, not silent wrong result.
```

### Task 10.2 — Shed roof algorithm

```text
TASK 10.2: Implement shed/one-slope roof

Formulas:
projected_slope_width = building_width + eave_overhang_low + eave_overhang_high
roof_length = building_length + side_overhang_left + side_overhang_right
slope_length = projected_slope_width / cos(roof_angle)
roof_area = slope_length * roof_length
rafters_count = ceil(roof_length / rafter_step) + 1
rafter_length = slope_length + tail_allowance
batten_rows_count = ceil(slope_length / batten_step) + 1
batten_total_length = batten_rows_count * roof_length
counter_batten_total_length = rafters_count * slope_length

Acceptance:
- Returns roof area, rafters, battens, counter battens, membranes, gutters, edge strips.
```

### Task 10.3 — Gable roof algorithm

```text
TASK 10.3: Implement gable roof

Formulas:
half_span = building_width / 2 + eave_overhang
roof_length = building_length + 2 * gable_overhang
slope_length = half_span / cos(roof_angle)
one_slope_area = slope_length * roof_length
roof_area = one_slope_area * 2
ridge_length = roof_length
eave_length_total = roof_length * 2
gable_strip_length = slope_length * 4
rafters_count_per_slope = ceil(roof_length / rafter_step) + 1
total_rafters_count = rafters_count_per_slope * 2

Acceptance:
- Works for metal tile and soft roof downstream.
```

### Task 10.4 — Hip roof algorithm

```text
TASK 10.4: Implement hip roof

Formulas:
roof_length = building_length + 2 * eave_overhang
roof_width = building_width + 2 * eave_overhang
half_span = roof_width / 2
roof_rise = half_span * tan(roof_angle)
common_rafter_length = half_span / cos(roof_angle)
ridge_length = roof_length - roof_width
side_slope_area = ((roof_length + ridge_length) / 2) * common_rafter_length
side_slopes_area = side_slope_area * 2
hip_end_slope_area = (roof_width * common_rafter_length) / 2
hip_end_slopes_area = hip_end_slope_area * 2
roof_area = side_slopes_area + hip_end_slopes_area
hip_rafter_horizontal_projection = sqrt((roof_width/2)^2 + (roof_width/2)^2)
hip_rafter_length = sqrt(hip_rafter_horizontal_projection^2 + roof_rise^2)
hip_rafters_total_length = hip_rafter_length * 4
ridge_and_hip_caps_length = ridge_length + hip_rafters_total_length
eave_length_total = 2 * (roof_length + roof_width)

Acceptance:
- If ridge_length < 0, return blocked invalid geometry.
- Calculation trace breaks down trapezoid and triangle areas.
```

### Task 10.5 — Roofing covering algorithms: metal tile and soft roof

```text
TASK 10.5: Implement metal tile and soft roof resource rules

Metal tile:
metal_tile_area = roof_area * waste_factor
sheet mode uses effective_sheet_width and sheet_length from Module №1 if selected.
Do not store screw consumption in screw profile.
Fasteners are calculated from roof_covering_profile.fastening_pattern.

Soft roof:
osb_area = roof_area * osb_waste_factor
underlayment_area = roof_area * underlayment_overlap_factor
shingle_area = roof_area * shingle_waste_factor
nails = roof_covering_profile.fastening_pattern or technology_default
mastic = critical_zones_length * mastic_consumption_per_m

Acceptance:
- Fasteners depend on covering/fastening pattern, not screw material profile.
- Missing fastening pattern returns warning and fallback.
```

### Task 10.6 — Mansard insulation by rafters

```text
TASK 10.6: Implement mansard insulation by rafters

Formulas:
insulated_slope_area = roof_area or sum of insulated slope segments
insulation_volume = insulated_slope_area * total_insulation_thickness * waste_factor
rafter_bays_count = rafters_count - 1
bay_width = rafter_step - rafter_width
between_rafters_insulation_area = rafter_bays_count * bay_width * rafter_length * slopes_count
cross_layer_insulation_area = insulated_slope_area * cross_layer_waste_factor
vapor_barrier_area = insulated_slope_area * vapor_barrier_overlap_factor
wind_membrane_area = roof_area * wind_membrane_overlap_factor
counter_batten_total_length = rafters_count * rafter_length * slopes_count
inside_lining_area = insulated_slope_area * layers_count * waste_factor

Acceptance:
- Supports cold attic and insulated mansard modes.
- Returns insulation, vapor barrier, tape, wind membrane, counter battens, inner lining.
```

### Task 10.7 — Gutters, snow guards, soffits

```text
TASK 10.7: Implement roof accessories

Gutters:
gutter_length = eave_length_where_gutters_installed
downpipes_count = ceil(gutter_length / max_gutter_length_per_downpipe)
downpipes_length = downpipes_count * wall_height
gutter_brackets_count = ceil(gutter_length / gutter_bracket_step)

Snow guards:
snow_guard_length = rows_count * selected_eave_sides_length
snow_guard_brackets_count = ceil(snow_guard_length / bracket_step)

Soffits:
soffit_area = eave_length_total * soffit_width + gable_edges_total_length * gable_soffit_width

Acceptance:
- Works for shed, gable and hip roofs.
```

---

## Sprint 11 — Facades Pack

### Task 11.1 — Wet facade

```text
TASK 11.1: Implement wet facade

Formulas:
facade_area_net = gross_area - openings_area
insulation_area = facade_area_net * waste_factor
adhesive_for_insulation = facade_area_net * adhesive_consumption_per_m2 * waste_factor
dowels_count = facade_area_net * dowels_per_m2 + corner_zones_area * extra_dowels_per_m2
mesh_area = facade_area_net * mesh_overlap_factor
basecoat = facade_area_net * basecoat_consumption_per_m2 * waste_factor
decorative_plaster = facade_area_net * decorative_plaster_consumption_per_m2 * waste_factor
primer = facade_area_net * primer_consumption_per_m2 * layers_count
corner_profile_length = external_corners_total_length + opening_corners_total_length

Acceptance:
- Supports mineral wool and EPS insulation groups from Module №1.
```

### Task 11.2 — Siding and ventilated facade

```text
TASK 11.2: Implement siding and simplified ИЖС ventilated facade

Siding:
siding_area = facade_area_net * waste_factor
starter_profile_length = facade_perimeter
corner_profile_length = external_corners_total_length
j_profile_length = openings_perimeter_total + finishing_edges_length
battens_total_length = ceil(facade_length / batten_step) * facade_height

Vent facade:
cladding_area = facade_area_net * waste_factor
vertical_profiles_length = ceil(facade_length / profile_step) * facade_height
brackets_count = vertical_profiles_length / bracket_step
wind_membrane_area = facade_area_net * overlap_factor

Acceptance:
- Returns resource spec only, no prices.
```

---

## Sprint 12 — Floors and floor coverings

### Task 12.1 — Screed, self-leveling floor, waterproofing

```text
TASK 12.1: Implement screed and self-leveling floor

Screed:
screed_volume = floor_area * screed_thickness
if dry mix:
dry_mix_quantity = floor_area * thickness_mm * consumption_kg_m2_mm * waste_factor
if cement+sand:
mortar_volume = floor_area * screed_thickness * waste_factor
cement_quantity = mortar_volume * cement_consumption_per_m3
sand_quantity = mortar_volume * sand_consumption_per_m3
damper_tape_length = room_perimeter * waste_factor
mesh_area = floor_area * mesh_overlap_factor

Self-leveling:
self_leveling_mix = floor_area * layer_thickness_mm * consumption_kg_m2_mm * waste_factor
primer = floor_area * primer_consumption_per_m2 * layers_count
```

### Task 12.2 — Laminate, vinyl, warm floors

```text
TASK 12.2: Implement floor coverings and warm floors

Laminate:
laminate_area = floor_area * waste_factor
underlay_area = floor_area * overlap_factor
skirting_length = room_perimeter - door_openings_width_sum
threshold_length = sum(door_openings_width)

Water heated floor:
pipe_length = heated_floor_area * pipe_length_per_m2
circuits_count = ceil(pipe_length / max_circuit_length)
clips_count = pipe_length / clip_step

Electric heated floor:
heating_mat_area = heated_floor_area
thermostat_count = zones_count
floor_sensor_count = zones_count
```

---

## Sprint 13 — Interior finish Pack

### Task 13.1 — Primer, plaster, putty, paint

```text
TASK 13.1: Implement core interior finish calculations

Primer:
primer_quantity = wall_area_net * primer_consumption_per_m2 * layers_count * waste_factor
Rule: gas_block -> deep_penetration_primer, smooth_concrete -> adhesion_primer.

Plaster:
plaster_quantity = wall_area_net * layer_thickness_mm * consumption_kg_m2_mm * waste_factor
beacon_length = (ceil(wall_length / beacon_step) + 1) * wall_height
corner_bead_length = external_corners_length + opening_corners_length
mesh if layer_thickness_mm > threshold or substrate_requires_mesh.

Putty:
putty_quantity = wall_area_net * layer_thickness_mm * consumption_kg_m2_mm * layers_count * waste_factor

Paint:
paint_quantity_l = wall_area_net * coats_count / coverage_m2_per_l * waste_factor
```

### Task 13.2 — Wallpaper, tile, ceilings, openings

```text
TASK 13.2: Implement wallpaper, tile, ceilings, windows/doors/slopes

Wallpaper:
strips_count = ceil(wallpaper_perimeter / roll_width)
strip_length = room_height + trimming_allowance
if pattern_repeat: strip_length = ceil(strip_length / pattern_repeat) * pattern_repeat
rolls_count = ceil(strips_count * strip_length / roll_length)

Tile:
tile_area = surface_area * waste_factor
adhesive = surface_area * adhesive_consumption_per_m2 * waste_factor
grout = surface_area * ((tile_length + tile_width)/(tile_length * tile_width)) * joint_width * joint_depth * grout_density * waste_factor

Stretch ceiling:
ceiling_area = room_area
profile_length = room_perimeter

GKL ceiling:
gkl_area = ceiling_area * layers_count * waste_factor
main_profile_length = ceil(room_width/main_profile_step) * room_length
hangers_count = main_profile_length / hanger_step

Windows:
window_area = width * height * count
slope_area = window_perimeter * slope_depth
foam = window_perimeter * foam_consumption_per_m
```

---

## Sprint 14 — Bathroom and wet zones

```text
TASK 14.1: Implement bathroom waterproofing and tile resources

Waterproofing:
waterproofing_floor_area = floor_area * layers_count * waste_factor
wall_upstand_area = room_perimeter * upstand_height
waterproofing_area = waterproofing_floor_area + wall_upstand_area
waterproofing_tape_length = room_perimeter + wet_corners_length

Bathroom tile:
wall_tile_area = wall_area_net * waste_factor
floor_tile_area = floor_area * waste_factor
adhesive = (wall_tile_area + floor_tile_area) * adhesive_consumption_per_m2
grout uses tile grout formula
sealant_length = bath_edges + shower_edges + internal_corners + sanitary_joints

Acceptance:
- Works for bathroom and kitchen wet zones.
```

---

## Sprint 15 — MEP Pack: private house and apartment

```text
TASK 15.1: Implement simplified deterministic MEP calculations

Electrical:
cable_length = sum(route_length_by_line) * waste_factor
or points_count * average_cable_length_per_point if route mode absent
conduit_length = cable_length * conduit_usage_factor
socket_boxes_count = sockets_count + switches_count + low_voltage_points_count
breakers_count = circuits_count

Water supply:
pipe_length_hot = sum(hot_water_routes) or hot_points * average_pipe_length_per_point
pipe_length_cold = sum(cold_water_routes) or cold_points * average_pipe_length_per_point
fittings_count = pipe_length * fittings_per_meter
collector_outlets = water_points_count

Sewerage:
sewer_pipe_length = sum(sewer_routes)
bends_count = turns_count
tees_count = connected_fixtures_count

Heating:
required_power = room_area * power_per_m2
heating_pipe_length = sum(routes_to_radiators) * 2
fittings_count = radiators_count * fittings_per_radiator + route_turns

Acceptance:
- All template/fallback estimates include assumption warnings.
```

---

## Sprint 16 — Landscaping, fences, porch, terrace

```text
TASK 16.1: Implement fences

Profiled sheet fence:
net_fence_length = fence_length - gate_width - wicket_width
posts_count = ceil(net_fence_length / post_step) + 1
rails_total_length = net_fence_length * rails_rows_count
sheets_count = ceil(net_fence_length / sheet_effective_width)
concrete_per_post = pi * (hole_diameter/2)^2 * hole_depth
concrete_total = concrete_per_post * posts_count

3D mesh fence:
sections_count = ceil(net_fence_length / panel_width)
posts_count = sections_count + 1
clamps_count = posts_count * clamps_per_post
```

```text
TASK 16.2: Implement paving, concrete paths, drainage, lawn, porch

Paving:
paving_area = area * waste_factor
sand_volume = area * sand_layer_thickness * compaction_factor
gravel_volume = area * gravel_layer_thickness * compaction_factor
geotextile_area = area * overlap_factor
curb_length = edges_length

Drainage:
trench_volume = drain_length * trench_width * trench_depth
gravel_volume = drain_length * trench_width * gravel_layer_height
geotextile_area = drain_length * geotextile_wrap_width * overlap_factor
drain_pipe_length = drain_length * waste_factor

Porch:
porch_concrete = porch_area * slab_thickness
steps_concrete = sum(step_width * step_depth * step_height)
porch_tile_area = horizontal_surfaces_area + vertical_risers_area
```

---

## Sprint 17 — Demolition and waste calculation

```text
TASK 17.1: Implement demolition and waste algorithms

Tile demolition:
waste_volume = surface_area * layer_thickness * loose_factor
or waste_weight = surface_area * waste_kg_per_m2

Screed demolition:
screed_demolition_volume = floor_area * screed_thickness
waste_weight = screed_demolition_volume * material_density

Partition demolition:
wall_volume = wall_area * wall_thickness
waste_weight = wall_volume * material_density

Waste handoff:
Module №2 returns waste_volume, waste_weight, waste_type.
Module №5 decides bags/container/truck/cost.
```

---

## Sprint 18 — Admin moderation and correction interface APIs

Цель: сделать возможность модерации и корректировки без изменения кода.

### Task 18.1 — Formula and resource moderation models

```text
TASK 18.1: Implement admin moderation domain models

Files:
src/admin/moderation/*

Implementation:
- FormulaOverride
- ResourceRuleOverride
- MaterialMappingOverride
- DefaultValueOverride
- TechnologyStatusChange
- ModerationAuditLog

Each change stores:
- changedBy
- changedAt
- reason
- oldValue
- newValue
- affectedTechnology
- affectedVersion

Acceptance:
- No admin change is anonymous.
- Overrides can be applied in sandbox before publishing.
```

### Task 18.2 — Calculation Sandbox API

```text
TASK 18.2: Implement calculation sandbox

Goal:
Allow admin to test technology with sample input before publishing.

Implementation:
- sandboxCalculateTechnology(request)
- does not save as production calculation
- returns trace, warnings, resources, test comparison

Acceptance:
- Sandbox can calculate strip foundation 8x10.
- Sandbox can compare result to expected golden values.
```

### Task 18.3 — Test Case Manager API

```text
TASK 18.3: Implement technology test case manager

Implementation:
- Create/update/delete test cases.
- Test case has input, expected calculated values, expected resources.
- Run all tests for technology.
- Publishing active version requires passing tests.

Acceptance:
- A technology with failing golden test cannot move to active.
```

---

## Sprint 19 — Module №5 integration bridge

Цель: подключить результат Модуля №2 к сметам, не смешивая ответственность.

### Task 19.1 — Module5 bridge contract

```text
TASK 19.1: Implement Module5 bridge for Technology Engine

Files:
packages/module5-estimates/src/module2Bridge/*

Implementation:
- Function requestTechnologyCalculation(input)
- Receives response from Module №2.
- Converts resources to material selection requirements.
- Does not modify Module №2 output.
- Stores technology snapshot in estimate draft.

Acceptance:
- Estimate draft stores technology_code, version, input_snapshot, resource_spec_snapshot.
```

### Task 19.2 — Recalculate with selected material

```text
TASK 19.2: Implement recalculation after material selection

Flow:
1. Module №5 gets preliminary resources from Module №2.
2. Module №5 selects material from Module №1.
3. If selected material has different technical profile, Module №5 calls Module №2 again with selectedMaterials.
4. Module №2 recalculates technical quantity.
5. Module №5 updates cost lines.

Acceptance:
- Plaster preliminary 0.9 kg/m2/mm can update to selected material 1.1 kg/m2/mm.
- Difference is visible in explanation.
```

---

## Sprint 20 — Module №5 widgets that show Module №2 results

Это UI не Модуля №2, но он показывает его результат.

```text
TASK 20.1: Implement Resource Preview widget

Shows:
- resource name
- technical quantity
- unit
- calculation explanation
- assumptions
- warnings
- link to reference article

Acceptance:
- No price shown in Resource Preview.
```

```text
TASK 20.2: Implement Calculation Explanation Drawer

Shows trace:
- formulas
- inputs
- intermediate values
- final resource quantities

Acceptance:
- User can understand why primer, mesh, formwork, rebar or fasteners were added.
```

```text
TASK 20.3: Implement Material Selection Bridge widget

Shows:
- requirement from Module №2
- candidate materials from Module №1
- selected material
- technical profile difference
- trigger for recalculation

Acceptance:
- Price appears only after Material Selection Bridge enters Module №5 estimate context.
```

---

## Sprint 21 — Public technology reference/wiki

```text
TASK 21.1: Implement read-only Technology Reference structure

Goal:
Expose user-facing explanation, not editable formulas.

Content structure:
- what is this technology
- where used
- what materials are usually needed
- why system added resources
- common mistakes
- related articles

Acceptance:
- Every active technology has referenceArticleCode.
- Module №5 widgets can link to reference pages.
```

---

## Sprint 22 — Golden tests and release hardening

```text
TASK 22.1: Add golden tests for all active technologies

Requirement:
Each active technology must have at least:
- 3 normal tests
- 1 missing-data test
- 1 selected-material recalculation test if material technical profile can change quantity
- 1 trace existence test

Acceptance:
- No active technology without tests.
- No technology can be active if Material Hub mapping is missing required fields.
```

```text
TASK 22.2: Add no-AI runtime guard test

Implementation:
- Search codebase for forbidden imports or API clients in module2 package.
- Add lint rule or test preventing OpenAI/LLM clients in runtime code.

Acceptance:
- Module №2 calculation package has no LLM dependency.
```

---

# 8. Definition of Done for every technology

Технология считается готовой, только если есть:

```text
1. Код технологии.
2. Пакет.
3. Версия.
4. Статус.
5. Input parameters.
6. Validation rules.
7. Formula nodes.
8. Resource rules.
9. Waste rules.
10. Overlap/lap rules where needed.
11. Material Hub mapping.
12. Required Module №1 technical fields.
13. Fallback profiles where acceptable.
14. Warnings for all fallbacks.
15. Calculation trace.
16. At least 3–5 golden tests.
17. Reference article code.
18. Module №5 handoff compatibility.
19. No price logic.
20. No AI runtime calls.
```

---

# 9. Definition of Done for each Codex task

Каждая задача для Codex считается готовой только если:

```text
1. Файлы созданы/изменены только в указанной зоне.
2. Добавлены или обновлены тесты.
3. Тесты проходят.
4. Typecheck проходит.
5. Нет цен в Модуле №2.
6. Нет LLM/API-вызовов в runtime.
7. Ошибки и fallback не скрываются.
8. Есть trace для расчетов.
9. Изменения можно откатить отдельным commit.
```

---

# 10. Самая важная инструкция для Codex

Использовать как системный контекст при каждой задаче:

```text
You are implementing Module №2 Technology Engine.
It is a deterministic calculation engine for private house construction and apartment renovation.
It must not calculate prices.
It must not call AI/LLM APIs at runtime.
It must return technical resource quantities, warnings, assumptions, material selectors, and calculation trace.
Module №1 provides material technical profiles and prices.
Module №5 handles estimates, selected materials, packaging, prices and final costs.
Do not mix responsibilities.
Add tests for every calculation.
```

---

# 11. Why this sprint structure is Codex-friendly

Codex работает лучше, когда задача:

```text
- ограничена конкретными файлами;
- имеет понятный expected output;
- имеет тесты;
- не требует одновременно менять весь проект;
- не смешивает backend, frontend, данные и UI;
- завершается проверяемым acceptance criteria.
```

Поэтому итоговый подход такой:

```text
Не короткие продуктовые спринты.
А нормальные реализационные спринты + короткие Codex task cards.
```

---

# 12. Что делать после загрузки файла в проект

Рекомендуемый порядок:

```text
1. Положить файл в docs/.
2. Создать issue/эпики по Sprint 0–22.
3. Начать с Task 0.1.
4. После каждого task card — тесты и commit.
5. Не переходить к технологиям, пока не готовы core: Quantity, Unit Conversion, Formula Engine, Rule Engine, Material Resolver, Orchestrator.
6. Когда core готов — пачками добавлять Technology Packs.
7. Каждый Technology Pack активировать только после golden tests.
```

---

# 13. Финальная фиксация

Этот план учитывает, что реализация будет идти через Codex в VSCode.

Основная разница с обычным планом:

```text
Обычный план говорит, что нужно построить.
Codex-ready план говорит, какие файлы менять, какие тесты писать и как проверить готовность.
```

Для Модуля №2 это особенно важно, потому что ошибка в расчетном ядре опаснее, чем отсутствие красивого UI.

Главный принцип:

```text
Сначала надежное ядро и контракты.
Потом алгоритмы.
Потом модерация.
Потом UI-виджеты в Модуле №5.
Потом справочник.
```

При этом полный Technology Registry создается сразу, чтобы ничего не забыть и не потерять.
