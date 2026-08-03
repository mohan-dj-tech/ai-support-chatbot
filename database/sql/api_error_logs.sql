CREATE TABLE IF NOT EXISTS api_error_logs (
	record_id       VARCHAR PRIMARY KEY,
	country_code    VARCHAR(2),
	business_code   VARCHAR,
	email          VARCHAR,
	api_name        VARCHAR NOT NULL,
	error_response  VARCHAR,
	create_date_time TIMESTAMP
);