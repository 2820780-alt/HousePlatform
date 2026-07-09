# Модуль №1 — База материалов и данных / Material Data Hub v2.0

**Проект:** строительная платформа АТОМ  
**Модуль:** Модуль №1  
**Файл:** новый Codex-ready план реализации и предзаполнения Модуля №1  
**Статус:** переписано полностью, исходный черновик можно заменить  
**Формат:** Markdown для работы в VSCode/Codex  

---

## 0. Главное решение

Модуль №1 — это самостоятельный модуль платформы. Он не является слоем поверх Модуля №2, Модуля №5 или других модулей.

Модуль №1 должен быть реализован как **Material Data Hub**: центр сбора, нормализации, классификации, модерации, хранения и качества данных по строительным материалам, документам, источникам, поставщикам, производителям, ценам и техническим характеристикам.

Модуль №1 должен сразу получить **предзаполненное ядро знаний о материалах**:

```text
категории материалов
подкатегории
характеристики по группам
правила сбора с сайтов
правила нормализации
правила единиц измерения
правила конверсии
технологические роли материалов
аналоговые и альтернативные группы
совместимость / несовместимость
required fields по группам
quality score
модерационные очереди
```

Цель: не строить ядро годами ручной модерации, а сразу создать рабочую структуру, которую модерация будет уточнять и улучшать.

---

## 1. Жесткие границы Модуля №1

### 1.1. Что делает Модуль №1

```text
1. Собирает данные из сайтов, файлов, API, прайсов, документов и ручного ввода.
2. Хранит сырые данные как evidence, но не считает их истиной.
3. Нормализует материалы, характеристики, единицы, цены, документы и источники.
4. Создает canonical materials только через pipeline и модерацию.
5. Хранит категории, подкатегории и технические профили материалов.
6. Хранит цены как наблюдения с историей, а не как одно поле в материале.
7. Хранит документы и связывает их с материалами, категориями, производителями и источниками.
8. Хранит поставщиков, производителей и участников строительной базы как directory records.
9. Хранит правила аналогов, альтернатив, совместимости и применимости.
10. Дает другим модулям только очищенные canonical/evidence data.
```

### 1.2. Что Модуль №1 не делает

```text
1. Не считает смету.
2. Не считает технологические объемы работ.
3. Не хранит формулы фундамента, кровли, отделки и других технологий.
4. Не управляет ролями и правами доступа — это Модуль №3.
5. Не делает аналитику динамики цен — это Модуль №11.
6. Не создает Material напрямую из сайта или файла.
7. Не считает сайт документом.
8. Не затирает историю цен.
9. Не смешивает материал, работу, услугу и поставщика в одну сущность.
10. Не редактирует спринты Модуля №2.
```

### 1.3. Важная формулировка

Модуль №1 может хранить данные, которые нужны Модулю №2 для расчетов: размеры, расходы, массы, плотности, полезные ширины, упаковки, совместимость, документы и технические профили.

Но это не делает Модуль №1 частью Модуля №2. Это нормальная функция Material Data Hub.

---

## 2. Целевая архитектура данных

```text
Source
  ↓
ExtractionRun
  ↓
RawIngestionItem
  ↓
Normalizer
  ↓
MatchCandidate
  ↓
ModerationDecision
  ↓
CanonicalMaterial
  ↓
MaterialTechnicalProfile
  ↓
MaterialRole / Applicability / Alternative / Compatibility
  ↓
PriceObservation / DocumentLink / SupplierOffer
  ↓
Clean Data API для других модулей
```

---

## 3. Предлагаемая структура репозитория

Codex должен адаптировать пути под существующий стек проекта, но логика файлов должна быть такой:

```text
src/modules/module1/
  domain/
    material.ts
    category.ts
    characteristicSchema.ts
    technicalProfile.ts
    materialRole.ts
    alternativeRule.ts
    compatibilityRule.ts
    source.ts
    extractionRun.ts
    rawIngestionItem.ts
    document.ts
    participant.ts
    priceObservation.ts
    moderation.ts
    quality.ts

  seeds/
    materialTaxonomy.seed.ts
    characteristicSchemas.seed.ts
    extractionBlueprints.seed.ts
    unitDictionary.seed.ts
    conversionRules.seed.ts
    synonymDictionary.seed.ts
    materialRoles.seed.ts
    alternativeRules.seed.ts
    compatibilityRules.seed.ts
    requiredFields.seed.ts
    goldenMaterials.seed.ts

  services/
    sourceAdapter.service.ts
    extractionProfile.service.ts
    rawIngestion.service.ts
    materialNormalizer.service.ts
    materialMatcher.service.ts
    canonicalMaterial.service.ts
    technicalProfile.service.ts
    priceObservation.service.ts
    document.service.ts
    moderation.service.ts
    qualityScore.service.ts
    exportPackage.service.ts

  validators/
    unit.validator.ts
    characteristic.validator.ts
    requiredFields.validator.ts
    materialProfile.validator.ts
    compatibility.validator.ts

  ui/
    pages/
      Module1OverviewPage.tsx
      DataCollectionPage.tsx
      MaterialsPage.tsx
      MaterialCardPage.tsx
      DocumentsPage.tsx
      SourcesPage.tsx
      ParticipantsPage.tsx
      PricesAndWorkRatesPage.tsx
      ModerationPage.tsx
      DataQualityPage.tsx
      ExtractionProfilesPage.tsx
    widgets/
      DataQualityWidget.tsx
      SourceRunStatusWidget.tsx
      MaterialCompletenessWidget.tsx
      MaterialRoleWidget.tsx
      AlternativeMaterialsWidget.tsx
      CompatibilityWarningsWidget.tsx
      RequiredFieldsWidget.tsx
      ExtractionWorkbenchWidget.tsx
      ModerationQueueWidget.tsx

  api/
    module1.routes.ts
    material.controller.ts
    source.controller.ts
    extraction.controller.ts
    moderation.controller.ts
    export.controller.ts

  tests/
    normalization/
    matching/
    requiredFields/
    qualityScore/
    extractionBlueprints/
    goldenMaterials/
```

---

## 4. Основные сущности Модуля №1

### 4.1. MaterialCategory

```ts
type MaterialCategory = {
  id: string;
  code: string;
  name: string;
  parentCode?: string;
  level: number;
  description?: string;
  isActive: boolean;
};
```

### 4.2. CharacteristicSchema

```ts
type CharacteristicSchema = {
  id: string;
  materialGroupCode: string;
  version: string;
  fields: CharacteristicField[];
  requiredForCanonical: string[];
  requiredForAutomaticCalculation: string[];
  optionalFields: string[];
};
```

### 4.3. CharacteristicField

```ts
type CharacteristicField = {
  key: string;
  label: string;
  valueType: 'number' | 'string' | 'enum' | 'boolean' | 'range' | 'dimension' | 'list';
  unit?: string;
  allowedUnits?: string[];
  allowedValues?: string[];
  aliases?: string[];
  normalizer?: string;
  validation?: {
    min?: number;
    max?: number;
    regex?: string;
  };
};
```

### 4.4. CanonicalMaterial

```ts
type CanonicalMaterial = {
  id: string;
  canonicalName: string;
  categoryCode: string;
  subcategoryCode?: string;
  materialGroupCode: string;
  manufacturerId?: string;
  brandId?: string;
  normalizedCharacteristics: Record<string, unknown>;
  technicalProfileId?: string;
  documentIds: string[];
  aliases: string[];
  status: 'draft' | 'moderation' | 'verified' | 'archived';
  qualityScore: number;
  createdAt: string;
  updatedAt: string;
};
```

### 4.5. MaterialTechnicalProfile

```ts
type MaterialTechnicalProfile = {
  id: string;
  canonicalMaterialId: string;
  materialGroupCode: string;
  baseUnit: string;
  alternativeUnits: string[];
  dimensions?: {
    lengthMm?: number;
    widthMm?: number;
    heightMm?: number;
    thicknessMm?: number;
  };
  physicalProperties?: Record<string, unknown>;
  consumptionProfile?: Record<string, unknown>;
  packagingProfile?: PackagingProfile;
  compatibilityTags: string[];
  usageTags: string[];
  calculationReadiness: 'ready' | 'partial' | 'blocked';
  missingForCalculation: string[];
  sourceConfidence: number;
};
```

### 4.6. MaterialRole

```ts
type MaterialRole = {
  id: string;
  materialGroupCode: string;
  roleCode: string;
  roleName: string;
  usageContexts: string[];
  requiredAttributes?: Record<string, unknown>;
  forbiddenAttributes?: Record<string, unknown>;
  priority?: number;
};
```

Пример: доска 25×150×6000 имеет canonical group `lumber_board`, но роли могут быть `formwork_board`, `roof_batten`, `temporary_structure`, `fence_auxiliary_lumber`.

### 4.7. AlternativeRule

```ts
type AlternativeRule = {
  id: string;
  sourceMaterialGroupCode: string;
  alternativeMaterialGroupCode: string;
  alternativeType: 'full_analog' | 'technical_alternative' | 'functional_alternative' | 'conditional_alternative' | 'forbidden_replacement';
  condition?: Record<string, unknown>;
  recalculationRequired: boolean;
  warningText?: string;
};
```

### 4.8. CompatibilityRule

```ts
type CompatibilityRule = {
  id: string;
  materialGroupCode: string;
  substrateOrContext: string;
  status: 'allowed' | 'warning' | 'forbidden';
  requiredAdditionalMaterialGroups?: string[];
  explanation: string;
};
```

### 4.9. Source

