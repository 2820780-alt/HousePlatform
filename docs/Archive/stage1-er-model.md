# ЭТАП 1 — ER-МОДЕЛЬ И ПРОЕКТИРОВАНИЕ БД

## 1. ПЕРЕЧЕНЬ СУЩНОСТЕЙ

### Ядро пользователей и ролей
- **User** — пользователь платформы
- **Supplier** — поставщик (компания)
- **SupplierAccount** — связь User ↔ Supplier
- **SupplierBranch** — филиал поставщика

### Источники данных
- **DataSource** — загруженный документ / источник
- **RawProductLine** — извлечённая строка из документа

### База материалов
- **MaterialCategory** — категория материала
- **MaterialCategorySchema** — схема характеристик категории
- **Material** — каноническая карточка материала
- **MaterialAlias** — синоним / альтернативное название
- **MaterialAttribute** — характеристика материала

### Единицы измерения
- **Unit** — единица измерения
- **UnitAlias** — синоним единицы измерения
- **UnitConversion** — правила конвертации единиц

### Коммерция
- **SupplierOffer** — предложение поставщика
- **PriceHistory** — история цен

### Аудит
- **AuditEvent** — лог событий платформы

---

## 2. ER-ДИАГРАММА (текстовая)

```
User 1──N SupplierAccount N──1 Supplier
                                    │
                              1─────N SupplierBranch
                              │
                              1─────N DataSource
                              │           │
                              │      1────N RawProductLine
                              │                │
                              │           (match)│
                              │                ▼
                              │          Material 1──N MaterialAlias
                              │               │
                              │          1────N MaterialAttribute
                              │               │
                              │          N────1 MaterialCategory
                              │                    │
                              │               1────N MaterialCategorySchema
                              │
                              1─────N SupplierOffer N──1 Material
                              │
                              1─────N PriceHistory  N──1 Material

Unit 1──N UnitAlias
Unit 1──N UnitConversion (from)
Unit 1──N UnitConversion (to)
```

---

## 3. ТАБЛИЦЫ И ПОЛЯ

### 3.1 users
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK, default gen |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| phone | VARCHAR(50) | NULL |
| name | VARCHAR(255) | NULL |
| password_hash | VARCHAR(255) | NOT NULL |
| role | ENUM(user_role) | NOT NULL, DEFAULT 'SUPPLIER' |
| status | ENUM(user_status) | NOT NULL, DEFAULT 'active' |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Индексы:**
- UNIQUE(email)
- INDEX(role)
- INDEX(status)

---

### 3.2 suppliers
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| name | VARCHAR(500) | NOT NULL |
| inn | VARCHAR(20) | UNIQUE, NULL |
| site | VARCHAR(500) | NULL |
| email | VARCHAR(255) | NULL |
| phone | VARCHAR(50) | NULL |
| city | VARCHAR(255) | NULL |
| region | VARCHAR(255) | NULL |
| country | VARCHAR(100) | DEFAULT 'Россия' |
| address | TEXT | NULL |
| description | TEXT | NULL |
| status | ENUM(supplier_status) | NOT NULL, DEFAULT 'potential' |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- UNIQUE(inn) WHERE inn IS NOT NULL
- INDEX(city)
- INDEX(region)
- INDEX(status)
- INDEX(name) GIN trigram (для поиска)

---

### 3.3 supplier_accounts
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL |
| supplier_id | UUID | FK → suppliers.id, NOT NULL |
| role_in_company | VARCHAR(100) | NULL |
| access_status | ENUM(access_status) | DEFAULT 'active' |
| created_at | TIMESTAMPTZ | NOT NULL |
| last_login_at | TIMESTAMPTZ | NULL |

**Индексы:**
- UNIQUE(user_id, supplier_id)
- INDEX(supplier_id)

---

