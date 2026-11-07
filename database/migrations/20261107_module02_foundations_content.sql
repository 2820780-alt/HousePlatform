-- M2-FOUNDATIONS-1 content package. No schema changes or prices.
-- The MCHS-hosted SP 70 text is the 2020 edition; no numerical requirement is
-- copied from it. Check the current Rosstandart amendments for project use.
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('houseplatform:m2-foundations-1'));

CREATE TEMP TABLE fnd_sources (
    code text PRIMARY KEY, title text NOT NULL, url text NOT NULL UNIQUE,
    evidence_scope text NOT NULL
) ON COMMIT DROP;
INSERT INTO fnd_sources VALUES
 ('SP22', 'СП 22.13330.2016: основания зданий и сооружений', 'https://protect.gost.ru/sp/details/71e96332-a446-4a15-87a0-2db895479f61', 'Official status and scope; project-specific foundation design, not construction dimensions'),
 ('SP63', 'СП 63.13330.2018: бетонные и железобетонные конструкции', 'https://protect.gost.ru/sp/details/8b67e228-0c9f-4a62-b562-964b3a58c667', 'Official status and scope; reinforced-concrete design, not a fixed grade'),
 ('SP70', 'СП 70.13330.2012: производство и приемка несущих конструкций', 'https://protect.gost.ru/sp/details/2239acf1-711f-4f1f-aaa7-902fa06a8a60', 'Official current status and amendment list; check the applicable edition'),
 ('SP70_TEXT', 'СП 70.13330.2012: текст редакции 30.12.2020, МЧС России', 'https://mchs.gov.ru/uploads/document/2025-04-18/a4fdaa23dd52e900a59f40c57124e039.pdf', 'Primary published text for general work sequence in sections 5 and 6; later amendments not incorporated'),
 ('GOST_CONCRETE', 'ГОСТ 26633-2015: тяжелые и мелкозернистые бетоны', 'https://protect.gost.ru/gost/details/b9da3cd9-2fb4-4473-9553-3979ad6be453', 'Official material class scope; no universal concrete grade'),
 ('GOST_REBAR', 'ГОСТ 34028-2016: арматурный прокат', 'https://protect.gost.ru/gost/details/50236208-68a9-443c-974d-4cc3dc04d15a', 'Official material class scope; no universal steel class or diameter'),
 ('GOST_FBS', 'ГОСТ 13579-2018: бетонные блоки стен подвалов', 'https://protect.gost.ru/gost/details/590002ea-b5b0-4bf5-9e47-a772c8c16f06', 'Official scope: solid blocks may be used for foundations; design still required'),
 ('GOST_FL', 'ГОСТ 13580-2021: сборные плиты ленточных фундаментов', 'https://protect.gost.ru/gost/details/ae76fad3-1e46-4c89-af7a-1a4c6e9617c3', 'Official scope of prefabricated strip-footing slabs; use is design-dependent'),
 ('SP28', 'СП 28.13330.2017: защита строительных конструкций от коррозии', 'https://protect.gost.ru/sp/details/bd3c594c-26c7-41a9-9c76-510d0fa1ca92', 'Official protection scope; specific waterproofing is project-dependent'),
 ('SP50', 'СП 50.13330.2024: тепловая защита зданий', 'https://protect.gost.ru/sp/details/5081dae9-9ee9-455f-80e8-d093d495361c', 'Official thermal-design scope; insulation is not universal for every foundation'),
 ('RIBBED_PAPER', 'Eldin et al. 2021: ribbed raft on swell-shrink soils', 'https://eijest.journals.ekb.eg/article_153965_5030d71d83e7b78838464cc5c4a4efd3.pdf', 'Original research on a particular ribbed system; not a Russian residential design prescription');

INSERT INTO knowledge_resources (resource_type, title, resource_url, source_url, metadata_json, status)
SELECT 'STANDARD_REFERENCE', s.title, s.url, s.url,
       jsonb_build_object('package', 'M2-FOUNDATIONS-1', 'source_code', s.code,
                          'evidence_scope', s.evidence_scope, 'reviewed_on', '2026-11-07'),
       'ACTIVE'
FROM fnd_sources s
WHERE NOT EXISTS (SELECT 1 FROM knowledge_resources k WHERE k.source_url = s.url);

DO $check$
BEGIN
 IF EXISTS (SELECT 1 FROM fnd_sources s LEFT JOIN knowledge_resources k
            ON k.source_url = s.url AND k.status = 'ACTIVE'
            GROUP BY s.code HAVING count(k.id) <> 1) THEN
   RAISE EXCEPTION 'M1 evidence URL is missing, duplicate, or inactive';
 END IF;
END $check$;

