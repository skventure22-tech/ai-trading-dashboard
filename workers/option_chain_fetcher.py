#!/usr/bin/env python3
"""
option_chain_fetcher.py

- Lightweight production-ready worker that:
  1) Reads SMARTAPI_SESSION_FILE for jwtToken
  2) Fetches NIFTY underlying + option chain from SmartAPI (adjust endpoint)
  3) Writes snapshot to `option_chain_snapshots` and `option_chain_rows` tables
  4) Has retries, backoff, rate-limit, logging, SIM_MODE check

Usage:
    python3 option_chain_fetcher.py

Environment variables (recommended via /home/<user>/storage/.env):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
    SMARTAPI_BASE, SMARTAPI_SESSION_FILE, SMARTAPI_API_KEY
    LOG_DIR, SIM_MODE, OC_POLL_INTERVAL

Notes:
 - Adapt `fetch_option_chain()` to your actual SmartAPI endpoint / schema.
 - Run in a persistent session (tmux) or supervise with systemd on a VPS.
"""

import os
import time
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import requests
from dotenv import load_dotenv

# Load environment from storage .env if present
ENV_PATH = os.path.expanduser('~/storage/.env')
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH, override=False)

# Config
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_NAME = os.getenv('DB_NAME', '')
DB_USER = os.getenv('DB_USER', '')
DB_PASS = os.getenv('DB_PASS', '')
DB_CHARSET = os.getenv('DB_CHARSET', 'utf8mb4')

SMARTAPI_BASE = os.getenv('SMARTAPI_BASE', 'https://api.smartapi.angelbroking.com')
SMARTAPI_SESSION_FILE = os.getenv('SMARTAPI_SESSION_FILE', os.path.expanduser('~/storage/smartapi_session.json'))
SMARTAPI_API_KEY = os.getenv('SMARTAPI_API_KEY', '')

LOG_DIR = os.getenv('LOG_DIR', os.path.expanduser('~/storage/logs'))
SIM_MODE = os.getenv('SIM_MODE', '1') == '1'
POLL_INTERVAL = max(1, int(os.getenv('OC_POLL_INTERVAL', '2')))

# Logging setup
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, 'option_chain_fetcher.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger('oc_fetcher')

# SQLAlchemy engine
DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset={DB_CHARSET}"
engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=3600)

# Graceful shutdown
running = True
def handle_sigterm(signum, frame):
    global running
    logger.info("Received shutdown signal.")
    running = False

signal.signal(signal.SIGINT, handle_sigterm)
signal.signal(signal.SIGTERM, handle_sigterm)

