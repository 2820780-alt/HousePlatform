-- Module 03 / Sprint 1.1. PlatformRegionRegistry and pilot region
-- Adds platform regional registry tables and seeds Krasnodar Krai as data, not code logic.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'region_status') THEN
        CREATE TYPE region_status AS ENUM ('DRAFT', 'ACTIVE', 'DISABLED', 'ARCHIVED');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS platform_regions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(120) NOT NULL UNIQUE,
    name varchar(255) NOT NULL,
    country varchar(10) NOT NULL DEFAULT 'RU',
    status region_status NOT NULL DEFAULT 'DRAFT',
    is_active boolean NOT NULL DEFAULT false,
    is_pilot_region boolean NOT NULL DEFAULT false,
    is_open_for_users boolean NOT NULL DEFAULT false,
    is_open_for_suppliers boolean NOT NULL DEFAULT false,
    is_open_for_marketplace boolean NOT NULL DEFAULT false,
    is_open_for_analytics boolean NOT NULL DEFAULT false,
    display_order integer NOT NULL DEFAULT 100,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_platform_regions_code ON platform_regions(code);
CREATE INDEX IF NOT EXISTS ix_platform_regions_name ON platform_regions(name);
CREATE INDEX IF NOT EXISTS ix_platform_regions_country ON platform_regions(country);
CREATE INDEX IF NOT EXISTS ix_platform_regions_status ON platform_regions(status);
CREATE INDEX IF NOT EXISTS ix_platform_regions_is_active ON platform_regions(is_active);
CREATE INDEX IF NOT EXISTS ix_platform_regions_is_pilot_region ON platform_regions(is_pilot_region);
CREATE INDEX IF NOT EXISTS ix_platform_regions_display_order ON platform_regions(display_order);
ALTER TABLE platform_regions ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE platform_regions ALTER COLUMN country SET DEFAULT 'RU';
ALTER TABLE platform_regions ALTER COLUMN status SET DEFAULT 'DRAFT';
ALTER TABLE platform_regions ALTER COLUMN is_active SET DEFAULT false;
ALTER TABLE platform_regions ALTER COLUMN is_pilot_region SET DEFAULT false;
ALTER TABLE platform_regions ALTER COLUMN is_open_for_users SET DEFAULT false;
ALTER TABLE platform_regions ALTER COLUMN is_open_for_suppliers SET DEFAULT false;
ALTER TABLE platform_regions ALTER COLUMN is_open_for_marketplace SET DEFAULT false;
ALTER TABLE platform_regions ALTER COLUMN is_open_for_analytics SET DEFAULT false;
ALTER TABLE platform_regions ALTER COLUMN display_order SET DEFAULT 100;
ALTER TABLE platform_regions ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE platform_regions ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS platform_cities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id uuid NOT NULL REFERENCES platform_regions(id),
    name varchar(255) NOT NULL,
    status region_status NOT NULL DEFAULT 'ACTIVE',
    display_order integer NOT NULL DEFAULT 100,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_platform_cities_region_id ON platform_cities(region_id);
CREATE INDEX IF NOT EXISTS ix_platform_cities_name ON platform_cities(name);
CREATE INDEX IF NOT EXISTS ix_platform_cities_status ON platform_cities(status);
CREATE INDEX IF NOT EXISTS ix_platform_cities_display_order ON platform_cities(display_order);
CREATE UNIQUE INDEX IF NOT EXISTS ux_platform_cities_region_name ON platform_cities(region_id, name);
ALTER TABLE platform_cities ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE platform_cities ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE platform_cities ALTER COLUMN display_order SET DEFAULT 100;
ALTER TABLE platform_cities ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE platform_cities ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS delivery_zones (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id uuid NOT NULL REFERENCES platform_regions(id),
    city_id uuid REFERENCES platform_cities(id),
    name varchar(255) NOT NULL,
    description text,
    status region_status NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_delivery_zones_region_id ON delivery_zones(region_id);
CREATE INDEX IF NOT EXISTS ix_delivery_zones_city_id ON delivery_zones(city_id);
CREATE INDEX IF NOT EXISTS ix_delivery_zones_name ON delivery_zones(name);
CREATE INDEX IF NOT EXISTS ix_delivery_zones_status ON delivery_zones(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_delivery_zones_scope_name
    ON delivery_zones(region_id, COALESCE(city_id, '00000000-0000-0000-0000-000000000000'::uuid), name);
ALTER TABLE delivery_zones ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE delivery_zones ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE delivery_zones ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE delivery_zones ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS active_regions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id uuid NOT NULL REFERENCES platform_regions(id),
    scope varchar(50) NOT NULL DEFAULT 'GENERAL',
    status region_status NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_active_regions_region_id ON active_regions(region_id);
CREATE INDEX IF NOT EXISTS ix_active_regions_scope ON active_regions(scope);
CREATE INDEX IF NOT EXISTS ix_active_regions_status ON active_regions(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_regions_region_scope ON active_regions(region_id, scope);
ALTER TABLE active_regions ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE active_regions ALTER COLUMN scope SET DEFAULT 'GENERAL';
ALTER TABLE active_regions ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE active_regions ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE active_regions ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS pilot_regions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id uuid NOT NULL REFERENCES platform_regions(id),
    pilot_key varchar(120) NOT NULL DEFAULT 'MVP',
    status region_status NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_pilot_regions_region_id ON pilot_regions(region_id);
CREATE INDEX IF NOT EXISTS ix_pilot_regions_pilot_key ON pilot_regions(pilot_key);
CREATE INDEX IF NOT EXISTS ix_pilot_regions_status ON pilot_regions(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_pilot_regions_pilot_key ON pilot_regions(pilot_key);
ALTER TABLE pilot_regions ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE pilot_regions ALTER COLUMN pilot_key SET DEFAULT 'MVP';
ALTER TABLE pilot_regions ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE pilot_regions ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE pilot_regions ALTER COLUMN updated_at SET DEFAULT now();

INSERT INTO platform_regions (
    code,
    name,
    country,
    status,
    is_active,
    is_pilot_region,
    is_open_for_users,
    is_open_for_suppliers,
    is_open_for_marketplace,
    is_open_for_analytics,
    display_order
)
VALUES (
    'KRASNODAR_KRAI',
    U&'\041A\0440\0430\0441\043D\043E\0434\0430\0440\0441\043A\0438\0439\0020\043A\0440\0430\0439',
    'RU',
    'ACTIVE',
    true,
    true,
    false,
    false,
    false,
    true,
    10
)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    country = EXCLUDED.country,
    status = EXCLUDED.status,
    is_active = EXCLUDED.is_active,
    is_pilot_region = EXCLUDED.is_pilot_region,
    is_open_for_analytics = EXCLUDED.is_open_for_analytics,
    display_order = EXCLUDED.display_order,
    updated_at = now();

INSERT INTO active_regions (region_id, scope, status)
SELECT id, 'GENERAL', 'ACTIVE'
FROM platform_regions
WHERE code = 'KRASNODAR_KRAI'
ON CONFLICT (region_id, scope) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = now();

INSERT INTO pilot_regions (region_id, pilot_key, status)
SELECT id, 'MVP', 'ACTIVE'
FROM platform_regions
WHERE code = 'KRASNODAR_KRAI'
ON CONFLICT (pilot_key) DO UPDATE SET
    region_id = EXCLUDED.region_id,
    status = EXCLUDED.status,
    updated_at = now();

COMMIT;
