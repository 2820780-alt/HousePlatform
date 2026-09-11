# Work Catalog Reference — Module №1
Нормализованный справочник работ для ИЖС и ремонта квартир.
Стоимость работ **не хранится** в этом справочнике. Исполнитель вводит ее отдельно через persistent-контракт `ProviderWorkCostOffer`.
Всего работ: **209**.
## Правила
- Справочник содержит только виды работ, единицы и связи с будущими модулями.
- Нет цен, исполнителей, контактов, источников сайтов или данных парсинга.
- `is_range_allowed = true` означает, что исполнитель может указать фиксированную цену или диапазон.
- `applies_to`: `private_house`, `apartment`, `both`.

## Подготовительные работы
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `preparation_vyezd_specialista_na_obekt` | Выезд специалиста на объект | `visit` | да | `both` | `site_specialist_visit` | `labor_cost_line` |
| `preparation_obmer_pomescheniya` | Обмер помещения | `object` | да | `apartment` | `apartment_measurement` | `labor_cost_line` |
| `preparation_obmer_chastnogo_doma_obekta` | Обмер частного дома / объекта | `object` | да | `private_house` | `private_house_measurement` | `labor_cost_line` |
| `preparation_razmetka_pyatna_zastroyki` | Разметка пятна застройки | `object` | да | `private_house` | `building_footprint_layout` | `labor_cost_line` |
| `preparation_razmetka_pomescheniy` | Разметка помещений | `object` | да | `both` | `room_layout` | `labor_cost_line` |
| `preparation_raschistka_uchastka` | Расчистка участка | `m2` | да | `private_house` | `site_clearing` | `labor_cost_line` |
| `preparation_vremennoe_ukrytie_i_zaschita_poverhnostey` | Временное укрытие и защита поверхностей | `m2` | да | `both` | `surface_protection` | `labor_cost_line` |
| `preparation_uborka_stroitelnogo_musora_vruchnuyu` | Уборка строительного мусора вручную | `m3` | да | `both` | `manual_waste_cleanup` | `labor_cost_line` |
| `preparation_pogruzka_stroitelnogo_musora` | Погрузка строительного мусора | `m3` | да | `both` | `waste_loading` | `labor_cost_line` |

## Демонтаж
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `demolition_demontazh_oboev` | Демонтаж обоев | `m2` | да | `apartment` | `wallpaper_demolition` | `labor_cost_line` |
| `demolition_demontazh_plitki_so_sten` | Демонтаж плитки со стен | `m2` | да | `both` | `wall_tile_demolition` | `labor_cost_line` |
| `demolition_demontazh_plitki_s_pola` | Демонтаж плитки с пола | `m2` | да | `both` | `floor_tile_demolition` | `labor_cost_line` |
| `demolition_demontazh_shtukaturki` | Демонтаж штукатурки | `m2` | да | `both` | `plaster_demolition` | `labor_cost_line` |
| `demolition_demontazh_shpaklevki_kraski` | Демонтаж шпаклевки / краски | `m2` | да | `both` | `paint_putty_demolition` | `labor_cost_line` |
| `demolition_demontazh_styazhki` | Демонтаж стяжки | `m2` | да | `both` | `screed_demolition` | `labor_cost_line` |
| `demolition_demontazh_peregorodok_gkl` | Демонтаж перегородок ГКЛ | `m2` | да | `both` | `gkl_partition_demolition` | `labor_cost_line` |
| `demolition_demontazh_kirpichnyh_peregorodok` | Демонтаж кирпичных перегородок | `m2` | да | `both` | `brick_partition_demolition` | `labor_cost_line` |
| `demolition_demontazh_dvernogo_bloka` | Демонтаж дверного блока | `piece` | да | `both` | `door_block_demolition` | `labor_cost_line` |
| `demolition_demontazh_okonnogo_bloka` | Демонтаж оконного блока | `piece` | да | `both` | `window_block_demolition` | `labor_cost_line` |
| `demolition_demontazh_napolnogo_pokrytiya` | Демонтаж напольного покрытия | `m2` | да | `both` | `floor_covering_demolition` | `labor_cost_line` |
| `demolition_demontazh_potolochnogo_pokrytiya` | Демонтаж потолочного покрытия | `m2` | да | `both` | `ceiling_finish_demolition` | `labor_cost_line` |
| `demolition_demontazh_santehniki` | Демонтаж сантехники | `point` | да | `both` | `plumbing_fixture_demolition` | `labor_cost_line` |
| `demolition_demontazh_elektriki` | Демонтаж электрики | `point` | да | `both` | `electrical_point_demolition` | `labor_cost_line` |