def read_session():
    """Read session JSON from SMARTAPI_SESSION_FILE and return dict or None."""
    try:
        with open(SMARTAPI_SESSION_FILE, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.warning("Could not read SMARTAPI session file: %s", e)
        return None

def fetch_option_chain(jwt_token: str, underlying_symbol: str = 'NIFTY'):
    """
    Fetch option chain and underlying. This function is written defensively:
    - SmartAPI exact endpoint/params may vary; adjust below to match your SmartAPI plan.
    - Returns dict with keys: 'underlying' and 'rows' where rows is a list of dicts:
        { 'strike': float, 'option_type': 'CE'/'PE', 'ltp': float, 'volume': int, 'oi': int, 'bid': float, 'ask': float, 'iv': float, 'derivative_id': optional }
    """
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'X-API-KEY': SMARTAPI_API_KEY,
        'Content-Type': 'application/json'
    }

    # Placeholder endpoint: change to actual SmartAPI option-chain endpoint
    # Example (not guaranteed): /service/optionChain or /market/option-chain
    url = SMARTAPI_BASE.rstrip('/') + '/service/optionChain'  # adapt if needed

    params = {
        'symbol': underlying_symbol
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        logger.warning("Option chain fetch failed: %s", e)
        return None

    # Attempt to normalize payload
    # Expected shapes vary; try to handle popular shapes:
    # Case A: payload = { "underlying": {"ltp":..., "expiry": "YYYY-MM-DD"}, "rows": [...] }
    # Case B: payload = { "data": {...} } etc.
    if isinstance(payload, dict):
        if 'underlying' in payload and 'rows' in payload:
            return payload
        if 'data' in payload and isinstance(payload['data'], dict):
            data = payload['data']
            if 'underlying' in data and 'rows' in data:
                return {'underlying': data['underlying'], 'rows': data['rows']}
            # Sometimes rows under data -> chain
            if 'chain' in data:
                return {'underlying': data.get('underlying', {}), 'rows': data['chain']}
    # Fallback: try to interpret entire payload as rows
    if isinstance(payload, list):
        return {'underlying': {}, 'rows': payload}
    return None

def find_underlying_id(conn, symbol='NIFTY'):
    """Find underlying id from symbols table (returns int or None)."""
    try:
        q = text("SELECT id FROM symbols WHERE exchange = 'NSE_IDX' AND symbol = :sym LIMIT 1")
        res = conn.execute(q, {"sym": symbol}).fetchone()
        if res:
            return int(res[0])
    except Exception as e:
        logger.exception("find_underlying_id error: %s", e)
    return None

def save_snapshot(conn, underlying_id, expiry_date, underlying_price, rows):
    """
    Save snapshot and rows in a single transaction.
    Expect tables:
      - option_chain_snapshots (id, underlying_id, expiry_date, snapshot_ts, underlying_price, created_at)
      - option_chain_rows (snapshot_id, derivative_id, strike_price, option_type, ltp, volume, oi, bid_price, ask_price, iv, greeks_json, created_at)
    """
    now = datetime.now(timezone.utc)
    try:
        with conn.begin():
            insert_snap = text("""
                INSERT INTO option_chain_snapshots
                  (underlying_id, expiry_date, snapshot_ts, underlying_price, created_at)
                VALUES (:uid, :expiry, :ts, :price, :created)
            """)
            res = conn.execute(insert_snap, {
                "uid": underlying_id,
                "expiry": expiry_date,
                "ts": now,
                "price": underlying_price,
                "created": now
            })
            snapshot_id = res.lastrowid

            insert_row = text("""
                INSERT INTO option_chain_rows
                  (snapshot_id, derivative_id, strike_price, option_type, ltp, volume, oi, bid_price, ask_price, iv, greeks_json, created_at)
                VALUES (:sid, :did, :strike, :opt, :ltp, :volume, :oi, :bid, :ask, :iv, :greeks, :created)
            """)
            for r in rows:
                conn.execute(insert_row, {
                    "sid": snapshot_id,
                    "did": r.get("derivative_id"),
                    "strike": float(r.get("strike") or 0),
                    "opt": r.get("option_type"),
                    "ltp": float(r.get("ltp") or 0.0),
                    "volume": int(r.get("volume") or 0),
                    "oi": int(r.get("oi") or 0),
                    "bid": float(r.get("bid") or 0.0),
                    "ask": float(r.get("ask") or 0.0),
                    "iv": float(r.get("iv") or 0.0) if r.get("iv") is not None else None,
                    "greeks": json.dumps(r.get("greeks")) if r.get("greeks") is not None else None,
                    "created": now
                })
        logger.info("Saved snapshot %s with %d rows", snapshot_id, len(rows))
    except SQLAlchemyError as e:
        logger.exception("DB error while saving snapshot: %s", e)
        raise

def normalize_rows(raw_rows):
    """Convert provider-specific row format to our row dict format."""
    out = []
    for item in raw_rows:
        # try common keys
        strike = item.get('strike') or item.get('strike_price') or item.get('strikePrice')
        typ = (item.get('option_type') or item.get('type') or item.get('opt_type') or '').upper()
        ltp = item.get('ltp') or item.get('lastPrice') or item.get('last')
        volume = item.get('volume') or item.get('vol') or item.get('volumeTraded') or 0
        oi = item.get('oi') or item.get('openInterest') or 0
        bid = item.get('bid_price') or item.get('bid') or None
        ask = item.get('ask_price') or item.get('ask') or None
        iv = item.get('iv') or item.get('impliedVolatility') or None
        did = item.get('derivative_id') or item.get('instrumentToken') or item.get('instrument_id') or None
        greeks = item.get('greeks') if 'greeks' in item else None

        out.append({
            'strike': float(strike) if strike is not None else None,
            'option_type': 'CE' if 'CE' in typ else ('PE' if 'PE' in typ else typ),
            'ltp': float(ltp) if ltp is not None else 0.0,
            'volume': int(volume) if volume is not None else 0,
            'oi': int(oi) if oi is not None else 0,
            'bid': float(bid) if bid is not None and bid != '' else None,
            'ask': float(ask) if ask is not None and ask != '' else None,
            'iv': float(iv) if iv not in (None, '') else None,
            'derivative_id': did,
            'greeks': greeks
        })
    return out

def main_loop():
    logger.info("Starting option_chain_fetcher; SIM_MODE=%s", SIM_MODE)
    backoff_base = 1
    while running:
        try:
            if SIM_MODE:
                logger.info("SIM_MODE=1, worker will still fetch snapshots but won't perform trades (safe mode).")

            # read session for jwt token
            session = read_session()
            if not session or 'jwtToken' not in session:
                logger.warning("No valid SmartAPI session found. Will retry in %d seconds.", max(5, backoff_base))
                time.sleep(min(60, backoff_base))
                backoff_base = min(300, backoff_base * 2)
                continue
            jwt = session['jwtToken']

            data = fetch_option_chain(jwt)
            if not data:
                logger.warning("No data returned from fetch_option_chain; retrying after POLL_INTERVAL")
                time.sleep(POLL_INTERVAL)
                continue

            underlying = data.get('underlying', {}) or {}
            rows_raw = data.get('rows', []) or []

            # Interpret underlying
            underlying_price = float(underlying.get('ltp') or underlying.get('last') or underlying.get('ltp1') or 0.0)
            expiry = underlying.get('expiry') or underlying.get('expiryDate') or underlying.get('expiry_date') or None

            rows = normalize_rows(rows_raw)
            if not rows:
                logger.info("No rows to insert; sleeping.")
                time.sleep(POLL_INTERVAL)
                continue

            # write to DB
            with engine.connect() as conn:
                underlying_id = find_underlying_id(conn, 'NIFTY')
                if not underlying_id:
                    logger.error("Could not find underlying id for NIFTY; ensure symbols table populated.")
                    time.sleep(30)
                    continue
                save_snapshot(conn, underlying_id, expiry, underlying_price, rows)

            # reset backoff on success
            backoff_base = 1
            # Respect poll interval
            time.sleep(POLL_INTERVAL)

        except Exception as e:
            logger.exception("Unhandled error in main loop: %s", e)
            # exponential backoff for errors
            sleep_for = min(300, backoff_base)
            logger.info("Sleeping for %s seconds before retrying.", sleep_for)
            time.sleep(sleep_for)
            backoff_base = min(300, backoff_base * 2)

    logger.info("Worker shutting down gracefully.")

if __name__ == '__main__':
    try:
        main_loop()
    except Exception:
        logger.exception("Fatal error, exiting.")
        sys.exit(1)
