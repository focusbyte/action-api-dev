from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_sort(sort: str):
    if not isinstance(sort, str):
        return (
            f"❌ The 'sort' value must be a string. "
            f"You provided a value of type: {type(sort).__name__}. "
            f"Expected format: 'column.asc' or 'column.desc'."
        )

    if '.' not in sort:
        return (
            f"❌ The 'sort' value '{sort}' is invalid — it is missing the required '.asc' or '.desc' suffix. "
            f"✅ Correct usage: 'absorbency.asc', 'date_added.desc'. "
            f"💡 Format must be: '<column>.<direction>' with no spaces."
        )

    if not sort.endswith((".asc", ".desc")):
        return (
            f"❌ The 'sort' value '{sort}' must end with '.asc' or '.desc'. "
            f"✅ Valid examples: 'type.asc', 'date_added.desc'. "
            f"⚠️ Avoid formats like 'absorbency', 'absorbency descending', or 'absorbency-desc'."
        )

    column_name = sort.split('.')[0]
    if not column_name.isidentifier():
        return (
            f"❌ Invalid column name '{column_name}' in the 'sort' value. "
            f"Column names must start with a letter or underscore, and contain only letters, digits, or underscores. "
            f"💡 Example: 'absorbency.asc'"
        )

    return None  # ✅ Valid sort


def validate_limit(limit):
    if not isinstance(limit, int):
        return f"❌ 'limit' must be an integer. You provided: {type(limit).__name__}."
    if not (1 <= limit <= 1000):
        return f"❌ 'limit' must be between 1 and 1000. You provided: {limit}."
    return None


def validate_component(action: str, component: str):
    if not component:
        return (
            "❌ Missing required field: 'payload.component'. "
            "Please specify the schema name, e.g. 'TissuesReadPayload'."
        )

    expected_components = {
        "read": "TissuesReadPayload",
        "create": "TissuesCreatePayload",
        "update": "TissuesUpdatePayload",
        "delete": "TissuesDeletePayload"
    }

    expected = expected_components.get(action)
    if expected and component != expected:
        return (
            f"❌ You used 'component: {component}' for action '{action}', but this does not match the expected schema '{expected}'. "
            f"💡 To fix this, use the correct schema fields defined in '#/components/schemas/{expected}' — not just the component name."
        )

    return None  # ✅ Valid

def validate_payload_fields(action: str, payload: dict):
    allowed_fields = {
        "read": {"component", "status", "type", "absorbency", "date_added", "notes", "sort", "limit"},
        "create": {"component", "status", "type", "absorbency", "date_added", "notes"},
        "update": {"component", "id", "status", "type", "absorbency", "date_added", "notes"},
        "delete": {"component", "id"}
    }

    allowed = allowed_fields.get(action, set())
    extra = set(payload.keys()) - allowed

    if extra:
        return (
            f"❌ Unexpected fields in payload for action '{action}': {', '.join(extra)}. "
            f"💡 These fields do not belong in a '{action}' request or do not match the expected schema."
        )

    return None


# Initialize FastAPI app
app = FastAPI()

# Retrieve Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Log the presence of keys
logger.info(f"SUPABASE_URL = {SUPABASE_URL}")
logger.info(f"SUPABASE_KEY present? {bool(SUPABASE_KEY)}")

# Health check endpoint
@app.get("/hello")
async def hello():
    return {"status": "OK"}

# Action endpoint for CRUD
@app.post("/action")
async def action_handler(request: Request):
    body = await request.json()
    logger.info(body)
    table = body.get("table")
    action = body.get("action")
    payload = body.get("payload")

    if not table or not action or payload is None:
        return JSONResponse(status_code=400, content={"error": "Missing required fields"})

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    url = f"{SUPABASE_URL}/rest/v1/{table}"

    component = payload.get("component")

    # ✅ Validate component string for this action
    component_error = validate_component(action, component)
    if component_error:
        return JSONResponse(status_code=400, content={"error": component_error})

    # ✅ Validate allowed fields in the payload
    field_error = validate_payload_fields(action, payload)
    if field_error:
        return JSONResponse(status_code=400, content={"error": field_error})

    
    if action == "create":
        response = requests.post(url, json=payload, headers=headers)

    elif action == "read":
        try:
            sort = payload.pop("sort", None)
            if sort:
                sort_error = validate_sort(sort)
                if sort_error:
                    return JSONResponse(status_code=400, content={"error": sort_error})
                    
            limit = payload.pop("limit", None)


            if limit is None:
                limit = 50  # sensible default for LLM use
            else:
                limit_error = validate_limit(limit)
                if limit_error:
                    return JSONResponse(status_code=400, content={"error": limit_error})

            filters = [f"{k}=eq.{v}" for k, v in payload.items()]
            query = "&".join(filters)

            if sort:
                query += f"&order={sort}"
            if limit:
                query += f"&limit={limit}"

            full_url = f"{url}?{query}" if query else url
            response = requests.get(full_url, headers=headers)
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": f"Invalid read parameters: {str(e)}"})

    elif action == "update":
        id = payload.pop("id", None)
        if not id:
            return JSONResponse(status_code=400, content={"error": "Missing 'id' for update"})
        response = requests.patch(f"{url}?id=eq.{id}", json=payload, headers=headers)

    elif action == "delete":
        id = payload.get("id")
        if not id:
            return JSONResponse(status_code=400, content={"error": "Missing 'id' for delete"})
        response = requests.delete(f"{url}?id=eq.{id}", headers=headers)

    else:
        return JSONResponse(status_code=400, content={"error": "Invalid action"})

    try:
        json_response = response.json()
    except Exception as e:
        json_response = {
            "error": "Supabase did not return valid JSON",
            "status_code": response.status_code,
            "text": response.text,
            "details": str(e)
        }

    return JSONResponse(status_code=response.status_code, content=json_response)