## Земляные работы
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `earthworks_razrabotka_grunta_vruchnuyu` | Разработка грунта вручную | `m3` | да | `private_house` | `manual_excavation` | `labor_cost_line` |
| `earthworks_razrabotka_grunta_tehnikoy` | Разработка грунта техникой | `m3` | да | `private_house` | `machine_excavation` | `labor_cost_line` |
| `earthworks_ryte_transhei_vruchnuyu` | Рытье траншеи вручную | `linear_meter` | да | `private_house` | `manual_trench_excavation` | `labor_cost_line` |
| `earthworks_ryte_transhei_tehnikoy` | Рытье траншеи техникой | `linear_meter` | да | `private_house` | `machine_trench_excavation` | `labor_cost_line` |
| `earthworks_planirovka_osnovaniya` | Планировка основания | `m2` | да | `private_house` | `base_grading` | `labor_cost_line` |
| `earthworks_obratnaya_zasypka` | Обратная засыпка | `m3` | да | `private_house` | `backfilling` | `labor_cost_line` |
| `earthworks_ustroystvo_peschanoy_podushki` | Устройство песчаной подушки | `m3` | да | `private_house` | `sand_bedding` | `labor_cost_line` |
| `earthworks_ustroystvo_schebenochnoy_podushki` | Устройство щебеночной подушки | `m3` | да | `private_house` | `gravel_bedding` | `labor_cost_line` |
| `earthworks_ukladka_geotekstilya` | Укладка геотекстиля | `m2` | да | `private_house` | `geotextile_installation` | `labor_cost_line` |
| `earthworks_vyvoz_grunta` | Вывоз грунта | `m3` | да | `private_house` | `soil_disposal` | `labor_cost_line` |

## Фундаменты и бетонные работы
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `foundations_concrete_ustroystvo_lentochnogo_fundamenta` | Устройство ленточного фундамента | `m3` | да | `private_house` | `strip_foundation` | `labor_cost_line` |
| `foundations_concrete_ustroystvo_plitnogo_fundamenta` | Устройство плитного фундамента | `m3` | да | `private_house` | `slab_foundation` | `labor_cost_line` |
| `foundations_concrete_ustroystvo_svayno_rostverkovogo_fundamenta` | Устройство свайно-ростверкового фундамента | `linear_meter` | да | `private_house` | `pile_grillage_foundation` | `labor_cost_line` |
| `foundations_concrete_montazh_vintovyh_svay` | Монтаж винтовых свай | `piece` | да | `private_house` | `screw_pile_installation` | `labor_cost_line` |
| `foundations_concrete_burenie_pod_svai` | Бурение под сваи | `piece` | да | `private_house` | `pile_drilling` | `labor_cost_line` |
| `foundations_concrete_ustroystvo_podbetonki` | Устройство подбетонки | `m2` | да | `private_house` | `lean_concrete` | `labor_cost_line` |
| `foundations_concrete_montazh_opalubki_fundamenta` | Монтаж опалубки фундамента | `m2` | да | `private_house` | `foundation_formwork` | `labor_cost_line` |
| `foundations_concrete_demontazh_opalubki` | Демонтаж опалубки | `m2` | да | `private_house` | `formwork_removal` | `labor_cost_line` |
| `foundations_concrete_betonirovanie_konstrukciy` | Бетонирование конструкций | `m3` | да | `private_house` | `concrete_placing` | `labor_cost_line` |
| `foundations_concrete_vibrirovanie_betona` | Вибрирование бетона | `m3` | да | `private_house` | `concrete_vibration` | `labor_cost_line` |
| `foundations_concrete_gidroizolyaciya_fundamenta` | Гидроизоляция фундамента | `m2` | да | `private_house` | `foundation_waterproofing` | `labor_cost_line` |
| `foundations_concrete_uteplenie_fundamenta` | Утепление фундамента | `m2` | да | `private_house` | `foundation_insulation` | `labor_cost_line` |
| `foundations_concrete_ustroystvo_otmostki_betonnoy` | Устройство отмостки бетонной | `m2` | да | `private_house` | `concrete_blind_area` | `labor_cost_line` |
| `foundations_concrete_ustroystvo_betonnogo_krylca` | Устройство бетонного крыльца | `m3` | да | `private_house` | `concrete_porch` | `labor_cost_line` |

## Армирование
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `reinforcement_vyazka_armaturnogo_karkasa` | Вязка арматурного каркаса | `kg` | да | `private_house` | `rebar_cage_binding` | `labor_cost_line` |
| `reinforcement_montazh_armaturnoy_setki` | Монтаж арматурной сетки | `m2` | да | `both` | `rebar_mesh_installation` | `labor_cost_line` |
| `reinforcement_armirovanie_fundamenta` | Армирование фундамента | `kg` | да | `private_house` | `foundation_reinforcement` | `labor_cost_line` |
| `reinforcement_armirovanie_plity` | Армирование плиты | `kg` | да | `private_house` | `slab_reinforcement` | `labor_cost_line` |
| `reinforcement_armirovanie_armopoyasa` | Армирование армопояса | `linear_meter` | да | `private_house` | `bond_beam_reinforcement` | `labor_cost_line` |
| `reinforcement_armirovanie_peremychek` | Армирование перемычек | `linear_meter` | да | `private_house` | `lintel_reinforcement` | `labor_cost_line` |

