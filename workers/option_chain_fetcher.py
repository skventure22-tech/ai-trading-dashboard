import time
import json
import requests

# ================= FIXED CONFIG =================
PHP_RECEIVE_URL = "https://surgialgo.shop/api/receive_oc_snapshot.php"

API_WRITE_TOKEN = (
    "1d0050a2f757a1aa39e252a89076bcdf0a82c7333e62d3c1c1e9c9012b187d80"
)

SIM_MODE = True
POLL_INTERVAL = 3

UNDERLYING_ID = 1          # NIFTY
EXPIRY_DATE   = "2025-12-09"
STRIKE_STEP   = 50

# ================= SIM OPTION CHAIN =================
def fetch_option_chain_sim():
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
    print("🚀 Option Chain Worker started | DOMAIN = surgialgo.shop")

    while True:
        try:
            payload = fetch_option_chain_sim()

            r = requests.post(
                PHP_RECEIVE_URL,
                headers={
                    "Authorization": f"Bearer {API_WRITE_TOKEN}",
                    "Content-Type": "application/json"
                },
                data=json.dumps(payload),
                timeout=10
            )

            print("POST STATUS:", r.status_code)

        except Exception as e:
            print("ERROR:", e)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
