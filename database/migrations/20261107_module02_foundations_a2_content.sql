-- A2 additive foundation content. The approved M1 Work Catalog is immutable.
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('houseplatform:m2-foundations-a2'));

CREATE TEMP TABLE a2_sources (
 code text PRIMARY KEY, title text NOT NULL, url text NOT NULL UNIQUE,
 scope text NOT NULL
) ON COMMIT DROP;
INSERT INTO a2_sources VALUES
 ('SP22','СП 22.13330.2016: основания зданий и сооружений','https://protect.gost.ru/sp/details/71e96332-a446-4a15-87a0-2db895479f61','Design scope; geometry and bearing capacity require a project'),
 ('SP24','СП 24.13330.2021: свайные фундаменты','https://protect.gost.ru/sp/details/1e90a34c-6379-4236-8256-38be93e29766','Pile-foundation design scope; check current amendments'),
 ('SP45','СП 45.13330.2017: земляные сооружения, основания и фундаменты','https://protect.gost.ru/sp/details/6b8a4ce8-2c63-46f8-8c16-6efec70cede8','Foundation execution scope; no numerical tolerances copied'),
 ('SP63','СП 63.13330.2018: бетонные и железобетонные конструкции','https://protect.gost.ru/sp/details/8b67e228-0c9f-4a62-b562-964b3a58c667','RC design scope; reinforcement is project-dependent'),
 ('SP70','СП 70.13330.2012: производство и приемка несущих конструкций','https://protect.gost.ru/sp/details/2239acf1-711f-4f1f-aaa7-902fa06a8a60','Official status; check current amendments for project use'),
 ('SP250','СП 250.1325800.2016: защита от подземных вод','https://protect.gost.ru/sp/details/990885bc-664d-4329-b54c-5aa3d581c20d','Waterproofing design scope for buried residential structures'),
 ('SP50','СП 50.13330.2024: тепловая защита зданий','https://protect.gost.ru/sp/details/5081dae9-9ee9-455f-80e8-d093d495361c','Thermal-design scope; no universal thickness'),
 ('GOST_CONCRETE','ГОСТ 26633-2015: тяжелые и мелкозернистые бетоны','https://protect.gost.ru/gost/details/b9da3cd9-2fb4-4473-9553-3979ad6be453','Material class, not a prescribed grade'),
 ('GOST_REBAR','ГОСТ 34028-2016: арматурный прокат','https://protect.gost.ru/gost/details/50236208-68a9-443c-974d-4cc3dc04d15a','Material class, not a prescribed diameter'),
 ('GOST_SCREW','ГОСТ Р 59106-2020: сваи стальные винтовые','https://protect.gost.ru/gost/details/a9b16798-7882-4820-b838-c23c3d680e2e','Steel screw-pile product scope, not a universal pile specification'),
 ('GOST_XPS','ГОСТ 32310-2020: изделия из экструзионного пенополистирола','https://protect.gost.ru/gost/details/e81b18f6-742d-417b-83c7-c361be521951','XPS material characteristics; below-grade suitability is selected by project'),
 ('GOST_MASTIC','ГОСТ 30693-2000: мастики кровельные и гидроизоляционные','https://protect.gost.ru/gost/details/8bea94a2-17da-452d-8965-915ba60168a4','Waterproofing mastic material scope; system selection is project-dependent');

INSERT INTO knowledge_resources (resource_type,title,resource_url,source_url,metadata_json,status)
SELECT 'STANDARD_REFERENCE',title,url,url,
 jsonb_build_object('package','M2-FOUNDATIONS-A2','source_code',code,'evidence_scope',scope,'reviewed_on','2026-11-07'), 'ACTIVE'
FROM a2_sources s WHERE NOT EXISTS (SELECT 1 FROM knowledge_resources k WHERE k.source_url=s.url);
DO $gate$ BEGIN
 IF EXISTS (SELECT 1 FROM a2_sources s LEFT JOIN knowledge_resources k ON k.source_url=s.url AND k.status='ACTIVE'
            GROUP BY s.code HAVING count(k.id)<>1) THEN
  RAISE EXCEPTION 'A2 source is missing, duplicate or inactive';
 END IF;