## Стены и кладка
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `walls_masonry_kladka_gazobloka_naruzhnyh_sten` | Кладка газоблока наружных стен | `m3` | да | `private_house` | `aerated_concrete_outer_wall_masonry` | `labor_cost_line` |
| `walls_masonry_kladka_peregorodok_iz_gazobloka` | Кладка перегородок из газоблока | `m2` | да | `both` | `aerated_concrete_partition_masonry` | `labor_cost_line` |
| `walls_masonry_kladka_kirpicha` | Кладка кирпича | `m3` | да | `private_house` | `brick_masonry` | `labor_cost_line` |
| `walls_masonry_kladka_oblicovochnogo_kirpicha` | Кладка облицовочного кирпича | `m2` | да | `private_house` | `facing_brick_masonry` | `labor_cost_line` |
| `walls_masonry_kladka_keramicheskogo_bloka` | Кладка керамического блока | `m3` | да | `private_house` | `ceramic_block_masonry` | `labor_cost_line` |
| `walls_masonry_ustroystvo_armopoyasa` | Устройство армопояса | `linear_meter` | да | `private_house` | `bond_beam` | `labor_cost_line` |
| `walls_masonry_montazh_peremychek` | Монтаж перемычек | `piece` | да | `both` | `lintel_installation` | `labor_cost_line` |
| `walls_masonry_ustroystvo_monolitnyh_uchastkov` | Устройство монолитных участков | `m3` | да | `private_house` | `monolithic_inserts` | `labor_cost_line` |
| `walls_masonry_montazh_gkl_peregorodki` | Монтаж ГКЛ-перегородки | `m2` | да | `both` | `gypsum_board_partition` | `labor_cost_line` |
| `walls_masonry_montazh_karkasnoy_steny` | Монтаж каркасной стены | `m2` | да | `private_house` | `frame_wall` | `labor_cost_line` |
| `walls_masonry_zvukoizolyaciya_peregorodok` | Звукоизоляция перегородок | `m2` | да | `both` | `partition_sound_insulation` | `labor_cost_line` |

## Перекрытия и черновые полы
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `floors_structural_montazh_derevyannyh_balok_perekrytiya` | Монтаж деревянных балок перекрытия | `m2` | да | `private_house` | `wood_floor_beams` | `labor_cost_line` |
| `floors_structural_ustroystvo_chernovogo_pola_po_lagam` | Устройство чернового пола по лагам | `m2` | да | `private_house` | `subfloor_on_joists` | `labor_cost_line` |
| `floors_structural_uteplenie_perekrytiya` | Утепление перекрытия | `m2` | да | `private_house` | `floor_structure_insulation` | `labor_cost_line` |
| `floors_structural_montazh_paroizolyacii_perekrytiya` | Монтаж пароизоляции перекрытия | `m2` | да | `private_house` | `floor_vapor_barrier` | `labor_cost_line` |
| `floors_structural_montazh_plit_perekrytiya` | Монтаж плит перекрытия | `piece` | да | `private_house` | `precast_slab_installation` | `labor_cost_line` |
| `floors_structural_ustroystvo_monolitnogo_perekrytiya` | Устройство монолитного перекрытия | `m3` | да | `private_house` | `monolithic_floor_slab` | `labor_cost_line` |