```ts
type Source = {
  id: string;
  name: string;
  sourceType: 'supplier_site' | 'manufacturer_site' | 'api' | 'file' | 'manual' | 'open_source';
  baseUrl?: string;
  region?: string;
  city?: string;
  participantId?: string;
  status: 'active' | 'paused' | 'error' | 'archived';
  reliabilityScore: number;
};
```

### 4.10. ExtractionProfile

```ts
type ExtractionProfile = {
  id: string;
  sourceId: string;
  profileName: string;
  allowedObjects: ('material' | 'price' | 'document' | 'availability' | 'work_rate')[];
  paginationRules?: Record<string, unknown>;
  productCardSelectors?: Record<string, string>;
  characteristicSelectors?: Record<string, string>;
  documentSelectors?: Record<string, string>;
  fieldMappingRules: Record<string, string>;
  unitMappingRules: Record<string, string>;
  categoryMappingRules: Record<string, string>;
  status: 'draft' | 'active' | 'testing' | 'archived';
};
```

### 4.11. RawIngestionItem

```ts
type RawIngestionItem = {
  id: string;
  sourceId: string;
  sourceUrl?: string;
  sourceType: string;
  rawTitle: string;
  rawDescription?: string;
  rawCategory?: string;
  rawBreadcrumbs?: string[];
  rawPrice?: string;
  rawUnit?: string;
  rawCharacteristics?: Record<string, unknown>;
  rawDocumentLinks?: string[];
  rawImages?: string[];
  rawAvailability?: string;
  rawSupplier?: string;
  rawManufacturer?: string;
  region?: string;
  city?: string;
  capturedAt: string;
  extractionProfileId?: string;
  adapterVersion: string;
  confidence: number;
};
```

### 4.12. PriceObservation

```ts
type PriceObservation = {
  id: string;
  canonicalMaterialId?: string;
  rawIngestionItemId?: string;
  supplierId?: string;
  sourceId: string;
  price: number;
  currency: string;
  unit: string;
  region?: string;
  city?: string;
  availability?: string;
  deliveryInfo?: string;
  observedAt: string;
  validFrom?: string;
  validTo?: string;
  sourceUrl?: string;
  confidence: number;
};
```

### 4.13. Document

```ts
type MaterialDocument = {
  id: string;
  title: string;
  documentType: 'certificate' | 'declaration' | 'technical_card' | 'installation_instruction' | 'passport' | 'album' | 'node' | 'manual' | 'reference';
  fileType: 'pdf' | 'docx' | 'xlsx' | 'image' | 'html' | 'other';
  sourceId?: string;
  manufacturerId?: string;
  linkedMaterialIds: string[];
  linkedCategoryCodes: string[];
  validFrom?: string;
  validTo?: string;
  parseStatus: 'not_parsed' | 'parsed' | 'ocr_needed' | 'error';
  checksum?: string;
  moderationStatus: 'raw' | 'candidate' | 'verified' | 'rejected';
};
```

---

## 5. Universal Website Extraction Blueprint

Это общий алгоритм того, что Модуль №1 должен собирать с сайтов поставщиков и производителей.

### 5.1. С карточки товара в листинге

```text
rawTitle
rawCategory
breadcrumbs
price
priceUnit
availability
imageUrl
productUrl
supplierName
region/city, если есть
rawBadges
shortCharacteristics
```

### 5.2. Со страницы товара

```text
canonical-like title from page
full description
brand
manufacturer
country of origin, если есть
category breadcrumbs
all technical characteristics
all dimensions
all package data
all units of sale
price observations
availability
related products
recommended products
analog products, если сайт показывает
certificates / declarations / datasheets / instructions links
images
SKU / article / vendor code
source URL
capture time
```

### 5.3. Из PDF/документов производителя

```text
document title
document type
manufacturer
product series
linked product names
technical tables
consumption tables
installation recommendations
compatibility notes
limitations
certification data
validity dates
```

### 5.4. Чего нельзя делать при extraction

```text
1. Нельзя создавать CanonicalMaterial напрямую.
2. Нельзя считать найденный title каноническим названием.
3. Нельзя добавлять alias без matching/moderation.
4. Нельзя перезаписывать характеристики без provenance.
5. Нельзя затирать цену: каждая цена — PriceObservation.
6. Нельзя считать документом сам сайт или страницу товара.
```

---

## 6. Полная таксономия материалов для ИЖС и квартир

### 6.1. Верхний уровень

```text
01_concrete_mortar
02_rebar_metal
03_masonry_blocks_bricks
04_lumber_wood
05_sheet_materials
06_drywall_systems
07_insulation
08_membranes_waterproofing
09_roofing
10_facade
11_dry_mixes
12_primers_paints_chemistry
13_tile_systems
14_flooring
15_wall_ceiling_finish
16_windows_doors_installation
17_fasteners_hardware
18_electrical
19_plumbing_water_supply
20_sewer_drainage
21_heating
22_ventilation
23_landscaping
24_fences_gates
25_demolition_waste
26_tools_consumables
```

---

## 7. Category Schemas: что собирать по материалам

Ниже — предзаполненные схемы характеристик. Codex должен перенести их в `characteristicSchemas.seed.ts` и `requiredFields.seed.ts`.

### 7.1. Бетон / растворы / готовые смеси

**Группы:** `ready_mix_concrete`, `lean_concrete`, `masonry_mortar`, `repair_mortar`, `dry_concrete_mix`.

| Поле | Обязательность | Ед. | Комментарий |
|---|---:|---|---|
| concrete_class | required | enum | B15/B20/B25/B30 и т.д. |
| strength_mark | optional | enum | M200/M250/M300 и т.д. |
| mobility | recommended | enum | P1/P2/P3/P4/P5 |
| frost_resistance | recommended | enum | F50/F100/F150/F200 |
| water_resistance | recommended | enum | W2/W4/W6/W8 |
| aggregate_type | optional | enum | gravel/granite/etc |
| max_aggregate_size_mm | optional | mm | для насосов/тонких элементов |
| application | required | list | foundation/slab/bond_beam/path/blind_area/fence_posts |
| base_unit | required | m3/kg | готовый бетон обычно m3, сухой бетон kg |
| min_order_m3 | optional | m3 | для смет/закупки |
| delivery_type | optional | enum | mixer/pump/bag |

**Роли:**

```text
strip_foundation_concrete
slab_foundation_concrete
pile_concrete
bond_beam_concrete
lintel_concrete
porch_concrete
concrete_path
blind_area_concrete
fence_post_concrete
```

**Критично для расчета:** `base_unit`, `concrete_class`, `application`.

---

### 7.2. Арматура, сетка, проволока

**Группы:** `rebar`, `rebar_mesh`, `masonry_mesh`, `tie_wire`, `rebar_spacer`.

| Поле | Обязательность | Ед. | Комментарий |
|---|---:|---|---|
| diameter_mm | required для rebar | mm | Ø6/8/10/12/14/16 |
| steel_class | required для rebar | enum | A240/A400/A500C etc |
| profile_type | recommended | enum | smooth/periodic |
| kg_per_meter | required для расчетов | kg/m | можно fallback: d²/162 |
| standard_bar_length_m | recommended | m | 6/11.7/12 м |
| mesh_cell_size_mm | required для mesh | mm | 50x50, 100x100 etc |
| wire_diameter_mm | required для mesh | mm | диаметр проволоки |
| sheet_width_mm | required для mesh | mm | ширина карты |
| sheet_length_mm | required для mesh | mm | длина карты |
| roll_width_m | optional | m | для рулонной сетки |
| roll_length_m | optional | m | для рулонной сетки |
| coating | optional | enum | galvanized/polymer/none |
| base_unit | required | kg/m/pcs/m2 | единица продажи |

**Роли:**

```text
foundation_longitudinal_rebar
foundation_stirrups
slab_rebar_grid
bond_beam_rebar
lintel_rebar
masonry_reinforcement
screed_mesh
plaster_mesh
facade_mesh
```

**Критично:** арматура без `diameter_mm` и `kg_per_meter` неполна для автоматического расчета.

---

### 7.3. Газоблок / газобетон

**Группы:** `aerated_concrete_block`, `gas_block`, `u_block`, `partition_block`.

| Поле | Обязательность | Ед. | Комментарий |
|---|---:|---|---|
| length_mm | required | mm | длина блока |
| width_mm | required | mm | толщина стены/блока |
| height_mm | required | mm | высота блока |
| density_class | required | enum | D300/D400/D500/D600 |
| strength_class | recommended | enum | B2.0/B2.5/B3.5 etc |
| thermal_conductivity | optional | W/mK | теплопроводность |
| frost_resistance | optional | cycles | F25/F35/F50 |
| block_volume_m3 | derived | m3 | length×width×height |
| blocks_per_m3 | derived/recommended | pcs/m3 | можно вычислять |
| pcs_per_pallet | recommended | pcs | для закупки |
| pallet_volume_m3 | recommended | m3 | для закупки |
| weight_kg | optional | kg | вес одного блока |
| usage_type | required | enum | outer_wall/inner_wall/partition/u_block |
| base_unit | required | pcs/m3/pallet | единица продажи |

**Роли:**

```text
autoclaved_aerated_concrete_wall
partition_wall_block
u_block_bond_beam_form
masonry_wall_material
```

**Критично:** без размеров блок нельзя корректно считать по м2/м3.

---

### 7.4. Кирпич / керамический блок