END $gate$;

CREATE TEMP TABLE a2_classes (slug text PRIMARY KEY, name text NOT NULL, source_code text NOT NULL) ON COMMIT DROP;
INSERT INTO a2_classes VALUES
 ('foundation-structural-concrete','Конструкционный бетон для фундаментов','GOST_CONCRETE'),
 ('foundation-reinforcing-steel','Арматурный прокат для железобетона','GOST_REBAR'),
 ('foundation-formwork','Опалубочные материалы и системы','SP70'),
 ('foundation-waterproofing','Гидроизоляционные материалы подземных конструкций','SP250'),
 ('foundation-screw-piles','Стальные винтовые сваи','GOST_SCREW'),
 ('foundation-bored-pile-casing','Обсадные элементы буронабивных свай','SP45'),
 ('foundation-waterproofing-mastics','Гидроизоляционные мастики для подземных конструкций','GOST_MASTIC'),
 ('foundation-xps-insulation','Плиты XPS для подземной теплоизоляции','GOST_XPS');
INSERT INTO material_categories (id,name,slug,status,level,sort_order,created_at,updated_at)
SELECT gen_random_uuid(),name,slug,'ACTIVE',0,0,now(),now() FROM a2_classes
ON CONFLICT (slug) DO NOTHING;
DO $gate$ BEGIN
 IF EXISTS (SELECT 1 FROM a2_classes s LEFT JOIN material_categories c ON c.slug=s.slug
            WHERE c.id IS NULL OR c.name<>s.name OR c.status<>'ACTIVE') THEN
  RAISE EXCEPTION 'A2 M1 material class conflict';
 END IF;
END $gate$;
INSERT INTO knowledge_resource_links (resource_id,category_id,link_type,status)
SELECT k.id,c.id,'APPLIES_TO','ACTIVE' FROM a2_classes s
JOIN material_categories c ON c.slug=s.slug
JOIN a2_sources src ON src.code=s.source_code
JOIN knowledge_resources k ON k.source_url=src.url AND k.status='ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM knowledge_resource_links l WHERE l.resource_id=k.id AND l.category_id=c.id AND l.link_type='APPLIES_TO');

