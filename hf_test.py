# Hugging Face rasm ulanishini tekshirish:  python hf_test.py
import os, sys, base64, importlib.util
from dotenv import load_dotenv
load_dotenv()
sys.argv = [sys.argv[0], "check"]
spec = importlib.util.spec_from_file_location("server", "server.py"); S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
if not S.HFK: print("❌ .env da HF_TOKEN yo'q"); sys.exit(1)
print("Model:", S.HFM)
try:
    out = S.image_hf("red YouTube thumbnail, big text 100 000$, shocked face, bright background", "16:9")
    open("hf_test.jpg", "wb").write(base64.b64decode(out.split(",", 1)[1]))
    print("✅ Ishladi! hf_test.jpg saqlandi")
except Exception as e:
    print("❌ Xato:", e)