**Группы:** `ceramic_brick`, `silicate_brick`, `facing_brick`, `ceramic_block`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| length_mm | required | mm |
| width_mm | required | mm |
| height_mm | required | mm |
| strength_mark | recommended | enum |
| frost_resistance | recommended | enum |
| density | optional | kg/m3 |
| hollow_percent | optional | % |
| water_absorption | optional | % |
| pcs_per_m2_by_wall_thickness | recommended | pcs/m2 |
| pcs_per_m3 | recommended | pcs/m3 |
| pcs_per_pallet | recommended | pcs |
| usage_type | required | structural/facing/partition |
| base_unit | required | pcs/pallet/m3 |

**Роли:**

```text
brick_wall
facing_brick_facade
partition_masonry
chimney_masonry
```

---

### 7.5. Кладочные клеи и растворы

**Группы:** `gas_block_adhesive`, `masonry_mix`, `thin_joint_mortar`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| mix_type | required | enum |
| consumption_kg_m2 | recommended | kg/m2 |
| consumption_kg_m3 | recommended | kg/m3 |
| layer_thickness_mm | recommended | mm |
| min_temperature | optional | C |
| frost_resistant | optional | boolean |
| interior_exterior | required | enum |
| package_weight_kg | required | kg |
| compatible_blocks | recommended | list |

---

### 7.6. Пиломатериалы

**Группы:** `lumber_board`, `timber_beam`, `batten`, `lath`, `decking_board`, `formwork_panel`.

| Поле | Обязательность | Ед. | Комментарий |
|---|---:|---|---|
| thickness_mm | required | mm | например 25 |
| width_mm | required | mm | например 150 |
| length_mm | required | mm | например 6000 |
| section_label | derived | string | 25×150×6000 |
| volume_m3_per_piece | derived | m3 | t×w×l |
| wood_species | optional | enum | pine/spruce/etc |
| grade | recommended | enum | сорт |
| moisture_percent | recommended | % | для обрешетки/стропил важно |
| treatment | optional | enum | antiseptic/fireproof/none |
| planed | optional | boolean | строганая/нестроганая |
| base_unit | required | pcs/m3/lm | единица продажи |

**Роли:**

```text
formwork_board
roof_batten
counter_batten
rafter_lumber
temporary_structure
fence_lag
floor_lag
porch_lumber
```

**Пример:** доска 25×150×6000 может применяться и для опалубки, и для обрешетки, но применимость зависит от требований технологии, сечения, влажности и качества.

---

### 7.7. OSB / фанера / листовые материалы

**Группы:** `osb_board`, `plywood`, `cement_board`, `fiberboard`, `chipboard`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| length_mm | required | mm |
| width_mm | required | mm |
| thickness_mm | required | mm |
| sheet_area_m2 | derived | m2 |
| sheet_volume_m3 | derived | m3 |
| board_type | required | enum |
| moisture_resistance | recommended | enum/boolean |
| edge_type | optional | enum |
| application | required | roof_decking/floor/wall/formwork/interior |
| sheets_per_pack | optional | pcs |
| base_unit | required | sheet/m2/m3 |

**Роли:**

```text
soft_roof_solid_decking
floor_sheeting
wall_sheathing
formwork_sheet
```

---

### 7.8. ГКЛ / ГВЛ / листы для внутренних работ

**Группы:** `gkl_sheet`, `gklv_sheet`, `gklo_sheet`, `gklvo_sheet`, `gvl_sheet`, `aqua_panel`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| length_mm | required | mm |
| width_mm | required | mm |
| thickness_mm | required | mm |
| sheet_area_m2 | derived | m2 |
| sheet_weight_kg | recommended | kg |
| sheet_type | required | regular/moisture/fire/moisture_fire/gvl |
| edge_type | recommended | enum |
| application | required | walls/ceilings/partitions/wet_zones |
| sheets_per_pack | optional | pcs |
| base_unit | required | sheet/m2 |

**Роли:**

```text
drywall_partition_sheet
drywall_ceiling_sheet
interior_slope_sheet
bathroom_box_sheet
mansard_inside_lining
```

**Запрещенная замена:** обычный ГКЛ не должен автоматически заменять влагостойкий лист во влажной зоне.

---

### 7.9. Профили для ГКЛ

**Группы:** `drywall_profile_cw`, `drywall_profile_uw`, `drywall_profile_cd`, `drywall_profile_ud`, `hanger`, `connector`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| profile_type | required | enum |
| width_mm | recommended | mm |
| height_mm | recommended | mm |
| length_mm | required | mm |
| metal_thickness_mm | recommended | mm |
| application | required | partition/ceiling/wall_lining |
| base_unit | required | pcs/lm |

---

### 7.10. Утеплители

**Группы:** `mineral_wool`, `basalt_wool`, `glass_wool`, `xps`, `eps`, `pir`, `loose_insulation`.

| Поле | Обязательность | Ед. | Комментарий |
|---|---:|---|---|
| insulation_type | required | enum | mineral/xps/eps/pir/etc |
| length_mm | required для плит | mm | |
| width_mm | required для плит | mm | |
| thickness_mm | required | mm | |
| area_per_piece_m2 | derived | m2 | |
| volume_per_piece_m3 | derived | m3 | |
| area_per_pack_m2 | recommended | m2 | |
| volume_per_pack_m3 | recommended | m3 | |
| density_kg_m3 | recommended | kg/m3 | |
| thermal_conductivity | recommended | W/mK | |
| compressive_strength | required для XPS/EPS/PIR в фундаменте/полу | kPa | |
| fire_class | optional | enum | |
| application | required | facade/roof/floor/foundation/partition/mansard |
| base_unit | required | pack/m2/m3/sheet | |

**Роли:**

```text
facade_insulation
roof_insulation_between_rafters
cross_layer_insulation
floor_insulation
foundation_insulation
blind_area_insulation
partition_sound_insulation
```

---

### 7.11. Мембраны, пленки, гидроизоляция

**Группы:** `vapor_barrier`, `wind_waterproof_membrane`, `diffusion_membrane`, `roof_underlayment`, `roll_waterproofing`, `waterproofing_mastic`, `bathroom_waterproofing`, `waterproofing_tape`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| membrane_type | required | enum |
| roll_width_m | required для рулонов | m |
| roll_length_m | required для рулонов | m |
| roll_area_m2 | derived/recommended | m2 |
| density_g_m2 | recommended | g/m2 |
| vapor_permeability | optional | g/m2/24h |
| water_resistance | optional | mm water column |
| uv_resistance_days | optional | days |
| overlap_recommendation_mm | recommended | mm |
| application | required | roof/facade/floor/bathroom/foundation/mansard |
| base_unit | required | roll/m2/l/kg |

**Роли:**

```text
mansard_vapor_barrier
roof_wind_membrane
facade_wind_membrane
foundation_waterproofing
bathroom_waterproofing
floor_waterproofing
```

---

### 7.12. Кровельные покрытия

**Группы:** `metal_tile`, `profiled_sheet_roof`, `soft_shingle`, `standing_seam`, `roof_tile`.

| Поле | Обязательность | Ед. | Комментарий |
|---|---:|---|---|
| roof_covering_type | required | enum | metal_tile/soft_shingle/etc |
| profile_name | recommended | string | профиль |
| total_width_mm | recommended | mm | для листов |
| effective_width_mm | required для точного расчета листов | mm | полезная ширина |
| sheet_length_mm | optional | mm | если фиксированная длина |
| metal_thickness_mm | recommended для металла | mm | |
| coating_type | recommended | enum | polyester/pural/etc |
| wave_step_mm | recommended | mm | для металлочерепицы |
| min_slope_deg | recommended | deg | минимальный уклон |
| overlap_side_mm | recommended | mm | боковой нахлест |
| overlap_end_mm | recommended | mm | продольный нахлест |
| fastening_pattern_code | required для крепежа | string | схема крепления покрытия |
| compatible_accessories | recommended | list | конек/ендова/планки |
| base_unit | required | m2/sheet/pack | |

**Важно по кровельным саморезам:** расход крепежа не является главным свойством самореза. Он определяется `fastening_pattern_code`, кровельным покрытием, профилем, схемой крепления, нахлестами, краями, доборными элементами и шагом обрешетки.

---

### 7.13. Водосточные системы

**Группы:** `gutter`, `downpipe`, `gutter_bracket`, `downpipe_clamp`, `gutter_corner`, `gutter_connector`, `gutter_end_cap`, `funnel`, `elbow`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| system_type | required | plastic/metal |
| element_type | required | gutter/downpipe/bracket/etc |
| diameter_mm | recommended | mm |
| width_mm | recommended | mm |
| length_mm | required для желоба/трубы | mm |
| color | optional | string |
| coating | optional | enum |
| compatible_system_series | recommended | string |
| base_unit | required | pcs/lm |

---

### 7.14. Доборные элементы кровли

**Группы:** `ridge_cap`, `hip_cap`, `eave_strip`, `gable_strip`, `valley_strip`, `abutment_strip`, `snow_guard`, `soffit`, `soffit_profile`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| accessory_type | required | enum |
| length_mm | required | mm |
| useful_length_mm | recommended | mm |
| width_mm | optional | mm |
| metal_thickness_mm | optional | mm |
| coating_type | optional | enum |
| color | optional | string |
| compatible_roof_coverings | recommended | list |
| base_unit | required | pcs/lm/m2 |

---

### 7.15. Кровельный крепеж

**Группы:** `roofing_screw`, `roofing_nail`, `shingle_nail`, `roof_bracket_fastener`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| fastener_type | required | enum |
| diameter_mm | recommended | mm |
| length_mm | required | mm |
| washer_type | recommended для саморезов | enum |
| drill_point_type | recommended | wood/metal |
| coating | recommended | enum |
| color | optional | string |
| compatible_materials | recommended | list |
| base_unit | required | pcs/pack/kg |

