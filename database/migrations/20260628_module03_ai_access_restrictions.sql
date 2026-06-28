-- Module 03 / Sprint 26: AI Assistant access restrictions
-- AI can explain and draft access changes, but cannot apply administrative decisions.

CREATE TABLE IF NOT EXISTS ai_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_code VARCHAR(160) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    explanation TEXT NOT NULL,
    source_module_code VARCHAR(120) NOT NULL DEFAULT 'MODULE_12_AI_ASSISTANT',
    target_module_code VARCHAR(120),
    canonical_module_code VARCHAR(120),
    feature_code VARCHAR(120),
    widget_code VARCHAR(160),
    role_code VARCHAR(80),
    severity VARCHAR(40) NOT NULL DEFAULT 'INFO',
    status VARCHAR(40) NOT NULL DEFAULT 'DRAFT',
    requires_admin_approval BOOLEAN NOT NULL DEFAULT FALSE,
    payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ai_recommendations_source_module_code
    ON ai_recommendations (source_module_code);

CREATE INDEX IF NOT EXISTS ix_ai_recommendations_canonical_module_code
    ON ai_recommendations (canonical_module_code);

CREATE INDEX IF NOT EXISTS ix_ai_recommendations_widget_code
    ON ai_recommendations (widget_code);

CREATE INDEX IF NOT EXISTS ix_ai_recommendations_role_code
    ON ai_recommendations (role_code);

CREATE INDEX IF NOT EXISTS ix_ai_recommendations_status
    ON ai_recommendations (status);

CREATE TABLE IF NOT EXISTS access_change_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suggestion_code VARCHAR(160) NOT NULL UNIQUE,
    change_type VARCHAR(120) NOT NULL,
    source_module_code VARCHAR(120) NOT NULL DEFAULT 'MODULE_12_AI_ASSISTANT',
    target_user_id VARCHAR(160),
    workspace_id VARCHAR(160),
    module_code VARCHAR(120),
    canonical_module_code VARCHAR(120),
    feature_code VARCHAR(120),
    widget_code VARCHAR(160),
    role_code VARCHAR(80),
    old_value JSONB,
    new_value JSONB,
    reason TEXT,
    created_by VARCHAR(80) NOT NULL DEFAULT 'AI_ASSISTANT',
    approval_status VARCHAR(40) NOT NULL DEFAULT 'PENDING_ADMIN_APPROVAL',
    requires_admin_approval BOOLEAN NOT NULL DEFAULT TRUE,
    approved_by_user_id VARCHAR(160),
    approved_at TIMESTAMP,
    payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_access_change_suggestions_change_type
    ON access_change_suggestions (change_type);

CREATE INDEX IF NOT EXISTS ix_access_change_suggestions_source_module_code
    ON access_change_suggestions (source_module_code);

CREATE INDEX IF NOT EXISTS ix_access_change_suggestions_canonical_module_code
    ON access_change_suggestions (canonical_module_code);

CREATE INDEX IF NOT EXISTS ix_access_change_suggestions_widget_code
    ON access_change_suggestions (widget_code);

CREATE INDEX IF NOT EXISTS ix_access_change_suggestions_role_code
    ON access_change_suggestions (role_code);

CREATE INDEX IF NOT EXISTS ix_access_change_suggestions_approval_status
    ON access_change_suggestions (approval_status);

COMMENT ON TABLE ai_recommendations
IS 'Sprint 26 non-mutating AI Assistant recommendations. AI can explain, find conflicts and prepare recommendations only.';

COMMENT ON TABLE access_change_suggestions
IS 'Sprint 26 AI-generated access-change drafts. Administrative changes require explicit administrator approval before application.';
