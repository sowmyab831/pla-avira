-- RA Avira - Real Estate Intelligence Platform
-- Database Initialization

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- ============================================================
-- CORE TABLES
-- ============================================================

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone VARCHAR(15) UNIQUE,
    email VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    password_hash VARCHAR(255),
    language_preference VARCHAR(10) DEFAULT 'te', -- te, en, hi
    budget_min BIGINT,
    budget_max BIGINT,
    preferred_areas TEXT[],
    property_types TEXT[],
    family_size INTEGER,
    vastu_preference BOOLEAN DEFAULT FALSE,
    investment_goal VARCHAR(50), -- residential, investment, rental
    nri BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Builders
CREATE TABLE builders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE,
    rera_ids TEXT[],
    website VARCHAR(500),
    reputation_score FLOAT DEFAULT 0,
    total_projects INTEGER DEFAULT 0,
    completed_projects INTEGER DEFAULT 0,
    delayed_projects INTEGER DEFAULT 0,
    complaints_count INTEGER DEFAULT 0,
    avg_delay_months FLOAT DEFAULT 0,
    legal_cases INTEGER DEFAULT 0,
    established_year INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Areas / Localities
CREATE TABLE areas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE,
    city VARCHAR(100) DEFAULT 'Hyderabad',
    zone VARCHAR(100), -- West, East, North, South
    pin_codes TEXT[],
    center_lat DOUBLE PRECISION,
    center_lng DOUBLE PRECISION,
    boundary GEOMETRY(POLYGON, 4326),
    avg_price_sqft INTEGER,
    appreciation_1y FLOAT,
    appreciation_3y FLOAT,
    appreciation_5y FLOAT,
    rental_yield FLOAT,
    metro_distance_km FLOAT,
    upcoming_metro BOOLEAN DEFAULT FALSE,
    flood_risk_score FLOAT DEFAULT 0,
    water_availability_score FLOAT DEFAULT 5,
    traffic_score FLOAT DEFAULT 5,
    infrastructure_score FLOAT DEFAULT 5,
    school_density INTEGER DEFAULT 0,
    hospital_density INTEGER DEFAULT 0,
    it_corridor_distance_km FLOAT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Properties (Master)
CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    slug VARCHAR(500),
    property_type VARCHAR(50) NOT NULL, -- apartment, villa, plot, penthouse
    transaction_type VARCHAR(20) NOT NULL, -- sale, resale, rent
    status VARCHAR(30) DEFAULT 'active', -- active, sold, delisted, suspicious
    
    -- Location
    area_id UUID REFERENCES areas(id),
    address TEXT,
    landmark VARCHAR(255),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location GEOMETRY(POINT, 4326),
    pin_code VARCHAR(10),
    
    -- Pricing
    price BIGINT NOT NULL, -- in INR
    price_per_sqft INTEGER,
    registration_value BIGINT,
    market_value_estimate BIGINT,
    negotiable BOOLEAN DEFAULT TRUE,
    
    -- Specifications
    bedrooms INTEGER,
    bathrooms INTEGER,
    balconies INTEGER,
    total_area_sqft INTEGER,
    carpet_area_sqft INTEGER,
    super_buildup_area_sqft INTEGER,
    floor_number INTEGER,
    total_floors INTEGER,
    facing VARCHAR(20), -- East, West, North, South, NE, NW, SE, SW
    age_years INTEGER,
    possession_status VARCHAR(30), -- ready, under_construction, upcoming
    possession_date DATE,
    furnishing VARCHAR(20), -- unfurnished, semi, fully
    parking_count INTEGER DEFAULT 0,
    
    -- Builder
    builder_id UUID REFERENCES builders(id),
    project_name VARCHAR(255),
    rera_id VARCHAR(100),
    
    -- Scores
    overall_score FLOAT DEFAULT 0,
    value_score FLOAT DEFAULT 0,
    legal_score FLOAT DEFAULT 0,
    location_score FLOAT DEFAULT 0,
    builder_score FLOAT DEFAULT 0,
    fraud_probability FLOAT DEFAULT 0,
    
    -- Amenities
    amenities TEXT[],
    
    -- Source tracking
    source VARCHAR(50), -- magicbricks, 99acres, nobroker, instagram, etc.
    source_url TEXT,
    source_listing_id VARCHAR(255),
    
    -- AI
    embedding vector(1536),
    ai_summary TEXT,
    ai_highlights TEXT[],
    ai_concerns TEXT[],
    
    -- Media
    images TEXT[],
    floor_plan_url TEXT,
    video_url TEXT,
    virtual_tour_url TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    crawled_at TIMESTAMP,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Property Price History
CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    price BIGINT NOT NULL,
    price_per_sqft INTEGER,
    recorded_at TIMESTAMP DEFAULT NOW(),
    source VARCHAR(50)
);

-- Listings (Raw crawled data before dedup)
CREATE TABLE raw_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(50) NOT NULL,
    source_url TEXT NOT NULL,
    source_listing_id VARCHAR(255),
    raw_data JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    property_id UUID REFERENCES properties(id),
    duplicate_of UUID REFERENCES raw_listings(id),
    images_hash TEXT[],
    crawled_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- LEGAL & COMPLIANCE