**Запрет:** не хранить универсальный `screws_per_m2` как свойство самореза. Если сайт указывает рекомендацию расхода — сохранить как `manufacturer_recommended_usage_note`, но расчет должен использовать fastening pattern покрытия/технологии.

---

### 7.16. Фасадные материалы

**Группы:** `facade_insulation`, `facade_adhesive`, `facade_basecoat`, `facade_mesh`, `facade_dowel`, `decorative_plaster`, `facade_primer`, `corner_profile`, `starter_profile`, `siding_panel`, `vent_facade_panel`, `vent_facade_profile`, `bracket`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| material_type | required | enum |
| application | required | wet_facade/siding/vent_facade/plinth |
| consumption_kg_m2 | recommended для смесей | kg/m2 |
| panel_length_mm | required для панелей | mm |
| panel_width_mm | required для панелей | mm |
| panel_area_m2 | derived | m2 |
| thickness_mm | recommended | mm |
| density | optional | kg/m3 |
| color/texture | optional | string |
| compatible_substrates | recommended | list |
| exterior_use | required | boolean |
| base_unit | required | m2/pcs/kg/lm |

---

### 7.17. Сухие смеси

**Группы:** `gypsum_plaster`, `cement_plaster`, `putty_start`, `putty_finish`, `screed_mix`, `self_leveling_mix`, `tile_adhesive`, `masonry_mix`, `repair_mix`.

| Поле | Обязательность | Ед. | Комментарий |
|---|---:|---|---|
| mix_type | required | enum | plaster/putty/screed/tile_adhesive |
| binder_type | recommended | gypsum/cement/polymer |
| consumption_kg_m2_mm | required для слоев | kg/m2/mm | штукатурка/стяжка/наливной |
| consumption_kg_m2 | recommended | kg/m2 | клей/базовый слой |
| min_layer_mm | recommended | mm | |
| max_layer_mm | recommended | mm | |
| compatible_substrates | required | list | concrete/brick/gas_block/etc |
| interior_exterior | required | enum | interior/exterior/both |
| wet_rooms_allowed | recommended | boolean | |
| underfloor_heating_allowed | recommended | boolean | |
| frost_resistant | recommended | boolean | |
| package_weight_kg | required | kg | |
| water_per_kg | optional | l/kg | |
| pot_life_minutes | optional | min | |
| drying_time_hours | optional | h | |
| base_unit | required | kg/bag | |

---

### 7.18. Грунтовки, краски, химия

**Группы:** `deep_penetration_primer`, `adhesion_primer`, `concrete_contact`, `universal_primer`, `paint_interior`, `paint_facade`, `enamel`, `sealant`, `mounting_foam`, `adhesive_foam`, `mastic`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| product_type | required | enum |
| consumption_l_m2 | recommended | l/m2 |
| consumption_kg_m2 | optional | kg/m2 |
| coverage_m2_l | recommended для красок | m2/l |
| compatible_substrates | required | list |
| interior_exterior | required | enum |
| wet_rooms_allowed | recommended | boolean |
| drying_time_hours | optional | h |
| package_volume_l | recommended | l |
| package_weight_kg | optional | kg |
| color/base | optional | string |
| base_unit | required | l/kg/pcs |

**Правила:**

```text
gas_block + plaster -> deep_penetration_primer
smooth_concrete + plaster -> adhesion_primer/concrete_contact
bathroom + tile -> waterproofing + compatible primer
```

---

### 7.19. Плитка, клей, затирка, СВП

**Группы:** `ceramic_tile`, `porcelain_tile`, `mosaic`, `tile_adhesive`, `grout`, `tile_spacer`, `svp_system`, `sanitary_sealant`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| tile_type | required для плитки | enum |
| length_mm | required для плитки | mm |
| width_mm | required для плитки | mm |
| thickness_mm | recommended | mm |
| tile_area_m2 | derived | m2 |
| pcs_per_box | recommended | pcs |
| area_per_box_m2 | required для закупки | m2 |
| surface | optional | glossy/matte/textured |
| application | required | wall/floor/exterior/wet_zone |
| frost_resistant | recommended | boolean |
| slip_resistance | optional | enum |
| adhesive_class | recommended для клея | enum |
| grout_joint_width_mm | optional | mm |
| base_unit | required | m2/box/pcs/kg |

**Критично:** плитка без размеров может считаться по площади, но нельзя точно считать затирку.

---

### 7.20. Напольные покрытия

**Группы:** `laminate`, `engineered_board`, `parquet_board`, `quartz_vinyl`, `pvc_tile`, `linoleum`, `floor_underlay`, `skirting_board`, `threshold_profile`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| floor_covering_type | required | enum |
| length_mm | recommended | mm |
| width_mm | recommended | mm |
| thickness_mm | recommended | mm |
| area_per_pack_m2 | required | m2 |
| pcs_per_pack | optional | pcs |
| wear_class | recommended | enum |
| water_resistant | recommended | boolean |
| underfloor_heating_allowed | recommended | boolean |
| installation_type | required | click/glue/free_lay |
| base_unit | required | m2/pack/lm |

---

### 7.21. Обои и настенные покрытия

**Группы:** `wallpaper`, `glass_fiber_wallpaper`, `wallpaper_adhesive`, `decorative_panel`, `wall_panel_profile`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| roll_width_m | required для обоев | m |
| roll_length_m | required для обоев | m |
| roll_area_m2 | derived | m2 |
| pattern_repeat_m | recommended | m |
| wallpaper_type | required | paper/vinyl/nonwoven/etc |
| adhesive_type_required | recommended | enum |
| base_unit | required | roll/m2/kg |

---

### 7.22. Потолочные системы

**Группы:** `stretch_ceiling_film`, `ceiling_profile`, `ceiling_insert`, `drywall_ceiling_profile`, `ceiling_hanger`, `light_ring`, `pipe_bypass`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| material_type | required | enum |
| width_m | recommended для полотна | m |
| length_m | optional | m |
| profile_length_mm | required для профиля | mm |
| application | required | stretch_ceiling/drywall_ceiling |
| base_unit | required | m2/lm/pcs |

---

### 7.23. Окна, двери и монтажные материалы

**Группы:** `window`, `interior_door`, `exterior_door`, `window_sill`, `external_sill`, `casing`, `extension_board`, `mounting_foam`, `vapor_tape`, `waterproof_tape`, `anchor_plate`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| product_type | required | enum |
| width_mm | required для изделий | mm |
| height_mm | required для изделий | mm |
| thickness_mm/depth_mm | recommended | mm |
| material | recommended | pvc/wood/metal/mdf |
| opening_direction | optional | enum |
| fire/moisture rating | optional | enum |
| foam_yield_l | recommended для пены | l |
| tape_width_mm | recommended для лент | mm |
| roll_length_m | recommended для лент | m |
| base_unit | required | pcs/lm/roll |

---

### 7.24. Крепеж и метизы

**Группы:** `wood_screw`, `drywall_screw`, `anchor`, `dowel`, `nail`, `bolt`, `nut`, `washer`, `perforated_plate`, `joist_hanger`, `corner_bracket`, `chemical_anchor`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| fastener_type | required | enum |
| diameter_mm | recommended | mm |
| length_mm | required | mm |
| material | recommended | steel/stainless/etc |
| coating | recommended | zinc/polymer/etc |
| head_type | optional | enum |
| drive_type | optional | enum |
| compatible_materials | recommended | list |
| load_rating | optional | kN/kg |
| base_unit | required | pcs/pack/kg |

---

### 7.25. Электрика

**Группы:** `cable`, `conduit_corrugated`, `junction_box`, `socket_box`, `socket`, `switch`, `breaker`, `rcd`, `distribution_board`, `light_fixture`, `terminal_block`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| product_type | required | enum |
| cable_type | required для кабеля | enum |
| conductor_material | required для кабеля | copper/aluminum |
| cores_count | required для кабеля | pcs |
| cross_section_mm2 | required для кабеля | mm2 |
| voltage_rating | recommended | V |
| fire_rating | recommended | enum |
| conduit_diameter_mm | required для гофры | mm |
| ip_rating | recommended для изделий | enum |
| base_unit | required | m/pcs/pack |

---

### 7.26. Водоснабжение и сантехника

**Группы:** `ppr_pipe`, `pex_pipe`, `metal_plastic_pipe`, `hdpe_pipe`, `pipe_fitting`, `valve`, `manifold`, `pipe_insulation`, `water_filter`, `pump`, `water_meter`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| pipe_type | required для труб | enum |
| diameter_mm | required | mm |
| wall_thickness_mm | recommended | mm |
| pressure_rating | recommended | bar |
| temperature_rating | recommended | C |
| fitting_type | required для фитингов | enum |
| connection_type | recommended | solder/press/thread |
| length_m | required для труб | m |
| base_unit | required | m/pcs |

---

### 7.27. Канализация, дренаж, ливневка

**Группы:** `sewer_pipe`, `sewer_fitting`, `inspection_well`, `septic_tank`, `drainage_pipe`, `storm_tray`, `rainwater_inlet`, `geotextile`, `crushed_stone`, `sand`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| product_type | required | enum |
| diameter_mm | required для труб | mm |
| length_m | required для труб | m |
| stiffness_class | recommended | SN |
| fitting_angle_deg | recommended | deg |
| well_diameter_mm | optional | mm |
| septic_volume_m3 | required для септика | m3 |
| geotextile_density_g_m2 | recommended | g/m2 |
| fraction_mm | recommended для щебня/песка | mm |
| base_unit | required | m/pcs/m3/m2 |