CREATE TEMP TABLE a2_tech (
 code text PRIMARY KEY, family text NOT NULL, name text NOT NULL, description text NOT NULL,
 applicability text NOT NULL, exclusion text NOT NULL, before_work text NOT NULL,
 during_work text NOT NULL, after_work text NOT NULL, common_error text NOT NULL,
 project_values text NOT NULL, design_source text NOT NULL, work_source text NOT NULL
) ON COMMIT DROP;
INSERT INTO a2_tech VALUES
 ('FND_PILE_BORED_RC','PILE_FOUNDATIONS','Буронабивные железобетонные сваи',
  'Свая из бетона, уложенного в подготовленную скважину с проектным армированием. Способ удержания стенок скважины и бетонирования выбирается по грунту и воде; это не универсальная инструкция для сложных специальных свай.',
  'Применяется для жилого здания только по результатам изысканий, расчета и проекта свайного основания.',
  'Не применять метод без подтверждения устойчивости скважины и проектной технологии работ.',
  'Проверить проект свайного поля, грунт, воду, допуск к бурению и решение об обсадке.',
  'Контролировать скважину, положение арматуры и непрерывность проектного бетонирования.',
  'Принять исполнительное положение и подготовить головы свай к проектному соединению с ростверком.',
  'Ошибка: считать обсадку всегда ненужной или заменять проектный контроль визуальной оценкой.',
  'Число, шаг, длина, диаметр, армирование и несущая способность задаются изысканиями и проектом.',
  'SP24','SP45'),
 ('FND_PILE_SCREW','PILE_FOUNDATIONS','Стальные винтовые сваи',
  'Заводские стальные винтовые сваи с трубчатым стволом; выбор типа, защита стали и соединение с обвязкой определяются проектом. Не равнозначны забивным или буронабивным сваям.',
  'Возможны для жилой или вспомогательной конструкции при подтвержденном проектном расчете и условиях площадки.',
  'Не назначать тип сваи, антикоррозионную защиту и несущую способность без проекта и данных среды.',
  'Проверить проект, маркировку элементов, защиту и точки установки.',
  'Контролировать положение и выбранный проектом способ погружения, не заменяя им приемочные критерии.',
  'Принять исполнительное положение, оголовки, соединения и защиту поврежденных участков.',
  'Ошибка: считать одинаковые сваи пригодными для любых грунтов и сред.',
  'Диаметр, длина, лопасти, количество, несущая способность и защита определяются проектом.',
  'SP24','GOST_SCREW'),
 ('FND_PILE_GRILLAGE','PILE_GRILLAGE_FOUNDATIONS','Монолитный железобетонный ростверк свайного фундамента',
  'Система объединения свай монолитным железобетонным ростверком. Выбор типа свай остается отдельной Technology; соединение и совместная работа назначаются проектом.',
  'Применяется с проектно совместимым свайным основанием и расчетной схемой передачи нагрузок.',
  'Не соединять произвольную сваю и ростверк без проектного узла.',
  'Проверить исполнительное положение и подготовку голов свай, опалубку и армирование.',
  'Контролировать проектные соединения, укладку и уход за бетоном.',
  'Принять ростверк и соединения по проектной документации.',
  'Ошибка: считать любую обвязку эквивалентом монолитного железобетонного ростверка.',
  'Размер, армирование, отметки, соединения и нагрузки рассчитываются проектом.',
  'SP24','SP70'),
 ('FND_COLUMN_CONCRETE_RC','COLUMN_FOUNDATIONS','Бетонные и железобетонные столбчатые фундаменты',
  'Отдельные бетонные или железобетонные опоры для проектно допустимой жилой или вспомогательной конструкции; армирование является вариантом расчетной схемы.',
  'Применимость устанавливается расчетом основания и конструкции для конкретной схемы нагрузок.',
  'Не считать отдельные столбы универсальным основанием для тяжелого жилого здания или сложных грунтов.',
  'Проверить проектные точки опирания и принятое основание.',
  'Контролировать форму, армирование при его наличии и укладку бетона.',
  'Принять положение опор и узлы передачи нагрузок.',
  'Ошибка: назначать шаг и сечение столбов по типовой картинке без расчета.',
  'Число, шаг, сечение, заложение и армирование определяются проектом.',
  'SP22','SP70'),
 ('FND_BASEMENT_WALL_MONOLITHIC','BASEMENT_AND_SUBSTRUCTURE','Монолитная железобетонная стена подвала',
  'Несущая или ограждающая монолитная железобетонная стена подземной части; ее связь с фундаментом и система защиты от воды являются проектными решениями.',
  'Применяется в проекте жилого здания с подвалом при подтвержденных грунтовых и гидрогеологических условиях.',
  'Не выбирать конструкцию стены и гидроизоляцию без расчета грунтового и водного воздействия.',
  'Проверить основание, сопряжение с фундаментом, опалубку и армирование.',
  'Контролировать проектные швы, положение арматуры и укладку бетона.',
  'Принять конструкцию, затем выполнить назначенную проектом защиту подземной части.',
  'Ошибка: нарушать стену поздними вводами коммуникаций без согласованного узла.',
  'Толщина, армирование, бетон, швы и водозащита определяются проектом.',
  'SP63','SP70'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_COATING','BASEMENT_AND_SUBSTRUCTURE','Мастичная гидроизоляция подземной части',
  'Мастичная система защиты проектно выбранных подземных поверхностей. Не подменяет рулонные, мембранные и конструкционные системы защиты от подземных вод.',
  'Применяется только там, где проект защиты от подземных вод допускает выбранную систему и материал.',
  'Не применять произвольную мастику без проверки воды, основания, сопряжений и паспорта системы.',
  'Подготовить и принять основание по проекту и технической документации системы.',
  'Контролировать непрерывность нанесения, сопряжения и проходки согласно проекту.',
  'Проверить сплошность и предусмотреть защиту покрытия до обратной засыпки.',
  'Ошибка: закрывать обратной засыпкой незащищенное или непроверенное покрытие.',
  'Тип системы, число слоев, расход и требуемая защита назначаются проектом.',
  'SP250','GOST_MASTIC'),
 ('FND_SUBSTRUCTURE_INSULATION_XPS','BASEMENT_AND_SUBSTRUCTURE','Теплоизоляция подземной части плитами XPS',
  'Теплоизоляционная система с плитами XPS для проектно выбранных подземных участков; не заменяет гидроизоляцию и не является универсальным слоем каждого фундамента.',
  'Применяется при теплотехнической необходимости и проверенной совместимости с водозащитой и средой.',
  'Не назначать толщину, способ крепления и защиту без расчета и проверки конкретной системы.',
  'Проверить готовность водозащиты и требуемые свойства плит.',
  'Контролировать расположение плит, примыкания и совместимость крепления с гидроизоляцией.',
  'До засыпки проверить непрерывность изоляции и предусмотренную защиту.',
  'Ошибка: повреждать гидроизоляцию крепежом без согласованного узла.',
  'Толщина, прочность, крепление и защита плит определяются проектом.',
  'SP50','GOST_XPS');

