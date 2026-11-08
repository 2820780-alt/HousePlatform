-- A2.1: preliminary platform assumptions, never design values or consumption norms.
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('houseplatform:m2-foundation-defaults'));

DO $gate$ BEGIN
 IF (SELECT count(*) FROM module2_technologies WHERE status='ACTIVE' AND technology_code LIKE 'FND_%') <> 15 THEN
  RAISE EXCEPTION 'A2.1 requires exactly 15 active foundation technologies';
 END IF;
 IF EXISTS (SELECT 1 FROM module2_technology_material_requirements r
  JOIN module2_technologies t ON t.id=r.technology_id
  WHERE t.status='ACTIVE' AND t.technology_code LIKE 'FND_%'
    AND (r.selector_kind<>'MATERIAL_CLASS' OR r.material_category_id IS NULL)) THEN
  RAISE EXCEPTION 'A2.1 material requirements need scoped M1 categories';
 END IF;
END $gate$;

INSERT INTO module2_technology_default_assumptions
 (technology_id,assumption_code,revision,parameter_code,name_ru,value_type,default_value,
  source_kind,applicability,auto_fallback,warning_level,warning_text,allowed_values_strategy,
  allowed_values,material_requirement_id,status)
SELECT t.id, 'MATERIAL_'||r.code, 1, 'MATERIAL_'||r.code,
 CASE r.code
  WHEN 'CONCRETE' THEN 'Класс материала: конструкционный бетон'
  WHEN 'REBAR' THEN 'Класс материала: арматура'
  WHEN 'WATERPROOFING' THEN 'Класс материала: гидроизоляция'
  WHEN 'FORMWORK' THEN 'Класс материала: опалубка'
  WHEN 'INSULATION' THEN 'Класс материала: теплоизоляция'
  WHEN 'XPS' THEN 'Класс материала: плиты XPS'
  WHEN 'PILE' THEN 'Класс материала: сваи'
  WHEN 'FBS' THEN 'Класс материала: блоки ФБС'
  WHEN 'FL' THEN 'Класс материала: плиты ФЛ'
  WHEN 'MORTAR' THEN 'Класс материала: кладочный раствор'
  WHEN 'MASTIC' THEN 'Класс материала: мастика'
  WHEN 'MEMBRANE' THEN 'Класс материала: мембрана'
  WHEN 'CASING' THEN 'Класс материала: обсадная труба'
  ELSE 'Класс материала по требованию технологии' END,
 'MATERIAL_CLASS',jsonb_build_object('value',r.material_category_id::text),
 'PLATFORM_ASSUMPTION',jsonb_build_object('mode','PRELIMINARY_ONLY','requirement_code',r.code),
 true,'WARNING','Предварительный класс M1; конкретный материал и совместимость подтверждаются проектом.',
 'M1_REQUIREMENT_CATEGORY',jsonb_build_object('category_ids',jsonb_build_array(r.material_category_id::text)),
 r.id,'ACTIVE'
FROM module2_technologies t JOIN module2_technology_material_requirements r ON r.technology_id=t.id
WHERE t.status='ACTIVE' AND t.technology_code LIKE 'FND_%'
ON CONFLICT (technology_id,assumption_code,revision) DO NOTHING;

INSERT INTO module2_technology_default_assumptions
 (technology_id,assumption_code,revision,parameter_code,name_ru,value_type,
  default_value,source_kind,applicability,auto_fallback,warning_level,warning_text,
  allowed_values_strategy,allowed_values,material_requirement_id,status)
SELECT t.id, r.code||'_CLASS',1,r.code||'_CLASS',
 CASE r.code WHEN 'CONCRETE' THEN 'Класс бетона' ELSE 'Класс арматуры' END,
 'ENUM',
 jsonb_build_object('value',CASE r.code WHEN 'CONCRETE' THEN 'B25' ELSE 'A500C' END),
 'PLATFORM_ASSUMPTION',jsonb_build_object('mode','PRELIMINARY_ONLY','requirement_code',r.code),
 true,'CRITICAL',
 'Предварительный вариант платформы. Класс назначается расчетом и проектом; стандарт не устанавливает универсальный выбор.',
 'REQUIREMENT_ENUM',
 jsonb_build_object('values',CASE r.code WHEN 'CONCRETE' THEN jsonb_build_array('B20','B25','B30')
  ELSE jsonb_build_array('A400','A500C') END),r.id,'ACTIVE'
FROM module2_technologies t JOIN module2_technology_material_requirements r ON r.technology_id=t.id
WHERE t.status='ACTIVE' AND t.technology_code LIKE 'FND_%' AND r.code IN ('CONCRETE','REBAR')
ON CONFLICT (technology_id,assumption_code,revision) DO NOTHING;

INSERT INTO module2_technology_default_assumptions
 (technology_id,assumption_code,revision,parameter_code,name_ru,value_type,unit,
  default_value,source_kind,applicability,auto_fallback,warning_level,warning_text,
  allowed_values_strategy,allowed_values,material_requirement_id,status)
SELECT t.id,'REBAR_DIAMETER_MM',1,'REBAR_DIAMETER_MM','Диаметр арматуры','NUMBER','мм',
 jsonb_build_object('value',12),'PLATFORM_ASSUMPTION',
 jsonb_build_object('mode','PRELIMINARY_ONLY','requirement_code','REBAR'),true,'CRITICAL',
 'Предварительное предположение платформы; диаметр и схема армирования назначаются расчетом и проектом.',
 'BOUNDED_NUMBER',jsonb_build_object('min',6,'max',40),r.id,'ACTIVE'
FROM module2_technologies t JOIN module2_technology_material_requirements r ON r.technology_id=t.id
WHERE t.status='ACTIVE' AND t.technology_code LIKE 'FND_%' AND r.code='REBAR'
ON CONFLICT (technology_id,assumption_code,revision) DO NOTHING;