### 3.4 supplier_branches
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| supplier_id | UUID | FK → suppliers.id, NOT NULL |
| name | VARCHAR(500) | NULL |
| city | VARCHAR(255) | NOT NULL |
| region | VARCHAR(255) | NULL |
| address | TEXT | NULL |
| contacts | JSONB | NULL |
| delivery_zone | TEXT | NULL |
| is_main | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- INDEX(supplier_id)
- INDEX(city)
- INDEX(region)

---

### 3.5 data_sources
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| type | ENUM(datasource_type) | NOT NULL |
| supplier_id | UUID | FK → suppliers.id, NULL |
| supplier_branch_id | UUID | FK → supplier_branches.id, NULL |
| uploaded_by_user_id | UUID | FK → users.id, NULL |
| original_filename | VARCHAR(500) | NULL |
| file_size_bytes | INTEGER | NULL |
| mime_type | VARCHAR(100) | NULL |
| file_hash | VARCHAR(128) | NULL |
| city | VARCHAR(255) | NULL |
| region | VARCHAR(255) | NULL |
| upload_date | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| price_date | DATE | NULL |
| processing_status | ENUM(ds_processing_status) | DEFAULT 'uploaded' |
| total_lines_found | INTEGER | DEFAULT 0 |
| total_errors | INTEGER | DEFAULT 0 |
| total_new_materials | INTEGER | DEFAULT 0 |
| total_duplicates_found | INTEGER | DEFAULT 0 |
| processing_started_at | TIMESTAMPTZ | NULL |
| processing_finished_at | TIMESTAMPTZ | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- INDEX(supplier_id)
- INDEX(uploaded_by_user_id)
- INDEX(processing_status)
- INDEX(upload_date)
- INDEX(file_hash)

---

### 3.6 raw_product_lines
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| datasource_id | UUID | FK → data_sources.id, NOT NULL |
| supplier_id | UUID | FK → suppliers.id, NOT NULL |
| supplier_branch_id | UUID | FK → supplier_branches.id, NULL |
| row_number | INTEGER | NULL |
| original_name | TEXT | NULL |
| original_price | DECIMAL(15,2) | NULL |
| original_currency | VARCHAR(10) | DEFAULT 'RUB' |
| original_unit | VARCHAR(50) | NULL |
| quantity | DECIMAL(15,4) | NULL |
| total_sum | DECIMAL(15,2) | NULL |
| sku | VARCHAR(100) | NULL |
| brand | VARCHAR(255) | NULL |
| manufacturer | VARCHAR(255) | NULL |
| normalized_name | TEXT | NULL |
| matched_material_id | UUID | FK → materials.id, NULL |
| matched_unit_id | UUID | FK → units.id, NULL |
| confidence_score | DECIMAL(5,4) | NULL |
| processing_status | ENUM(rpl_status) | DEFAULT 'extracted' |
| error_message | TEXT | NULL |
| ai_response | JSONB | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- INDEX(datasource_id)
- INDEX(supplier_id)
- INDEX(matched_material_id)
- INDEX(processing_status)
- INDEX(sku)
- GIN INDEX(original_name) trigram

---

### 3.7 material_categories
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| parent_id | UUID | FK → material_categories.id, NULL |
| name | VARCHAR(255) | NOT NULL |
| slug | VARCHAR(255) | UNIQUE, NOT NULL |
| level | INTEGER | DEFAULT 0 |
| sort_order | INTEGER | DEFAULT 0 |
| created_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- UNIQUE(slug)
- INDEX(parent_id)
- INDEX(level)

---

### 3.8 material_category_schemas
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| category_id | UUID | FK → material_categories.id, NOT NULL |
| required_attributes | JSONB | NOT NULL, DEFAULT '[]' |
| optional_attributes | JSONB | NOT NULL, DEFAULT '[]' |
| comparison_rules | JSONB | NOT NULL, DEFAULT '{}' |
| dedup_rules | JSONB | NOT NULL, DEFAULT '{}' |
| unit_rules | JSONB | NOT NULL, DEFAULT '{}' |
| normalization_rules | JSONB | NOT NULL, DEFAULT '{}' |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- UNIQUE(category_id)

