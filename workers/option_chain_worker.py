import time, json, os, math, requests
from datetime import date

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

def current_expiry():
    today = date.today()
    return today.strftime("%Y-%m-%d")

def simulate_chain(ul):
    spot = {
        "NIFTY":26186.45,
        "BANKNIFTY":48250,
        "SENSEX":72100
    }[ul["symbol"]]

    step = ul["step"]
    atm  = round(spot/step)*step
    rows = []

    for s in range(atm-3*step, atm+4*step, step):
        rows.append({"strike_price":s,"option_type":"CE","ltp":round(abs(spot-s)*0.45+5,1),"oi":100000})
        rows.append({"strike_price":s,"option_type":"PE","ltp":round(abs(spot-s)*0.45+5,1),"oi":120000})

    return {
        "underlying_id":ul["id"],
        "expiry_date":current_expiry(),
        "underlying_price":spot,
        "rows":rows
    }

print("🚀 Option Chain Worker running")

while True:
    for ul in UNDERLYINGS:
        try:
            payload = simulate_chain(ul)
            r = requests.post(
                POST_URL,
                headers={
                    "X-API-KEY":API_TOKEN,
                    "Content-Type":"application/json"
                },
                data=json.dumps(payload),
                timeout=10
            )
            print(ul["symbol"], r.status_code)
        except Exception as e:
            print("ERR", ul["symbol"], e)

    time.sleep(POLL)
