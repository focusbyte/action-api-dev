from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests
import os
from dotenv import load_dotenv
import logging

# Load .env
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App init
app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

logger.info(f"SUPABASE_URL = {SUPABASE_URL}")
logger.info(f"SUPABASE_KEY present? {bool(SUPABASE_KEY)}")

@app.get("/hello")
async def hello():
    return {"status": "OK"}

@app.post("/action")
async def action_handler(request: Request):
    body = await request.json()
    table = body.get("table")
    action = body.get("action")
    payload = body.get("payload")

    if not table or not action or not payload:
        return JSONResponse(status_code=400, content={"error": "Missing required fields"})

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"  # ✅ Ask Supabase to return the inserted/updated row
    }

    url = f"{SUPABASE_URL}/rest/v1/{table}"

    if action == "create":
        response = requests.post(url, json=payload, headers=headers)
    elif action == "read":
        # Convert payload into Supabase filter syntax (e.g., {"status": "clean"} → "status=eq.clean")
        params = {f"{k}=eq.{v}" for k, v in payload.items()}
        # Join into query string
        query_string = "&".join(params)
        full_url = f"{url}?{query_string}"
        response = requests.get(full_url, headers=headers)
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