---

### 7.28. Отопление и теплый пол

**Группы:** `radiator`, `underfloor_heating_pipe`, `manifold_heating`, `insulation_board_floor_heating`, `mounting_mat`, `clip`, `thermostat`, `boiler`, `circulation_pump`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| product_type | required | enum |
| power_w | recommended для радиатора/котла | W |
| section_count | optional для радиатора | pcs |
| pipe_diameter_mm | required для трубы | mm |
| pipe_length_m | required для бухты | m |
| max_temperature_c | recommended | C |
| pressure_rating | recommended | bar |
| compatible_system | recommended | list |
| base_unit | required | pcs/m/roll |

---

### 7.29. Вентиляция

**Группы:** `vent_duct`, `vent_fan`, `grille`, `duct_connector`, `backdraft_damper`, `flexible_duct`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| duct_shape | recommended | round/rectangular |
| diameter_mm | required for round | mm |
| width_mm | required for rectangular | mm |
| height_mm | required for rectangular | mm |
| length_m | required для duct | m |
| airflow_m3_h | recommended для вентилятора | m3/h |
| noise_db | optional | dB |
| base_unit | required | m/pcs |

---

### 7.30. Благоустройство

**Группы:** `paving_slab`, `curb_stone`, `sand`, `crushed_stone`, `gravel`, `topsoil`, `lawn_seed`, `geotextile`, `concrete_path_material`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| product_type | required | enum |
| length_mm | required для плитки/бордюра | mm |
| width_mm | required | mm |
| thickness_mm | required | mm |
| area_per_piece_m2 | derived | m2 |
| pcs_per_m2 | recommended | pcs/m2 |
| fraction_mm | required для щебня/песка | mm |
| density_kg_m3 | recommended | kg/m3 |
| base_unit | required | pcs/m2/m3/kg |

---

### 7.31. Заборы и ворота

**Группы:** `fence_profiled_sheet`, `fence_post`, `fence_rail`, `3d_fence_panel`, `euro_picket`, `gate`, `wicket`, `fence_fastener`, `post_cap`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| product_type | required | enum |
| length_mm | required | mm |
| width_mm | recommended | mm |
| height_mm | required для листов/панелей/столбов | mm |
| thickness_mm | recommended | mm |
| coating | recommended | enum |
| color | optional | string |
| effective_width_mm | recommended для профлиста | mm |
| section_width_mm | required для столбов/лаг | mm |
| base_unit | required | pcs/lm/m2 |

---

### 7.32. Демонтаж и мусор

Это не материалы в классическом смысле, но Модуль №1 может хранить справочные типы мусора, плотности и упаковочные единицы вывоза.

**Группы:** `construction_waste_bag`, `waste_container`, `demolition_waste_type`, `protective_film`, `temporary_covering`.

| Поле | Обязательность | Ед. |
|---|---:|---|
| waste_type | required | enum |
| density_kg_m3 | recommended | kg/m3 |
| bag_volume_l | recommended | l |
| container_volume_m3 | recommended | m3 |
| allowed_waste_types | recommended | list |
| base_unit | required | pcs/m3/kg |

---

## 8. Словарь синонимов

Codex должен создать `synonymDictionary.seed.ts`.

```text
gas_block = газоблок, газобетон, газобетонный блок, автоклавный газобетон, aerated concrete block
u_block = U-блок, U block, лотковый блок
rebar = арматура, арматура строительная, стержень арматурный
xps = ЭППС, XPS, экструдированный пенополистирол
mineral_wool = минвата, минераловатная плита, каменная вата, базальтовая вата
gkl = ГКЛ, гипсокартон, гипсокартонный лист
gklv = ГКЛВ, влагостойкий гипсокартон
osb = ОСБ, OSB, oriented strand board
metal_tile = металлочерепица, металлическая черепица
soft_shingle = мягкая кровля, гибкая черепица, битумная черепица
profiled_sheet = профлист, профнастил
vapor_barrier = пароизоляция, пароизоляционная пленка
wind_membrane = гидро-ветрозащита, ветрозащита, супердиффузионная мембрана
primer_deep = грунтовка глубокого проникновения
concrete_contact = бетонконтакт, адгезионная грунтовка
self_leveling_mix = наливной пол, самовыравнивающаяся смесь
ppr_pipe = ППР труба, полипропиленовая труба
pex_pipe = PEX, сшитый полиэтилен
hdpe_pipe = ПНД труба, HDPE
```

---

## 9. Словарь единиц и нормализация

Codex должен создать `unitDictionary.seed.ts`.

```text
мм -> mm
см -> cm
м -> m
пог.м -> lm
м.п. -> lm
пм -> lm
м2 -> m2
м² -> m2
кв.м -> m2
м3 -> m3
м³ -> m3
куб.м -> m3
кг -> kg
гр -> g
г -> g
т -> ton
л -> l
мл -> ml
шт -> pcs
уп -> pack
упак -> pack
рулон -> roll
лист -> sheet
мешок -> bag
поддон -> pallet
паллет -> pallet
бухта -> coil
```

---

## 10. Конверсии материалов

Codex должен создать `conversionRules.seed.ts`.

### 10.1. Арматура

```text
kg_per_meter = diameter_mm² / 162, если нет точного значения.
weight_kg = length_m × kg_per_meter.
```

Но если Модуль №1 нашел `kg_per_meter` из источника или документа, использовать его как priority source.

### 10.2. Пиломатериал

```text
volume_m3_per_piece = thickness_m × width_m × length_m
pieces_per_m3 = 1 / volume_m3_per_piece
```

### 10.3. Газоблок

```text
block_volume_m3 = length_m × width_m × height_m
blocks_per_m3 = 1 / block_volume_m3
block_face_area_m2 = length_m × height_m
blocks_per_m2 = 1 / block_face_area_m2
```

### 10.4. ГКЛ / OSB / фанера

```text
sheet_area_m2 = length_m × width_m
sheet_volume_m3 = length_m × width_m × thickness_m
```

### 10.5. Утеплитель

```text
piece_area_m2 = length_m × width_m
piece_volume_m3 = length_m × width_m × thickness_m
pack_area_m2 = piece_area_m2 × pieces_per_pack
pack_volume_m3 = piece_volume_m3 × pieces_per_pack
```

### 10.6. Мембрана / обои

```text
roll_area_m2 = roll_width_m × roll_length_m
```

### 10.7. Плитка

```text
tile_area_m2 = length_m × width_m
box_area_m2 = tile_area_m2 × pcs_per_box
```

### 10.8. Краска

```text
quantity_l = area_m2 / coverage_m2_l × coats_count
```

Если есть `consumption_l_m2`, использовать:

```text
quantity_l = area_m2 × consumption_l_m2 × coats_count
```

---

## 11. Material Roles: один материал — много применений

Codex должен создать `materialRoles.seed.ts`.

### 11.1. Доска

```text
lumber_board:
  - formwork_board
  - roof_batten
  - counter_batten
  - fence_rail
  - temporary_structure
  - floor_lag_auxiliary
```

### 11.2. Бетон

```text
ready_mix_concrete:
  - strip_foundation_concrete
  - slab_foundation_concrete
  - pile_concrete
  - bond_beam_concrete
  - lintel_concrete
  - porch_concrete
  - concrete_path
  - blind_area_concrete
  - fence_post_concrete
```

### 11.3. XPS

```text
xps:
  - foundation_insulation
  - blind_area_insulation
  - floor_insulation
  - plinth_insulation
  - flat_roof_insulation, если применимо
```

### 11.4. Минвата

```text
mineral_wool:
  - facade_insulation
  - mansard_roof_insulation
  - partition_sound_insulation
  - floor_between_joists_insulation
  - attic_floor_insulation
```

### 11.5. OSB

```text
osb_board:
  - soft_roof_solid_decking
  - frame_wall_sheathing
  - floor_sheeting
  - temporary_decking
```

### 11.6. ГКЛ

```text
gkl_sheet:
  - drywall_partition
  - drywall_ceiling
  - wall_lining
  - window_slope
  - mansard_inside_lining
```

### 11.7. Грунтовка

```text
deep_penetration_primer:
  - gas_block_before_plaster
  - brick_before_plaster
  - porous_substrate_before_putty
  - floor_before_self_leveling

adhesion_primer/concrete_contact:
  - smooth_concrete_before_plaster
  - dense_substrate_before_tile_or_plaster
```

---

## 12. Аналоги и альтернативы

Codex должен создать `alternativeRules.seed.ts`.

### 12.1. Типы замен

```text
full_analog              Материал почти равнозначен при совпадении ключевых характеристик.
technical_alternative    Можно заменить, но изменится расход или расчет.
functional_alternative   Выполняет ту же функцию, но меняется технология.
conditional_alternative  Можно заменить только при условиях.
forbidden_replacement    Нельзя заменять автоматически.
```

### 12.2. Примеры full analog

```text
ГКЛ 12.5 мм обычный одного производителя ↔ ГКЛ 12.5 мм обычный другого производителя.
Арматура A500C Ø12 одного производителя ↔ арматура A500C Ø12 другого производителя.
Газоблок D500 600×300×200 ↔ газоблок D500 600×300×200 другого производителя, если совпадают прочность и назначение.
```

### 12.3. Примеры technical alternative

