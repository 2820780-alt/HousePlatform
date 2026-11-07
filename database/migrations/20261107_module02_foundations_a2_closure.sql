-- A2 continuation: source-scoped residential foundation content and closure gate.
-- Historical A1/A2 publications remain available; no project design values.
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('houseplatform:m2-foundations-a2-closure'));

CREATE TEMP TABLE a2c_sources (
 code text PRIMARY KEY, title text NOT NULL, url text NOT NULL UNIQUE, scope text NOT NULL
) ON COMMIT DROP;
INSERT INTO a2c_sources VALUES
 ('SP22','СП 22.13330.2016: основания зданий и сооружений','https://protect.gost.ru/sp/details/71e96332-a446-4a15-87a0-2db895479f61','Project-specific foundation design'),
 ('SP24','СП 24.13330.2021: свайные фундаменты','https://protect.gost.ru/sp/details/1e90a34c-6379-4236-8256-38be93e29766','Pile-foundation design scope and current amendments'),
 ('SP45','СП 45.13330.2017: земляные сооружения, основания и фундаменты','https://protect.gost.ru/sp/details/6b8a4ce8-2c63-46f8-8c16-6efec70cede8','Foundation execution scope, not fixed installation tolerances'),
 ('SP63','СП 63.13330.2018: бетонные и железобетонные конструкции','https://protect.gost.ru/sp/details/8b67e228-0c9f-4a62-b562-964b3a58c667','Project-specific reinforced-concrete design'),
 ('SP70','СП 70.13330.2012: производство и приемка несущих конструкций','https://protect.gost.ru/sp/details/2239acf1-711f-4f1f-aaa7-902fa06a8a60','Execution and acceptance scope; check applicable amendments'),
 ('SP250','СП 250.1325800.2016: защита от подземных вод','https://protect.gost.ru/sp/details/990885bc-664d-4329-b54c-5aa3d581c20d','Project-specific underground water protection'),
 ('SP50','СП 50.13330.2024: тепловая защита зданий','https://protect.gost.ru/sp/details/5081dae9-9ee9-455f-80e8-d093d495361c','Thermal design; no universal insulation thickness'),
 ('SP71','СП 71.13330.2017: изоляционные и отделочные покрытия','https://protect.gost.ru/sp/details/ca915ed9-5bce-4de4-94af-debfd041a939','Execution and acceptance of insulation works; check amendments'),
 ('GOST_CONCRETE','ГОСТ 26633-2015: тяжелые и мелкозернистые бетоны','https://protect.gost.ru/gost/details/b9da3cd9-2fb4-4473-9553-3979ad6be453','Concrete material class, not a universal grade'),
 ('GOST_REBAR','ГОСТ 34028-2016: арматурный прокат','https://protect.gost.ru/gost/details/50236208-68a9-443c-974d-4cc3dc04d15a','Reinforcement material class, not a universal layout'),
 ('GOST_FBS','ГОСТ 13579-2018: бетонные блоки стен подвалов','https://protect.gost.ru/gost/details/590002ea-b5b0-4bf5-9e47-a772c8c16f06','Solid FBS may be used in foundations; wall and footing applications differ'),
 ('GOST_FL','ГОСТ 13580-2021: сборные плиты ленточных фундаментов','https://protect.gost.ru/gost/details/ae76fad3-1e46-4c89-af7a-1a4c6e9617c3','FL product class; use is conditional on design'),
 ('GOST_RC_PILE','ГОСТ 19804-2021: заводские железобетонные сваи','https://protect.gost.ru/gost/details/1dd4f62d-2f16-4ee8-bdff-41dc947d9167','Factory-made RC pile product class'),
 ('GOST_PVC','ГОСТ Р 56704-2022: ПВХ гидроизоляционные мембраны','https://protect.gost.ru/gost/details/5958ec60-aac8-48ba-a968-43299bd33004','PVC membrane product scope, including foundations and buried structures'),
 ('TN_USHP','ТЕХНОНИКОЛЬ: руководство по проектированию ребристой УШП','https://nav.tn.ru/documents/des_oper_inst/ast_rukovodstvo_proekt_ushp/','Manufacturer system example; not a universal foundation prescription'),
 ('TN_RIBBED','ТЕХНОНИКОЛЬ: альбом Плита Универсал с ребрами жесткости','https://nav.tn.ru/documents/albums_technical_solutions/ast_10020036_ru_RU_pdf/','Manufacturer ribbed slab details; dimensions and products are not generalized'),
 ('TN_UFF','ТЕХНОНИКОЛЬ: технический лист системы УФФ','https://nav.tn.ru/cloud/iblock/d00/xnebblj7peq45nzy6jbfkemm34nt0blm/Tekhlist-FND_23_Sistema-TN_FUNDAMENT-UFF_RU_ru.pdf','Manufacturer strip/floor composition; no universal design values'),
 ('TN_BITUMEN','ТЕХНОНИКОЛЬ: руководство по битумно-полимерным мембранам фундаментов','https://nav.tn.ru/documents/des_oper_inst/ast_design_gui_watpr_dev_found_use_bitpol_mem/','Manufacturer-specific membrane variants and sequence'),
 ('TN_POLYMER','ТЕХНОНИКОЛЬ: руководство по полимерным мембранам фундаментов','https://nav.tn.ru/documents/des_oper_inst/ast_guide_foundation_waterproof/','Manufacturer-specific welded membrane variants and sequence');

INSERT INTO knowledge_resources (resource_type,title,resource_url,source_url,metadata_json,status)
SELECT 'STANDARD_REFERENCE',title,url,url,
 jsonb_build_object('package','M2-FOUNDATIONS-A2-CLOSURE','source_code',code,'evidence_scope',scope,'reviewed_on','2026-11-07'),
 'ACTIVE' FROM a2c_sources s