## Кровля
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `roofing_montazh_mauerlata` | Монтаж мауэрлата | `linear_meter` | да | `private_house` | `mauerlat_installation` | `labor_cost_line` |
| `roofing_montazh_stropilnoy_sistemy` | Монтаж стропильной системы | `m2` | да | `private_house` | `rafter_system` | `labor_cost_line` |
| `roofing_montazh_obreshetki` | Монтаж обрешетки | `m2` | да | `private_house` | `roof_batten_installation` | `labor_cost_line` |
| `roofing_montazh_kontrobreshetki` | Монтаж контробрешетки | `m2` | да | `private_house` | `counter_batten_installation` | `labor_cost_line` |
| `roofing_montazh_gidro_vetrozaschity_krovli` | Монтаж гидро-ветрозащиты кровли | `m2` | да | `private_house` | `roof_wind_membrane` | `labor_cost_line` |
| `roofing_montazh_paroizolyacii_krovli` | Монтаж пароизоляции кровли | `m2` | да | `private_house` | `roof_vapor_barrier` | `labor_cost_line` |
| `roofing_montazh_metallocherepicy` | Монтаж металлочерепицы | `m2` | да | `private_house` | `metal_tile_roofing` | `labor_cost_line` |
| `roofing_montazh_myagkoy_krovli` | Монтаж мягкой кровли | `m2` | да | `private_house` | `flexible_shingle_roofing` | `labor_cost_line` |
| `roofing_montazh_profnastila_na_krovlyu` | Монтаж профнастила на кровлю | `m2` | да | `private_house` | `profiled_sheet_roofing` | `labor_cost_line` |
| `roofing_montazh_osb_pod_myagkuyu_krovlyu` | Монтаж OSB под мягкую кровлю | `m2` | да | `private_house` | `osb_roof_decking` | `labor_cost_line` |
| `roofing_montazh_konkov_i_dobornyh_elementov` | Монтаж коньков и доборных элементов | `linear_meter` | да | `private_house` | `roof_ridge_accessories` | `labor_cost_line` |
| `roofing_montazh_endovy` | Монтаж ендовы | `linear_meter` | да | `private_house` | `roof_valley_installation` | `labor_cost_line` |
| `roofing_montazh_snegozaderzhateley` | Монтаж снегозадержателей | `linear_meter` | да | `private_house` | `snow_guard_installation` | `labor_cost_line` |
| `roofing_montazh_vodostochnoy_sistemy` | Монтаж водосточной системы | `linear_meter` | да | `private_house` | `gutter_system_installation` | `labor_cost_line` |
| `roofing_podshivka_svesov_sofity` | Подшивка свесов / софиты | `m2` | да | `private_house` | `soffit_installation` | `labor_cost_line` |

## Мансарда и утепление
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `mansard_insulation_uteplenie_krovli_po_stropilam` | Утепление кровли по стропилам | `m2` | да | `private_house` | `mansard_rafter_insulation` | `labor_cost_line` |
| `mansard_insulation_perekrestnoe_uteplenie_mansardy` | Перекрестное утепление мансарды | `m2` | да | `private_house` | `mansard_cross_insulation` | `labor_cost_line` |
| `mansard_insulation_montazh_paroizolyacii_mansardy` | Монтаж пароизоляции мансарды | `m2` | да | `private_house` | `mansard_vapor_barrier` | `labor_cost_line` |
| `mansard_insulation_montazh_vnutrenney_obreshetki_mansardy` | Монтаж внутренней обрешетки мансарды | `m2` | да | `private_house` | `mansard_inner_batten` | `labor_cost_line` |
| `mansard_insulation_obshivka_mansardy_gkl` | Обшивка мансарды ГКЛ | `m2` | да | `private_house` | `mansard_gkl_lining` | `labor_cost_line` |
| `mansard_insulation_obshivka_mansardy_vagonkoy_imitaciey_brusa` | Обшивка мансарды вагонкой / имитацией бруса | `m2` | да | `private_house` | `mansard_wood_lining` | `labor_cost_line` |

## Фасад
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `facade_uteplenie_fasada_minvatoy` | Утепление фасада минватой | `m2` | да | `private_house` | `facade_mineral_wool_insulation` | `labor_cost_line` |
| `facade_uteplenie_fasada_penopolistirolom` | Утепление фасада пенополистиролом | `m2` | да | `private_house` | `facade_eps_insulation` | `labor_cost_line` |
| `facade_montazh_fasadnoy_setki_i_bazovogo_sloya` | Монтаж фасадной сетки и базового слоя | `m2` | да | `private_house` | `facade_basecoat_mesh` | `labor_cost_line` |
| `facade_dekorativnaya_shtukaturka_fasada` | Декоративная штукатурка фасада | `m2` | да | `private_house` | `facade_decorative_plaster` | `labor_cost_line` |
| `facade_montazh_saydinga` | Монтаж сайдинга | `m2` | да | `private_house` | `siding_installation` | `labor_cost_line` |
| `facade_montazh_ventiliruemogo_fasada` | Монтаж вентилируемого фасада | `m2` | да | `private_house` | `ventilated_facade` | `labor_cost_line` |
| `facade_otdelka_cokolya` | Отделка цоколя | `m2` | да | `private_house` | `plinth_finish` | `labor_cost_line` |
| `facade_naruzhnye_otkosy` | Наружные откосы | `linear_meter` | да | `private_house` | `external_slopes` | `labor_cost_line` |

