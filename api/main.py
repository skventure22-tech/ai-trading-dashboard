# api/main.py
from fastapi import FastAPI, Header, HTTPException, Request
import os
import json
from .routes import receive_oc_snapshot

app = FastAPI(title="SurgiAlgo API")

API_KEY = os.getenv("API_WRITE_TOKEN", "replace_with_token")

@app.post("/api/receive_oc_snapshot")
async def receive_snapshot(request: Request, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="invalid_api_key")
    payload = await request.json()
    # For hybrid: forward to Hostinger PHP endpoint OR write to DB (choose)
    # Here simply return ok (implement DB writing per db.py if desired)
    return {"ok": True, "received": True}