WHERE NOT EXISTS (SELECT 1 FROM knowledge_resources k WHERE k.source_url=s.url);
DO $gate$ BEGIN
 IF EXISTS (SELECT 1 FROM a2c_sources s LEFT JOIN knowledge_resources k
  ON k.source_url=s.url AND k.status='ACTIVE' GROUP BY s.code HAVING count(k.id)<>1) THEN
  RAISE EXCEPTION 'A2 closure source missing, duplicate or inactive';
 END IF;
END $gate$;

CREATE TEMP TABLE a2c_classes (slug text PRIMARY KEY,name text NOT NULL,source_code text NOT NULL) ON COMMIT DROP;
INSERT INTO a2c_classes VALUES
 ('foundation-structural-concrete','Конструкционный бетон для фундаментов','GOST_CONCRETE'),
 ('foundation-reinforcing-steel','Арматурный прокат для железобетона','GOST_REBAR'),
 ('foundation-formwork','Опалубочные материалы и системы','SP70'),
 ('foundation-fbs-blocks','Сплошные фундаментные блоки ФБС','GOST_FBS'),
 ('foundation-fl-slabs','Сборные фундаментные плиты ФЛ','GOST_FL'),
 ('foundation-masonry-mortar','Растворы для монтажа сборных фундаментных элементов','SP70'),
 ('foundation-waterproofing','Гидроизоляционные материалы подземных конструкций','SP250'),
 ('foundation-xps-insulation','Плиты XPS для подземной теплоизоляции','SP50'),
 ('foundation-rc-piles','Заводские железобетонные сваи','GOST_RC_PILE'),
 ('foundation-waterproofing-membranes','Гидроизоляционные мембраны подземных конструкций','SP250');
INSERT INTO material_categories (id,name,slug,status,level,sort_order,created_at,updated_at)
SELECT gen_random_uuid(),name,slug,'ACTIVE',0,0,now(),now() FROM a2c_classes
ON CONFLICT (slug) DO NOTHING;
DO $gate$ BEGIN
 IF EXISTS (SELECT 1 FROM a2c_classes s LEFT JOIN material_categories c ON c.slug=s.slug
  WHERE c.id IS NULL OR c.name<>s.name OR c.status<>'ACTIVE') THEN
  RAISE EXCEPTION 'A2 closure M1 material class conflict';
 END IF;
END $gate$;
INSERT INTO knowledge_resource_links (resource_id,category_id,link_type,status)
SELECT k.id,c.id,'APPLIES_TO','ACTIVE' FROM a2c_classes s
JOIN material_categories c ON c.slug=s.slug JOIN a2c_sources src ON src.code=s.source_code
JOIN knowledge_resources k ON k.source_url=src.url AND k.status='ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM knowledge_resource_links l
 WHERE l.resource_id=k.id AND l.category_id=c.id AND l.link_type='APPLIES_TO');