INSERT INTO module2_technologies (technology_code,revision,name,description,system_code,category_id,status,source_kind,input_blockers)
SELECT s.code,1,s.name,s.description,s.code,c.id,'ACTIVE','REVIEWED_CONTENT_SEED','[]'::jsonb
FROM a2_tech s JOIN module2_technology_categories c ON c.code=s.family AND c.status='ACTIVE'
ON CONFLICT (technology_code,revision) DO NOTHING;
DO $gate$ BEGIN
 IF (SELECT count(*) FROM a2_tech)<>(SELECT count(*) FROM a2_tech s
  JOIN module2_technology_categories c ON c.code=s.family
  JOIN module2_technologies t ON t.technology_code=s.code AND t.revision=1
  WHERE t.category_id=c.id AND t.name=s.name AND t.description=s.description AND t.status='ACTIVE') THEN
  RAISE EXCEPTION 'A2 Technology conflict';
 END IF;
END $gate$;

CREATE TEMP TABLE a2_requirements (
 tech text NOT NULL, code text NOT NULL, class_slug text NOT NULL, role text NOT NULL,
 notes text NOT NULL, source_code text NOT NULL, PRIMARY KEY(tech,code)
) ON COMMIT DROP;
INSERT INTO a2_requirements VALUES
 ('FND_PILE_BORED_RC','CONCRETE','foundation-structural-concrete','CONCRETE','Свойства смеси по проекту.','GOST_CONCRETE'),
 ('FND_PILE_BORED_RC','REBAR','foundation-reinforcing-steel','REINFORCEMENT','Каркас и защитный слой по проекту.','GOST_REBAR'),
 ('FND_PILE_BORED_RC','CASING','foundation-bored-pile-casing','TEMPORARY_CASING','Применяется лишь когда назначена технология удержания скважины.','SP45'),
 ('FND_PILE_SCREW','PILE','foundation-screw-piles','STEEL_PILE','Тип, геометрия и защита по проекту.','GOST_SCREW'),
 ('FND_PILE_GRILLAGE','CONCRETE','foundation-structural-concrete','CONCRETE','Свойства по проекту.','GOST_CONCRETE'),
 ('FND_PILE_GRILLAGE','REBAR','foundation-reinforcing-steel','REINFORCEMENT','Соединение со сваями по проекту.','GOST_REBAR'),
 ('FND_COLUMN_CONCRETE_RC','CONCRETE','foundation-structural-concrete','CONCRETE','Свойства по проекту.','GOST_CONCRETE'),
 ('FND_COLUMN_CONCRETE_RC','REBAR','foundation-reinforcing-steel','REINFORCEMENT','Только для проектного железобетонного варианта.','GOST_REBAR'),
 ('FND_BASEMENT_WALL_MONOLITHIC','CONCRETE','foundation-structural-concrete','CONCRETE','Свойства по проекту.','GOST_CONCRETE'),
 ('FND_BASEMENT_WALL_MONOLITHIC','REBAR','foundation-reinforcing-steel','REINFORCEMENT','Схема армирования по проекту.','GOST_REBAR'),
 ('FND_BASEMENT_WALL_MONOLITHIC','WATERPROOFING','foundation-waterproofing','WATERPROOFING','Система защиты по проекту.','SP250'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_COATING','MASTIC','foundation-waterproofing-mastics','WATERPROOFING','Конкретный состав и применимость по проекту и документации системы.','GOST_MASTIC'),
 ('FND_SUBSTRUCTURE_INSULATION_XPS','XPS','foundation-xps-insulation','THERMAL_PROTECTION','Характеристики и толщина по теплотехническому проекту.','GOST_XPS');
INSERT INTO module2_technology_material_requirements
 (technology_id,code,selector_kind,material_role_code,material_category_id,notes)
SELECT t.id,s.code,'MATERIAL_CLASS',s.role,c.id,s.notes FROM a2_requirements s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN material_categories c ON c.slug=s.class_slug AND c.status='ACTIVE'
ON CONFLICT (technology_id,code) DO NOTHING;

CREATE TEMP TABLE a2_layers (
 tech text NOT NULL, position integer NOT NULL, role text NOT NULL,
 requirement_code text NOT NULL, mandatory boolean NOT NULL, notes text NOT NULL,
 PRIMARY KEY(tech,position)
) ON COMMIT DROP;
INSERT INTO a2_layers VALUES
 ('FND_PILE_BORED_RC',1,'BORED_PILE_CONCRETE','CONCRETE',true,'Геометрия и бетонирование по проекту.'),
 ('FND_PILE_BORED_RC',2,'PILE_REINFORCEMENT','REBAR',true,'Армирование по проекту.'),
 ('FND_PILE_BORED_RC',3,'BORE_CASING','CASING',false,'Обсадка условна; способ удержания стенок зависит от условий.'),
 ('FND_PILE_SCREW',1,'STEEL_SCREW_PILE','PILE',true,'Защита и соединение по проекту.'),
 ('FND_PILE_GRILLAGE',1,'GRILLAGE_CONCRETE','CONCRETE',true,'Железобетонный ростверк по расчету.'),
 ('FND_PILE_GRILLAGE',2,'GRILLAGE_REINFORCEMENT','REBAR',true,'Связь с головами свай по проекту.'),
 ('FND_COLUMN_CONCRETE_RC',1,'COLUMN_CONCRETE','CONCRETE',true,'Форма и положение по проекту.'),
 ('FND_COLUMN_CONCRETE_RC',2,'COLUMN_REINFORCEMENT','REBAR',false,'Только для железобетонного варианта.'),
 ('FND_BASEMENT_WALL_MONOLITHIC',1,'WALL_CONCRETE','CONCRETE',true,'Конструкция и швы по проекту.'),
 ('FND_BASEMENT_WALL_MONOLITHIC',2,'WALL_REINFORCEMENT','REBAR',true,'Положение по проекту.'),
 ('FND_BASEMENT_WALL_MONOLITHIC',3,'WALL_WATERPROOFING','WATERPROOFING',false,'Только назначенная проектом защита.'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_COATING',1,'COATING_SYSTEM','MASTIC',true,'Подготовка, сопряжения и защита по проекту и документации системы.'),
 ('FND_SUBSTRUCTURE_INSULATION_XPS',1,'XPS_LAYER','XPS',true,'Крепление и защиту выбирать с учетом водозащиты.');
INSERT INTO module2_technology_layers
 (technology_id,position,functional_role,material_requirement_id,is_mandatory,notes)
SELECT t.id,s.position,s.role,r.id,s.mandatory,s.notes FROM a2_layers s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.requirement_code
ON CONFLICT (technology_id,position) DO NOTHING;

CREATE TEMP TABLE a2_steps (
 tech text NOT NULL, position integer NOT NULL, work_code text NOT NULL,
 applicability text NOT NULL, instruction text NOT NULL, source_code text NOT NULL,
 PRIMARY KEY(tech,position)
) ON COMMIT DROP;
INSERT INTO a2_steps VALUES
 ('FND_PILE_BORED_RC',1,'foundations_concrete_burenie_pod_svai','По проекту','Выполнить скважину с проектным способом удержания стенок и контролем основания.','SP45'),
 ('FND_PILE_BORED_RC',2,'reinforcement_armirovanie_fundamenta','По проекту','Установить проектный арматурный каркас.','SP63'),
 ('FND_PILE_BORED_RC',3,'foundations_concrete_betonirovanie_konstrukciy','По проекту/ППР','Уложить бетон проектным способом, контролировать непрерывность и подготовить голову сваи.','SP45'),
 ('FND_PILE_SCREW',1,'foundations_concrete_montazh_vintovyh_svay','По проекту','Погрузить сваи, проверить положение, оголовки, соединение и восстановление защиты.','SP45'),
 ('FND_PILE_GRILLAGE',1,'foundations_concrete_ustroystvo_svayno_rostverkovogo_fundamenta','Только при проектной совместимости свай','Подготовить головы свай, собрать армирование и опалубку, выполнить монолитный ростверк и принять соединения.','SP45'),
 ('FND_COLUMN_CONCRETE_RC',1,'foundations_concrete_montazh_opalubki_fundamenta','Если требуется проектом','Собрать форму отдельных опор по проектным отметкам.','SP70'),
 ('FND_COLUMN_CONCRETE_RC',2,'reinforcement_armirovanie_fundamenta','Для железобетонного варианта','Установить арматуру и принять защитный слой до бетонирования.','SP63'),
 ('FND_COLUMN_CONCRETE_RC',3,'foundations_concrete_betonirovanie_konstrukciy','После приемки основания и формы','Уложить смесь, обеспечить уход и принять опоры.','SP70'),
 ('FND_BASEMENT_WALL_MONOLITHIC',1,'foundations_concrete_montazh_opalubki_fundamenta','По проекту','Собрать и проверить форму стены и сопряжение с фундаментом.','SP70'),
 ('FND_BASEMENT_WALL_MONOLITHIC',2,'reinforcement_armirovanie_fundamenta','По проекту','Установить и принять арматуру и проектные закладные.','SP63'),
 ('FND_BASEMENT_WALL_MONOLITHIC',3,'foundations_concrete_betonirovanie_konstrukciy','После приемки','Уложить бетон, принять швы и обеспечить проектный уход.','SP70'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_COATING',1,'foundations_concrete_gidroizolyaciya_fundamenta','Только для проектно выбранной мастичной системы','Подготовить основание, нанести систему, проверить сопряжения и защитить до засыпки.','SP250'),
 ('FND_SUBSTRUCTURE_INSULATION_XPS',1,'foundations_concrete_uteplenie_fundamenta','Только по теплотехническому проекту','Смонтировать проектно выбранные плиты без повреждения водозащиты; проверить примыкания.','SP50');
INSERT INTO module2_technology_work_steps
 (technology_id,position,work_code,applicability_expression,instructions)
SELECT t.id,s.position,s.work_code,s.applicability,s.instruction FROM a2_steps s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
ON CONFLICT (technology_id,position) DO NOTHING;

CREATE TEMP TABLE a2_nodes (
 tech text NOT NULL, code text NOT NULL, name text NOT NULL,
 description text NOT NULL, source_code text NOT NULL, PRIMARY KEY(tech,code)
) ON COMMIT DROP;
INSERT INTO a2_nodes VALUES
 ('FND_PILE_BORED_RC','PILE_HEAD','Голова буронабивной сваи','Обрезка, подготовка и соединение с ростверком по проекту.','SP24'),
 ('FND_PILE_BORED_RC','BORE_STABILITY','Устойчивость скважины','Решение об обсадке и бетонировании зависит от грунта и воды.','SP45'),
 ('FND_PILE_SCREW','PILE_HEAD','Оголовок винтовой сваи','Соединение с обвязкой и защита стальной детали по проекту.','SP24'),
 ('FND_PILE_SCREW','CORROSION_JUNCTION','Защита стальной сваи','Покрытие, среда и восстановление повреждений определяются проектом.','GOST_SCREW'),
 ('FND_PILE_GRILLAGE','PILE_GRILLAGE_CONNECTION','Соединение сваи и ростверка','Тип сваи, передача нагрузки и армирование узла по проекту.','SP24'),
 ('FND_COLUMN_CONCRETE_RC','COLUMN_BEARING','Опирание на столб','Положение и передача нагрузки определяются проектом.','SP22'),
 ('FND_BASEMENT_WALL_MONOLITHIC','WALL_FOOTING_JUNCTION','Сопряжение стены и фундамента','Шов, армирование и водозащита по проекту.','SP250'),
 ('FND_BASEMENT_WALL_MONOLITHIC','UTILITY_PENETRATION','Ввод коммуникаций','Место, гильза и герметизация согласуются до бетонирования; инженерные сети здесь не проектируются.','SP250'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_COATING','UTILITY_PENETRATION','Герметизация проходки','Непрерывность выбранной системы на гильзе и проходке по проектному узлу.','SP250'),
 ('FND_SUBSTRUCTURE_WATERPROOFING_COATING','PROTECTIVE_LAYER','Защита гидроизоляции','Защитить покрытие от повреждения последующими работами и засыпкой.','SP250'),
 ('FND_SUBSTRUCTURE_INSULATION_XPS','WATERPROOFING_INTERFACE','Сопряжение XPS и гидроизоляции','Крепление и совместимость с водозащитной системой проверяются проектом.','SP250');
INSERT INTO module2_technology_nodes (technology_id,code,node_type,name,description)
SELECT t.id,s.code,'INTERFACE',s.name,s.description FROM a2_nodes s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
ON CONFLICT (technology_id,code) DO NOTHING;

CREATE TEMP TABLE a2_rules (
 tech text NOT NULL, code text NOT NULL, section text NOT NULL, message text NOT NULL,
 source_code text NOT NULL, PRIMARY KEY(tech,code)
) ON COMMIT DROP;
INSERT INTO a2_rules
SELECT s.code, x.rule_code, x.section, x.message, x.source_code
FROM a2_tech s CROSS JOIN LATERAL (VALUES
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
FROM a2_rules s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
ON CONFLICT (technology_id,rule_code,revision) DO NOTHING;

CREATE TEMP TABLE a2_evidence (
 tech text NOT NULL, source_code text NOT NULL, target_kind text NOT NULL,
 target_reference text, interpretation text NOT NULL
) ON COMMIT DROP;
INSERT INTO a2_evidence SELECT s.code,s.design_source,'TECHNOLOGY',NULL,'Project-specific design scope; no numerical recipe.' FROM a2_tech s;
INSERT INTO a2_evidence SELECT s.tech,s.source_code,'MATERIAL_REQUIREMENT',r.id::text,s.notes
FROM a2_requirements s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.code;
INSERT INTO a2_evidence SELECT s.tech,r.source_code,'LAYER',l.id::text,s.notes
FROM a2_layers s JOIN a2_requirements r ON r.tech=s.tech AND r.code=s.requirement_code
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_layers l ON l.technology_id=t.id AND l.position=s.position;
INSERT INTO a2_evidence SELECT s.tech,s.source_code,'WORK_STEP',w.id::text,s.instruction
FROM a2_steps s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_work_steps w ON w.technology_id=t.id AND w.position=s.position;
INSERT INTO a2_evidence SELECT s.tech,s.source_code,'NODE',n.id::text,s.description
FROM a2_nodes s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_technology_nodes n ON n.technology_id=t.id AND n.code=s.code;
INSERT INTO a2_evidence SELECT s.tech,s.source_code,'KNOWLEDGE_RULE',r.id::text,s.message
FROM a2_rules s JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN module2_knowledge_rules r ON r.technology_id=t.id AND r.rule_code=s.code AND r.revision=1;
INSERT INTO module2_technology_evidence_references
 (technology_id,knowledge_resource_id,target_kind,target_reference,interpretation)
SELECT t.id,k.id,s.target_kind,s.target_reference,s.interpretation FROM a2_evidence s
JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
JOIN a2_sources src ON src.code=s.source_code
JOIN knowledge_resources k ON k.source_url=src.url AND k.status='ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM module2_technology_evidence_references e
 WHERE e.technology_id=t.id AND e.knowledge_resource_id=k.id AND e.target_kind=s.target_kind
 AND e.target_reference IS NOT DISTINCT FROM s.target_reference);

DO $gate$ BEGIN
 IF (SELECT count(*) FROM a2_requirements)<>(SELECT count(*) FROM a2_requirements s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
  JOIN material_categories c ON c.slug=s.class_slug AND c.status='ACTIVE'
  JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.code
  WHERE r.material_category_id=c.id AND r.selector_kind='MATERIAL_CLASS' AND r.material_role_code=s.role AND r.notes=s.notes) THEN
  RAISE EXCEPTION 'A2 material requirement conflict';
 END IF;
 IF (SELECT count(*) FROM a2_layers)<>(SELECT count(*) FROM a2_layers s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
  JOIN module2_technology_material_requirements r ON r.technology_id=t.id AND r.code=s.requirement_code
  JOIN module2_technology_layers l ON l.technology_id=t.id AND l.position=s.position
  WHERE l.material_requirement_id=r.id AND l.functional_role=s.role AND l.is_mandatory=s.mandatory AND l.notes=s.notes) THEN
  RAISE EXCEPTION 'A2 layer conflict';
 END IF;
 IF (SELECT count(*) FROM a2_steps)<>(SELECT count(*) FROM a2_steps s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
  JOIN module2_technology_work_steps w ON w.technology_id=t.id AND w.position=s.position
  WHERE w.work_code=s.work_code AND w.applicability_expression=s.applicability AND w.instructions=s.instruction) THEN
  RAISE EXCEPTION 'A2 work-step conflict';
 END IF;
 IF (SELECT count(*) FROM a2_nodes)<>(SELECT count(*) FROM a2_nodes s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
  JOIN module2_technology_nodes n ON n.technology_id=t.id AND n.code=s.code
  WHERE n.name=s.name AND n.description=s.description) THEN
  RAISE EXCEPTION 'A2 node conflict';
 END IF;
 IF (SELECT count(*) FROM a2_rules)<>(SELECT count(*) FROM a2_rules s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
  JOIN module2_knowledge_rules r ON r.technology_id=t.id AND r.rule_code=s.code AND r.revision=1
  WHERE r.status='ACTIVE' AND r.outcome_payload->>'section'=s.section AND r.outcome_payload->>'message'=s.message) THEN
  RAISE EXCEPTION 'A2 rule conflict';
 END IF;
 IF (SELECT count(*) FROM a2_evidence)<>(SELECT count(*) FROM a2_evidence s
  JOIN module2_technologies t ON t.technology_code=s.tech AND t.revision=1
  JOIN a2_sources src ON src.code=s.source_code JOIN knowledge_resources k ON k.source_url=src.url AND k.status='ACTIVE'
  JOIN module2_technology_evidence_references e ON e.technology_id=t.id AND e.knowledge_resource_id=k.id
   AND e.target_kind=s.target_kind AND e.target_reference IS NOT DISTINCT FROM s.target_reference) THEN
  RAISE EXCEPTION 'A2 evidence conflict';
 END IF;
END $gate$;

UPDATE module2_technology_categories SET content_status='IN_PROGRESS'
WHERE code IN ('PILE_FOUNDATIONS','PILE_GRILLAGE_FOUNDATIONS','COLUMN_FOUNDATIONS','BASEMENT_AND_SUBSTRUCTURE')
AND content_status='EMPTY';
COMMIT;