-- ============================================================

CREATE TABLE legal_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID REFERENCES properties(id),
    area_id UUID REFERENCES areas(id),
    record_type VARCHAR(50), -- rera, encumbrance, court_case, complaint, ghmc
    status VARCHAR(30), -- clean, flagged, disputed, resolved
    title TEXT,
    description TEXT,
    source_url TEXT,
    risk_level VARCHAR(10), -- low, medium, high, critical
    details JSONB DEFAULT '{}',
    recorded_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE rera_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rera_number VARCHAR(100) UNIQUE NOT NULL,
    project_name VARCHAR(500),
    builder_id UUID REFERENCES builders(id),
    area_id UUID REFERENCES areas(id),
    status VARCHAR(30), -- registered, expired, revoked, complaint
    registration_date DATE,
    expiry_date DATE,
    total_units INTEGER,
    sold_units INTEGER,
    completion_percentage FLOAT,
    complaints INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- COST BREAKDOWN
-- ============================================================

CREATE TABLE cost_breakdowns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    base_price BIGINT,
    registration_charges BIGINT,
    stamp_duty BIGINT,
    gst BIGINT,
    brokerage BIGINT,
    parking_charges BIGINT,
    clubhouse_charges BIGINT,
    corpus_fund BIGINT,
    maintenance_deposit BIGINT,
    interior_estimate BIGINT,
    loan_processing_fee BIGINT,
    legal_verification BIGINT,
    furnishing_estimate BIGINT,
    hidden_charges BIGINT,
    total_ownership_cost BIGINT,
    monthly_emi_estimate BIGINT,
    monthly_maintenance BIGINT,
    notes JSONB DEFAULT '{}',
    calculated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- AI & CONVERSATIONS
-- ============================================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    language VARCHAR(10) DEFAULT 'te',
    context JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    language VARCHAR(10),
    voice_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- RECOMMENDATIONS & INTERACTIONS
-- ============================================================

CREATE TABLE user_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    property_id UUID REFERENCES properties(id),
    interaction_type VARCHAR(30), -- view, save, call, visit, reject, share
    duration_seconds INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE saved_properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, property_id)
);

CREATE TABLE site_visits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    property_id UUID REFERENCES properties(id),
    scheduled_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, completed, cancelled
    notes TEXT,
    rating INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- SOCIAL MEDIA DISCOVERY
-- ============================================================

CREATE TABLE social_media_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform VARCHAR(30) NOT NULL, -- instagram, youtube, telegram, facebook, twitter
    source_type VARCHAR(30), -- reel, post, video, message, tweet
    source_url TEXT NOT NULL,
    source_id VARCHAR(255),
    author VARCHAR(255),
    content TEXT,
    transcription TEXT,
    extracted_data JSONB DEFAULT '{}', -- AI extracted: price, area, type, etc.
    property_id UUID REFERENCES properties(id),
    processed BOOLEAN DEFAULT FALSE,
    sentiment_score FLOAT,
    urgency_score FLOAT,
    fake_probability FLOAT DEFAULT 0,
    media_urls TEXT[],
    crawled_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- AREA STATISTICS & INVESTMENT
-- ============================================================

CREATE TABLE area_price_trends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    area_id UUID REFERENCES areas(id),
    month DATE NOT NULL,
    avg_price_sqft INTEGER,
    median_price_sqft INTEGER,
    transaction_count INTEGER,
    rental_avg INTEGER,
    appreciation_pct FLOAT,
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE infrastructure_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(500) NOT NULL,
    project_type VARCHAR(50), -- metro, road, flyover, it_park, airport, hospital
    status VARCHAR(30), -- announced, under_construction, completed
    completion_date DATE,
    affected_areas UUID[],
    impact_radius_km FLOAT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    estimated_appreciation_pct FLOAT,
    source_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_properties_area ON properties(area_id);
CREATE INDEX idx_properties_type ON properties(property_type);
CREATE INDEX idx_properties_price ON properties(price);
CREATE INDEX idx_properties_bedrooms ON properties(bedrooms);
CREATE INDEX idx_properties_status ON properties(status);
CREATE INDEX idx_properties_source ON properties(source);
CREATE INDEX idx_properties_builder ON properties(builder_id);
CREATE INDEX idx_properties_location ON properties USING GIST(location);
CREATE INDEX idx_properties_embedding ON properties USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_properties_fraud ON properties(fraud_probability) WHERE fraud_probability > 0.5;

CREATE INDEX idx_price_history_property ON price_history(property_id);
CREATE INDEX idx_legal_records_property ON legal_records(property_id);
CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_interactions_user ON user_interactions(user_id);
CREATE INDEX idx_interactions_property ON user_interactions(property_id);
CREATE INDEX idx_area_trends_area ON area_price_trends(area_id, month);
CREATE INDEX idx_social_platform ON social_media_sources(platform, processed);

-- Full text search
CREATE INDEX idx_properties_title_fts ON properties USING GIN(to_tsvector('english', title));
CREATE INDEX idx_properties_address_fts ON properties USING GIN(to_tsvector('english', COALESCE(address, '')));
