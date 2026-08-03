CREATE OR REPLACE VIEW v_normalized_api_errors AS
SELECT
    record_id,
    country_code,
    business_code,
    email,
    api_name,
    error_response,
    create_date_time,
    CAST(create_date_time AS DATE) AS log_date,
    CASE
        -- Service Point Creation
        WHEN TRIM(error_response) ILIKE '%1:%' THEN 'Service point creation error due to missing building / floor / department in PNOL'

        -- Dynamic Visit Processing (Case-insensitive & handles leading whitespace/prefixes)
        WHEN TRIM(error_response) ILIKE '%20093:% Unable to find LOCATION with value % in PREP_USED' THEN '20093: Unable to find LOCATION with value in PREP_USED'
        WHEN TRIM(error_response) ILIKE '%20093:% Unable to find LOCATION with value % in INFESTATION' THEN '20093: Unable to find LOCATION with value in INFESTATION'
        WHEN TRIM(error_response) ILIKE '%20093:% Unable to find LOCATION with value % in LOCATION_SCAN' THEN '20093: Unable to find LOCATION with value in LOCATION_SCAN'

        WHEN TRIM(error_response) ILIKE '%20093:%Unable to find TASK%' THEN '20093: Unable to find TASK with value in TASK_ACTION'
        WHEN TRIM(error_response) ILIKE '%20093:%Unable to find RECOMMENDATION_REF%' THEN '20093: Unable to find RECOMMENDATION_REF with value in RECOMMENDATION'
        WHEN TRIM(error_response) ILIKE '%20093:%Unable to find PREP%' THEN '20093: Unable to find PREP with value in PREP_USED'
        WHEN TRIM(error_response) ILIKE '%20093:%Unable to find INFESTATION_LEVEL with value %' THEN '20093: Unable to find INFESTATION_LEVEL with value in INFESTATION'
        WHEN TRIM(error_response) ILIKE '%20093:%Unable to find SITE_REF%' THEN '20093: Unable to find SITE_REF with value in VISIT_AUX_DATA'
        WHEN TRIM(error_response) ILIKE '%20093:%Unable to find EMPLOYEE%' THEN '20093: Unable to find EMPLOYEE with value in VISIT_AUX_DATA'
        WHEN TRIM(error_response) ILIKE '%20093:%Unexpected number of results for INFESTATION_LEVEL%' THEN '20093: Unexpected number of results for INFESTATION_LEVEL'

        -- Dynamic Division & Record Errors
        WHEN TRIM(error_response) ILIKE '%20097:%Error while saving site division data: Missing building%' THEN '20097: Error while saving site division data: Missing building'
        WHEN TRIM(error_response) ILIKE '%20097:%Error while saving site division data: Missing floor%' THEN '20097: Error while saving site division data: Missing floor'
        WHEN TRIM(error_response) ILIKE '%20097:%Error while saving site division data: Missing site%' THEN '20097: Error while saving site division data: Missing site'

        WHEN TRIM(error_response) ILIKE '%20010:%Record Not Found%' THEN '20010: Record Not Found in iCABS'
        WHEN TRIM(error_response) ILIKE '%20015:%Unable To Create Record%' THEN '20015: Unable To Create Record'

        -- Standard Fixed Error Codes
        WHEN TRIM(error_response) ILIKE '%Error while calling API%' THEN 'Error calling API'
        WHEN TRIM(error_response) ILIKE '%20091:%WorkPoint Must Be Supplied%' THEN '20091: WorkPoint Must Be Supplied'
        WHEN TRIM(error_response) ILIKE '%20087:%Invalid Infestation Dataset%' THEN '20087: Invalid Infestation Dataset'
        WHEN TRIM(error_response) ILIKE '%20081:%This WorkOrder Has Been Closed%' THEN '20081: WorkOrder Closed'
        WHEN TRIM(error_response) ILIKE '%20012:%User Not Assigned to An Employee Record%' THEN '20012: User Not Assigned to Employee'
        WHEN TRIM(error_response) ILIKE '%20011:%Invalid Input Parameters%' THEN '20011: Invalid Input Parameters'
        WHEN TRIM(error_response) ILIKE '%20008:%Branch Access Denied%' THEN '20008: Branch Access Denied'
        WHEN TRIM(error_response) ILIKE '%20004:%Invalid User%' THEN '20004: Invalid User'
        WHEN TRIM(error_response) ILIKE '%20003:%Invalid User Access%' THEN '20003: Invalid User Access'
        WHEN TRIM(error_response) ILIKE '%20086:%Invalid Treatment Dataset%' THEN '20086: Invalid Treatment Dataset'

        -- General fallback for any remaining 20093 errors
        WHEN TRIM(error_response) ILIKE '%20093:%' THEN '20093: Visit Processing Error'

        WHEN TRIM(error_response) ILIKE '%Error while calling API %' THEN '50000: Internal Server Error'

        ELSE error_response
    END AS normalized_error_category
FROM api_error_logs;