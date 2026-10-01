-- Additive migration (Releases 2–4: memory/capture, durable jobs, tracked
-- products, family member lifecycle). Back up and apply before deploying.

BEGIN;

CREATE TABLE IF NOT EXISTS memory_items (
	id VARCHAR NOT NULL,
	user_id VARCHAR NOT NULL,
	kind VARCHAR(32) NOT NULL,
	text TEXT NOT NULL,
	tags JSON,
	source VARCHAR(32) NOT NULL,
	pinned BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_memory_items_user_id ON memory_items (user_id);

CREATE TABLE IF NOT EXISTS jobs (
	id VARCHAR NOT NULL,
	kind VARCHAR(64) NOT NULL,
	payload JSON NOT NULL,
	status VARCHAR(16) NOT NULL,
	run_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	attempts INTEGER NOT NULL,
	max_attempts INTEGER NOT NULL,
	locked_by VARCHAR(64),
	locked_at TIMESTAMP WITHOUT TIME ZONE,
	dedupe_key VARCHAR(128),
	result JSON,
	last_error TEXT,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	finished_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (dedupe_key)
);
CREATE INDEX IF NOT EXISTS ix_jobs_run_at ON jobs (run_at);
CREATE INDEX IF NOT EXISTS ix_jobs_status_run_at ON jobs (status, run_at);
CREATE INDEX IF NOT EXISTS ix_jobs_kind ON jobs (kind);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs (status);

CREATE TABLE IF NOT EXISTS tracked_products (
	id VARCHAR NOT NULL,
	user_id VARCHAR NOT NULL,
	product_key VARCHAR(256) NOT NULL,
	title VARCHAR(300) NOT NULL,
	retailer VARCHAR(120),
	url TEXT,
	currency VARCHAR(3) NOT NULL,
	target_minor BIGINT,
	drop_pct INTEGER NOT NULL,
	baseline_minor BIGINT,
	last_minor BIGINT,
	active BOOLEAN NOT NULL,
	last_alerted_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_tracked_products_user_id ON tracked_products (user_id);
CREATE INDEX IF NOT EXISTS ix_tracked_products_product_key ON tracked_products (product_key);
CREATE UNIQUE INDEX IF NOT EXISTS ix_tracked_user_key ON tracked_products (user_id, product_key);

ALTER TABLE family_members ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active';
UPDATE family_members SET status = 'active' WHERE status IS NULL;

COMMIT;
