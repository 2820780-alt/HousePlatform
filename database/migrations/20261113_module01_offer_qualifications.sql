BEGIN;
CREATE TABLE IF NOT EXISTS module1_calculation_offer_qualifications (
    id uuid PRIMARY KEY,
    supplier_price_id uuid REFERENCES supplier_prices(id) ON DELETE RESTRICT,
    work_offer_id uuid REFERENCES provider_work_cost_offers(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    status varchar(12) NOT NULL CHECK (status IN ('CONFIRMED', 'WITHDRAWN')),
    terms varchar(500) NOT NULL,
    offer_fingerprint varchar(64) NOT NULL,
    base_units_per_sale_unit numeric(24, 8) CHECK (base_units_per_sale_unit IS NULL OR base_units_per_sale_unit > 0),
    conversion_source text,
    reviewed_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_m1_qualification_offer_owner CHECK (
        (supplier_price_id IS NOT NULL AND work_offer_id IS NULL) OR
        (supplier_price_id IS NULL AND work_offer_id IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_m1_qualification_material_version
    ON module1_calculation_offer_qualifications(supplier_price_id, version) WHERE supplier_price_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_m1_qualification_work_version
    ON module1_calculation_offer_qualifications(work_offer_id, version) WHERE work_offer_id IS NOT NULL;
COMMIT;
