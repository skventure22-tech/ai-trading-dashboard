import time
import json
import requests
import logging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("oc_worker")

# ================= CONFIG =================
PHP_RECEIVE_URL = "https://surgialgo.shop/api/receive_oc_snapshot.php"

API_WRITE_TOKEN = (
    "1d0050a2f757a1aa39e252a89076bcdf0a82c7333e62d3c1c1e9c9012b187d80"
)

POLL_INTERVAL = 3          # seconds
UNDERLYING_ID = 1          # NIFTY
EXPIRY_DATE   = "2025-12-09"
STRIKE_STEP   = 50

# ================= SIM OPTION CHAIN =================
def fetch_option_chain_sim():
    """
    Generate FULL option chain (ATM ±500, CE + PE)
    """
    spot = 26186.45
    atm  = round(spot / STRIKE_STEP) * STRIKE_STEP

    rows = []
    for strike in range(atm - 500, atm + 550, STRIKE_STEP):
        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(max(5, abs(spot - strike) * 0.45), 2),
            "oi": 100000 + abs(atm - strike) * 10
        })
        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(max(5, abs(spot - strike) * 0.45), 2),
            "oi": 120000 + abs(atm - strike) * 12
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": spot,
        "rows": rows
    }

# ================= MAIN LOOP =================
def main():
    LOG.info("🚀 Option Chain Worker STARTED")
    LOG.info("Posting to %s", PHP_RECEIVE_URL)

    while True:
        try:
            payload = fetch_option_chain_sim()
            row_count = len(payload["rows"])

            resp = requests.post(
                PHP_RECEIVE_URL,
                headers={
                    "Authorization": f"Bearer {API_WRITE_TOKEN}",
                    "Content-Type": "application/json"
                },
                data=json.dumps(payload),
                timeout=10
            )

            LOG.info(
                "POST %s | rows=%d",
                resp.status_code,
                row_count
            )

            if resp.status_code != 200:
                LOG.warning("Response body: %s", resp.text)

        except Exception as e:
            LOG.error("Worker error: %s", e)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