CREATE TEMP TABLE a2c_tech (
 code text NOT NULL, revision integer NOT NULL, family text NOT NULL,
 name text NOT NULL, description text NOT NULL, applicability text NOT NULL,
 exclusion text NOT NULL, before_work text NOT NULL, during_work text NOT NULL,
 after_work text NOT NULL, common_error text NOT NULL, project_values text NOT NULL,
 design_source text NOT NULL, work_source text NOT NULL,
 PRIMARY KEY(code,revision)
) ON COMMIT DROP;
INSERT INTO a2c_tech VALUES
 ('FND_STRIP_PRECAST_FBS_FL',2,'STRIP_FOUNDATIONS','Сборный ленточный фундамент из ФБС (ФЛ по проекту)',
  'Сборная несущая лента из сплошных блоков ФБС; плиты ФЛ применяются только по проекту. Те же блоки могут образовывать стену подвала, но ее назначение, нагрузки и защита рассматриваются отдельно.',
  'Применимость подтверждается изысканиями и расчетной схемой основания и сборной конструкции.',
  'Не считать ФЛ обязательными и не заменять проектные элементы произвольными ФБС.',
  'Проверить проект, основание, изделия и план монтажа.',
  'Контролировать последовательность ФЛ при их наличии, затем ФБС, положение и стыки.',
  'Принять положение, соединения и проектную защиту.',
  'Ошибка: считать монтаж ФЛ и ФБС одной и той же работой или универсальным узлом.',
  'Размеры, типы элементов, перевязка, раствор, усиление и водозащита по проекту.',
  'SP22','SP70'),
 ('FND_SLAB_RIBBED_RC',2,'SLAB_FOUNDATIONS','Ребристая железобетонная фундаментная плита',
  'Отдельная конструктивная схема с плитной частью и ребрами жесткости. Варианты ориентации ребер являются параметрами расчета; УШП может использовать ребристую конструкцию, но включает дополнительные системы.',
  'Для жилого здания применимость ребристой схемы подтверждают изыскания и расчет по проекту.',
  'Не переносить размеры и армирование из альбома конкретного производителя на другой объект.',
  'Проверить проектную схему ребер, основание, опалубку и армирование.',
  'Контролировать узлы ребро-плита и бетонирование по проекту и ППР.',
  'Принять конструкцию и обеспечить проектный уход за бетоном.',
  'Ошибка: трактовать ребра вверх и вниз как взаимозаменяемые без расчета.',
  'Ориентация, шаг, размеры ребер, плиты и армирование определяются проектом.',
  'SP22','TN_RIBBED'),
 ('FND_SLAB_USHP',1,'SLAB_FOUNDATIONS','Утепленная шведская плита (УШП)',
  'Композиционная фундаментная система: железобетонная плитно-ребристая часть, проектно выбранная теплоизоляция и согласованные проходки. Пол, отопление и сети остаются отдельными категориями и не дублируются здесь.',
  'Применяется в жилом проекте после проверки основания, теплотехники, несущей схемы и интерфейсов инженерных сетей.',
  'Не использовать брендовый альбом как универсальную схему армирования или нагрузки.',
  'Согласовать проектные отметки, подготовку основания, водозащиту, теплоизоляцию и проходки.',
  'Контролировать положение изоляции, опалубку, армирование и бетонирование конструктивной части.',
  'Принять конструкцию и передать согласованные интерфейсы исполнителям пола и инженерных систем.',
  'Ошибка: заливать плиту до согласования проходок и проектных интерфейсов.',
  'Геология, толщина, ребра, армирование, теплоизоляция и коммуникации задаются проектом.',
  'SP22','TN_USHP'),
 ('FND_UFF',1,'STRIP_FOUNDATIONS','Утепленный финский фундамент (УФФ)',
  'Композиционная система с ленточной несущей частью и утепленным сопряжением с полом по грунту. Сам пол, отопление, водоснабжение и канализация не копируются в фундаментную Technology.',
  'Применимость ленточной части, пола и изоляции устанавливается отдельными расчетами и согласованным проектом.',
  'Не применять конкретный вендорский разрез как универсальный для грунта или уровня воды.',
  'Согласовать основание, проект ленты, водо- и теплоизоляцию и интерфейс пола.',
  'Контролировать опалубку, армирование, бетон и сопряжения изоляции.',
  'Принять фундаментную часть и передать интерфейс пола и инженерных систем.',
  'Ошибка: считать теплоизолированный пол частью несущей ленты без отдельного расчета.',
  'Заложение, геометрия, бетон, армирование и утепление определяются проектом.',
  'SP22','TN_UFF'),
 ('FND_PILE_DRIVEN_RC',1,'PILE_FOUNDATIONS','Забивные заводские железобетонные сваи',
  'Заводские железобетонные сваи, погружаемые по проектной технологии. Подготовка головы и соединение с ростверком определяются отдельным узлом проекта.',
  'Применимость для жилого здания подтверждается изысканиями и проектом свайного основания.',
  'Не назначать тип, длину, сечение или усилие погружения без проекта и условий площадки.',
  'Проверить проект свайного поля, изделия, точки погружения и ППР.',
  'Контролировать положение свай и погружение по проектной технологии.',
  'Принять исполнительное положение, подготовить головы и соединение с ростверком.',
  'Ошибка: считать заводскую маркировку доказательством несущей способности на конкретном грунте.',
  'Количество, шаг, длина, сечение и несущая способность определяются проектом.',
  'SP24','SP45'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE',1,'BASEMENT_AND_SUBSTRUCTURE','Мембранная гидроизоляция подземной части',
  'Отдельная от мастичной система защиты с проектно выбранной битумно-полимерной или полимерной мембраной. Число слоев, фиксация и тип швов являются вариантами конкретной системы.',
  'Применяется к проектно выбранным подземным конструкциям при подтвержденных условиях воды, основания и совместимости материалов.',
  'Не переносить способ сварки полимерной мембраны на битумно-полимерную или наоборот.',
  'Проверить проектную систему, основание, проходки и техническую документацию выбранного материала.',
  'Контролировать непрерывность полотна, швы, примыкания и совместимость выбранного способа монтажа.',
  'Принять систему и защитить ее от последующих работ и обратной засыпки.',
  'Ошибка: закрыть непроверенный шов или проходку защитным слоем.',
  'Тип мембраны, число слоев, нахлест, способ крепления и защита по проекту и техдокументации.',
  'SP250','TN_POLYMER');

INSERT INTO module2_technologies
 (technology_code,revision,name,description,system_code,category_id,status,source_kind,input_blockers,supersedes_id)
SELECT s.code,s.revision,s.name,s.description,s.code,c.id,'ACTIVE','REVIEWED_CONTENT_SEED','[]'::jsonb,
 prior.id FROM a2c_tech s
JOIN module2_technology_categories c ON c.code=s.family AND c.status='ACTIVE'
LEFT JOIN module2_technologies prior ON prior.technology_code=s.code AND prior.revision=s.revision-1
WHERE (s.revision=1 OR prior.id IS NOT NULL)
ON CONFLICT (technology_code,revision) DO NOTHING;
DO $gate$ BEGIN
 IF (SELECT count(*) FROM a2c_tech)<>(SELECT count(*) FROM a2c_tech s
  JOIN module2_technology_categories c ON c.code=s.family
  JOIN module2_technologies t ON t.technology_code=s.code AND t.revision=s.revision
  WHERE t.name=s.name AND t.description=s.description AND t.category_id=c.id
   AND t.status='ACTIVE' AND (s.revision=1 OR t.supersedes_id IS NOT NULL)) THEN
  RAISE EXCEPTION 'A2 closure Technology conflict or missing prior revision';
 END IF;
END $gate$;