```text
Гипсовая штукатурка с расходом 0.9 кг/м2/мм ↔ гипсовая штукатурка с расходом 1.1 кг/м2/мм.
Плиточный клей одного класса ↔ плиточный клей другого класса с другим расходом.
Минвата 50 мм в два слоя ↔ минвата 100 мм в один слой, если технология допускает.
```

### 12.4. Примеры functional alternative

```text
ЦПС стяжка ↔ сухая стяжка ↔ наливной пол.
Мокрый фасад ↔ сайдинг ↔ вентфасад.
ГКЛ-перегородка ↔ блоковая перегородка.
Металлочерепица ↔ мягкая кровля — это не замена материала, а замена кровельной технологии.
```

### 12.5. Примеры conditional alternative

```text
EPS вместо XPS — не для всех зон, запрещать или предупреждать в фундаменте/отмостке, если нет нужной прочности и влагостойкости.
ГКЛВ вместо ГКЛ — можно во влажных помещениях.
ГКЛ вместо ГКЛВ — нельзя во влажных помещениях.
Внутренний плиточный клей на фасаде — forbidden.
```

---

## 13. Compatibility Matrix

Codex должен создать `compatibilityRules.seed.ts`.

| Контекст | Материал | Статус | Дополнительное правило |
|---|---|---:|---|
| gas_block_before_plaster | deep_penetration_primer | allowed | рекомендуется 1–2 слоя |
| smooth_concrete_before_plaster | concrete_contact / adhesion_primer | allowed | обычная грунтовка — warning/forbidden |
| bathroom_tile | waterproofing | required | пол + заход на стены |
| warm_floor_tile | tile_adhesive_underfloor_allowed | required | клей должен поддерживать теплый пол |
| exterior_tile | exterior_tile_adhesive | required | морозостойкость обязательна |
| soft_roof | osb_or_plywood_decking | required | нужна сплошная основа |
| metal_tile | batten_by_profile_step | required | шаг обрешетки задает покрытие |
| mansard_roof | vapor_barrier_inside | required | изнутри обязательна пароизоляция |
| mansard_roof | wind_membrane_outside | required | снаружи мембрана/гидро-ветрозащита |
| ordinary_gkl_in_wet_zone | gkl_sheet | forbidden | использовать влагостойкий лист |
| xps_foundation | xps | allowed | нужна прочность на сжатие |
| eps_foundation | eps | warning/forbidden | зависит от характеристик |
| facade_insulation | facade_dowel | required | для мокрого фасада |
| laminate_floor | floor_underlay | required | кроме систем со встроенной подложкой |
| wallpaper | wallpaper_adhesive | required | тип клея зависит от обоев |
| window_installation | mounting_foam + tapes | recommended|required | зависит от монтажного стандарта |

---

## 14. Required Fields Validator

Codex должен создать `requiredFields.validator.ts`.

### 14.1. Примеры блокирующих условий

```text
Газоблок без length/width/height -> blocked_for_calculation.
Арматура без diameter -> blocked_for_calculation.
Арматура без kg_per_meter -> partial, fallback возможен.
Доска без thickness/width/length -> blocked_for_conversion_to_m3.
OSB без sheet size -> blocked_for_sheet_count.
ГКЛ без sheet size/thickness/type -> partial/blocked.
Штукатурка без consumption_kg_m2_mm -> blocked_for_precise_calculation.
Плитка без length/width -> partial, нельзя точно считать затирку.
Металлочерепица без effective_width -> partial, нельзя точно считать листы.
Кровельное покрытие без fastening_pattern_code -> partial, нельзя точно считать крепеж.
Мембрана без roll_width/roll_length -> partial, нельзя округлять рулоны.
Краска без coverage или consumption -> blocked_for_calculation.
Пиломатериал без сечения -> blocked_for_volume_conversion.
```

---

## 15. Quality Score

Codex должен создать `qualityScore.service.ts`.

### 15.1. Баллы

```text
+10 есть categoryCode
+10 есть subcategory/materialGroup
+15 есть required characteristics
+10 есть normalized units
+10 есть technical profile
+10 есть packaging profile, если применимо
+10 есть price observations
+10 есть documents/evidence
+10 есть manufacturer/brand
+5 есть source provenance
+5 есть moderation verified
```

### 15.2. Статусы

```text
90–100 verified_ready
70–89 usable_with_warnings
50–69 partial
30–49 moderation_required
0–29 raw_or_blocked
```

---

## 16. Matching и Dedup Logic

### 16.1. Сигналы совпадения

```text
normalized title
manufacturer
brand
article/SKU
category
material group
key dimensions
technical class
package size
source aliases
document links
image similarity, если есть
```

### 16.2. Пример ключей matching

```text
Газоблок:
manufacturer + density_class + length + width + height + strength_class

Арматура:
steel_class + diameter + profile_type

ГКЛ:
manufacturer + sheet_type + length + width + thickness + edge_type

Штукатурка:
manufacturer + product_line + mix_type + package_weight

Плитка:
brand + collection + length + width + color/article
```

### 16.3. Confidence

```text
>= 0.92 auto-match candidate, но canonical update через модерационные правила.
0.75–0.91 moderation queue.
< 0.75 likely new candidate or unresolved.
```

---

## 17. Документы

### 17.1. Типы документов

```text
certificate
declaration
technical_card
installation_instruction
passport
catalog
album_solution
node_detail
warranty
safety_data_sheet
reference_article
```

### 17.2. Связи документов

```text
document -> material
document -> material group
document -> manufacturer
document -> category
document -> source
document -> evidence record
```

### 17.3. Обязательные правила

```text
1. Один документ может относиться к нескольким материалам.
2. Документ не дублируется для каждого материала.
3. Срок действия хранится отдельно.
4. PDF без текстового слоя помечается ocr_needed.
5. Документ может повышать confidence характеристики.
```

---

## 18. Участники строительной базы

Модуль №1 хранит не аккаунты, а строительные directory records.

```text
supplier
manufacturer
distributor
contractor
service_provider
```

Права и доступы — Модуль №3. В Модуле №1 только данные участника.

---

## 19. Цены и работы

### 19.1. PriceObservation

Цена материала — всегда наблюдение.

```text
materialId / candidateId
supplierId
sourceId
price
currency
unit
region
city
availability
observedAt
sourceUrl
confidence
```

### 19.2. WorkRateObservation

Расценка работы хранится отдельно от материала.

```text
workType
unit
price
region
source
contractor
observedAt
confidence
linkedTechnologyHint
moderationStatus
```

---

## 20. UI Модуля №1

### 20.1. Вкладки

```text
1. Обзор
2. Сбор данных
3. Материалы
4. Категории и схемы
5. Документы
6. Источники
7. Участники
8. Цены и работы
9. Аналоги и применимость
10. Модерация
11. Качество данных
12. Профили извлечения
13. Настройки справочников
```

### 20.2. Виджеты

```text
Data Quality Summary
Material Completeness
Missing Required Fields
Source Run Status
Extraction Workbench
Moderation Queue
Duplicate Candidates
Alternative Materials
Compatibility Warnings
Price Observation History
Document Evidence Widget
Technical Profile Readiness
```

---

## 21. Export Packages из Модуля №1

Это не слой над другими модулями. Это нормальные выходные пакеты Модуля №1.

### 21.1. CleanMaterialPackage

```ts
type CleanMaterialPackage = {
  canonicalMaterialId: string;
  canonicalName: string;
  categoryCode: string;
  materialGroupCode: string;
  normalizedCharacteristics: Record<string, unknown>;
  technicalProfile?: MaterialTechnicalProfile;
  documents: MaterialDocument[];
  qualityScore: number;
  moderationStatus: string;
  provenance: Record<string, unknown>;
};
```

### 21.2. MaterialSelectorPackage

```ts
type MaterialSelectorPackage = {
  materialGroupCode: string;
  requiredAttributes?: Record<string, unknown>;
  compatibleContext?: string;
  region?: string;
  includePrices?: boolean;
  includeDocuments?: boolean;
  candidates: CleanMaterialPackage[];
};
```

### 21.3. TechnicalProfilePackage

```ts
type TechnicalProfilePackage = {
  materialGroupCode: string;
  requiredFields: string[];
  genericProfile?: Record<string, unknown>;
  matchedProfiles: MaterialTechnicalProfile[];
  missingDataWarnings: string[];
};
```

---

# 22. Codex-ready Sprints для реализации Модуля №1

Правило для Codex: не брать весь модуль одним заданием. Выполнять спринт, затем task card, затем тесты, затем отчет.

---

## Sprint M1-0 — Audit and Lock Scope

**Цель:** проверить текущий Module №1, если он есть, и зафиксировать, что файл переписывает старый черновик.

**Codex tasks:**

```text
TASK M1-0.1: Найти текущие файлы Module 1.
TASK M1-0.2: Составить отчет: что есть, что удалить, что сохранить.
TASK M1-0.3: Проверить, что изменения не затрагивают Module 2.
```

**Acceptance:**

```text
- есть audit report;
- найдены текущие routes/models/services/pages;
- нет изменений в module2;
- зафиксированы legacy risks.
```

---

## Sprint M1-1 — Domain Skeleton

**Цель:** создать каркас доменных сущностей Модуля №1.

**Files:**

```text
src/modules/module1/domain/*.ts
src/modules/module1/services/*.ts
src/modules/module1/seeds/*.ts
```

**Tasks:**

```text
TASK M1-1.1: Create domain folder and base types.
TASK M1-1.2: Create MaterialCategory, CharacteristicSchema, CanonicalMaterial.
TASK M1-1.3: Create Source, RawIngestionItem, PriceObservation, Document.
TASK M1-1.4: Create MaterialRole, AlternativeRule, CompatibilityRule.
```

