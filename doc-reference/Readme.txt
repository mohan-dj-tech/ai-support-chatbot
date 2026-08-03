https://google.github.io/adk-docs/
https://google.github.io/adk-docs/get-started/python/


https://medium.com/@dzbik.konrad/google-adk-on-your-local-machine-a-beginners-guide-6914300b2283


https://github.com/google/adk-samples/tree/main/python/agents


Useful Commands:
----------------
adk create my_agent
adk run my_agent
adk web --port 8000
adk web --log_level DEBUG

pip install -r requirements.txt

-----------------------------------------------------------------------------------------------------------------------------------------------

select RecordId as record_id, CountryCode as country_code, BusinessCode as business_code, Email as email, ApiName as api_name, ErrorResponse as error_response, CreatedDateTime as create_date_time from  ApiRetryProcessingJob where Status = 'PENDING' and CAST(CreatedDateTime as DATE)  BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH) AND CURRENT_DATE();


DuckDB:
./duckdb.exe analytics.duckdb

 CREATE TABLE api_error_logs (
	record_id       VARCHAR PRIMARY KEY,
	country_code    VARCHAR(2),
	business_code   VARCHAR,
	email          VARCHAR,
	api_name        VARCHAR NOT NULL,
	error_response  VARCHAR,
	create_date_time TIMESTAMP
);
						
COPY api_error_logs FROM 'C:\Mohan_DJ_WorkSpace\Softwares\AI Project Softwares\DBDumpEMEA.csv' (HEADER, DELIMITER ',');

CREATE TABLE country_mappings (
    country_code VARCHAR(5) PRIMARY KEY,
    name VARCHAR
);

COPY country_mappings FROM 'C:\Mohan_DJ_WorkSpace\Softwares\AI Project Softwares\DBDump\Country.csv' (HEADER, DELIMITER ',');

 CREATE TABLE IF NOT EXISTS servicenow_incidents (
                    number VARCHAR PRIMARY KEY,
                    sys_id VARCHAR,
                    short_description VARCHAR,
                    description VARCHAR,
                    state VARCHAR,
                    priority VARCHAR,
                    assigned_to VARCHAR,
                    sys_created_on TIMESTAMP
                )


