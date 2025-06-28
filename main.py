from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests
import os

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

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
        "Content-Type": "application/json"
    }

    url = f"{SUPABASE_URL}/rest/v1/{table}"

    if action == "create":
        response = requests.post(url, json=payload, headers=headers)
    elif action == "read":
        response = requests.get(url, headers=headers, params=payload)
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

    return JSONResponse(status_code=response.status_code, content=response.json())
