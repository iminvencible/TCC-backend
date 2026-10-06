-- Generated from Alembic migrations for MySQL 8; use alembic upgrade head for existing databases.

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> b6f535f44c51

CREATE TABLE roles (
    id INTEGER NOT NULL AUTO_INCREMENT,
    code VARCHAR(32) NOT NULL,
    display_name VARCHAR(64) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (code)
);

CREATE TABLE users (
    id INTEGER NOT NULL AUTO_INCREMENT,
    public_code VARCHAR(24) NOT NULL,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id INTEGER NOT NULL,
    city VARCHAR(100),
    state VARCHAR(2),
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    weather_notifications BOOL NOT NULL,
    alert_sound BOOL NOT NULL,
    dark_theme BOOL NOT NULL,
    email_verified_at DATETIME,
    is_active BOOL NOT NULL,
    token_version INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_user_coordinates_pair CHECK ((latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)),
    CONSTRAINT ck_user_lat CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_user_lon CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT,
    UNIQUE (email),
    UNIQUE (public_code)
);

CREATE INDEX ix_users_name ON users (name);

CREATE INDEX ix_users_role_id ON users (role_id);

CREATE TABLE educational_contents (
    id INTEGER NOT NULL AUTO_INCREMENT,
    source_key VARCHAR(80),
    author_id INTEGER,
    title VARCHAR(180) NOT NULL,
    body TEXT NOT NULL,
    media_url VARCHAR(500),
    reference_url VARCHAR(500) NOT NULL,
    published_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE SET NULL,
    UNIQUE (source_key)
);

CREATE INDEX ix_education_published ON educational_contents (published_at);

CREATE TABLE forecasts (
    id INTEGER NOT NULL AUTO_INCREMENT,
    source_key VARCHAR(80),
    created_by INTEGER,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(2) NOT NULL,
    `condition` VARCHAR(120) NOT NULL,
    temperature_c NUMERIC(5, 2) NOT NULL,
    minimum_c NUMERIC(5, 2) NOT NULL,
    maximum_c NUMERIC(5, 2) NOT NULL,
    humidity INTEGER NOT NULL,
    wind_kmh NUMERIC(6, 2) NOT NULL,
    rain_probability INTEGER NOT NULL,
    severity VARCHAR(24) NOT NULL,
    description TEXT,
    polygon JSON,
    source_name VARCHAR(120) NOT NULL,
    issued_at DATETIME NOT NULL,
    valid_until DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_forecast_humidity CHECK (humidity BETWEEN 0 AND 100),
    CONSTRAINT ck_forecast_rain CHECK (rain_probability BETWEEN 0 AND 100),
    CONSTRAINT ck_forecast_validity CHECK (valid_until > issued_at),
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL,
    UNIQUE (source_key)
);

CREATE INDEX ix_forecasts_location_valid ON forecasts (city, state, valid_until);