CREATE TEMP TABLE a2c_requirements (
 tech text NOT NULL, code text NOT NULL, class_slug text NOT NULL, role text NOT NULL,
 notes text NOT NULL, source_code text NOT NULL, PRIMARY KEY(tech,code)
) ON COMMIT DROP;
INSERT INTO a2c_requirements VALUES
 ('FND_STRIP_PRECAST_FBS_FL','FBS','foundation-fbs-blocks','PRECAST_BLOCK','Сплошные ФБС по проектной схеме.','GOST_FBS'),
 ('FND_STRIP_PRECAST_FBS_FL','FL','foundation-fl-slabs','FOOTING_SLAB','ФЛ только при назначении проектом.','GOST_FL'),
 ('FND_STRIP_PRECAST_FBS_FL','MORTAR','foundation-masonry-mortar','ASSEMBLY_JOINT','Раствор и стыки по проекту.','SP70'),
 ('FND_STRIP_PRECAST_FBS_FL','WATERPROOFING','foundation-waterproofing','WATERPROOFING','Защита только по проекту.','SP250'),
 ('FND_SLAB_RIBBED_RC','CONCRETE','foundation-structural-concrete','CONCRETE','Свойства бетона по проекту.','GOST_CONCRETE'),
 ('FND_SLAB_RIBBED_RC','REBAR','foundation-reinforcing-steel','REINFORCEMENT','Схема ребер и плиты по расчету.','GOST_REBAR'),
 ('FND_SLAB_RIBBED_RC','FORMWORK','foundation-formwork','RIB_FORMWORK','Форма ребер по проекту и ППР.','TN_RIBBED'),
 ('FND_SLAB_USHP','CONCRETE','foundation-structural-concrete','CONCRETE','Свойства по проекту.','GOST_CONCRETE'),
 ('FND_SLAB_USHP','REBAR','foundation-reinforcing-steel','REINFORCEMENT','Армирование по расчету.','GOST_REBAR'),
 ('FND_SLAB_USHP','XPS','foundation-xps-insulation','THERMAL_PROTECTION','Характеристики и толщина по проекту.','SP50'),
 ('FND_SLAB_USHP','WATERPROOFING','foundation-waterproofing','WATERPROOFING','Система только по проекту.','SP250'),
 ('FND_UFF','CONCRETE','foundation-structural-concrete','CONCRETE','Несущая лента по проекту.','GOST_CONCRETE'),
 ('FND_UFF','REBAR','foundation-reinforcing-steel','REINFORCEMENT','Армирование ленты по расчету.','GOST_REBAR'),
 ('FND_UFF','XPS','foundation-xps-insulation','THERMAL_PROTECTION','Тепловой контур по проекту.','SP50'),
 ('FND_UFF','WATERPROOFING','foundation-waterproofing','WATERPROOFING','Система по проекту.','SP250'),
 ('FND_PILE_DRIVEN_RC','PILE','foundation-rc-piles','FACTORY_RC_PILE','Тип и свойства заводской сваи по проекту.','GOST_RC_PILE'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE','MEMBRANE','foundation-waterproofing-membranes','WATERPROOFING','Вариант и характеристики мембраны по проекту и техдокументации.','SP250');
INSERT INTO module2_technology_material_requirements
 (technology_id,code,selector_kind,material_role_code,material_category_id,notes)
SELECT t.id,s.code,'MATERIAL_CLASS',s.role,c.id,s.notes FROM a2c_requirements s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
JOIN material_categories c ON c.slug=s.class_slug AND c.status='ACTIVE'
ON CONFLICT (technology_id,code) DO NOTHING;

CREATE TEMP TABLE a2c_layers (
 tech text NOT NULL, position integer NOT NULL, role text NOT NULL,
 requirement_code text NOT NULL, mandatory boolean NOT NULL, notes text NOT NULL,
 PRIMARY KEY(tech,position)
) ON COMMIT DROP;
INSERT INTO a2c_layers VALUES
 ('FND_STRIP_PRECAST_FBS_FL',1,'PREFABRICATED_FOOTING','FL',false,'ФЛ условны по проекту.'),
 ('FND_STRIP_PRECAST_FBS_FL',2,'LOAD_BEARING_BLOCKS','FBS',true,'Положение и опирание ФБС по проекту.'),
 ('FND_STRIP_PRECAST_FBS_FL',3,'ASSEMBLY_JOINTS','MORTAR',true,'Стыки и раствор по проекту.'),
 ('FND_STRIP_PRECAST_FBS_FL',4,'SUBSTRUCTURE_PROTECTION','WATERPROOFING',false,'Защита только по проекту.'),
 ('FND_SLAB_RIBBED_RC',1,'SLAB_AND_RIBS','CONCRETE',true,'Геометрия по расчету.'),
 ('FND_SLAB_RIBBED_RC',2,'RIB_AND_SLAB_REINFORCEMENT','REBAR',true,'Армирование по проекту.'),
 ('FND_SLAB_RIBBED_RC',3,'RIB_FORM','FORMWORK',false,'Форма ребер по проекту.'),
 ('FND_SLAB_USHP',1,'INSULATED_BASE','XPS',true,'Теплотехника и прочность по проекту.'),
 ('FND_SLAB_USHP',2,'RIBBED_RC_FOUNDATION','CONCRETE',true,'Несущая часть по расчету.'),
 ('FND_SLAB_USHP',3,'STRUCTURAL_REINFORCEMENT','REBAR',true,'Армирование по проекту.'),
 ('FND_SLAB_USHP',4,'WATER_PROTECTION','WATERPROOFING',false,'Водозащита по проекту.'),
 ('FND_UFF',1,'LOAD_BEARING_STRIP','CONCRETE',true,'Несущая лента по расчету.'),
 ('FND_UFF',2,'STRIP_REINFORCEMENT','REBAR',true,'Армирование по проекту.'),
 ('FND_UFF',3,'THERMAL_INTERFACE','XPS',true,'Сопряжение с полом, не сам пол.'),
 ('FND_UFF',4,'WATER_PROTECTION','WATERPROOFING',false,'Водозащита по проекту.'),
 ('FND_PILE_DRIVEN_RC',1,'FACTORY_RC_PILE','PILE',true,'Тип и геометрия по проекту.'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE',1,'MEMBRANE_SYSTEM','MEMBRANE',true,'Тип, число слоев и швы по выбранной системе.');
INSERT INTO module2_technology_layers
 (technology_id,position,functional_role,material_requirement_id,is_mandatory,notes)
SELECT t.id,s.position,s.role,r.id,s.mandatory,s.notes FROM a2c_layers s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.requirement_code
ON CONFLICT (technology_id,position) DO NOTHING;

CREATE TEMP TABLE a2c_steps (
 tech text NOT NULL, position integer NOT NULL, work_code text NOT NULL,
 applicability text NOT NULL, instruction text NOT NULL, source_code text NOT NULL,
 PRIMARY KEY(tech,position)
) ON COMMIT DROP;
INSERT INTO a2c_steps VALUES
 ('FND_STRIP_PRECAST_FBS_FL',1,'foundations_concrete_montazh_fundamentnyh_plit_fl','Только если ФЛ есть в проекте','Смонтировать и принять ФЛ по проектной схеме до монтажа блоков.','GOST_FL'),
 ('FND_STRIP_PRECAST_FBS_FL',2,'foundations_concrete_montazh_blokov_fbs','По проекту','Смонтировать ФБС с проектным опиранием и соединениями; для стены подвала применять отдельный контекст защиты.','GOST_FBS'),
 ('FND_STRIP_PRECAST_FBS_FL',3,'foundations_concrete_gidroizolyaciya_fundamenta','Если предусмотрено проектом','Выполнить выбранную систему защиты.','SP250'),
 ('FND_SLAB_RIBBED_RC',1,'foundations_concrete_montazh_opalubki_fundamenta','По проекту ребер','Подготовить форму ребер и плитной части.','TN_RIBBED'),
 ('FND_SLAB_RIBBED_RC',2,'reinforcement_armirovanie_plity','По проекту','Смонтировать и принять арматуру ребер и плиты.','SP63'),
 ('FND_SLAB_RIBBED_RC',3,'foundations_concrete_betonirovanie_konstrukciy','После приемки','Выполнить проектную последовательность бетонирования и уход.','SP70'),
 ('FND_SLAB_USHP',1,'foundations_concrete_uteplenie_fundamenta','По теплотехническому проекту','Смонтировать проектную теплоизоляцию конструктивной части.','TN_USHP'),
 ('FND_SLAB_USHP',2,'foundations_concrete_montazh_opalubki_fundamenta','По проекту','Подготовить форму плитно-ребристой части и согласованные проходки.','TN_USHP'),
 ('FND_SLAB_USHP',3,'reinforcement_armirovanie_plity','По проекту','Смонтировать и принять армирование несущей части.','SP63'),
 ('FND_SLAB_USHP',4,'foundations_concrete_betonirovanie_konstrukciy','После приемки','Выполнить бетонирование и уход по ППР; сети и полы не включены в этот WorkStep.','SP70'),
 ('FND_UFF',1,'foundations_concrete_montazh_opalubki_fundamenta','По проекту','Подготовить форму несущей ленты.','TN_UFF'),
 ('FND_UFF',2,'reinforcement_armirovanie_fundamenta','По проекту','Смонтировать и принять армирование ленты.','SP63'),
 ('FND_UFF',3,'foundations_concrete_betonirovanie_konstrukciy','После приемки','Выполнить бетонирование несущей части и уход.','SP70'),
 ('FND_UFF',4,'foundations_concrete_uteplenie_fundamenta','По теплотехническому проекту','Выполнить теплоизоляционное сопряжение; пол по грунту остается другой категорией.','TN_UFF'),
 ('FND_PILE_DRIVEN_RC',1,'foundations_concrete_pogruzhenie_zhelezobetonnyh_svay','По проекту свайного поля','Погрузить проектные заводские ЖБ сваи, проконтролировать положение и подготовить головы к ростверку.','SP45'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE',1,'foundations_concrete_gidroizolyaciya_fundamenta','По выбранной проектом системе','Подготовить основание, смонтировать мембрану и принять швы, примыкания и защиту.','SP71');
INSERT INTO module2_technology_work_steps
 (technology_id,position,work_code,applicability_expression,instructions)
SELECT t.id,s.position,s.work_code,s.applicability,s.instruction FROM a2c_steps s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
ON CONFLICT (technology_id,position) DO NOTHING;

CREATE TEMP TABLE a2c_nodes (
 tech text NOT NULL, code text NOT NULL, kind text NOT NULL, name text NOT NULL,
 description text NOT NULL, target_code text, source_code text NOT NULL,
 PRIMARY KEY(tech,code)
) ON COMMIT DROP;
INSERT INTO a2c_nodes VALUES
 ('FND_STRIP_PRECAST_FBS_FL','FL_FBS_BEARING','INTERFACE','Опирание ФБС на ФЛ','ФЛ применяются только по проекту; узел опирания и стыки проектные.',NULL,'GOST_FL'),
 ('FND_STRIP_PRECAST_FBS_FL','BLOCK_JOINT','INTERFACE','Стык сборных элементов','Соединения и перевязка по проекту.',NULL,'SP70'),
 ('FND_STRIP_PRECAST_FBS_FL','BASEMENT_WALL_APPLICATION','RELATED_CATEGORY','Стена подвала из ФБС','Те же блоки могут работать как стена подвала; нагрузки, сопряжения и водозащита по проекту.','BASEMENT_AND_SUBSTRUCTURE','GOST_FBS'),
 ('FND_STRIP_PRECAST_FBS_FL','PLINTH_APPLICATION','INTERFACE','Цокольный участок','Цоколь является участком стены или фундамента, не отдельной технологией.',NULL,'SP22'),
 ('FND_SLAB_RIBBED_RC','RIB_ORIENTATION','DESIGN_VARIANT','Ориентация ребер','Направление и геометрия ребер зависят от расчета, не отдельная Technology.',NULL,'TN_RIBBED'),
 ('FND_SLAB_RIBBED_RC','RIB_SLAB_JUNCTION','INTERFACE','Сопряжение ребра и плиты','Армирование и последовательность по проекту.',NULL,'SP63'),
 ('FND_SLAB_RIBBED_RC','USHP_COMPOSITION','RELATED_TECHNOLOGY','УШП как композиция','УШП включает ребристую схему только когда она предусмотрена проектом.','FND_SLAB_USHP','TN_USHP'),
 ('FND_SLAB_USHP','SLAB_EDGE','INTERFACE','Край и ребро плиты','Опалубка, армирование, тепло- и водозащита по проекту.',NULL,'TN_USHP'),
 ('FND_SLAB_USHP','UTILITY_PENETRATION','INTERFACE','Проходки коммуникаций','Место, гильзы и герметизация согласуются до бетонирования.',NULL,'TN_USHP'),
 ('FND_SLAB_USHP','FLOOR_INTERFACE','RELATED_CATEGORY','Пол по грунту','Конструкция пола относится к FLOORS_AND_STAIRS.','FLOORS_AND_STAIRS','TN_USHP'),
 ('FND_SLAB_USHP','HEATING_INTERFACE','RELATED_CATEGORY','Отопление','Теплый пол и отопление относятся к HEATING_AND_DHW.','HEATING_AND_DHW','TN_USHP'),
 ('FND_SLAB_USHP','WATER_INTERFACE','RELATED_CATEGORY','Вода и канализация','Сети относятся к WATER_AND_SEWER.','WATER_AND_SEWER','TN_USHP'),
 ('FND_UFF','STRIP_FLOOR_JUNCTION','INTERFACE','Сопряжение ленты и пола','Конструктивный и тепловой узел по проекту, не дублирование пола.',NULL,'TN_UFF'),
 ('FND_UFF','FLOOR_INTERFACE','RELATED_CATEGORY','Пол по грунту','Пол относится к FLOORS_AND_STAIRS.','FLOORS_AND_STAIRS','TN_UFF'),
 ('FND_UFF','HEATING_INTERFACE','RELATED_CATEGORY','Отопление','Система подогрева относится к HEATING_AND_DHW.','HEATING_AND_DHW','TN_UFF'),
 ('FND_UFF','WATER_INTERFACE','RELATED_CATEGORY','Вода и канализация','Сети относятся к WATER_AND_SEWER.','WATER_AND_SEWER','TN_UFF'),
 ('FND_UFF','SITE_INTERFACE','RELATED_CATEGORY','Дренаж и отмостка','Участок и наружный дренаж относятся к SITE_WORKS.','SITE_WORKS','TN_UFF'),
 ('FND_PILE_DRIVEN_RC','PILE_HEAD','INTERFACE','Голова забивной сваи','Подготовка и соединение с ростверком по проекту.',NULL,'SP24'),
 ('FND_PILE_DRIVEN_RC','GRILLAGE_INTERFACE','RELATED_TECHNOLOGY','Свайно-ростверковая система','Ростверк является отдельной проектной системой.','FND_PILE_GRILLAGE','SP24'),
 ('FND_PILE_DRIVEN_RC','PREPARATION_INTERFACE','RELATED_CATEGORY','Подготовка площадки','Подготовительные земляные работы относятся к PREPARATION.','PREPARATION','SP45'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE','MEMBRANE_SEAM','INTERFACE','Шов мембраны','Способ соединения зависит от выбранного материала и системы.',NULL,'TN_POLYMER'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE','UTILITY_PENETRATION','INTERFACE','Проходка через мембрану','Герметизация проходки по проектному узлу.',NULL,'SP250'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE','PROTECTIVE_LAYER','INTERFACE','Защита мембраны','Защита от последующих работ и обратной засыпки по проекту.',NULL,'SP250'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE','SITE_DRAINAGE','RELATED_CATEGORY','Наружный дренаж','Система дренажа относится к SITE_WORKS.','SITE_WORKS','SP250');
INSERT INTO module2_technology_nodes (technology_id,code,node_type,name,description,conditions)
SELECT t.id,s.code,s.kind,s.name,s.description,
 CASE WHEN s.kind='RELATED_CATEGORY' THEN jsonb_build_object('category_code',s.target_code)
      WHEN s.kind='RELATED_TECHNOLOGY' THEN jsonb_build_object('technology_code',s.target_code)
      ELSE '{}'::jsonb END
FROM a2c_nodes s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
ON CONFLICT (technology_id,code) DO NOTHING;

CREATE TEMP TABLE a2c_rules (
 tech text NOT NULL, code text NOT NULL, section text NOT NULL,
 message text NOT NULL, source_code text NOT NULL, PRIMARY KEY(tech,code)
) ON COMMIT DROP;
INSERT INTO a2c_rules
SELECT s.code,x.rule_code,x.section,x.message,x.source_code
FROM a2c_tech s CROSS JOIN LATERAL (VALUES
 ('APPLICABILITY','applicability',s.applicability,s.design_source),
 ('EXCLUSIONS','exclusions',s.exclusion,s.design_source),
 ('QUALITY_BEFORE','quality_before',s.before_work,s.work_source),
 ('QUALITY_DURING','quality_during',s.during_work,s.work_source),
 ('QUALITY_AFTER','quality_after',s.after_work,s.work_source),
 ('COMMON_ERROR','common_error',s.common_error,s.work_source),
 ('PROJECT_DEPENDENT','project_dependent',s.project_values,s.design_source)
) AS x(rule_code,section,message,source_code);
INSERT INTO module2_knowledge_rules
 (technology_id,rule_code,revision,scope_kind,conditions,outcome_type,outcome_payload,status,source_kind,blockers)
SELECT t.id,s.code,1,'TECHNOLOGY','[]'::jsonb,'INFORMATION',
 jsonb_build_object('section',s.section,'message',s.message),'ACTIVE','REVIEWED_CONTENT_SEED','[]'::jsonb
FROM a2c_rules s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
ON CONFLICT (technology_id,rule_code,revision) DO NOTHING;

CREATE TEMP TABLE a2c_evidence (
 tech text NOT NULL, source_code text NOT NULL, target_kind text NOT NULL,
 target_reference text, interpretation text NOT NULL
) ON COMMIT DROP;
INSERT INTO a2c_evidence SELECT s.code,s.design_source,'TECHNOLOGY',NULL,'Scope and project-dependent design, not a universal recipe.' FROM a2c_tech s;
INSERT INTO a2c_evidence SELECT s.code,
 CASE s.code WHEN 'FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE' THEN 'TN_BITUMEN'
             WHEN 'FND_STRIP_PRECAST_FBS_FL' THEN 'GOST_FBS'
             ELSE s.work_source END,
 'TECHNOLOGY',NULL,'System or product-specific technical context; project selection remains required.'
FROM a2c_tech s;
INSERT INTO a2c_evidence SELECT s.tech,s.source_code,'MATERIAL_REQUIREMENT',r.id::text,s.notes
FROM a2c_requirements s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.code;
INSERT INTO a2c_evidence SELECT s.tech,r.source_code,'LAYER',l.id::text,s.notes
FROM a2c_layers s JOIN a2c_requirements r ON r.tech=s.tech AND r.code=s.requirement_code
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
JOIN module2_technology_layers l ON l.technology_id=t.id AND l.position=s.position;
INSERT INTO a2c_evidence SELECT s.tech,s.source_code,'WORK_STEP',w.id::text,s.instruction
FROM a2c_steps s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
JOIN module2_technology_work_steps w ON w.technology_id=t.id AND w.position=s.position;
INSERT INTO a2c_evidence SELECT s.tech,s.source_code,'NODE',n.id::text,s.description
FROM a2c_nodes s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
JOIN module2_technology_nodes n ON n.technology_id=t.id AND n.code=s.code;
INSERT INTO a2c_evidence SELECT s.tech,s.source_code,'KNOWLEDGE_RULE',r.id::text,s.message
FROM a2c_rules s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
JOIN module2_knowledge_rules r ON r.technology_id=t.id AND r.rule_code=s.code AND r.revision=1;
INSERT INTO module2_technology_evidence_references
 (technology_id,knowledge_resource_id,target_kind,target_reference,interpretation)
SELECT t.id,k.id,s.target_kind,s.target_reference,s.interpretation FROM a2c_evidence s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
 WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
JOIN a2c_sources src ON src.code=s.source_code
JOIN knowledge_resources k ON k.source_url=src.url AND k.status='ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM module2_technology_evidence_references e
 WHERE e.technology_id=t.id AND e.knowledge_resource_id=k.id AND e.target_kind=s.target_kind
 AND e.target_reference IS NOT DISTINCT FROM s.target_reference);

DO $gate$ BEGIN
 IF (SELECT count(*) FROM a2c_requirements)<>(SELECT count(*) FROM a2c_requirements s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
   WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
  JOIN material_categories c ON c.slug=s.class_slug AND c.status='ACTIVE'
  JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.code
  WHERE r.material_category_id=c.id AND r.selector_kind='MATERIAL_CLASS' AND r.notes=s.notes) THEN
  RAISE EXCEPTION 'A2 closure material requirement conflict';
 END IF;
 IF (SELECT count(*) FROM a2c_layers)<>(SELECT count(*) FROM a2c_layers s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
   WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
  JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.requirement_code
  JOIN module2_technology_layers l ON l.technology_id=t.id AND l.position=s.position
  WHERE l.material_requirement_id=r.id AND l.functional_role=s.role AND l.is_mandatory=s.mandatory) THEN
  RAISE EXCEPTION 'A2 closure layer conflict';
 END IF;
 IF (SELECT count(*) FROM a2c_steps)<>(SELECT count(*) FROM a2c_steps s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
   WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
  JOIN module2_technology_work_steps w ON w.technology_id=t.id AND w.position=s.position
  WHERE w.work_code=s.work_code AND w.instructions=s.instruction) THEN
  RAISE EXCEPTION 'A2 closure work step conflict';
 END IF;
 IF (SELECT count(*) FROM a2c_nodes)<>(SELECT count(*) FROM a2c_nodes s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
   WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
  JOIN module2_technology_nodes n ON n.technology_id=t.id AND n.code=s.code
  WHERE n.node_type=s.kind AND n.name=s.name AND n.description=s.description) THEN
  RAISE EXCEPTION 'A2 closure node conflict';
 END IF;
 IF (SELECT count(*) FROM a2c_rules)<>(SELECT count(*) FROM a2c_rules s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
   WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
  JOIN module2_knowledge_rules r ON r.technology_id=t.id AND r.rule_code=s.code AND r.revision=1
  WHERE r.status='ACTIVE' AND r.outcome_payload->>'section'=s.section
   AND r.outcome_payload->>'message'=s.message) THEN
  RAISE EXCEPTION 'A2 closure rule conflict';
 END IF;
 IF (SELECT count(*) FROM a2c_evidence)<>(SELECT count(*) FROM a2c_evidence s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=CASE
   WHEN s.tech IN ('FND_STRIP_PRECAST_FBS_FL','FND_SLAB_RIBBED_RC') THEN 2 ELSE 1 END
  JOIN a2c_sources src ON src.code=s.source_code
  JOIN knowledge_resources k ON k.source_url=src.url AND k.status='ACTIVE'
  JOIN module2_technology_evidence_references e ON e.technology_id=t.id
   AND e.knowledge_resource_id=k.id AND e.target_kind=s.target_kind
   AND e.target_reference IS NOT DISTINCT FROM s.target_reference) THEN
  RAISE EXCEPTION 'A2 closure evidence conflict';
 END IF;
END $gate$;

UPDATE module2_technologies old SET status='ARCHIVED'
WHERE old.technology_code IN ('FND_SLAB_RIBBED_RC','FND_STRIP_PRECAST_FBS_FL')
 AND old.revision=1 AND old.status IN ('DRAFT','ACTIVE')
AND EXISTS (SELECT 1 FROM module2_technologies current
 WHERE current.technology_code=old.technology_code AND current.revision=2
  AND current.status='ACTIVE' AND current.supersedes_id=old.id);

CREATE TEMP TABLE a2c_inventory (
 code text PRIMARY KEY, final_state text NOT NULL, target_code text
) ON COMMIT DROP;
INSERT INTO a2c_inventory VALUES
 ('FND_STRIP_MONOLITHIC_RC','ACTIVE','FND_STRIP_MONOLITHIC_RC'),
 ('FND_STRIP_PRECAST_FBS_FL','ACTIVE','FND_STRIP_PRECAST_FBS_FL'),
 ('FND_STRIP_GEOMETRY_VARIANTS','PARAMETER',NULL),
 ('FND_SLAB_MONOLITHIC_RC','ACTIVE','FND_SLAB_MONOLITHIC_RC'),
 ('FND_SLAB_RIBBED_RC','ACTIVE','FND_SLAB_RIBBED_RC'),
 ('FND_SLAB_RIB_ORIENTATION','PARAMETER',NULL),
 ('FND_SLAB_USHP','ACTIVE','FND_SLAB_USHP'),
 ('FND_UFF','ACTIVE','FND_UFF'),
 ('FND_PILE_DRIVEN_RC','ACTIVE','FND_PILE_DRIVEN_RC'),
 ('FND_PILE_BORED_RC','ACTIVE','FND_PILE_BORED_RC'),
 ('FND_PILE_SCREW','ACTIVE','FND_PILE_SCREW'),
 ('FND_PILE_GRILLAGE','ACTIVE','FND_PILE_GRILLAGE'),
 ('FND_COLUMN_CONCRETE_RC','ACTIVE','FND_COLUMN_CONCRETE_RC'),
 ('FND_BASEMENT_WALL_MONOLITHIC','ACTIVE','FND_BASEMENT_WALL_MONOLITHIC'),
 ('FND_BASEMENT_WALL_PRECAST','REUSED','FND_STRIP_PRECAST_FBS_FL'),
 ('FND_PLINTH_WALL','COMPONENT','FND_STRIP_PRECAST_FBS_FL'),
 ('FND_FOUNDATION_BEAM','OUT_OF_SCOPE',NULL),
 ('FND_SUBSTRUCTURE_WATERPROOFING','ACTIVE','FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE'),
 ('FND_SUBSTRUCTURE_INSULATION','ACTIVE','FND_SUBSTRUCTURE_INSULATION_XPS'),
 ('FND_WATERPROOFING_PROTECTION','NODE','FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE'),
 ('FND_UTILITY_PENETRATION','NODE','FND_BASEMENT_WALL_MONOLITHIC');
DO $gate$ DECLARE item record; current_id uuid; BEGIN
 IF (SELECT count(*) FROM a2c_inventory)<>21 THEN
  RAISE EXCEPTION 'FOUNDATIONS inventory must have exactly 21 final decisions';
 END IF;
 IF EXISTS (SELECT 1 FROM a2c_inventory WHERE final_state NOT IN
  ('ACTIVE','PARAMETER','REUSED','COMPONENT','OUT_OF_SCOPE','NODE')) THEN
  RAISE EXCEPTION 'FOUNDATIONS inventory has unresolved state';
 END IF;
 FOR item IN SELECT * FROM a2c_inventory WHERE target_code IS NOT NULL LOOP
  SELECT id INTO current_id FROM module2_technologies
  WHERE technology_code=item.target_code AND status='ACTIVE'
  ORDER BY revision DESC LIMIT 1;
  IF current_id IS NULL THEN
   RAISE EXCEPTION 'FOUNDATIONS target is not ACTIVE: %', item.code;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM module2_technology_material_requirements WHERE technology_id=current_id)
   OR NOT EXISTS (SELECT 1 FROM module2_technology_layers WHERE technology_id=current_id)
   OR NOT EXISTS (SELECT 1 FROM module2_technology_work_steps WHERE technology_id=current_id)
   OR NOT EXISTS (SELECT 1 FROM module2_technology_nodes WHERE technology_id=current_id)
   OR NOT EXISTS (SELECT 1 FROM module2_knowledge_rules WHERE technology_id=current_id AND status='ACTIVE')
   OR NOT EXISTS (SELECT 1 FROM module2_technology_evidence_references WHERE technology_id=current_id) THEN
   RAISE EXCEPTION 'FOUNDATIONS target lacks content: %', item.code;
  END IF;
 END LOOP;
 IF NOT EXISTS (SELECT 1 FROM module2_technology_nodes n JOIN module2_technologies t ON t.id=n.technology_id
  WHERE t.technology_code='FND_STRIP_PRECAST_FBS_FL' AND t.revision=2
   AND n.code='BASEMENT_WALL_APPLICATION' AND n.conditions->>'category_code'='BASEMENT_AND_SUBSTRUCTURE') THEN
  RAISE EXCEPTION 'Precast basement wall reuse link is absent';
 END IF;
 IF EXISTS (SELECT 1 FROM module2_technologies WHERE technology_code IN
  ('FND_SLAB_RIBBED_RC','FND_STRIP_PRECAST_FBS_FL') AND revision=1 AND status<>'ARCHIVED') THEN
  RAISE EXCEPTION 'Superseded foundations revision remains published';
 END IF;
 IF (SELECT count(DISTINCT c.code) FROM module2_technologies t
  JOIN module2_technology_categories c ON c.id=t.category_id
  WHERE t.status='ACTIVE' AND c.code IN ('STRIP_FOUNDATIONS','SLAB_FOUNDATIONS',
   'PILE_FOUNDATIONS','PILE_GRILLAGE_FOUNDATIONS','COLUMN_FOUNDATIONS','BASEMENT_AND_SUBSTRUCTURE'))<>6 THEN
  RAISE EXCEPTION 'Not every FOUNDATIONS family has ACTIVE content';
 END IF;
END $gate$;

UPDATE module2_technology_categories SET content_status='CONTENT_COMPLETE'
WHERE code IN ('STRIP_FOUNDATIONS','SLAB_FOUNDATIONS','PILE_FOUNDATIONS',
 'PILE_GRILLAGE_FOUNDATIONS','COLUMN_FOUNDATIONS','BASEMENT_AND_SUBSTRUCTURE','FOUNDATIONS')
AND content_status<>'CONTENT_COMPLETE';
COMMIT;
