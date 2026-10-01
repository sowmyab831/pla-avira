-- Additive migration (Release 1, AI gateway): back up and apply before deploying.

BEGIN;

CREATE TABLE IF NOT EXISTS ai_connections (
	id VARCHAR NOT NULL, 
	owner_kind VARCHAR NOT NULL, 
	owner_id VARCHAR NOT NULL, 
	provider VARCHAR NOT NULL, 
	label VARCHAR(80) NOT NULL, 
	endpoint_ref VARCHAR, 
	secret_ciphertext TEXT, 
	secret_hint VARCHAR(12), 
	encryption_version VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	last_checked_at TIMESTAMP WITHOUT TIME ZONE, 
	last_error VARCHAR(200), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_ai_conn_owner_provider ON ai_connections (owner_kind, owner_id, provider);
CREATE INDEX IF NOT EXISTS ix_ai_connections_owner_id ON ai_connections (owner_id);

CREATE TABLE IF NOT EXISTS ai_model_catalog (
	id VARCHAR NOT NULL, 
	provider VARCHAR NOT NULL, 
	model_id VARCHAR NOT NULL, 
	display_name VARCHAR(120) NOT NULL, 
	capabilities JSON NOT NULL, 
	lifecycle VARCHAR NOT NULL, 
	tier VARCHAR NOT NULL, 
	context_window INTEGER, 
	source_url TEXT, 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	price_version VARCHAR, 
	price_micro_usd JSON, 
	enabled BOOLEAN NOT NULL, 
	notes TEXT NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (provider, model_id)
);

CREATE INDEX IF NOT EXISTS ix_ai_model_catalog_provider ON ai_model_catalog (provider);

CREATE TABLE IF NOT EXISTS ai_preferences (
	id VARCHAR NOT NULL, 
	scope_kind VARCHAR NOT NULL, 
	scope_id VARCHAR NOT NULL, 
	mode VARCHAR NOT NULL, 
	profile VARCHAR NOT NULL, 
	default_provider VARCHAR, 
	default_model VARCHAR, 
	per_task JSON NOT NULL, 
	fallback_providers JSON NOT NULL, 
	cloud_allowed BOOLEAN NOT NULL, 
	max_data_class_cloud VARCHAR NOT NULL, 
	detail_level VARCHAR NOT NULL, 
	monthly_cap_micro_usd BIGINT, 
	version INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (scope_kind, scope_id)
);

CREATE INDEX IF NOT EXISTS ix_ai_preferences_scope_id ON ai_preferences (scope_id);

CREATE TABLE IF NOT EXISTS ai_budget_accounts (
	id VARCHAR NOT NULL, 
	scope_kind VARCHAR NOT NULL, 
	scope_id VARCHAR NOT NULL, 
	funding VARCHAR NOT NULL, 
	period VARCHAR NOT NULL, 
	limit_micro_usd BIGINT, 
	reserved_micro_usd BIGINT NOT NULL, 
	spent_micro_usd BIGINT NOT NULL, 
	pending_micro_usd BIGINT NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (scope_kind, scope_id, period, funding)
);

CREATE INDEX IF NOT EXISTS ix_ai_budget_accounts_scope_id ON ai_budget_accounts (scope_id);

CREATE TABLE IF NOT EXISTS ai_usage_events (
	id VARCHAR NOT NULL, 
	request_id VARCHAR NOT NULL, 
	idempotency_key VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	task VARCHAR NOT NULL, 
	provider VARCHAR NOT NULL, 
	model VARCHAR NOT NULL, 
	locality VARCHAR NOT NULL, 
	funding VARCHAR NOT NULL, 
	connection_id VARCHAR, 
	state VARCHAR NOT NULL, 
	reserved_micro_usd BIGINT NOT NULL, 
	actual_micro_usd BIGINT, 
	price_version VARCHAR, 
	usage JSON NOT NULL, 
	provider_request_id VARCHAR, 
	fallback_from VARCHAR, 
	attempt INTEGER NOT NULL, 
	latency_ms INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	settled_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS ix_ai_usage_events_created_at ON ai_usage_events (created_at);
CREATE INDEX IF NOT EXISTS ix_ai_usage_events_user_id ON ai_usage_events (user_id);
CREATE INDEX IF NOT EXISTS ix_ai_usage_events_tenant_id ON ai_usage_events (tenant_id);
CREATE INDEX IF NOT EXISTS ix_ai_usage_events_request_id ON ai_usage_events (request_id);

CREATE TABLE IF NOT EXISTS ai_audit_events (
	id VARCHAR NOT NULL, 
	actor_id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	action VARCHAR NOT NULL, 
	target VARCHAR, 
	decision VARCHAR, 
	reason VARCHAR(200), 
	request_id VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_ai_audit_events_actor_id ON ai_audit_events (actor_id);
CREATE INDEX IF NOT EXISTS ix_ai_audit_events_created_at ON ai_audit_events (created_at);

COMMIT;

-- Rollback (data-destroying; only if the release is abandoned):
-- DROP TABLE ai_audit_events, ai_usage_events, ai_budget_accounts, ai_preferences, ai_model_catalog, ai_connections;