## Окна, двери, откосы
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `windows_doors_slopes_montazh_okna` | Монтаж окна | `piece` | да | `both` | `window_installation` | `labor_cost_line` |
| `windows_doors_slopes_montazh_vhodnoy_dveri` | Монтаж входной двери | `piece` | да | `both` | `entrance_door_installation` | `labor_cost_line` |
| `windows_doors_slopes_montazh_mezhkomnatnoy_dveri` | Монтаж межкомнатной двери | `piece` | да | `both` | `interior_door_installation` | `labor_cost_line` |
| `windows_doors_slopes_ustroystvo_okonnyh_otkosov` | Устройство оконных откосов | `linear_meter` | да | `both` | `window_slopes` | `labor_cost_line` |
| `windows_doors_slopes_ustroystvo_dvernyh_otkosov` | Устройство дверных откосов | `linear_meter` | да | `both` | `door_slopes` | `labor_cost_line` |
| `windows_doors_slopes_montazh_podokonnika` | Монтаж подоконника | `linear_meter` | да | `both` | `window_sill_installation` | `labor_cost_line` |
| `windows_doors_slopes_montazh_otliva` | Монтаж отлива | `linear_meter` | да | `private_house` | `external_sill_installation` | `labor_cost_line` |

## Штукатурка, шпаклевка, стены
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `wall_finishing_gruntovka_sten` | Грунтовка стен | `m2` | да | `both` | `wall_primer` | `labor_cost_line` |
| `wall_finishing_shtukaturka_sten_gipsovaya` | Штукатурка стен гипсовая | `m2` | да | `both` | `wall_plaster_gypsum` | `labor_cost_line` |
| `wall_finishing_shtukaturka_sten_cementnaya` | Штукатурка стен цементная | `m2` | да | `both` | `wall_plaster_cement` | `labor_cost_line` |
| `wall_finishing_montazh_shtukaturnoy_setki` | Монтаж штукатурной сетки | `m2` | да | `both` | `plaster_mesh_installation` | `labor_cost_line` |
| `wall_finishing_ustanovka_mayakov` | Установка маяков | `m2` | да | `both` | `plaster_beacon_installation` | `labor_cost_line` |
| `wall_finishing_shpaklevka_startovaya` | Шпаклевка стартовая | `m2` | да | `both` | `start_putty` | `labor_cost_line` |
| `wall_finishing_shpaklevka_finishnaya` | Шпаклевка финишная | `m2` | да | `both` | `finish_putty` | `labor_cost_line` |
| `wall_finishing_shlifovka_sten` | Шлифовка стен | `m2` | да | `both` | `wall_sanding` | `labor_cost_line` |
| `wall_finishing_pokraska_sten` | Покраска стен | `m2` | да | `both` | `wall_painting` | `labor_cost_line` |
| `wall_finishing_pokleyka_oboev` | Поклейка обоев | `m2` | да | `both` | `wallpaper_installation` | `labor_cost_line` |
| `wall_finishing_montazh_dekorativnyh_paneley_na_steny` | Монтаж декоративных панелей на стены | `m2` | да | `both` | `decorative_wall_panels` | `labor_cost_line` |

## Полы и стяжки
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `floors_screeds_gruntovka_pola` | Грунтовка пола | `m2` | да | `both` | `floor_primer` | `labor_cost_line` |
| `floors_screeds_gidroizolyaciya_pola` | Гидроизоляция пола | `m2` | да | `both` | `floor_waterproofing` | `labor_cost_line` |
| `floors_screeds_ustroystvo_cementno_peschanoy_styazhki` | Устройство цементно-песчаной стяжки | `m2` | да | `both` | `cement_screed` | `labor_cost_line` |
| `floors_screeds_ustroystvo_polusuhoy_styazhki` | Устройство полусухой стяжки | `m2` | да | `both` | `semi_dry_screed` | `labor_cost_line` |
| `floors_screeds_ustroystvo_nalivnogo_pola` | Устройство наливного пола | `m2` | да | `both` | `self_leveling_floor` | `labor_cost_line` |
| `floors_screeds_ukladka_armiruyuschey_setki` | Укладка армирующей сетки | `m2` | да | `both` | `floor_reinforcement_mesh` | `labor_cost_line` |
| `floors_screeds_montazh_dempfernoy_lenty` | Монтаж демпферной ленты | `linear_meter` | да | `both` | `damper_tape_installation` | `labor_cost_line` |
| `floors_screeds_ukladka_laminata` | Укладка ламината | `m2` | да | `both` | `laminate_installation` | `labor_cost_line` |
| `floors_screeds_ukladka_kvarcvinila` | Укладка кварцвинила | `m2` | да | `both` | `vinyl_floor_installation` | `labor_cost_line` |
| `floors_screeds_ukladka_linoleuma` | Укладка линолеума | `m2` | да | `both` | `linoleum_installation` | `labor_cost_line` |
| `floors_screeds_montazh_plintusa` | Монтаж плинтуса | `linear_meter` | да | `both` | `skirting_installation` | `labor_cost_line` |
| `floors_screeds_montazh_porozhkov` | Монтаж порожков | `piece` | да | `both` | `threshold_installation` | `labor_cost_line` |

