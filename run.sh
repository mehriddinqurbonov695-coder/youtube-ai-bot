#!/data/data/com.termux/files/usr/bin/bash
# Botni ishga tushirish:   bash run.sh
# Yangi fayllarni Download'dan olib ishga tushirish:   bash run.sh update
APP="$HOME/bot"; DL="$HOME/storage/downloads"
cd "$APP" || { echo "❌ $APP yo'q. Avval termux_setup.sh ni ishlating"; exit 1; }
newest() { ls -t "$DL"/$1 2>/dev/null | head -1; }

if [ "$1" = "update" ]; then
  echo "▶ Fayllar Download'dan yangilanmoqda..."
  for pair in "server*.py:server.py" "index*.html:index.html" "admin*.html:admin.html" "sim_test*.py:sim_test.py"; do
    pat="${pair%%:*}"; out="${pair##*:}"; f="$(newest "$pat")"
    if [ -n "$f" ]; then cp -f "$f" "$out"; echo "   ✅ $out  <-  $(basename "$f")"
    elif [ -f "$out" ]; then echo "   ℹ️ $out oldingisi qoldi"; fi
  done
fi
for x in server.py index.html admin.html; do
  [ -f "$x" ] || { echo "❌ $x yo'q. Download papkasiga yuklab, 'bash run.sh update' yozing"; exit 1; }
done

# 5sim.net ga ulanishni tekshirish (VPN kerak bo'lishi mumkin)
code="$(curl -s -o /dev/null -m 12 -A 'Mozilla/5.0' -w '%{http_code}' https://5sim.net/v1/guest/countries 2>/dev/null)"
if [ "$code" = "000" ] || [ -z "$code" ]; then
  echo "⚠️  5sim.net ochilmayapti. VPN yoqing va VPN ilovasida TERMUX ga ham ruxsat bering"
  echo "   (Per-app / Split tunneling ichida Termux tanlangan bo'lsin). Bot baribir ishga tushadi."
else echo "✅ 5sim.net ochiladi (kod $code)"; fi

pkill -f "cloudflared tunnel" 2>/dev/null
pkill -f "python server.py" 2>/dev/null
sleep 1
URL=""
for try in 1 2 3; do
  echo "▶ Tunnel ochilmoqda ($try/3)..."
  : > tunnel.log
  nohup cloudflared tunnel --protocol http2 --no-autoupdate --url http://localhost:8000 > tunnel.log 2>&1 &
  OKC=0; URL=""
  for i in $(seq 1 45); do
    URL="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' tunnel.log | head -1)"
    grep -q "Registered tunnel connection" tunnel.log && OKC=1
    [ -n "$URL" ] && [ "$OKC" = 1 ] && break; sleep 1
  done
  [ -n "$URL" ] && [ "$OKC" = 1 ] && break
  pkill -f "cloudflared tunnel" 2>/dev/null; URL=""; sleep 2
done
if [ -z "$URL" ]; then
  echo "❌ Tunnel ulanmadi. tunnel.log oxiri:"; tail -n 6 tunnel.log
  echo "   VPN'da boshqa server tanlang yoki qayta urinib ko'ring: bash run.sh"; exit 1
fi
touch .env
sed -i '/^PUBLIC_URL=/d' .env; echo "PUBLIC_URL=$URL" >> .env
echo "🌐 Manzil: $URL"
echo "   Admin panel: $URL/admin  (yoki botga /admin yozing)"
echo "   To'xtatish: Ctrl+C"
termux-wake-lock 2>/dev/null
exec python server.py