CREATE PROCEDURE pg_temp.seed_foundations_components()
LANGUAGE plpgsql AS $components$
BEGIN
CREATE TEMP TABLE fnd_layers (
    tech text NOT NULL, position integer NOT NULL, role text NOT NULL,
    requirement_code text NOT NULL, mandatory boolean NOT NULL, notes text NOT NULL,
    PRIMARY KEY (tech, position)
) ON COMMIT DROP;
INSERT INTO fnd_layers VALUES
 ('FND_STRIP_MONOLITHIC_RC',1,'LOAD_BEARING_STRIP','CONCRETE',true,'Сечение и бетон назначаются проектом.'),
 ('FND_STRIP_MONOLITHIC_RC',2,'STRUCTURAL_REINFORCEMENT','REBAR',true,'Положение, соединения и защитный слой по проекту.'),
 ('FND_STRIP_MONOLITHIC_RC',3,'CONSTRUCTION_FORM','FORMWORK',false,'Опалубка применяется в предусмотренной ППР схеме.'),
 ('FND_STRIP_MONOLITHIC_RC',4,'SUBSTRUCTURE_PROTECTION','WATERPROOFING',false,'Гидроизоляция только по проекту.'),
 ('FND_STRIP_MONOLITHIC_RC',5,'THERMAL_PROTECTION','INSULATION',false,'Теплоизоляция только по теплотехническому проекту.'),
 ('FND_STRIP_PRECAST_FBS_FL',1,'PREFABRICATED_FOOTING','FL',false,'ФЛ является проектным вариантом, не обязательным элементом каждой сборной ленты.'),
 ('FND_STRIP_PRECAST_FBS_FL',2,'LOAD_BEARING_BLOCKS','FBS',true,'Только сплошные блоки, применимость по расчету.'),
 ('FND_STRIP_PRECAST_FBS_FL',3,'ASSEMBLY_JOINTS','MORTAR',true,'Соединения и раствор выполняются по проекту/ППР.'),
 ('FND_STRIP_PRECAST_FBS_FL',4,'SUBSTRUCTURE_PROTECTION','WATERPROOFING',false,'Система защиты по проекту.'),
 ('FND_STRIP_PRECAST_FBS_FL',5,'THERMAL_PROTECTION','INSULATION',false,'Теплоизоляция только по теплотехническому проекту.'),
 ('FND_SLAB_MONOLITHIC_RC',1,'LOAD_BEARING_SLAB','CONCRETE',true,'Толщина и свойства бетона по проекту.'),
 ('FND_SLAB_MONOLITHIC_RC',2,'STRUCTURAL_REINFORCEMENT','REBAR',true,'Армирование по расчету и проекту.'),
 ('FND_SLAB_MONOLITHIC_RC',3,'EDGE_FORM','FORMWORK',false,'Краевая опалубка, если нужна проекту.'),
 ('FND_SLAB_MONOLITHIC_RC',4,'SUBSTRUCTURE_PROTECTION','WATERPROOFING',false,'Защита по проекту.'),
 ('FND_SLAB_MONOLITHIC_RC',5,'THERMAL_PROTECTION','INSULATION',false,'Теплоизоляция только по теплотехническому проекту.'),
 ('FND_SLAB_RIBBED_RC',1,'SLAB_AND_RIBS','CONCRETE',true,'DRAFT: отдельная расчетная схема должна быть подтверждена для российского ИЖС.'),
 ('FND_SLAB_RIBBED_RC',2,'RIB_AND_SLAB_REINFORCEMENT','REBAR',true,'DRAFT: армирование рассчитывается для выбранной схемы.'),
 ('FND_SLAB_RIBBED_RC',3,'RIB_FORM','FORMWORK',false,'DRAFT: форма ребер и последовательность не утверждены.');

INSERT INTO module2_technology_layers
 (technology_id, position, functional_role, material_requirement_id, is_mandatory, notes)
SELECT t.id, s.position, s.role, r.id, s.mandatory, s.notes
FROM fnd_layers s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.requirement_code
ON CONFLICT (technology_id, position) DO NOTHING;