---

### 3.9 materials
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| canonical_name | VARCHAR(500) | NOT NULL |
| category_id | UUID | FK → material_categories.id, NULL |
| subcategory_id | UUID | FK → material_categories.id, NULL |
| base_unit_id | UUID | FK → units.id, NULL |
| brand | VARCHAR(255) | NULL |
| manufacturer | VARCHAR(255) | NULL |
| description | TEXT | NULL |
| status | ENUM(material_status) | DEFAULT 'draft' |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- INDEX(category_id)
- INDEX(brand)
- INDEX(manufacturer)
- INDEX(status)
- GIN INDEX(canonical_name) trigram

---

### 3.10 material_aliases
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| material_id | UUID | FK → materials.id, NOT NULL |
| original_name | TEXT | NOT NULL |
| normalized_name | TEXT | NOT NULL |
| source_supplier_id | UUID | FK → suppliers.id, NULL |
| confidence_score | DECIMAL(5,4) | DEFAULT 0.5 |
| created_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- INDEX(material_id)
- INDEX(source_supplier_id)
- GIN INDEX(normalized_name) trigram

---

### 3.11 material_attributes
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| material_id | UUID | FK → materials.id, NOT NULL |
| attribute_name | VARCHAR(100) | NOT NULL |
| attribute_value | VARCHAR(500) | NOT NULL |
| unit_id | UUID | FK → units.id, NULL |
| sort_order | INTEGER | DEFAULT 0 |

**Индексы:**
- INDEX(material_id)
- INDEX(attribute_name)
- UNIQUE(material_id, attribute_name)

---

### 3.12 units
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| name | VARCHAR(50) | NOT NULL |
| abbreviation | VARCHAR(20) | NOT NULL |
| unit_type | ENUM(unit_type) | NOT NULL |
| is_base | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- UNIQUE(abbreviation)
- INDEX(unit_type)

---

### 3.13 unit_aliases
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| unit_id | UUID | FK → units.id, NOT NULL |
| alias | VARCHAR(50) | NOT NULL |

**Индексы:**
- UNIQUE(alias)
- INDEX(unit_id)

---

### 3.14 unit_conversions
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| from_unit_id | UUID | FK → units.id, NOT NULL |
| to_unit_id | UUID | FK → units.id, NOT NULL |
| factor | DECIMAL(15,6) | NOT NULL |
| condition | TEXT | NULL |
| material_category_id | UUID | FK → material_categories.id, NULL |
| material_id | UUID | FK → materials.id, NULL |

**Индексы:**
- INDEX(from_unit_id, to_unit_id)
- INDEX(material_category_id)

---

### 3.15 supplier_offers
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| material_id | UUID | FK → materials.id, NOT NULL |
| supplier_id | UUID | FK → suppliers.id, NOT NULL |
| supplier_branch_id | UUID | FK → supplier_branches.id, NULL |
| datasource_id | UUID | FK → data_sources.id, NULL |
| raw_product_line_id | UUID | FK → raw_product_lines.id, NULL |
| price | DECIMAL(15,2) | NULL |
| currency | VARCHAR(10) | DEFAULT 'RUB' |
| unit_id | UUID | FK → units.id, NULL |
| price_per_base_unit | DECIMAL(15,2) | NULL |
| min_order_qty | DECIMAL(15,4) | NULL |
| stock_quantity | DECIMAL(15,4) | NULL |
| lead_time_days | INTEGER | NULL |
| city | VARCHAR(255) | NULL |
| region | VARCHAR(255) | NULL |
| price_date | DATE | NULL |
| is_active | BOOLEAN | DEFAULT true |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- INDEX(material_id)
- INDEX(supplier_id)
- INDEX(supplier_branch_id)
- INDEX(city)
- INDEX(region)
- INDEX(is_active)
- INDEX(price_date)

---