## Плиточные работы
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `tile_works_ukladka_plitki_na_pol` | Укладка плитки на пол | `m2` | да | `both` | `floor_tile_installation` | `labor_cost_line` |
| `tile_works_ukladka_plitki_na_steny` | Укладка плитки на стены | `m2` | да | `both` | `wall_tile_installation` | `labor_cost_line` |
| `tile_works_ukladka_keramogranita` | Укладка керамогранита | `m2` | да | `both` | `porcelain_tile_installation` | `labor_cost_line` |
| `tile_works_ukladka_plitki_po_diagonali` | Укладка плитки по диагонали | `m2` | да | `both` | `diagonal_tile_installation` | `labor_cost_line` |
| `tile_works_podrezka_plitki` | Подрезка плитки | `linear_meter` | да | `both` | `tile_cutting` | `labor_cost_line` |
| `tile_works_zatirka_shvov` | Затирка швов | `m2` | да | `both` | `tile_grouting` | `labor_cost_line` |
| `tile_works_sverlenie_otverstiy_v_plitke` | Сверление отверстий в плитке | `piece` | да | `both` | `tile_hole_drilling` | `labor_cost_line` |
| `tile_works_ustanovka_plitochnogo_ugolka` | Установка плиточного уголка | `linear_meter` | да | `both` | `tile_corner_profile` | `labor_cost_line` |

## Потолки
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `ceilings_montazh_gkl_potolka` | Монтаж ГКЛ-потолка | `m2` | да | `both` | `gkl_ceiling` | `labor_cost_line` |
| `ceilings_shpaklevka_potolka` | Шпаклевка потолка | `m2` | да | `both` | `ceiling_putty` | `labor_cost_line` |
| `ceilings_pokraska_potolka` | Покраска потолка | `m2` | да | `both` | `ceiling_painting` | `labor_cost_line` |
| `ceilings_montazh_natyazhnogo_potolka` | Монтаж натяжного потолка | `m2` | да | `both` | `stretch_ceiling` | `labor_cost_line` |
| `ceilings_montazh_potolochnogo_plintusa` | Монтаж потолочного плинтуса | `linear_meter` | да | `both` | `ceiling_skirting` | `labor_cost_line` |
| `ceilings_montazh_zakladnyh_pod_svetilniki` | Монтаж закладных под светильники | `piece` | да | `both` | `ceiling_light_backing` | `labor_cost_line` |

## Санузлы и мокрые зоны
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `bathroom_wet_zones_gidroizolyaciya_pola_sanuzla` | Гидроизоляция пола санузла | `m2` | да | `both` | `bathroom_floor_waterproofing` | `labor_cost_line` |
| `bathroom_wet_zones_gidroizolyaciya_sten_mokroy_zony` | Гидроизоляция стен мокрой зоны | `m2` | да | `both` | `wet_zone_wall_waterproofing` | `labor_cost_line` |
| `bathroom_wet_zones_montazh_gidroizolyacionnoy_lenty` | Монтаж гидроизоляционной ленты | `linear_meter` | да | `both` | `waterproofing_tape` | `labor_cost_line` |
| `bathroom_wet_zones_montazh_koroba_gkl_gvl` | Монтаж короба ГКЛ/ГВЛ | `m2` | да | `both` | `bathroom_gkl_box` | `labor_cost_line` |
| `bathroom_wet_zones_montazh_installyacii` | Монтаж инсталляции | `piece` | да | `both` | `toilet_installation_frame` | `labor_cost_line` |
| `bathroom_wet_zones_montazh_dushevogo_trapa` | Монтаж душевого трапа | `piece` | да | `both` | `shower_drain_installation` | `labor_cost_line` |
| `bathroom_wet_zones_germetizaciya_primykaniy` | Герметизация примыканий | `linear_meter` | да | `both` | `wet_zone_sealing` | `labor_cost_line` |
| `bathroom_wet_zones_montazh_ekrana_pod_vannu` | Монтаж экрана под ванну | `piece` | да | `both` | `bath_screen_installation` | `labor_cost_line` |

