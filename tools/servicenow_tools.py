import os
import requests
import logging
import json
import re
import time
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from config import settings  # Import settings from config.py

logger = logging.getLogger(__name__)

# Global variable to cache the OAuth token and its expiry
_oauth_token_cache = {
    "token": None,
    "expires_at": 0
}


def _get_oauth_token() -> str | None:
    """
    Acquires and caches an OAuth 2.0 token for ServiceNow using the Client Credentials grant type.
    Requires instance URL, client_id, and client_secret from settings.
    """
    current_time = time.time()
    # Refresh 60 seconds before expiry to avoid using an expired token
    if _oauth_token_cache["token"] and _oauth_token_cache["expires_at"] > current_time + 60:
        return _oauth_token_cache["token"]

    instance_url = settings.servicenow_instance_url
    client_id = settings.servicenow_client_id
    client_secret = settings.servicenow_client_secret

    if not all([instance_url, client_id, client_secret]):
        logger.error(
            "ServiceNow OAuth credentials (instance_url, client_id, client_secret) are not fully configured in config.py or .env for Client Credentials flow.")
        return None

    token_url = f"{instance_url}/oauth_token.do"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        response = requests.post(token_url, headers=headers, data=data, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        try:
            token_data = response.json()
        except json.JSONDecodeError:
            logger.error(
                f"ServiceNow OAuth token acquisition failed: Response was not valid JSON. Raw response: {response.text}")
            return None

        token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour if not provided

        if token:
            _oauth_token_cache["token"] = token
            _oauth_token_cache["expires_at"] = current_time + expires_in
            logger.info("Successfully acquired new ServiceNow OAuth token using Client Credentials.")
            return token
        else:
            logger.error(
                f"ServiceNow OAuth token acquisition failed: {token_data.get('error_description', token_data)}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error acquiring ServiceNow OAuth token: {e}. Request URL: {token_url}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during OAuth token acquisition: {e}")
        return None


def _get_servicenow_auth_headers() -> tuple[str | None, Dict[str, str] | None]:
    """Helper to retrieve ServiceNow instance URL and authorization headers."""
    instance_url = settings.servicenow_instance_url
    token = _get_oauth_token()

    if not instance_url or not token:
        return None, None  # Indicate failure to get credentials

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    return instance_url, headers


def _get_user_sys_id_by_email(email: str) -> str | None:
    """
    Queries ServiceNow sys_user table to get the sys_id of an active user by email.
    Returns the sys_id string if found, otherwise returns None.
    """
    logger.debug(f"Attempting to resolve user sys_id for email: {email}")
    instance_url, headers = _get_servicenow_auth_headers()

    if not instance_url or not headers:
        logger.error(
            "ServiceNow API credentials (OAuth token) are not configured or could not be acquired for user lookup.")
        return None

    url = f"{instance_url}/api/now/table/sys_user"
    # Query for active user with given email and return sys_id
    params = {"sysparm_query": f"email={email}^active=true", "sysparm_limit": 1, "sysparm_fields": "name,sys_id"}

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error(
                f"ServiceNow sys_user lookup failed: Response was not valid JSON. Raw response: {response.text}")
            return None

        if data.get("result") and len(data["result"]) > 0:
            user_sys_id = data["result"][0].get("sys_id")
            logger.debug(f"Found sys_id '{user_sys_id}' for email {email}")
            return user_sys_id
        else:
            logger.warning(f"No active user found for email: {email}. ServiceNow API response: {data}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error looking up user {email} in ServiceNow: {e}. Request URL: {url}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during user lookup for {email}: {e}")
        return None


def get_servicenow_ticket_details(ticket_number: str) -> str:
    """
    Retrieves detailed information about a ServiceNow incident or ticket using the ServiceNow REST API.
    """
    logger.info(f"🟢 AGENT TOOL CALLED: Fetching ServiceNow ticket details for {ticket_number} from API")

    instance_url, headers = _get_servicenow_auth_headers()

    if not instance_url or not headers:
        return json.dumps({"success": False,
                           "error": "ServiceNow API credentials (OAuth token) are not configured or could not be acquired. Please check your .env file and ServiceNow OAuth setup."})

    if not re.match(r"^INC\d{7,}$", ticket_number.upper()):
        error_msg = f"Invalid ticket format: '{ticket_number}'. ServiceNow incidents must start with 'INC' followed by at least 7 digits (e.g., INC0010001)."
        logger.warning(error_msg)
        return json.dumps({"success": False, "error": error_msg,
                           "suggested_action": "Please ask the user to verify the ticket number."})

    # Fetch main incident details, including comments_and_work_notes
    # Added sysparm_display_value=true which often helps correctly render journal fields
    incident_url = f"{instance_url}/api/now/table/incident"
    incident_params = {
        "sysparm_query": f"number={ticket_number}",
        "sysparm_limit": 1,
        "sysparm_display_value": "true",
        "sysparm_fields": "number,short_description,description,state,priority,impact,urgency,sys_id,sys_created_on,sys_created_by,caller_id,assigned_to,assignment_group,comments_and_work_notes,work_notes,comments,u_last_notes_added"
    }

    try:
        response = requests.get(
            incident_url,
            headers=headers,
            params=incident_params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("result"):
            error_msg = f"Incident '{ticket_number.upper()}' could not be found in ServiceNow. It may have been archived, deleted, or the number might be incorrect."
            return json.dumps({"success": False, "error": error_msg})

        ticket_data = data["result"][0]
        
        # Combine activity history from various possible fields
        activity_parts = []
        
        for field in ["comments_and_work_notes", "work_notes", "comments", "u_last_notes_added"]:
            raw_field = ticket_data.get(field, "")

            if isinstance(raw_field, dict):
                raw_text = raw_field.get("display_value", "") or raw_field.get("value", "")
            else:
                raw_text = str(raw_field)
                
            raw_text = raw_text.strip()
            if raw_text:
                activity_parts.append(f"--- {field.replace('_', ' ').title()} ---\n{raw_text}")
                
            # Clean up the raw field to avoid confusing the LLM if it tries to read the raw JSON
            ticket_data.pop(field, None)

        if activity_parts:
            ticket_data["formatted_activity_history"] = "\n\n".join(activity_parts)
        else:
            ticket_data["formatted_activity_history"] = "No recent comments or work notes."
            
        # Ensure description is always available as a plain string
        description = ticket_data.get("description", "")
        if isinstance(description, dict):
             ticket_data["description"] = description.get("display_value", "") or description.get("value", "")
        else:
             ticket_data["description"] = str(description).strip()

        return json.dumps({"success": True, "ticket_data": ticket_data})

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching ticket {ticket_number} from ServiceNow: {e}. Request URL: {incident_url}")
        return json.dumps({"success": False, "error": f"Failed to connect to ServiceNow or API error: {str(e)}"})
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching ticket {ticket_number}: {e}")
        return json.dumps({"success": False, "error": f"An unexpected error occurred: {str(e)}"})


def _resolve_file_path(file_path: str) -> str:
    """
    Attempts to resolve a file path. If not found directly, checks common workspace directories.
    """
    if os.path.exists(file_path):
        return file_path

    # Check search locations for filename
    file_name = os.path.basename(file_path)
    search_dirs = [
        os.getcwd(),
        os.path.join(os.getcwd(), "data"),
        os.path.join(os.getcwd(), "uploads"),
        os.path.join(os.getcwd(), "artifacts"),
        os.path.join(os.getcwd(), "workspace")
    ]

    for search_dir in search_dirs:
        candidate = os.path.join(search_dir, file_name)
        if os.path.exists(candidate):
            logger.info(f"Resolved file '{file_name}' at location: {candidate}")
            return candidate

    raise FileNotFoundError(f"File '{file_name}' could not be found on disk at target or standard workspace locations.")


def _attach_bytes_to_ticket(sys_id: str, file_name: str, file_data: bytes, content_type: str = "application/octet-stream"):
    """Helper method to attach raw bytes directly to an existing ticket via sys_id using ServiceNow REST API."""
    instance_url, headers = _get_servicenow_auth_headers()

    if not instance_url or not headers:
        raise ValueError(
            "ServiceNow API credentials (OAuth token) are not configured or could not be acquired for attachment.")

    url = f"{instance_url}/api/now/attachment/file"

    params = {
        "table_name": "incident",
        "table_sys_id": sys_id,
        "file_name": file_name
    }

    attachment_headers = headers.copy()
    attachment_headers["Content-Type"] = content_type

    try:
        response = requests.post(
            url,
            headers=attachment_headers,
            params=params,
            data=file_data,
            timeout=30
        )
        response.raise_for_status()

        try:
            res_json = response.json()
            logger.info(f"Successfully attached {file_name} to ServiceNow incident {sys_id}")
            return res_json
        except json.JSONDecodeError:
            logger.error(
                f"ServiceNow attachment failed for {file_name}: Response was not valid JSON. Raw response: {response.text}")
            raise ValueError(
                f"ServiceNow API returned a non-JSON response during attachment. Raw response: {response.text}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error attaching file {file_name} to ServiceNow: {e}. Request URL: {url}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during file attachment for {file_name}: {e}")
        raise


def _attach_file_to_ticket(sys_id: str, file_path: str):
    """Helper method to attach a single local file to an existing ticket via sys_id using ServiceNow REST API."""
    resolved_path = _resolve_file_path(file_path)
    file_name = os.path.basename(resolved_path)

    with open(resolved_path, "rb") as f:
        file_data = f.read()

    return _attach_bytes_to_ticket(sys_id, file_name, file_data)


def create_servicenow_ticket(
        short_description: str,
        description: str,
        priority: str,
        assignment_group: str,
        caller_name: str,
        caller_email: str,
        files: Optional[List[str]] = None,
        file_data_list: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Creates a new ServiceNow ticket (incident) using the ServiceNow REST API and optionally attaches files.

    Args:
        short_description: A brief summary of the issue.
        description: Detailed explanation of the issue.
        priority: The priority of the ticket (e.g., "1 - Critical", "2 - High", "3 - Moderate", "4 - Low").
        assignment_group: The team responsible for resolving the ticket.
        caller_name: The name of the user reporting the issue.
        caller_email: The email address of the user reporting the issue.
        files: Optional list of file paths to resolve and attach to the ticket.
               These files must exist on the server's file system where this script is executed.
        file_data_list: Optional list of dicts with raw binary/base64 data:
                        [{ "file_name": "report.pdf", "file_bytes": b"...", "base64_content": "..." }]
    """
    logger.info(f"🟢 AGENT TOOL CALLED: Creating new ServiceNow ticket via API")
    logger.debug(f"Description received for ticket: {description}")

    instance_url, headers = _get_servicenow_auth_headers()

    if not instance_url or not headers:
        return json.dumps({
            "success": False,
            "error": "ServiceNow API credentials (OAuth token) are not configured or could not be acquired. Please check your .env file and ServiceNow OAuth setup."
        })

    url = f"{instance_url}/api/now/table/incident"

    # sysparm_input_display_value=true allows passing display names directly (e.g. assignment_group)
    params = {"sysparm_input_display_value": "true"}

    incident_headers = headers.copy()
    incident_headers["Content-Type"] = "application/json"

    # Resolve caller_id: sys_id if found, otherwise None (serializes to null in JSON)
    resolved_caller_sys_id = _get_user_sys_id_by_email(caller_email)
    if not resolved_caller_sys_id:
        logger.warning(
            f"Could not find active user sys_id for email '{caller_email}'. Setting caller_id to None (null).")

    priority_value = priority.split(' - ')[0]

    payload = {
        "short_description": short_description,
        "description": description,
        "work_notes": description,  # Explicitly set work_notes to match description
        "priority": priority_value,  # Setting impact instead of priority directly
        "assignment_group": assignment_group,
        "caller_id": resolved_caller_sys_id,  # Serializes to null in JSON if resolved_caller_sys_id is None
        "contact_type": "Self-service",
        "u_business_service": "ServiceTrak - Corporate - Global",
    }

    try:
        logger.debug(f"Create Ticket Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(
            url,
            headers=incident_headers,
            params=params,
            json=payload,
            timeout=15
        )

        response.raise_for_status()

        try:
            result = response.json().get("result", {})
        except json.JSONDecodeError:
            logger.error(
                f"ServiceNow ticket creation failed: Response was not valid JSON. Raw response: {response.text}")
            return json.dumps({
                "success": False,
                "error": f"ServiceNow API returned a non-JSON response during ticket creation. Raw response: {response.text}"
            })

        sys_id = result.get("sys_id")
        ticket_number = result.get("number")

        if not sys_id or not ticket_number:
            logger.error(f"ServiceNow API did not return sys_id or number: {response.json()}")
            return json.dumps({
                "success": False,
                "error": "ServiceNow API did not return a valid ticket number or sys_id upon creation."
            })

        attached_files = []
        failed_files = []

        # 1. Process local file path attachments
        if files and sys_id:
            for file_path in files:
                try:
                    _attach_file_to_ticket(sys_id, file_path)
                    attached_files.append(file_path)
                except Exception as e:
                    logger.error(f"Failed to attach {file_path}: {e}")
                    failed_files.append({"file": file_path, "error": str(e)})

        # 2. Process in-memory byte/base64 attachments
        if file_data_list and sys_id:
            for item in file_data_list:
                file_name = item.get("file_name", "attachment.dat")
                content_type = item.get("content_type", "application/octet-stream")
                try:
                    if "file_bytes" in item and isinstance(item["file_bytes"], bytes):
                        raw_bytes = item["file_bytes"]
                    elif "base64_content" in item:
                        raw_bytes = base64.b64decode(item["base64_content"])
                    else:
                        raise ValueError("Neither 'file_bytes' nor 'base64_content' provided in file_data_list item.")

                    _attach_bytes_to_ticket(sys_id, file_name, raw_bytes, content_type)
                    attached_files.append(file_name)
                except Exception as e:
                    logger.error(f"Failed to attach in-memory file {file_name}: {e}")
                    failed_files.append({"file": file_name, "error": str(e)})

        return json.dumps({
            "success": True,
            "ticket_number": ticket_number,
            "sys_id": sys_id,
            "attached_files": attached_files,
            "failed_attachments": failed_files
        })
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating ticket in ServiceNow: {e}. Request URL: {url}")
        return json.dumps({"success": False, "error": f"Failed to connect to ServiceNow or API error: {str(e)}"})
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating ticket: {e}")
        return json.dumps({"success": False, "error": f"An unexpected error occurred: {str(e)}"})


def search_servicenow_incidents(query: str, limit: int = 5) -> str:
    """
    Searches for ServiceNow incidents based on a query string.
    The query can search across short_description, description, and number fields.
    It performs a flexible search by breaking down the query into keywords and also searching for the full phrase.
    Filters the results to only include open incidents created in the last 6 months.

    Args:
        query: The search string (e.g., "email not working", "INC0010001").
        limit: The maximum number of incidents to return.

    Returns:
        A JSON string with a list of matching incidents, or an error message.
    """
    logger.info(f"🟢 AGENT TOOL CALLED: Searching ServiceNow incidents for query: '{query}'")

    instance_url, headers = _get_servicenow_auth_headers()

    if not instance_url or not headers:
        return json.dumps({
            "success": False,
            "error": "ServiceNow API credentials (OAuth token) are not configured or could not be acquired. Please check your .env file and ServiceNow OAuth setup."
        })

    # Base conditions: state is not closed/resolved, created in last 6 months
    # State values: 1=New, 2=In Progress, 3=On Hold (ignoring 6=Resolved, 7=Closed, 8=Canceled)
    # Different ServiceNow instances might have different state mappings, but usually <=3 or <=5 are open.
    # We will use active=true which is a reliable standard for "open" tickets in ServiceNow.
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    base_filter = f"active=true^sys_created_on>={six_months_ago}"

    sysparm_query = ""

    # 1. If the query looks like a ticket number, do an exact search
    if re.match(r"^INC\d{7,}$", query.upper()):
        sysparm_query = f"{base_filter}^numberLIKE{query.upper()}"
    else:
        # Break down query into individual words for broader search
        # Filter out words shorter than 3 characters for better relevance
        search_terms = [word for word in query.split() if len(word) > 2]
        
        if not search_terms:
            sysparm_query = f"{base_filter}^short_descriptionLIKE{query}^ORdescriptionLIKE{query}"
        else:
            # We want incidents that match the exact phrase OR contain all terms in short_description OR contain all terms in description
            short_desc_query = "^".join([f"short_descriptionLIKE{term}" for term in search_terms])
            desc_query = "^".join([f"descriptionLIKE{term}" for term in search_terms])
            
            # Use ^NQ (New Query) to correctly group the OR conditions while keeping the base filter applied to all
            queries = [
                f"{base_filter}^short_descriptionLIKE{query}",
                f"{base_filter}^descriptionLIKE{query}",
                f"{base_filter}^{short_desc_query}",
                f"{base_filter}^{desc_query}"
            ]
            sysparm_query = "^NQ".join(queries)

    url = f"{instance_url}/api/now/table/incident"
    params = {
        "sysparm_query": sysparm_query,
        "sysparm_limit": limit,
        "sysparm_display_value": "true",
        "sysparm_fields": "number,short_description,description,state,priority,sys_id,sys_created_on,caller_id,assigned_to,assignment_group"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error(
                f"ServiceNow incident search failed: Response was not valid JSON. Raw response: {response.text}")
            return json.dumps({
                "success": False,
                "error": f"ServiceNow API returned a non-JSON response during search. Raw response: {response.text}"
            })

        if data.get("result"):
            incidents = data["result"]
            return json.dumps({"success": True, "incidents": incidents})
        else:
            return json.dumps({"success": True, "incidents": [], "message": "No incidents found matching the query."})

    except requests.exceptions.RequestException as e:
        logger.error(f"Error searching incidents in ServiceNow: {e}. Request URL: {url}")
        return json.dumps({"success": False, "error": f"Failed to connect to ServiceNow or API error: {str(e)}"})
    except Exception as e:
        logger.error(f"An unexpected error occurred while searching incidents: {e}")
        return json.dumps({"success": False, "error": f"An unexpected error occurred: {str(e)}"})


def update_servicenow_ticket(
        ticket_number: str,
        comments: Optional[str] = None,
        work_notes: Optional[str] = None,
        user_name: Optional[str] = None,
        user_email: Optional[str] = None
) -> str:
    """
    Updates an existing ServiceNow incident with comments or work notes.
    Optionally includes the user's name and email in the comment/work note text.

    Args:
        ticket_number: The number of the incident to update (e.g., INC0010001).
        comments: Text to add to the 'comments' field (visible to caller).
        work_notes: Text to add to the 'work_notes' field (internal only).
        user_name: The name of the user adding the comment/work note.
        user_email: The email of the user adding the comment/work note.

    Returns:
        A JSON string indicating success or failure.
    """
    logger.info(f"🟢 AGENT TOOL CALLED: Updating ServiceNow ticket {ticket_number}")

    instance_url, headers = _get_servicenow_auth_headers()

    if not instance_url or not headers:
        return json.dumps({
            "success": False,
            "error": "ServiceNow API credentials (OAuth token) are not configured or could not be acquired. Please check your .env file and ServiceNow OAuth setup."
        })

    # 1. Validate ticket number format
    if not re.match(r"^INC\d{7,}$", ticket_number.upper()):
        error_msg = f"Invalid ticket format: '{ticket_number}'. ServiceNow incidents must start with 'INC' followed by at least 7 digits (e.g., INC0010001)."
        logger.warning(error_msg)
        return json.dumps({"success": False, "error": error_msg,
                           "suggested_action": "Please ask the user to verify the ticket number."})

    # 2. Get the sys_id of the incident first
    # This also acts as a check if the ticket exists
    details_response = get_servicenow_ticket_details(ticket_number)
    details_data = json.loads(details_response)

    if not details_data.get("success"):
        return json.dumps({
            "success": False,
            "error": f"Could not retrieve ticket {ticket_number} to update: {details_data.get('error', 'Unknown error')}"
        })

    incident_sys_id = details_data["ticket_data"]["sys_id"]
    url = f"{instance_url}/api/now/table/incident/{incident_sys_id}"

    update_payload = {}

    # Prepend user info to comments/work_notes if provided
    user_info_prefix = ""
    if user_name:
        user_info_prefix += f"{user_name}"
    if user_email:
        user_info_prefix += f" <{user_email}>"
    if user_info_prefix:
        user_info_prefix = f"Comment by {user_info_prefix}:\n"

    if comments:
        update_payload["comments"] = user_info_prefix + comments
    if work_notes:
        update_payload["work_notes"] = user_info_prefix + work_notes

    if not update_payload:
        return json.dumps({"success": False, "error": "No comments or work notes provided for update."})

    incident_headers = headers.copy()
    incident_headers["Content-Type"] = "application/json"

    try:
        logger.debug(f"Update Ticket Payload for {ticket_number}: {json.dumps(update_payload, indent=2)}")

        response = requests.put(
            url,
            headers=incident_headers,
            json=update_payload,
            timeout=15
        )

        response.raise_for_status()

        return json.dumps({
            "success": True,
            "ticket_number": ticket_number,
            "message": f"Successfully added notes/comments to ticket {ticket_number}."
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating ticket {ticket_number} in ServiceNow: {e}. Request URL: {url}")
        return json.dumps({"success": False, "error": f"Failed to connect to ServiceNow or API error: {str(e)}"})
    except Exception as e:
        logger.error(f"An unexpected error occurred while updating ticket {ticket_number}: {e}")
        return json.dumps({"success": False, "error": f"An unexpected error occurred: {str(e)}"})