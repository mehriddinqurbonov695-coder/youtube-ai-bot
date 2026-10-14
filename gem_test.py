# Gemini kalitlari va modellarni tekshirish:  python gem_test.py
import os, re, requests
from dotenv import load_dotenv
load_dotenv()
B = "https://generativelanguage.googleapis.com/v1beta"
GK = os.getenv("GEMINI_API_KEY", ""); IK = os.getenv("GEMINI_IMAGE_API_KEY", "") or GK
CM = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash"); IM = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
mask = lambda k: (k[:4] + "…" + k[-3:] + " (" + str(len(k)) + " belgi)") if k else "YO'Q"
print("Chat kaliti:", mask(GK), "| Rasm kaliti:", mask(IK), "| alohida:", IK != GK)
print("Chat modeli:", CM, "| Rasm modeli:", IM, "\n")

def detail(msg):
    keep = [l.strip() for l in str(msg).split("\n") if re.search(r"Quota exceeded|limit:|retry in|no longer|not found|API key|location|billing", l, re.I)]
    return "\n   ".join(keep[:6]) or str(msg)[:300]

def call(name, key, model, body, img=False):
    if not key: print(f"❌ {name}: kalit yo'q"); return
    try: r = requests.post(f"{B}/models/{model}:generateContent", headers={"x-goog-api-key": key}, json=body, timeout=90)
    except Exception as e: print(f"❌ {name}: ulanish xatosi -> VPN? ({str(e)[:100]})"); return
    try: j = r.json()
    except Exception: j = {}
    parts = [p for c in j.get("candidates", []) for p in c.get("content", {}).get("parts", [])]
    ok = r.ok and (any(p.get("inlineData") or p.get("inline_data") for p in parts) if img else bool(parts))
    if ok: print(f"✅ {name} [{model}]: ishladi"); return
    print(f"❌ {name} [{model}]: HTTP {r.status_code}\n   " + detail((j.get("error") or {}).get("message") or j))

chat = {"contents": [{"parts": [{"text": "salom"}]}]}
img = {"contents": [{"parts": [{"text": "a red apple on white background"}]}], "generationConfig": {"imageConfig": {"aspectRatio": "1:1"}}}
call("chat, GEMINI_API_KEY", GK, CM, chat)
if IK != GK: call("chat, rasm kaliti", IK, CM, chat)
call("rasm, rasm kaliti", IK, IM, img, True)

print("\nKalit ko'ra oladigan modellar (chat uchun):")
for nm, k in (("GEMINI_API_KEY", GK), ("rasm kaliti", IK)):
    if not k or (nm == "rasm kaliti" and IK == GK): continue
    try:
        r = requests.get(f"{B}/models?pageSize=200", headers={"x-goog-api-key": k}, timeout=30)
        ms = [m["name"].split("/")[-1] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        print(f" {nm}:", ", ".join(m for m in ms if "flash" in m or "pro" in m)[:600] or "(bo'sh)")
    except Exception as e: print(f" {nm}: ro'yxat olinmadi ({str(e)[:80]})")
