-- Module 01 / Provider Work Cost Offers
-- Adds a separate persistence contract for performer-entered work cost offers.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS provider_work_cost_offers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    work_code varchar(120) NOT NULL,
    owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    region varchar(255) NOT NULL,
    pricing_mode varchar(20) NOT NULL,
    fixed_amount numeric(15, 2),
    minimum_amount numeric(15, 2),
    maximum_amount numeric(15, 2),
    currency varchar(10) NOT NULL DEFAULT 'RUB',
    pricing_unit varchar(50) NOT NULL,
    valid_from date,
    valid_until date,
    status varchar(30) NOT NULL DEFAULT 'draft',
    comment text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    updated_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT ck_provider_work_cost_pricing_mode CHECK (pricing_mode in ('fixed', 'range')),
    CONSTRAINT ck_provider_work_cost_status CHECK (status in ('draft', 'active', 'inactive')),
    CONSTRAINT ck_provider_work_cost_fixed_positive CHECK (fixed_amount is null or fixed_amount > 0),
    CONSTRAINT ck_provider_work_cost_min_positive CHECK (minimum_amount is null or minimum_amount > 0),
    CONSTRAINT ck_provider_work_cost_max_positive CHECK (maximum_amount is null or maximum_amount > 0),
    CONSTRAINT ck_provider_work_cost_validity CHECK (valid_until is null or valid_from is null or valid_until >= valid_from),
    CONSTRAINT ck_provider_work_cost_amount_contract CHECK (
        (
            pricing_mode = 'fixed'
            and fixed_amount is not null
            and minimum_amount is null
            and maximum_amount is null
        )
        or (
            pricing_mode = 'range'
            and fixed_amount is null
            and minimum_amount is not null
            and maximum_amount is not null
            and minimum_amount <= maximum_amount
        )
    )
);

CREATE INDEX IF NOT EXISTS ix_provider_work_cost_offers_work_code
    ON provider_work_cost_offers(work_code);
CREATE INDEX IF NOT EXISTS ix_provider_work_cost_offers_owner_user_id
    ON provider_work_cost_offers(owner_user_id);
CREATE INDEX IF NOT EXISTS ix_provider_work_cost_offers_region
    ON provider_work_cost_offers(region);
CREATE INDEX IF NOT EXISTS ix_provider_work_cost_offers_status
    ON provider_work_cost_offers(status);
CREATE INDEX IF NOT EXISTS ix_provider_work_cost_offers_valid_until
    ON provider_work_cost_offers(valid_until);
CREATE INDEX IF NOT EXISTS ix_provider_work_cost_owner_work_code
    ON provider_work_cost_offers(owner_user_id, work_code);
CREATE INDEX IF NOT EXISTS ix_provider_work_cost_region_status
    ON provider_work_cost_offers(region, status);

COMMIT;