CREATE TABLE news (
    id INTEGER NOT NULL AUTO_INCREMENT,
    author_id INTEGER,
    title VARCHAR(180) NOT NULL,
    summary TEXT NOT NULL,
    body TEXT NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    image_url VARCHAR(500),
    published_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_news_published ON news (published_at);

CREATE TABLE weather_alerts (
    id INTEGER NOT NULL AUTO_INCREMENT,
    source_key VARCHAR(80),
    is_demo BOOL NOT NULL,
    created_by INTEGER,
    title VARCHAR(140) NOT NULL,
    message TEXT NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    severity VARCHAR(24) NOT NULL,
    area_name VARCHAR(160) NOT NULL,
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    radius_km NUMERIC(7, 2),
    polygon JSON,
    recommendations JSON NOT NULL,
    issued_at DATETIME NOT NULL,
    valid_until DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_alert_lat CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_alert_lon CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CONSTRAINT ck_alert_coordinates_pair CHECK ((latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)),
    CONSTRAINT ck_alert_radius CHECK (radius_km IS NULL OR radius_km > 0),
    CONSTRAINT ck_alert_has_area CHECK (polygon IS NOT NULL OR (latitude IS NOT NULL AND longitude IS NOT NULL AND radius_km IS NOT NULL)),
    CONSTRAINT ck_alert_severity CHECK (severity IN ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')),
    CONSTRAINT ck_alert_validity CHECK (valid_until > issued_at),
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT,
    UNIQUE (source_key)
);

CREATE INDEX ix_alerts_active ON weather_alerts (valid_until, severity);

CREATE TABLE weather_reports (
    id INTEGER NOT NULL AUTO_INCREMENT,
    reporter_id INTEGER NOT NULL,
    reviewer_id INTEGER,
    description TEXT NOT NULL,
    occurred_at DATETIME NOT NULL,
    latitude NUMERIC(9, 6) NOT NULL,
    longitude NUMERIC(9, 6) NOT NULL,
    image_url VARCHAR(500),
    status VARCHAR(24) NOT NULL,
    review_notes TEXT,
    reviewed_at DATETIME,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_report_lat CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_report_lon CHECK (longitude BETWEEN -180 AND 180),
    CONSTRAINT ck_report_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    FOREIGN KEY(reporter_id) REFERENCES users (id) ON DELETE RESTRICT,
    FOREIGN KEY(reviewer_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_reports_review_queue ON weather_reports (status, created_at);

CREATE INDEX ix_reports_reporter_created ON weather_reports (reporter_id, created_at);

CREATE TABLE alert_reads (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    alert_id INTEGER NOT NULL,
    read_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(alert_id) REFERENCES weather_alerts (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT uq_alert_read_user_alert UNIQUE (user_id, alert_id)
);

INSERT INTO alembic_version (version_num) VALUES ('b6f535f44c51');

-- Running upgrade b6f535f44c51 -> 9d62a8f410be

UPDATE roles SET code = 'ADMIN', display_name = 'Administrador' WHERE code = 'OWNER';

UPDATE roles SET display_name = 'Usu�rio' WHERE code = 'USER';

ALTER TABLE weather_alerts ADD COLUMN origin VARCHAR(16) NOT NULL DEFAULT 'MANUAL';

ALTER TABLE weather_alerts ADD COLUMN source_name VARCHAR(120) NOT NULL DEFAULT 'PrevClima';

ALTER TABLE weather_alerts ADD COLUMN source_url VARCHAR(500);

ALTER TABLE weather_alerts ADD COLUMN validation_status VARCHAR(24) NOT NULL DEFAULT 'ACTIVE';

ALTER TABLE weather_alerts ADD COLUMN status_reason TEXT;

ALTER TABLE weather_alerts ADD COLUMN status_changed_by INTEGER;

ALTER TABLE weather_alerts ADD COLUMN status_changed_at DATETIME;

ALTER TABLE weather_alerts ADD CONSTRAINT ck_alert_origin CHECK (origin IN ('DEMO', 'MANUAL', 'INMET'));

ALTER TABLE weather_alerts ADD CONSTRAINT ck_alert_validation_status CHECK (validation_status IN ('ACTIVE', 'FALSE_ALARM', 'NEEDS_CORRECTION'));

ALTER TABLE weather_alerts ADD CONSTRAINT fk_weather_alerts_status_changed_by_users FOREIGN KEY(status_changed_by) REFERENCES users (id) ON DELETE SET NULL;

CREATE INDEX ix_alerts_validation ON weather_alerts (validation_status, valid_until);

UPDATE weather_alerts SET origin = 'DEMO', source_name = 'PrevClima - demonstracao' WHERE is_demo = TRUE;

CREATE TABLE alert_reviews (
    id INTEGER NOT NULL AUTO_INCREMENT,
    alert_id INTEGER NOT NULL,
    reviewer_id INTEGER NOT NULL,
    previous_status VARCHAR(24) NOT NULL,
    new_status VARCHAR(24) NOT NULL,
    reason TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_alert_review_previous_status CHECK (previous_status IN ('ACTIVE', 'FALSE_ALARM', 'NEEDS_CORRECTION')),
    CONSTRAINT ck_alert_review_new_status CHECK (new_status IN ('ACTIVE', 'FALSE_ALARM', 'NEEDS_CORRECTION')),
    FOREIGN KEY(alert_id) REFERENCES weather_alerts (id) ON DELETE RESTRICT,
    FOREIGN KEY(reviewer_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_alert_reviews_alert_created ON alert_reviews (alert_id, created_at);

CREATE TABLE audit_events (
    id INTEGER NOT NULL AUTO_INCREMENT,
    actor_id INTEGER,
    action VARCHAR(80) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id VARCHAR(64) NOT NULL,
    details JSON NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_target_created ON audit_events (target_type, target_id, created_at);

UPDATE alembic_version SET version_num='9d62a8f410be' WHERE alembic_version.version_num = 'b6f535f44c51';

-- Running upgrade 9d62a8f410be -> 4a8c1e7d2b90

ALTER TABLE forecasts ADD COLUMN source_url VARCHAR(500);

UPDATE alembic_version SET version_num='4a8c1e7d2b90' WHERE alembic_version.version_num = '9d62a8f410be';

-- Running upgrade 4a8c1e7d2b90 -> 5f0e7c29b4a1

ALTER TABLE forecasts ADD COLUMN latitude NUMERIC(9, 6);

ALTER TABLE forecasts ADD COLUMN longitude NUMERIC(9, 6);

ALTER TABLE forecasts ADD CONSTRAINT ck_forecast_lat CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90);

ALTER TABLE forecasts ADD CONSTRAINT ck_forecast_lon CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180);

ALTER TABLE forecasts ADD CONSTRAINT ck_forecast_coordinates_pair CHECK ((latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL));

CREATE INDEX ix_forecasts_coords_valid ON forecasts (latitude, longitude, valid_until);

ALTER TABLE weather_alerts DROP CHECK ck_alert_has_area;

ALTER TABLE weather_alerts ADD CONSTRAINT ck_alert_has_area CHECK (origin = 'INMET' OR polygon IS NOT NULL OR (latitude IS NOT NULL AND longitude IS NOT NULL AND radius_km IS NOT NULL));

UPDATE alembic_version SET version_num='5f0e7c29b4a1' WHERE alembic_version.version_num = '4a8c1e7d2b90';

-- Running upgrade 5f0e7c29b4a1 -> 3b6f82078bcf

CREATE TABLE weather_stations (
    code VARCHAR(16) NOT NULL,
    name VARCHAR(120) NOT NULL,
    state VARCHAR(2),
    kind VARCHAR(20) NOT NULL,
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (code),
    CONSTRAINT ck_station_lat CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_station_lon CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);

CREATE INDEX ix_stations_state_name ON weather_stations (state, name);

CREATE TABLE station_observations (
    id INTEGER NOT NULL AUTO_INCREMENT,
    station_code VARCHAR(16) NOT NULL,
    observed_at DATETIME NOT NULL,
    period VARCHAR(10) NOT NULL,
    temperature_c NUMERIC(6, 2),
    minimum_c NUMERIC(6, 2),
    maximum_c NUMERIC(6, 2),
    humidity NUMERIC(5, 2),
    precipitation_mm NUMERIC(9, 2),
    wind_ms NUMERIC(6, 2),
    source VARCHAR(32) NOT NULL,
    imported_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_observation_period CHECK (period IN ('HOURLY', 'DAILY', 'MONTHLY')),
    CONSTRAINT ck_observation_humidity CHECK (humidity IS NULL OR humidity BETWEEN 0 AND 100),
    CONSTRAINT ck_observation_rain CHECK (precipitation_mm IS NULL OR precipitation_mm >= 0),
    CONSTRAINT ck_observation_wind CHECK (wind_ms IS NULL OR wind_ms >= 0),
    FOREIGN KEY(station_code) REFERENCES weather_stations (code) ON DELETE RESTRICT,
    CONSTRAINT uq_station_observation UNIQUE (station_code, observed_at, period)
);

CREATE INDEX ix_observations_time ON station_observations (observed_at);

UPDATE alembic_version SET version_num='3b6f82078bcf' WHERE alembic_version.version_num = '5f0e7c29b4a1';
