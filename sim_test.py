# 5sim ulanishini tekshirish: python sim_test.py
import os
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("NUM_PROVIDER", "5sim")
import importlib.util, sys
sys.argv = [sys.argv[0], "check"]
spec = importlib.util.spec_from_file_location("server", "server.py"); S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
p = S.FiveSimProv()
print("Balans (5sim hisobida):", p.balance())
pr = sorted(p.prices(), key=lambda x: x["usd"])
print("Mavjud davlatlar:", len(pr), "| xizmat:", p.srv)
for x in pr[:8]: print(f'  {x["name"]:<18} narx={x["usd"]:<8} dona={x["count"]}')
print("\nSayt narxi bilan solishtiring: shu narxlar saytdagi bilan bir xil bo'lsa NUM_PRICE_TO_USD=1 qoldiring.")
