# Cloudflare rasm ulanishini tekshirish:  python cf_test.py
import os, base64, requests
from dotenv import load_dotenv
load_dotenv()
A = os.getenv("CF_ACCOUNT_ID", ""); T = os.getenv("CF_API_TOKEN", ""); M = os.getenv("CF_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
print("Provayder:", os.getenv("IMAGE_PROVIDER"), "| Account ID:", (A[:4] + "…" + str(len(A)) + " belgi") if A else "YO'Q", "| Token:", (T[:4] + "…" + str(len(T)) + " belgi") if T else "YO'Q")
if not (A and T): raise SystemExit("❌ .env da CF_ACCOUNT_ID yoki CF_API_TOKEN yo'q")
try:
    r = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{A}/ai/run/{M}", headers={"Authorization": "Bearer " + T},
                      json={"prompt": "a red apple on a wooden table, bright light", "steps": 6}, timeout=120)
except Exception as e: raise SystemExit("❌ Ulanish xatosi (VPN?): " + str(e)[:120])
try: j = r.json()
except Exception: j = {}
img = (j.get("result") or {}).get("image")
if r.ok and img:
    open("cf_test.jpg", "wb").write(base64.b64decode(img)); print("✅ Ishladi! cf_test.jpg saqlandi")
else:
    print("❌ HTTP", r.status_code, str(j.get("errors") or j)[:300])
    print({401: "token noto'g'ri", 403: "tokenda Workers AI ruxsati yo'q", 404: "Account ID yoki model nomi noto'g'ri"}.get(r.status_code, ""))