CREATE TEMP TABLE fnd_steps (
    tech text NOT NULL, position integer NOT NULL, work_code text NOT NULL,
    applicability text NOT NULL, instruction text NOT NULL,
    PRIMARY KEY (tech, position)
) ON COMMIT DROP;
INSERT INTO fnd_steps VALUES
 ('FND_STRIP_MONOLITHIC_RC',1,'foundations_concrete_montazh_opalubki_fundamenta','По проекту и ППР','Проверить форму, устойчивость и приемку опалубки до бетонирования; последовательность с армированием задает ППР.'),
 ('FND_STRIP_MONOLITHIC_RC',2,'reinforcement_armirovanie_fundamenta','По проекту','Смонтировать и принять армирование, соединения и проектный защитный слой до укладки смеси.'),
 ('FND_STRIP_MONOLITHIC_RC',3,'foundations_concrete_betonirovanie_konstrukciy','После приемки основания, опалубки и армирования','Уложить и уплотнить смесь по ППР; обеспечить проектный уход и контроль качества бетона.'),
 ('FND_STRIP_MONOLITHIC_RC',4,'foundations_concrete_demontazh_opalubki','После достижения проектно обоснованной готовности','Распалубливание и последующие нагрузки только по проекту и ППР.'),
 ('FND_STRIP_MONOLITHIC_RC',5,'foundations_concrete_gidroizolyaciya_fundamenta','Только если предусмотрено проектом','Выполнить назначенную систему защиты после готовности основания под нее.'),
 ('FND_STRIP_MONOLITHIC_RC',6,'foundations_concrete_uteplenie_fundamenta','Только если предусмотрено теплотехническим проектом','Материал и узел теплоизоляции назначаются проектом, не этим справочником.'),
 ('FND_STRIP_PRECAST_FBS_FL',1,'foundations_concrete_ustroystvo_lentochnogo_fundamenta','Сборная лента из сплошных ФБС; ФЛ только если назначены проектом','Смонтировать ФЛ, если они предусмотрены проектом, затем ФБС по проектной схеме и ППР; проверить положение, опирание и соединения. Отдельных кодов монтажа ФЛ/ФБС в M1 Work Catalog пока нет.'),
 ('FND_STRIP_PRECAST_FBS_FL',2,'foundations_concrete_gidroizolyaciya_fundamenta','Только если предусмотрено проектом','Защиту и узлы сопряжений выполнить по проекту.'),
 ('FND_STRIP_PRECAST_FBS_FL',3,'foundations_concrete_uteplenie_fundamenta','Только если предусмотрено теплотехническим проектом','Материал и узел теплоизоляции назначаются проектом.'),
 ('FND_SLAB_MONOLITHIC_RC',1,'foundations_concrete_montazh_opalubki_fundamenta','Если требуется опалубка края','Проверить проектную геометрию и устойчивость краевой формы.'),
 ('FND_SLAB_MONOLITHIC_RC',2,'reinforcement_armirovanie_plity','По проекту','Смонтировать и принять армирование и защитный слой по проектной схеме.'),
 ('FND_SLAB_MONOLITHIC_RC',3,'foundations_concrete_betonirovanie_konstrukciy','После приемки основания и армирования','Уложить и уплотнить смесь по ППР, затем обеспечить уход и контроль бетона.'),
 ('FND_SLAB_MONOLITHIC_RC',4,'foundations_concrete_demontazh_opalubki','Если опалубка применялась','Срок распалубливания и дальнейшие работы определяются проектом/ППР.'),
 ('FND_SLAB_MONOLITHIC_RC',5,'foundations_concrete_gidroizolyaciya_fundamenta','Только если предусмотрено проектом','Систему защиты и примыкания выполнить по проекту.'),
 ('FND_SLAB_MONOLITHIC_RC',6,'foundations_concrete_uteplenie_fundamenta','Только если предусмотрено теплотехническим проектом','Материал и узел теплоизоляции назначаются проектом.'),
 ('FND_SLAB_RIBBED_RC',1,'foundations_concrete_montazh_opalubki_fundamenta','DRAFT; схема не утверждена','Форма ребер зависит от проектной схемы.'),
 ('FND_SLAB_RIBBED_RC',2,'reinforcement_armirovanie_plity','DRAFT; схема не утверждена','Армирование ребер и плиты требует отдельного расчета.'),
 ('FND_SLAB_RIBBED_RC',3,'foundations_concrete_betonirovanie_konstrukciy','DRAFT; схема не утверждена','Последовательность бетонирования должна быть подтверждена для выбранной системы.');

INSERT INTO module2_technology_work_steps
 (technology_id, position, work_code, applicability_expression, instructions)
SELECT t.id, s.position, s.work_code, s.applicability, s.instruction
FROM fnd_steps s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
ON CONFLICT (technology_id, position) DO NOTHING;

CREATE TEMP TABLE fnd_nodes (
    tech text NOT NULL, code text NOT NULL, kind text NOT NULL,
    name text NOT NULL, description text NOT NULL, PRIMARY KEY (tech, code)
) ON COMMIT DROP;
INSERT INTO fnd_nodes VALUES
 ('FND_STRIP_MONOLITHIC_RC','BASE_CONTACT','INTERFACE','Контакт ленты с основанием','Подготовка и приемка основания, геометрия и отметки зависят от изысканий и проекта.'),
 ('FND_STRIP_MONOLITHIC_RC','UTILITY_PENETRATION','INTERFACE','Ввод коммуникаций','Место, гильза и герметизация задаются проектом до бетонирования; нельзя произвольно нарушать несущую схему.'),
 ('FND_STRIP_MONOLITHIC_RC','WATERPROOFING_JUNCTION','INTERFACE','Примыкание гидроизоляции','Непрерывность и сопряжение назначенной системы проверяются по проекту.'),
 ('FND_STRIP_PRECAST_FBS_FL','FL_FBS_BEARING','INTERFACE','Опирание ФБС на ФЛ','Узел применяется только при наличии ФЛ в проекте; размеры и раствор по проекту/ППР.'),
 ('FND_STRIP_PRECAST_FBS_FL','BLOCK_JOINT','INTERFACE','Стык сборных элементов','Положение, раствор, перевязка и усиление определяются проектной документацией.'),
 ('FND_SLAB_MONOLITHIC_RC','SLAB_EDGE','INTERFACE','Край фундаментной плиты','Краевая опалубка, защита и сопряжение со стеной выполняются по проекту.'),
 ('FND_SLAB_MONOLITHIC_RC','UTILITY_PENETRATION','INTERFACE','Проходка через плиту','Расположение и герметизация задаются проектом до бетонирования; самовольное отверстие недопустимо.'),
 ('FND_SLAB_RIBBED_RC','RIB_ORIENTATION','DESIGN_VARIANT','Ориентация ребер','DRAFT: направление и геометрия ребер являются параметрами расчета, не отдельными Technology.');