## Электрика
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `electrical_montazh_elektricheskoy_tochki` | Монтаж электрической точки | `point` | да | `both` | `electrical_point` | `labor_cost_line` |
| `electrical_shtroblenie_pod_kabel` | Штробление под кабель | `linear_meter` | да | `both` | `cable_chasing` | `labor_cost_line` |
| `electrical_prokladka_kabelya` | Прокладка кабеля | `linear_meter` | да | `both` | `cable_laying` | `labor_cost_line` |
| `electrical_montazh_podrozetnika` | Монтаж подрозетника | `piece` | да | `both` | `socket_box_installation` | `labor_cost_line` |
| `electrical_ustanovka_rozetki` | Установка розетки | `piece` | да | `both` | `socket_installation` | `labor_cost_line` |
| `electrical_ustanovka_vyklyuchatelya` | Установка выключателя | `piece` | да | `both` | `switch_installation` | `labor_cost_line` |
| `electrical_montazh_raspredelitelnoy_korobki` | Монтаж распределительной коробки | `piece` | да | `both` | `junction_box_installation` | `labor_cost_line` |
| `electrical_sborka_elektroschita` | Сборка электрощита | `piece` | да | `both` | `electrical_panel_assembly` | `labor_cost_line` |
| `electrical_montazh_avtomata_uzo` | Монтаж автомата / УЗО | `piece` | да | `both` | `breaker_rcd_installation` | `labor_cost_line` |
| `electrical_montazh_svetilnika` | Монтаж светильника | `piece` | да | `both` | `light_fixture_installation` | `labor_cost_line` |
| `electrical_montazh_teplogo_pola_elektricheskogo` | Монтаж теплого пола электрического | `m2` | да | `both` | `electric_underfloor_heating` | `labor_cost_line` |
| `electrical_montazh_zazemleniya_chastnogo_doma` | Монтаж заземления частного дома | `set` | да | `private_house` | `house_grounding` | `labor_cost_line` |

## Водоснабжение
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `water_supply_montazh_tochki_vodosnabzheniya` | Монтаж точки водоснабжения | `point` | да | `both` | `water_supply_point` | `labor_cost_line` |
| `water_supply_prokladka_trub_vodosnabzheniya` | Прокладка труб водоснабжения | `linear_meter` | да | `both` | `water_pipe_laying` | `labor_cost_line` |
| `water_supply_montazh_kollektora_vodosnabzheniya` | Монтаж коллектора водоснабжения | `piece` | да | `both` | `water_manifold_installation` | `labor_cost_line` |
| `water_supply_montazh_filtra` | Монтаж фильтра | `piece` | да | `both` | `water_filter_installation` | `labor_cost_line` |
| `water_supply_montazh_santehnicheskogo_pribora` | Монтаж сантехнического прибора | `piece` | да | `both` | `plumbing_fixture_installation` | `labor_cost_line` |
| `water_supply_montazh_vodonagrevatelya` | Монтаж водонагревателя | `piece` | да | `both` | `water_heater_installation` | `labor_cost_line` |
| `water_supply_vvod_vody_v_dom` | Ввод воды в дом | `linear_meter` | да | `private_house` | `house_water_entry` | `labor_cost_line` |
| `water_supply_uteplenie_vodoprovodnoy_truby` | Утепление водопроводной трубы | `linear_meter` | да | `private_house` | `water_pipe_insulation` | `labor_cost_line` |

## Канализация
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `sewerage_montazh_tochki_kanalizacii` | Монтаж точки канализации | `point` | да | `both` | `sewer_point` | `labor_cost_line` |
| `sewerage_prokladka_trub_kanalizacii` | Прокладка труб канализации | `linear_meter` | да | `both` | `sewer_pipe_laying` | `labor_cost_line` |
| `sewerage_montazh_stoyaka_kanalizacii` | Монтаж стояка канализации | `linear_meter` | да | `both` | `sewer_riser` | `labor_cost_line` |
| `sewerage_montazh_septika` | Монтаж септика | `piece` | да | `private_house` | `septic_tank_installation` | `labor_cost_line` |
| `sewerage_prokladka_naruzhnoy_kanalizacii` | Прокладка наружной канализации | `linear_meter` | да | `private_house` | `external_sewer_laying` | `labor_cost_line` |
| `sewerage_montazh_revizionnogo_kolodca` | Монтаж ревизионного колодца | `piece` | да | `private_house` | `sewer_inspection_well` | `labor_cost_line` |

## Отопление
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `heating_montazh_radiatora` | Монтаж радиатора | `piece` | да | `both` | `radiator_installation` | `labor_cost_line` |
| `heating_prokladka_trub_otopleniya` | Прокладка труб отопления | `linear_meter` | да | `both` | `heating_pipe_laying` | `labor_cost_line` |
| `heating_montazh_kollektora_otopleniya` | Монтаж коллектора отопления | `piece` | да | `both` | `heating_manifold` | `labor_cost_line` |
| `heating_montazh_vodyanogo_teplogo_pola` | Монтаж водяного теплого пола | `m2` | да | `both` | `water_underfloor_heating` | `labor_cost_line` |
| `heating_montazh_kotla` | Монтаж котла | `piece` | да | `private_house` | `boiler_installation` | `labor_cost_line` |
| `heating_montazh_gruppy_bezopasnosti` | Монтаж группы безопасности | `piece` | да | `private_house` | `heating_safety_group` | `labor_cost_line` |
| `heating_montazh_rasshiritelnogo_baka` | Монтаж расширительного бака | `piece` | да | `private_house` | `expansion_tank_installation` | `labor_cost_line` |