### 3.16 price_history
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| material_id | UUID | FK → materials.id, NOT NULL |
| supplier_id | UUID | FK → suppliers.id, NOT NULL |
| supplier_branch_id | UUID | FK → supplier_branches.id, NULL |
| city | VARCHAR(255) | NULL |
| region | VARCHAR(255) | NULL |
| price | DECIMAL(15,2) | NOT NULL |
| currency | VARCHAR(10) | DEFAULT 'RUB' |
| unit_id | UUID | FK → units.id, NULL |
| price_per_base_unit | DECIMAL(15,2) | NULL |
| price_date | DATE | NULL |
| datasource_id | UUID | FK → data_sources.id, NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

**Индексы:**
- INDEX(material_id, supplier_id, price_date)
- INDEX(material_id, city, price_date)
- INDEX(material_id, region, price_date)
- INDEX(price_date)

**ВАЖНО:** Записи НИКОГДА не обновляются и не удаляются. Только INSERT.

---

### 3.17 audit_events
| Поле | Тип | Ограничения |
|------|-----|-------------|
| id | UUID | PK |
| event_type | VARCHAR(100) | NOT NULL |
| entity_type | VARCHAR(100) | NULL |
| entity_id | UUID | NULL |
| user_id | UUID | FK → users.id, NULL |
| details | JSONB | NULL |
| ip_address | VARCHAR(50) | NULL |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Индексы:**
- INDEX(event_type)
- INDEX(entity_type, entity_id)
- INDEX(user_id)
- INDEX(created_at)

---

## 4. ENUM-СПРАВОЧНИКИ

### user_role
- ADMIN
- SUPPLIER
- CONTRACTOR (будущее)
- CUSTOMER (будущее)

### user_status
- active
- inactive
- blocked

### supplier_status
- potential
- verified
- partner
- premium
- blocked

### access_status
- active
- suspended
- revoked

### datasource_type
- ADMIN_UPLOAD
- SUPPLIER_UPLOAD
- API_IMPORT
- EMAIL_IMPORT

### ds_processing_status
- uploaded
- processing
- processed
- partially_processed
- failed
- approved
- rejected

### rpl_status (RawProductLine)
- extracted
- normalized
- matched
- review_required
- approved
- rejected
- error

### material_status
- draft
- verified
- review_required
- archived

### unit_type
- length
- area
- volume
- weight
- quantity
- package

---

## 5. КЛЮЧЕВЫЕ ОГРАНИЧЕНИЯ ЦЕЛОСТНОСТИ

1. price_history — INSERT ONLY, нет UPDATE/DELETE
2. raw_product_lines — хранятся постоянно, аудит происхождения
3. supplier.inn — UNIQUE при NOT NULL
4. user.email — UNIQUE, NOT NULL
5. material_attributes — UNIQUE(material_id, attribute_name)
6. unit_aliases.alias — UNIQUE глобально
7. supplier_accounts — UNIQUE(user_id, supplier_id)
8. material_category_schemas — UNIQUE(category_id)

---

## 6. СОВМЕСТИМОСТЬ С БУДУЩИМИ РОЛЯМИ

### CONTRACTOR (подрядчик)
- Добавится таблица `contractors`
- Добавится `contractor_accounts` (аналог supplier_accounts)
- Связь с materials через `work_items` и `work_prices`
- Не требует изменений текущих таблиц

### CUSTOMER (заказчик)
- Добавится таблица `construction_objects`
- Связь с suppliers через `procurement`
- Связь с materials через `estimates`
- Не требует изменений текущих таблиц

---

## 7. СОВМЕСТИМОСТЬ С БУДУЩИМИ МОДУЛЯМИ

| Модуль | Зависимость от Этапа 1 |
|--------|----------------------|
| Маркетплейс | suppliers, materials, supplier_offers, price_history |
| Тендеры | suppliers, materials, supplier_offers |
| Проверка смет | materials, price_history, units |
| Аналитика рынка | price_history, materials, regions |
| Прогноз цен | price_history, materials |
| AI-консультант | materials, material_attributes, material_category_schemas |
| Цифровой двойник | materials, material_attributes |