INSERT INTO module2_technology_nodes (technology_id, code, node_type, name, description)
SELECT t.id, s.code, s.kind, s.name, s.description
FROM fnd_nodes s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
ON CONFLICT (technology_id, code) DO NOTHING;
END $components$;

CREATE TEMP TABLE fnd_material_classes (slug text PRIMARY KEY, name text NOT NULL) ON COMMIT DROP;
INSERT INTO fnd_material_classes VALUES
 ('foundation-structural-concrete', 'Конструкционный бетон для фундаментов'),
 ('foundation-reinforcing-steel', 'Арматурный прокат для железобетона'),
 ('foundation-formwork', 'Опалубочные материалы и системы'),
 ('foundation-fbs-blocks', 'Сплошные фундаментные блоки ФБС'),
 ('foundation-fl-slabs', 'Сборные фундаментные плиты ФЛ'),
 ('foundation-masonry-mortar', 'Растворы для монтажа сборных фундаментных элементов'),
 ('foundation-waterproofing', 'Гидроизоляционные материалы подземных конструкций'),
 ('foundation-thermal-insulation', 'Теплоизоляционные материалы подземных конструкций');

INSERT INTO material_categories (id, name, slug, status, level, sort_order, created_at, updated_at)
SELECT gen_random_uuid(), name, slug, 'ACTIVE', 0, 0, now(), now() FROM fnd_material_classes
ON CONFLICT (slug) DO NOTHING;

DO $check$
BEGIN
 IF EXISTS (SELECT 1 FROM fnd_material_classes s LEFT JOIN material_categories c ON c.slug = s.slug
            WHERE c.id IS NULL OR c.name <> s.name OR c.status <> 'ACTIVE') THEN
   RAISE EXCEPTION 'M1 material class conflicts with existing category';
 END IF;
END $check$;

CREATE TEMP TABLE fnd_class_sources (slug text PRIMARY KEY, source_code text NOT NULL) ON COMMIT DROP;
INSERT INTO fnd_class_sources VALUES
 ('foundation-structural-concrete','GOST_CONCRETE'),
 ('foundation-reinforcing-steel','GOST_REBAR'),
 ('foundation-formwork','SP70_TEXT'),
 ('foundation-fbs-blocks','GOST_FBS'),
 ('foundation-fl-slabs','GOST_FL'),
 ('foundation-masonry-mortar','SP70_TEXT'),
 ('foundation-waterproofing','SP28'),
 ('foundation-thermal-insulation','SP50');
INSERT INTO knowledge_resource_links (resource_id, category_id, link_type, status)
SELECT k.id, c.id, 'APPLIES_TO', 'ACTIVE'
FROM fnd_class_sources s JOIN material_categories c ON c.slug=s.slug
JOIN fnd_sources src ON src.code=s.source_code
JOIN knowledge_resources k ON k.source_url=src.url AND k.status='ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM knowledge_resource_links l
                  WHERE l.resource_id=k.id AND l.category_id=c.id AND l.link_type='APPLIES_TO');

CREATE TEMP TABLE fnd_technologies (
    code text PRIMARY KEY, category_code text NOT NULL, name text NOT NULL,
    description text NOT NULL, status text NOT NULL
) ON COMMIT DROP;
INSERT INTO fnd_technologies VALUES
 ('FND_STRIP_MONOLITHIC_RC', 'STRIP_FOUNDATIONS', 'Монолитный железобетонный ленточный фундамент',
  'Непрерывная железобетонная лента под несущими линиями здания. Применимость, глубина заложения, геометрия, бетон, армирование и защита назначаются проектом по результатам изысканий и расчета. Не является типовым решением для любого грунта.', 'ACTIVE'),
 ('FND_STRIP_PRECAST_FBS_FL', 'STRIP_FOUNDATIONS', 'Сборный ленточный фундамент из ФБС (ФЛ по проекту)',
  'Сборная система из сплошных блоков ФБС; фундаментные плиты ФЛ применяются, когда предусмотрены проектом. ФБС по ГОСТ 13579 в первую очередь описаны для стен подвалов, но сплошные блоки допускаются для фундаментов. Несущая схема, стыки, раствор, перевязка и защита определяются проектом и ППР.', 'ACTIVE'),
 ('FND_SLAB_MONOLITHIC_RC', 'SLAB_FOUNDATIONS', 'Монолитная железобетонная фундаментная плита',
  'Железобетонная плита как фундаментная система здания. Основание, толщина, армирование, бетон, швы и защитные мероприятия назначаются проектом после изысканий и расчета. Не следует считать плиту универсально пригодной для любого грунта или нагрузки.', 'ACTIVE'),
 ('FND_SLAB_RIBBED_RC', 'SLAB_FOUNDATIONS', 'Ребристая железобетонная фундаментная плита',
  'Исследовательская boundary-карточка. Ребристая система может иметь самостоятельную расчетную и конструктивную схему, но найденное исследование относится к набухающим грунтам и зарубежным нормам. Российская residential-применимость и последовательность не подтверждены; публикация заблокирована.', 'DRAFT');