## Вентиляция
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `ventilation_montazh_ventilyacionnogo_kanala` | Монтаж вентиляционного канала | `linear_meter` | да | `both` | `vent_duct_installation` | `labor_cost_line` |
| `ventilation_montazh_ventilyacionnoy_reshetki` | Монтаж вентиляционной решетки | `piece` | да | `both` | `vent_grille_installation` | `labor_cost_line` |
| `ventilation_montazh_vytyazhnogo_ventilyatora` | Монтаж вытяжного вентилятора | `piece` | да | `both` | `exhaust_fan_installation` | `labor_cost_line` |
| `ventilation_montazh_kuhonnoy_vytyazhki` | Монтаж кухонной вытяжки | `piece` | да | `both` | `kitchen_hood_installation` | `labor_cost_line` |

## Благоустройство
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `landscaping_ustroystvo_otmostki` | Устройство отмостки | `m2` | да | `private_house` | `blind_area` | `labor_cost_line` |
| `landscaping_ukladka_trotuarnoy_plitki` | Укладка тротуарной плитки | `m2` | да | `private_house` | `paving_slabs` | `labor_cost_line` |
| `landscaping_ustanovka_bordyura` | Установка бордюра | `linear_meter` | да | `private_house` | `curb_installation` | `labor_cost_line` |
| `landscaping_ustroystvo_betonnoy_dorozhki` | Устройство бетонной дорожки | `m2` | да | `private_house` | `concrete_path` | `labor_cost_line` |
| `landscaping_ustroystvo_drenazha_uchastka` | Устройство дренажа участка | `linear_meter` | да | `private_house` | `site_drainage` | `labor_cost_line` |
| `landscaping_ustroystvo_livnevoy_kanalizacii` | Устройство ливневой канализации | `linear_meter` | да | `private_house` | `stormwater_drainage` | `labor_cost_line` |
| `landscaping_planirovka_uchastka` | Планировка участка | `m2` | да | `private_house` | `site_grading` | `labor_cost_line` |
| `landscaping_ustroystvo_gazona` | Устройство газона | `m2` | да | `private_house` | `lawn_installation` | `labor_cost_line` |
| `landscaping_montazh_terrasy_nastila` | Монтаж террасы / настила | `m2` | да | `private_house` | `deck_installation` | `labor_cost_line` |

## Заборы и ворота
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `fences_gates_montazh_zabora_iz_profnastila` | Монтаж забора из профнастила | `linear_meter` | да | `private_house` | `profiled_sheet_fence` | `labor_cost_line` |
| `fences_gates_montazh_zabora_iz_evroshtaketnika` | Монтаж забора из евроштакетника | `linear_meter` | да | `private_house` | `euro_picket_fence` | `labor_cost_line` |
| `fences_gates_montazh_zabora_3d_setka` | Монтаж забора 3D-сетка | `linear_meter` | да | `private_house` | `mesh_3d_fence` | `labor_cost_line` |
| `fences_gates_montazh_stolbov_zabora` | Монтаж столбов забора | `piece` | да | `private_house` | `fence_post_installation` | `labor_cost_line` |
| `fences_gates_betonirovanie_stolbov` | Бетонирование столбов | `piece` | да | `private_house` | `fence_post_concreting` | `labor_cost_line` |
| `fences_gates_montazh_vorot` | Монтаж ворот | `piece` | да | `private_house` | `gate_installation` | `labor_cost_line` |
| `fences_gates_montazh_kalitki` | Монтаж калитки | `piece` | да | `private_house` | `wicket_installation` | `labor_cost_line` |
| `fences_gates_montazh_avtomatiki_vorot` | Монтаж автоматики ворот | `set` | да | `private_house` | `gate_automation` | `labor_cost_line` |

## Вывоз мусора
| Код работы | Наименование | Ед. | Диапазон | Применимо | Module №2 hint | Module №5 hint |
|---|---|---:|---:|---|---|---|
| `waste_disposal_vynos_stroitelnogo_musora` | Вынос строительного мусора | `m3` | да | `both` | `waste_carrying` | `labor_cost_line` |
| `waste_disposal_vyvoz_stroitelnogo_musora_konteynerom` | Вывоз строительного мусора контейнером | `m3` | да | `both` | `waste_container_disposal` | `labor_cost_line` |
| `waste_disposal_vyvoz_stroitelnogo_musora_mashinoy` | Вывоз строительного мусора машиной | `trip` | да | `both` | `waste_truck_disposal` | `labor_cost_line` |
| `waste_disposal_upakovka_musora_v_meshki` | Упаковка мусора в мешки | `bag` | да | `both` | `waste_bagging` | `labor_cost_line` |
