-- Additive migration: back up and apply before deploying the new application.

BEGIN;


CREATE TABLE IF NOT EXISTS life_commitments (
	id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	title VARCHAR(180) NOT NULL, 
	kind VARCHAR NOT NULL, 
	country VARCHAR(2) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	amount_minor BIGINT, 
	due_date DATE NOT NULL, 
	timezone VARCHAR NOT NULL, 
	recurrence VARCHAR NOT NULL, 
	anchor_day INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	notes TEXT NOT NULL, 
	reference_url TEXT, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	history JSON NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX IF NOT EXISTS ix_life_commitments_due_date ON life_commitments (due_date);

CREATE INDEX IF NOT EXISTS ix_life_commitments_user_id ON life_commitments (user_id);


CREATE TABLE IF NOT EXISTS billing_accounts (
	id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	provider VARCHAR NOT NULL, 
	country VARCHAR NOT NULL, 
	tier VARCHAR NOT NULL, 
	provider_id VARCHAR, 
	checkout_id VARCHAR, 
	checkout_url TEXT, 
	status VARCHAR NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	UNIQUE (provider_id)
)

;


CREATE TABLE IF NOT EXISTS billing_events (
	id VARCHAR NOT NULL, 
	provider VARCHAR NOT NULL, 
	event_id VARCHAR NOT NULL, 
	received_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (provider, event_id)
)

;


CREATE TABLE IF NOT EXISTS owned_wishlist (
	id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	target_minor BIGINT, 
	currency VARCHAR(3) NOT NULL, 
	notes TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX IF NOT EXISTS ix_owned_wishlist_user_id ON owned_wishlist (user_id);

COMMIT;