INSERT INTO module2_technologies (technology_code, revision, name, description, system_code,
                                  category_id, status, source_kind, input_blockers)
SELECT s.code, 1, s.name, s.description, s.code, c.id, s.status, 'REVIEWED_CONTENT_SEED',
       CASE WHEN s.code = 'FND_SLAB_RIBBED_RC' THEN
         '["russian_residential_applicability_unverified", "ribbed_work_sequence_unverified"]'::jsonb
       ELSE '[]'::jsonb END
FROM fnd_technologies s JOIN module2_technology_categories c ON c.code = s.category_code
WHERE c.status = 'ACTIVE'
ON CONFLICT (technology_code, revision) DO NOTHING;

DO $check$
BEGIN
 IF EXISTS (SELECT 1 FROM fnd_technologies s
            LEFT JOIN module2_technology_categories c ON c.code = s.category_code
            LEFT JOIN module2_technologies t ON t.technology_code = s.code AND t.revision = 1
            WHERE c.id IS NULL OR t.id IS NULL OR t.category_id <> c.id OR t.name <> s.name
               OR t.status <> s.status OR t.description <> s.description
               OR (s.status='DRAFT' AND t.input_blockers='[]'::jsonb)) THEN
   RAISE EXCEPTION 'M2 foundation Technology conflicts with existing revision 1';
 END IF;
END $check$;

CREATE TEMP TABLE fnd_requirements (
    tech text NOT NULL, code text NOT NULL, class_slug text NOT NULL, role_code text NOT NULL,
    notes text NOT NULL, PRIMARY KEY (tech, code)
) ON COMMIT DROP;
INSERT INTO fnd_requirements VALUES
 ('FND_STRIP_MONOLITHIC_RC','CONCRETE','foundation-structural-concrete','CONCRETE','Класс и свойства бетона по проекту; ГОСТ 26633 не задает одну универсальную марку.'),
 ('FND_STRIP_MONOLITHIC_RC','REBAR','foundation-reinforcing-steel','REINFORCEMENT','Класс, диаметр и защитный слой по расчету и проекту.'),
 ('FND_STRIP_MONOLITHIC_RC','FORMWORK','foundation-formwork','FORMWORK','Опалубка должна обеспечить проектную форму; тип по ППР.'),
 ('FND_STRIP_MONOLITHIC_RC','WATERPROOFING','foundation-waterproofing','WATERPROOFING','Только система и участки, предусмотренные проектом с учетом среды и воды.'),
 ('FND_STRIP_MONOLITHIC_RC','INSULATION','foundation-thermal-insulation','THERMAL_PROTECTION','Только если теплотехнический проект требует теплоизоляцию.'),
 ('FND_SLAB_MONOLITHIC_RC','CONCRETE','foundation-structural-concrete','CONCRETE','Класс и свойства бетона по проекту.'),
 ('FND_SLAB_MONOLITHIC_RC','REBAR','foundation-reinforcing-steel','REINFORCEMENT','Схема армирования и защитный слой по расчету и проекту.'),
 ('FND_SLAB_MONOLITHIC_RC','FORMWORK','foundation-formwork','EDGE_FORMWORK','Краевая опалубка, когда требуется проектной схемой.'),
 ('FND_SLAB_MONOLITHIC_RC','WATERPROOFING','foundation-waterproofing','WATERPROOFING','Применимость и система по проекту, не универсальный слой.'),
 ('FND_SLAB_MONOLITHIC_RC','INSULATION','foundation-thermal-insulation','THERMAL_PROTECTION','Только если теплотехнический проект требует теплоизоляцию.'),
 ('FND_STRIP_PRECAST_FBS_FL','FBS','foundation-fbs-blocks','PRECAST_BLOCK','Только сплошные блоки в проектной несущей схеме; спецификация по проекту.'),
 ('FND_STRIP_PRECAST_FBS_FL','FL','foundation-fl-slabs','FOOTING_SLAB','Условный элемент: требуется лишь при назначении проектом.'),
 ('FND_STRIP_PRECAST_FBS_FL','MORTAR','foundation-masonry-mortar','BED_AND_JOINT','Тип, состав и прочность раствора по проекту/ППР.'),
 ('FND_STRIP_PRECAST_FBS_FL','WATERPROOFING','foundation-waterproofing','WATERPROOFING','Защита подземной конструкции по проекту.'),
 ('FND_STRIP_PRECAST_FBS_FL','INSULATION','foundation-thermal-insulation','THERMAL_PROTECTION','Только если теплотехнический проект требует теплоизоляцию.'),
 ('FND_SLAB_RIBBED_RC','CONCRETE','foundation-structural-concrete','CONCRETE','DRAFT: нельзя переносить параметры исследовательского примера в российский проект.'),
 ('FND_SLAB_RIBBED_RC','REBAR','foundation-reinforcing-steel','REINFORCEMENT','DRAFT: схема армирования требует расчета.'),
 ('FND_SLAB_RIBBED_RC','FORMWORK','foundation-formwork','RIB_FORMWORK','DRAFT: конструкция ребер и опалубки требует отдельного подтверждения.');