**Acceptance:**

```text
- types compile;
- no UI yet;
- no cross-module imports except allowed shared primitives;
- tests for basic type guards if project supports them.
```

---

## Sprint M1-2 — Seed Material Taxonomy

**Цель:** предзаполнить полную таксономию материалов.

**Files:**

```text
src/modules/module1/seeds/materialTaxonomy.seed.ts
src/modules/module1/tests/taxonomy/materialTaxonomy.test.ts
```

**Tasks:**

```text
TASK M1-2.1: Add top-level categories 01–26.
TASK M1-2.2: Add subcategories for IЖС and apartment renovation.
TASK M1-2.3: Add parent-child validation.
TASK M1-2.4: Add no-duplicate category code test.
```

**Acceptance:**

```text
- all material groups from this file exist;
- category codes are stable;
- no duplicate codes;
- taxonomy can be loaded from seed.
```

---

## Sprint M1-3 — Characteristic Schema Registry

**Цель:** реализовать схемы характеристик по группам материалов.

**Files:**

```text
src/modules/module1/seeds/characteristicSchemas.seed.ts
src/modules/module1/services/characteristicSchema.service.ts
src/modules/module1/validators/characteristic.validator.ts
```

**Tasks:**

```text
TASK M1-3.1: Add schema registry service.
TASK M1-3.2: Add schemas for concrete/rebar/gas block/lumber/sheet materials.
TASK M1-3.3: Add schemas for roofing/facade/dry mixes/finishes.
TASK M1-3.4: Add schemas for engineering/landscaping/fences.
TASK M1-3.5: Add validation tests for required fields.
```

**Acceptance:**

```text
- schema lookup by materialGroupCode works;
- validator flags missing required fields;
- characteristic fields have units and aliases;
- tests cover at least 20 material groups.
```

---

## Sprint M1-4 — Unit Dictionary and Conversion Rules

**Цель:** нормализация единиц и базовые конверсии.

**Files:**

```text
src/modules/module1/seeds/unitDictionary.seed.ts
src/modules/module1/seeds/conversionRules.seed.ts
src/modules/module1/services/unitNormalization.service.ts
src/modules/module1/services/conversion.service.ts
```

**Tasks:**

```text
TASK M1-4.1: Implement unit dictionary.
TASK M1-4.2: Implement dimension parser for 25×150×6000, 600x300x200, etc.
TASK M1-4.3: Implement rebar kg/m fallback d²/162.
TASK M1-4.4: Implement board volume, block volume, sheet area, roll area, tile area.
TASK M1-4.5: Add golden tests.
```

**Acceptance:**

```text
- parses common Russian unit formats;
- calculates board m3 per piece;
- calculates gas block pcs/m3;
- calculates sheet/roll/tile area;
- no price logic here.
```

---

## Sprint M1-5 — Extraction Blueprints

**Цель:** описать, что собирать с сайтов по группам материалов.

**Files:**

```text
src/modules/module1/seeds/extractionBlueprints.seed.ts
src/modules/module1/services/extractionBlueprint.service.ts
```

**Tasks:**

```text
TASK M1-5.1: Add universal listing/page/document blueprint.
TASK M1-5.2: Add material-group-specific target fields.
TASK M1-5.3: Add validation: blueprint required fields must exist in CharacteristicSchema.
TASK M1-5.4: Add tests for gas block, GKL, roofing, dry mixes, electrical.
```

**Acceptance:**

```text
- every materialGroup has extraction blueprint;
- required extraction fields map to schema fields;
- Codex must not hardcode site-specific selectors here.
```

---

## Sprint M1-6 — Source and Extraction Profile

**Цель:** сделать источник и профиль извлечения.

**Files:**

```text
src/modules/module1/domain/source.ts
src/modules/module1/services/extractionProfile.service.ts
src/modules/module1/ui/pages/SourcesPage.tsx
src/modules/module1/ui/pages/ExtractionProfilesPage.tsx
```

**Tasks:**

```text
TASK M1-6.1: Implement Source CRUD service.
TASK M1-6.2: Implement ExtractionProfile CRUD service.
TASK M1-6.3: Add UI list for sources.
TASK M1-6.4: Add UI profile editor for selectors/mapping rules.
```

**Acceptance:**

```text
- source can be active/paused/error/archived;
- profile does not create canonical materials;
- UI shows profile status and last run.
```

---

## Sprint M1-7 — Raw Ingestion Pipeline

**Цель:** адаптеры возвращают RawIngestionItem, а не canonical data.

**Files:**

```text
src/modules/module1/services/sourceAdapter.service.ts
src/modules/module1/services/rawIngestion.service.ts
src/modules/module1/domain/rawIngestionItem.ts
```

**Tasks:**

```text
TASK M1-7.1: Define SourceAdapter interface.
TASK M1-7.2: Implement raw ingestion storage.
TASK M1-7.3: Add preview mode.
TASK M1-7.4: Add tests ensuring adapters cannot create CanonicalMaterial.
```

**Acceptance:**

```text
- adapters return raw only;
- no canonical material created from extraction;
- raw data includes provenance.
```

---

## Sprint M1-8 — Material Normalizer

**Цель:** единый нормализатор материалов.

**Files:**

```text
src/modules/module1/services/materialNormalizer.service.ts
src/modules/module1/tests/normalization/*.test.ts
```

**Tasks:**

```text
TASK M1-8.1: Normalize title.
TASK M1-8.2: Extract dimensions.
TASK M1-8.3: Extract manufacturer/brand/article if present.
TASK M1-8.4: Classify category/material group.
TASK M1-8.5: Normalize units and characteristics.
TASK M1-8.6: Return NormalizedMaterialCandidate.
```

**Acceptance:**

```text
- one normalizer, not per-site normalizers;
- confidence score returned;
- raw source remains linked;
- tests cover common Russian titles.
```

---

## Sprint M1-9 — Matching and Dedup

**Цель:** предотвратить дубли материалов.

**Files:**

```text
src/modules/module1/services/materialMatcher.service.ts
src/modules/module1/domain/moderation.ts
src/modules/module1/tests/matching/*.test.ts
```

**Tasks:**

```text
TASK M1-9.1: Implement match keys per material group.
TASK M1-9.2: Implement confidence scoring.
TASK M1-9.3: Create MaterialMatchCandidate.
TASK M1-9.4: Add duplicate candidate queue.
```

**Acceptance:**

```text
- no low-confidence auto merge;
- alias is not added without decision;
- same gas block from two sources becomes match candidate.
```

---

## Sprint M1-10 — Moderation Core

**Цель:** рабочие очереди модерации.

**Files:**

```text
src/modules/module1/services/moderation.service.ts
src/modules/module1/ui/pages/ModerationPage.tsx
src/modules/module1/ui/widgets/ModerationQueueWidget.tsx
```

**Tasks:**

```text
TASK M1-10.1: Add moderation candidate model.
TASK M1-10.2: Add decision types: approve/reject/merge/create/edit/archive.
TASK M1-10.3: Add saved rule for similar cases.
TASK M1-10.4: Add UI queues.
```

**Acceptance:**

```text
- moderator decision is auditable;
- canonical material only via decision or verified rule;
- queue filters by type and confidence.
```

---

## Sprint M1-11 — Canonical Material Store and UI

**Цель:** создать полноценные материалы и карточку материала.

**Files:**

```text
src/modules/module1/services/canonicalMaterial.service.ts
src/modules/module1/ui/pages/MaterialsPage.tsx
src/modules/module1/ui/pages/MaterialCardPage.tsx
```

**Tasks:**

```text
TASK M1-11.1: Implement CanonicalMaterial store.
TASK M1-11.2: Add material list filters.
TASK M1-11.3: Add material card with characteristics, prices, docs, roles, alternatives.
TASK M1-11.4: Hide technical payload in collapsed panel.
```

**Acceptance:**

```text
- material has canonical name/category/group;
- characteristics normalized;
- source evidence visible;
- raw IDs not shown in main UI.
```

---

## Sprint M1-12 — Technical Profiles and Packaging

**Цель:** сделать technicalProfile для расчетов, закупок и качества данных.

**Files:**

```text
src/modules/module1/services/technicalProfile.service.ts
src/modules/module1/ui/widgets/MaterialCompletenessWidget.tsx
src/modules/module1/ui/widgets/RequiredFieldsWidget.tsx
```

**Tasks:**

```text
TASK M1-12.1: Build technical profile from normalized characteristics.
TASK M1-12.2: Add packaging profile.
TASK M1-12.3: Add calculationReadiness.
TASK M1-12.4: Add missingForCalculation.
```

**Acceptance:**

```text
- gas block has dimensions and derived block volume;
- rebar has kg/m or fallback flag;
- board has m3 per piece;
- dry mix has consumption profile if available.
```

---

## Sprint M1-13 — Material Roles

**Цель:** добавить роли применения материалов.

**Files:**

```text
src/modules/module1/seeds/materialRoles.seed.ts
src/modules/module1/services/materialRole.service.ts
src/modules/module1/ui/widgets/MaterialRoleWidget.tsx
```

**Tasks:**

```text
TASK M1-13.1: Seed roles for concrete, board, XPS, mineral wool, OSB, GKL, primer.
TASK M1-13.2: Add role lookup by materialGroup.
TASK M1-13.3: Add role constraints.
TASK M1-13.4: Show roles in material card.
```

**Acceptance:**

