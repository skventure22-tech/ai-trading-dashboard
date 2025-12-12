# workers/option_chain_worker.py
import os
import time
import json
import logging
import requests
from dotenv import load_dotenv

load_dotenv()  # for local dev; Render uses env vars

LOG = logging.getLogger("oc_worker")
logging.basicConfig(level=logging.INFO)

SERVER_API = os.getenv("SERVER_API", "https://surgialgo.shop/api/receive_oc_snapshot.php")
API_KEY = os.getenv("API_WRITE_TOKEN", "replace_with_token")
POLL = int(os.getenv("OC_POLL_INTERVAL", "2"))

def fetch_example_oc():
    # Replace with real SmartAPI call using SMARTAPI_* env vars on Render
    now = int(time.time())
    return {
        "ok": True,
        "expiry": "2025-12-18",
        "nifty": {"ltp": 18200.5},
        "option_chain": [
            {"strike": 18150, "ce_ltp": 120.5, "pe_ltp": 90.0},
            {"strike": 18200, "ce_ltp": 85.0, "pe_ltp": 110.0},
        ],
        "fetched_at": now
    }

def post_snapshot(snapshot):
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }
    try:
        r = requests.post(SERVER_API, headers=headers, json=snapshot, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        LOG.error("Post failed: %s", e)
        return None

def main():
    LOG.info("Option chain worker started. Poll interval=%s", POLL)
    while True:
        data = fetch_example_oc()
        res = post_snapshot(data)
        LOG.info("Posted, response: %s", str(res))
        time.sleep(POLL)

if __name__ == "__main__":
    main()