INSERT INTO module2_technology_material_requirements
 (technology_id, code, selector_kind, material_role_code, material_category_id, notes)
SELECT t.id, s.code, 'MATERIAL_CLASS', s.role_code, c.id, s.notes
FROM fnd_requirements s
JOIN module2_technologies t ON t.technology_code = s.tech AND t.revision = 1
JOIN material_categories c ON c.slug = s.class_slug AND c.status = 'ACTIVE'
ON CONFLICT (technology_id, code) DO NOTHING;

DO $check$
BEGIN
 IF (SELECT count(*) FROM fnd_requirements) <>
    (SELECT count(*) FROM fnd_requirements s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
     JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.code
     JOIN material_categories c ON c.slug=s.class_slug AND c.id=r.material_category_id
     WHERE r.selector_kind='MATERIAL_CLASS' AND r.material_role_code=s.role_code) THEN
   RAISE EXCEPTION 'M1 class references are incomplete or conflicting';
 END IF;
END $check$;

CALL pg_temp.seed_foundations_components();

CREATE TEMP TABLE fnd_rules (
    tech text NOT NULL, code text NOT NULL, section text NOT NULL,
    message text NOT NULL, source_code text NOT NULL, PRIMARY KEY (tech, code)
) ON COMMIT DROP;
INSERT INTO fnd_rules VALUES
 ('FND_STRIP_MONOLITHIC_RC','STRIP_APPLICABILITY','applicability','Применимость ленточной системы определяется изысканиями, нагрузками и проектным расчетом основания.','SP22'),
 ('FND_STRIP_MONOLITHIC_RC','STRIP_EXCLUSION','exclusions','Без проекта нельзя считать эту систему пригодной для конкретного грунта, уровня воды или режима эксплуатации.','SP22'),
 ('FND_STRIP_MONOLITHIC_RC','STRIP_BEFORE','quality_before','До работ проверить проектные отметки и принятое основание; перед бетонированием принять опалубку и армирование.','SP70_TEXT'),
 ('FND_STRIP_MONOLITHIC_RC','STRIP_DURING','quality_during','Во время бетонирования контролировать укладку, уплотнение и сохранение проектного положения арматуры.','SP70_TEXT'),
 ('FND_STRIP_MONOLITHIC_RC','STRIP_AFTER','quality_after','После укладки обеспечить уход за бетоном и дальнейшие работы только после проектной готовности.','SP70_TEXT'),
 ('FND_STRIP_MONOLITHIC_RC','STRIP_ERROR','common_error','Ошибка: бетонировать до приемки армирования или считать защитный слой универсальной величиной.','SP70_TEXT'),
 ('FND_STRIP_MONOLITHIC_RC','STRIP_DESIGN','project_dependent','Глубина, ширина, бетон, армирование, несущая способность и защита задаются проектом; здесь они не рассчитываются.','SP22'),
 ('FND_STRIP_PRECAST_FBS_FL','PRECAST_APPLICABILITY','applicability','Сплошные ФБС допускаются для фундаментов; ФЛ являются сборными плитами ленточных фундаментов. Их сочетание назначает проект.','GOST_FBS'),
 ('FND_STRIP_PRECAST_FBS_FL','PRECAST_EXCLUSION','exclusions','Не следует принимать ФЛ обязательными для каждой сборной ленты или использовать несоответствующие блоки как фундаментные.','GOST_FL'),
 ('FND_STRIP_PRECAST_FBS_FL','PRECAST_BEFORE','quality_before','До монтажа проверить проектную схему, основание, документы на элементы и порядок монтажа в ППР.','SP70_TEXT'),
 ('FND_STRIP_PRECAST_FBS_FL','PRECAST_DURING','quality_during','Во время монтажа контролировать положение, опирание и предусмотренные проектом соединения элементов.','SP70_TEXT'),
 ('FND_STRIP_PRECAST_FBS_FL','PRECAST_AFTER','quality_after','После монтажа принять стыки и положение элементов; защиту выполнять по проекту.','SP70_TEXT'),
 ('FND_STRIP_PRECAST_FBS_FL','PRECAST_ERROR','common_error','Ошибка: считать стеновые ФБС любого типа или ФЛ любого размера взаимозаменяемыми без расчетной схемы.','GOST_FBS'),
 ('FND_STRIP_PRECAST_FBS_FL','PRECAST_DESIGN','project_dependent','Размеры, тип элементов, раствор, перевязка, усиление и защита определяются проектом и ППР.','SP22'),
 ('FND_SLAB_MONOLITHIC_RC','SLAB_APPLICABILITY','applicability','Фундаментная плита применяется по результатам инженерных изысканий и расчетов основания и железобетонной конструкции.','SP22'),
 ('FND_SLAB_MONOLITHIC_RC','SLAB_EXCLUSION','exclusions','Без проекта нельзя считать плиту универсальным решением для любого грунта, нагрузки или уровня воды.','SP22'),
 ('FND_SLAB_MONOLITHIC_RC','SLAB_BEFORE','quality_before','До бетонирования проверить основание, проектную геометрию, опалубку при ее применении и принять армирование.','SP70_TEXT'),
 ('FND_SLAB_MONOLITHIC_RC','SLAB_DURING','quality_during','Во время укладки контролировать свойства смеси, укладку, уплотнение и положение арматуры.','SP70_TEXT'),
 ('FND_SLAB_MONOLITHIC_RC','SLAB_AFTER','quality_after','После бетонирования обеспечить назначенный уход и контроль прочности перед дальнейшими нагрузками.','SP70_TEXT'),
 ('FND_SLAB_MONOLITHIC_RC','SLAB_ERROR','common_error','Ошибка: использовать фиксированную толщину или схему армирования вместо проектного расчета.','SP63'),
 ('FND_SLAB_MONOLITHIC_RC','SLAB_DESIGN','project_dependent','Толщина, классы материалов, армирование, швы и защитные слои зависят от расчета и проектных условий.','SP63');