```text
- one material can have many roles;
- role is not same as category;
- board 25×150×6000 can be formwork and batten candidate.
```

---

## Sprint M1-14 — Alternatives and Analogs

**Цель:** запустить analog/alternative engine.

**Files:**

```text
src/modules/module1/seeds/alternativeRules.seed.ts
src/modules/module1/services/alternative.service.ts
src/modules/module1/ui/widgets/AlternativeMaterialsWidget.tsx
```

**Tasks:**

```text
TASK M1-14.1: Implement alternative types.
TASK M1-14.2: Seed full analog examples.
TASK M1-14.3: Seed technical alternatives.
TASK M1-14.4: Seed functional and conditional alternatives.
TASK M1-14.5: Add forbidden replacement logic.
```

**Acceptance:**

```text
- full analog only if key fields match;
- technical alternative marks recalculationRequired;
- functional alternative marks technologyChangeRequired;
- forbidden replacement returns warning/error.
```

---

## Sprint M1-15 — Compatibility Matrix

**Цель:** добавить совместимость материалов и контекстов.

**Files:**

```text
src/modules/module1/seeds/compatibilityRules.seed.ts
src/modules/module1/services/compatibility.service.ts
src/modules/module1/ui/widgets/CompatibilityWarningsWidget.tsx
```

**Tasks:**

```text
TASK M1-15.1: Add compatibility rule engine.
TASK M1-15.2: Seed wet zones, facades, roofs, mansards, substrates.
TASK M1-15.3: Add required additional material groups.
TASK M1-15.4: Add tests for forbidden/warning/allowed.
```

**Acceptance:**

```text
- ordinary GKL in wet zone forbidden;
- gas block before plaster requires primer;
- soft roof requires solid decking;
- roof covering without fastening pattern is partial.
```

---

## Sprint M1-16 — Documents

**Цель:** хранить и связывать документы.

**Files:**

```text
src/modules/module1/services/document.service.ts
src/modules/module1/ui/pages/DocumentsPage.tsx
```

**Tasks:**

```text
TASK M1-16.1: Create document store.
TASK M1-16.2: Link documents to materials/categories/manufacturers.
TASK M1-16.3: Add parseStatus and OCR-needed flag.
TASK M1-16.4: Add document evidence widget.
```

**Acceptance:**

```text
- document is not source website;
- one document can link to many materials;
- validity dates supported;
- checksum supported.
```

---

## Sprint M1-17 — Participants Directory

**Цель:** поставщики, производители, подрядчики как data records, не аккаунты.

**Files:**

```text
src/modules/module1/domain/participant.ts
src/modules/module1/services/participant.service.ts
src/modules/module1/ui/pages/ParticipantsPage.tsx
```

**Acceptance:**

```text
- participant has type and region;
- source can link to participant;
- no role/permission logic in Module 1.
```

---

## Sprint M1-18 — Price and Work Rate Observations

**Цель:** хранить цены и работы как наблюдения с историей.

**Files:**

```text
src/modules/module1/services/priceObservation.service.ts
src/modules/module1/services/workRateObservation.service.ts
src/modules/module1/ui/pages/PricesAndWorkRatesPage.tsx
```

**Acceptance:**

```text
- material price != work rate;
- price history not overwritten;
- region/city/source/observedAt stored;
- can show latest price but keep observations.
```

---

## Sprint M1-19 — Data Quality Dashboard

**Цель:** контроль качества данных без аналитического dashboard.

**Files:**

```text
src/modules/module1/services/qualityScore.service.ts
src/modules/module1/ui/pages/DataQualityPage.tsx
src/modules/module1/ui/widgets/DataQualityWidget.tsx
```

**Acceptance:**

```text
- shows missing required fields;
- shows incomplete technical profiles;
- shows sources with errors;
- shows documents without links;
- no large price analytics charts.
```

---

## Sprint M1-20 — Extraction Workbench

**Цель:** лабораторный стенд источника.

**Files:**

```text
src/modules/module1/ui/widgets/ExtractionWorkbenchWidget.tsx
src/modules/module1/services/rawIngestion.service.ts
```

**Acceptance:**

```text
- shows raw extraction;
- shows recognized fields;
- shows unknown fields;
- can send to normalizer;
- cannot directly create canonical material.
```

---

## Sprint M1-21 — Export Packages

**Цель:** CleanMaterialPackage, MaterialSelectorPackage, TechnicalProfilePackage.

**Files:**

```text
src/modules/module1/services/exportPackage.service.ts
src/modules/module1/api/export.controller.ts
```

**Acceptance:**

```text
- exports only canonical/evidence data;
- raw data not exported as truth;
- package can include technical profile and documents;
- no module2 formulas here.
```

---

## Sprint M1-22 — Seed Golden Materials

**Цель:** создать эталонные материалы для тестов и первого наполнения.

**Files:**

```text
src/modules/module1/seeds/goldenMaterials.seed.ts
src/modules/module1/tests/goldenMaterials/*.test.ts
```

**Golden examples:**

```text
Газоблок D500 600×300×200
Арматура A500C Ø12
Доска 25×150×6000
OSB-3 2500×1250×12
ГКЛВ 2500×1200×12.5
Минвата 100 мм фасадная
XPS 50 мм
Грунтовка глубокого проникновения 10 л
Гипсовая штукатурка 30 кг
Плиточный клей для теплого пола 25 кг
Металлочерепица с effective_width и fastening_pattern
Гибкая черепица с pack coverage
Пароизоляция рулон 1.5×50
Мембрана кровельная 1.5×50
Ламинат 33 класс с area_per_pack
Плитка 600×600 с area_per_box
Кабель ВВГнг-LS 3×2.5
ППР труба Ø20
Канализационная труба Ø110×2000
Профлист для забора
Тротуарная плитка
```

**Acceptance:**

```text
- all golden materials normalize;
- technical profile generated;
- required fields pass or produce expected warnings;
- role mapping works;
- alternatives and compatibility work.
```

---

## Sprint M1-23 — UI Integration

**Цель:** собрать интерфейс Module 1.

**Pages:**

```text
Overview
Data Collection
Materials
Material Card
Categories and Schemas
Documents
Sources
Participants
Prices and Work Rates
Analogs and Applicability
Moderation
Data Quality
Extraction Profiles
Settings
```

**Acceptance:**

```text
- user sees laboratory data hub, not analytics dashboard;
- technical payload hidden in advanced sections;
- no Module 3 role editor;
- no Module 2 technology editor;
- no Module 5 estimate logic.
```

---

## Sprint M1-24 — Final QA

**Цель:** проверить полный путь данных.

**Scenario:**

```text
1. Add source.
2. Add extraction profile.
3. Run preview.
4. Store RawIngestionItem.
5. Normalize material.
6. Create MatchCandidate.
7. Moderate candidate.
8. Create/Update CanonicalMaterial.
9. Generate TechnicalProfile.
10. Link documents.
11. Add PriceObservation.
12. Validate required fields.
13. Calculate QualityScore.
14. Export CleanMaterialPackage.
```

**Forbidden failures:**

```text
- adapter created material directly;
- source treated as document;
- price overwritten instead of observation;
- alias created without decision;
- ordinary GKL allowed in wet zone without warning;
- roof screws counted by screw property instead of roof fastening pattern;
- Module 2 files changed.
```

---

# 23. Codex Prompt Template

```text
Работаем только над Module №1 — Material Data Hub.

Это самостоятельный модуль предзаполненной базы строительных материалов и данных.
Он собирает, хранит, нормализует, классифицирует, модерирует и экспортирует очищенные canonical/evidence data.

Не трогай Module №2 и его спринты.
Не добавляй формулы технологий Module №2.
Не добавляй сметную логику Module №5.
Не добавляй роли и права Module №3.

В этом задании реализуй только указанную task card.
После выполнения дай отчет:
1. измененные файлы;
2. что добавлено;
3. какие тесты добавлены;
4. какие команды запускались;
5. какие риски остались;
6. что осталось TODO.
```

---

# 24. Definition of Done для Модуля №1

Модуль №1 готов, если:

```text
1. Есть полная таксономия материалов для ИЖС и квартир.
2. Есть CharacteristicSchema по всем основным группам.
3. Есть ExtractionBlueprint по всем основным группам.
4. Есть единицы, синонимы и конверсии.
5. Есть RawIngestion pipeline.
6. Есть единый MaterialNormalizer.
7. Есть Matching/Dedup.
8. Есть Moderation.
9. Есть CanonicalMaterial store.
10. Есть MaterialTechnicalProfile.
11. Есть roles/applicability для материалов.
12. Есть analog/alternative engine.
13. Есть compatibility matrix.
14. Есть documents/evidence.
15. Есть price observations и work rate observations.
16. Есть quality score.
17. Есть export packages.
18. Есть UI лаборатории данных.
19. Есть golden seed materials.
20. Есть тесты на нормализацию, matching, required fields, quality score и compatibility.
```

---

# 25. Главный итог

Модуль №1 должен быть не пустой таблицей материалов, а предзаполненным Material Data Hub.

Он должен сразу знать:

```text
что искать на сайтах;
какие характеристики нужны;
как нормализовать материалы;
как определять категории;
как понимать размеры;
как конвертировать единицы;
где материал может применяться;
какие материалы являются аналогами;
какие замены допустимы;
какие замены запрещены;
какие данные нужны для автоматических расчетов;
какие записи требуют модерации;
какое качество данных у материала.
```

Так Модуль №1 не будет годами формироваться вручную. Модерация станет не строительством базы с нуля, а контролем, уточнением и улучшением уже созданного ядра.
