import time, json, os, requests, datetime

POST_URL = os.getenv("SNAPSHOT_POST_URL")
API_TOKEN = os.getenv("API_WRITE_TOKEN")

if not POST_URL or not API_TOKEN:
    raise RuntimeError("ENV not set")

POLL = int(os.getenv("OC_POLL_INTERVAL", "3"))

UNDERLYINGS = [
    {"id":1,"symbol":"NIFTY","step":50},
    {"id":2,"symbol":"BANKNIFTY","step":100},
    {"id":3,"symbol":"SENSEX","step":100},
]

def detect_expiry():
    today = datetime.date.today()
    days = (3 - today.weekday()) % 7
    return (today + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

def build_payload(u, spot):
    atm = round(spot / u["step"]) * u["step"]
    rows = []

    for s in range(atm-3*u["step"], atm+4*u["step"], u["step"]):
        rows.append({
            "strike_price": s,
            "option_type": "CE",
            "ltp": round(abs(spot-s)*0.35+5,2),
            "oi": 100000
        })
        rows.append({
            "strike_price": s,
            "option_type": "PE",
            "ltp": round(abs(spot-s)*0.35+5,2),
            "oi": 120000
        })

    return {
        "underlying_id": u["id"],
        "expiry_date": detect_expiry(),
        "underlying_price": round(spot,2),
        "rows": rows
    }

print("🚀 Option Chain Worker started")

while True:
    for u in UNDERLYINGS:
        try:
            spot = {
                "NIFTY": 26186.45,
                "BANKNIFTY": 59069.20,
                "SENSEX": 84929.36
            }[u["symbol"]]

            payload = build_payload(u, spot)

            r = requests.post(
                POST_URL,
                headers={
                    "X-API-KEY": API_TOKEN,
                    "Content-Type": "application/json"
                },
                data=json.dumps(payload),
                timeout=10
            )

            print(u["symbol"], r.status_code)

        except Exception as e:
            print("❌ ERROR:", e)

    time.sleep(POLL)