INSERT INTO module2_knowledge_rules
 (technology_id, rule_code, revision, scope_kind, conditions, outcome_type, outcome_payload,
  status, source_kind, blockers)
SELECT t.id, s.code, 1, 'TECHNOLOGY', '[]'::jsonb, 'INFORMATION',
       jsonb_build_object('section', s.section, 'message', s.message),
       'ACTIVE', 'REVIEWED_CONTENT_SEED', '[]'::jsonb
FROM fnd_rules s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1 AND t.status='ACTIVE'
ON CONFLICT (technology_id, rule_code, revision) DO NOTHING;

CREATE TEMP TABLE fnd_tech_evidence (tech text NOT NULL, source_code text NOT NULL,
                                     PRIMARY KEY (tech, source_code)) ON COMMIT DROP;
INSERT INTO fnd_tech_evidence VALUES
 ('FND_STRIP_MONOLITHIC_RC','SP22'),('FND_STRIP_MONOLITHIC_RC','SP63'),
 ('FND_STRIP_MONOLITHIC_RC','SP70'),('FND_STRIP_MONOLITHIC_RC','SP70_TEXT'),
 ('FND_STRIP_PRECAST_FBS_FL','SP22'),('FND_STRIP_PRECAST_FBS_FL','SP70'),
 ('FND_STRIP_PRECAST_FBS_FL','SP70_TEXT'),('FND_STRIP_PRECAST_FBS_FL','GOST_FBS'),
 ('FND_STRIP_PRECAST_FBS_FL','GOST_FL'),
 ('FND_SLAB_MONOLITHIC_RC','SP22'),('FND_SLAB_MONOLITHIC_RC','SP63'),
 ('FND_SLAB_MONOLITHIC_RC','SP70'),('FND_SLAB_MONOLITHIC_RC','SP70_TEXT'),
 ('FND_SLAB_RIBBED_RC','RIBBED_PAPER');

CREATE TEMP TABLE fnd_evidence_targets (
    tech text NOT NULL, source_code text NOT NULL, target_kind text NOT NULL,
    target_reference text, interpretation text NOT NULL
) ON COMMIT DROP;
INSERT INTO fnd_evidence_targets
SELECT s.tech, s.source_code, 'TECHNOLOGY', NULL, src.evidence_scope
FROM fnd_tech_evidence s JOIN fnd_sources src ON src.code=s.source_code;
INSERT INTO fnd_evidence_targets
SELECT s.tech,
       CASE s.class_slug
         WHEN 'foundation-structural-concrete' THEN 'GOST_CONCRETE'
         WHEN 'foundation-reinforcing-steel' THEN 'GOST_REBAR'
         WHEN 'foundation-fbs-blocks' THEN 'GOST_FBS'
         WHEN 'foundation-fl-slabs' THEN 'GOST_FL'
         WHEN 'foundation-waterproofing' THEN 'SP28'
         WHEN 'foundation-thermal-insulation' THEN 'SP50'
         ELSE 'SP70_TEXT' END,
       'MATERIAL_REQUIREMENT', r.id::text, s.notes
FROM fnd_requirements s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.code;
INSERT INTO fnd_evidence_targets
SELECT s.tech,
       CASE WHEN s.work_code LIKE '%gidroizolyaciya%' THEN 'SP28'
            WHEN s.work_code LIKE '%uteplenie%' THEN 'SP50'
            ELSE 'SP70_TEXT' END,
       'WORK_STEP', w.id::text, 'General sequence only; details, edition and PPR are project-dependent.'