CREATE TEMP TABLE a21_numbers (
 technology_code text NOT NULL, parameter_code text NOT NULL, name_ru text NOT NULL,
 value numeric NOT NULL, unit text NOT NULL, minimum numeric NOT NULL, maximum numeric NOT NULL,
 PRIMARY KEY (technology_code,parameter_code)
) ON COMMIT DROP;
INSERT INTO a21_numbers VALUES
 ('FND_STRIP_MONOLITHIC_RC','FOUNDATION_DEPTH_MM','Глубина заложения',1200,'мм',100,10000),
 ('FND_STRIP_MONOLITHIC_RC','STRIP_WIDTH_MM','Ширина ленты',400,'мм',100,5000),
 ('FND_STRIP_PRECAST_FBS_FL','FOUNDATION_DEPTH_MM','Глубина заложения',1200,'мм',100,10000),
 ('FND_STRIP_PRECAST_FBS_FL','STRIP_WIDTH_MM','Расчетная ширина ленты',400,'мм',100,5000),
 ('FND_SLAB_MONOLITHIC_RC','SLAB_THICKNESS_MM','Толщина плиты',250,'мм',100,2000),
 ('FND_SLAB_RIBBED_RC','SLAB_THICKNESS_MM','Толщина плиты без ребер',250,'мм',100,2000),
 ('FND_SLAB_RIBBED_RC','RIB_HEIGHT_MM','Высота ребра',400,'мм',100,2000),
 ('FND_SLAB_USHP','SLAB_THICKNESS_MM','Толщина плиты УШП',200,'мм',100,2000),
 ('FND_UFF','SLAB_THICKNESS_MM','Толщина плиты пола УФФ',200,'мм',100,2000),
 ('FND_PILE_BORED_RC','PILE_LENGTH_MM','Длина буронабивной сваи',6000,'мм',500,30000),
 ('FND_PILE_BORED_RC','PILE_DIAMETER_MM','Диаметр буронабивной сваи',300,'мм',100,3000),
 ('FND_PILE_DRIVEN_RC','PILE_LENGTH_MM','Длина забивной сваи',6000,'мм',500,30000),
 ('FND_PILE_SCREW','PILE_LENGTH_MM','Длина винтовой сваи',2500,'мм',500,30000),
 ('FND_PILE_SCREW','PILE_DIAMETER_MM','Диаметр ствола винтовой сваи',108,'мм',50,1000),
 ('FND_PILE_GRILLAGE','GRILLAGE_WIDTH_MM','Ширина ростверка',400,'мм',100,5000),
 ('FND_PILE_GRILLAGE','GRILLAGE_HEIGHT_MM','Высота ростверка',400,'мм',100,5000),
 ('FND_COLUMN_CONCRETE_RC','COLUMN_WIDTH_MM','Ширина столбчатого фундамента',400,'мм',100,5000),
 ('FND_COLUMN_CONCRETE_RC','FOUNDATION_DEPTH_MM','Глубина заложения',1200,'мм',100,10000),
 ('FND_BASEMENT_WALL_MONOLITHIC','WALL_THICKNESS_MM','Толщина стены подвала',250,'мм',100,2000),
 ('FND_BASEMENT_WALL_MONOLITHIC','WALL_HEIGHT_MM','Высота стены подвала',2500,'мм',500,10000),
 ('FND_SUBSTRUCTURE_INSULATION_XPS','INSULATION_THICKNESS_MM','Толщина теплоизоляции XPS',100,'мм',20,500),
 ('FND_SUBSTRUCTURE_WATERPROOFING_COATING','COATING_THICKNESS_MM','Толщина мастичного покрытия',2,'мм',0.5,20),
 ('FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE','MEMBRANE_THICKNESS_MM','Толщина мембраны',2,'мм',0.5,20);

DO $gate$ BEGIN
 IF EXISTS (SELECT 1 FROM a21_numbers n LEFT JOIN module2_technologies t
  ON t.technology_code=n.technology_code AND t.status='ACTIVE' WHERE t.id IS NULL) THEN
  RAISE EXCEPTION 'A2.1 numeric default references missing active technology';
 END IF;
END $gate$;
INSERT INTO module2_technology_default_assumptions
 (technology_id,assumption_code,revision,parameter_code,name_ru,value_type,unit,default_value,
  source_kind,applicability,auto_fallback,warning_level,warning_text,allowed_values_strategy,
  allowed_values,status)
SELECT t.id,n.parameter_code,1,n.parameter_code,n.name_ru,'NUMBER',n.unit,
 jsonb_build_object('value',n.value), 'PLATFORM_ASSUMPTION',
 jsonb_build_object('mode','PRELIMINARY_ONLY','requires_project_review',true),
 true,'CRITICAL',
 'Предварительное предположение платформы, не проектный размер и не норматив. Проверить по проекту и изысканиям до применения.',
 'BOUNDED_NUMBER',jsonb_build_object('min',n.minimum,'max',n.maximum),'ACTIVE'
FROM a21_numbers n JOIN module2_technologies t ON t.technology_code=n.technology_code AND t.status='ACTIVE'
ON CONFLICT (technology_id,assumption_code,revision) DO NOTHING;

DO $gate$ BEGIN
 IF (SELECT count(DISTINCT t.id) FROM module2_technologies t JOIN module2_technology_default_assumptions a
  ON a.technology_id=t.id AND a.status='ACTIVE' WHERE t.status='ACTIVE' AND t.technology_code LIKE 'FND_%') <> 15 THEN
  RAISE EXCEPTION 'A2.1 defaults must cover all 15 active foundation technologies';
 END IF;
END $gate$;
COMMIT;