FROM fnd_steps s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_work_steps w ON w.technology_id=t.id AND w.position=s.position;
INSERT INTO fnd_evidence_targets
SELECT s.tech,
       CASE s.requirement_code
         WHEN 'CONCRETE' THEN 'GOST_CONCRETE' WHEN 'REBAR' THEN 'GOST_REBAR'
         WHEN 'FBS' THEN 'GOST_FBS' WHEN 'FL' THEN 'GOST_FL'
         WHEN 'WATERPROOFING' THEN 'SP28' WHEN 'INSULATION' THEN 'SP50'
         ELSE 'SP70_TEXT' END,
       'LAYER', l.id::text, s.notes
FROM fnd_layers s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_layers l ON l.technology_id=t.id AND l.position=s.position;
INSERT INTO fnd_evidence_targets
SELECT s.tech,
       CASE WHEN s.code LIKE '%WATERPROOFING%' THEN 'SP28'
            WHEN s.code='RIB_ORIENTATION' THEN 'RIBBED_PAPER'
            WHEN s.code IN ('BLOCK_JOINT','FL_FBS_BEARING') THEN 'SP70_TEXT'
            WHEN s.code='BASE_CONTACT' THEN 'SP22'
            ELSE 'SP63' END,
       'NODE', n.id::text,
       'This is a project-dependent interface; the source does not prescribe a universal detail.'
FROM fnd_nodes s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_nodes n ON n.technology_id=t.id AND n.code=s.code;
INSERT INTO fnd_evidence_targets
SELECT s.tech, s.source_code, 'KNOWLEDGE_RULE', r.id::text,
       'Statement reviewed against the named source scope; no universal numerical design value.'
FROM fnd_rules s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_knowledge_rules r ON r.technology_id=t.id AND r.rule_code=s.code AND r.revision=1;

INSERT INTO module2_technology_evidence_references
 (technology_id, knowledge_resource_id, target_kind, target_reference, interpretation)
SELECT t.id, k.id, s.target_kind, s.target_reference, s.interpretation
FROM fnd_evidence_targets s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN fnd_sources src ON src.code=s.source_code
JOIN knowledge_resources k ON k.source_url=src.url AND k.status='ACTIVE'
WHERE NOT EXISTS (
  SELECT 1 FROM module2_technology_evidence_references e
  WHERE e.technology_id=t.id AND e.knowledge_resource_id=k.id
    AND e.target_kind=s.target_kind AND e.target_reference IS NOT DISTINCT FROM s.target_reference
);

DO $check$
BEGIN
 IF (SELECT count(*) FROM fnd_layers) <>
    (SELECT count(*) FROM fnd_layers s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
     JOIN module2_technology_layers l ON l.technology_id=t.id AND l.position=s.position
     WHERE l.functional_role=s.role AND l.is_mandatory=s.mandatory) THEN
   RAISE EXCEPTION 'Foundation layers incomplete or conflicting';
 END IF;
 IF (SELECT count(*) FROM fnd_steps) <>
    (SELECT count(*) FROM fnd_steps s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
     JOIN module2_technology_work_steps w ON w.technology_id=t.id AND w.position=s.position
     WHERE w.work_code=s.work_code) THEN
   RAISE EXCEPTION 'Foundation WorkSteps incomplete or conflicting';
 END IF;
 IF (SELECT count(*) FROM fnd_nodes) <>
    (SELECT count(*) FROM fnd_nodes s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
     JOIN module2_technology_nodes n ON n.technology_id=t.id AND n.code=s.code) THEN
   RAISE EXCEPTION 'Foundation nodes incomplete';
 END IF;
 IF (SELECT count(*) FROM fnd_rules) <>
    (SELECT count(*) FROM fnd_rules s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
     JOIN module2_knowledge_rules r ON r.technology_id=t.id AND r.rule_code=s.code AND r.revision=1
     WHERE r.status='ACTIVE' AND r.outcome_payload->>'message'=s.message) THEN
   RAISE EXCEPTION 'Foundation knowledge rules incomplete or conflicting';
 END IF;
 IF (SELECT count(*) FROM fnd_evidence_targets) <>
    (SELECT count(*) FROM fnd_evidence_targets s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
     JOIN fnd_sources src ON src.code=s.source_code
     JOIN knowledge_resources k ON k.source_url=src.url AND k.status='ACTIVE'
     JOIN module2_technology_evidence_references e ON e.technology_id=t.id AND e.knowledge_resource_id=k.id
          AND e.target_kind=s.target_kind AND e.target_reference IS NOT DISTINCT FROM s.target_reference) THEN
   RAISE EXCEPTION 'Foundation evidence links incomplete';
 END IF;
END $check$;

UPDATE module2_technology_categories SET content_status='IN_PROGRESS'
WHERE code IN ('STRIP_FOUNDATIONS','SLAB_FOUNDATIONS') AND content_status='EMPTY';

COMMIT;
