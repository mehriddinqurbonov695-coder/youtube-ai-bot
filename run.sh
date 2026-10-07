#!/data/data/com.termux/files/usr/bin/bash
cd ~/bot
termux-wake-lock 2>/dev/null
pkill -f cloudflared 2>/dev/null; pkill -f "python server.py" 2>/dev/null
sleep 1
U=""
for n in 1 2 3 4 5 6; do
  echo "Tunnel yoqilmoqda ($n/6)..."
  : > tunnel.log
  cloudflared tunnel --protocol http2 --url http://localhost:8000 > tunnel.log 2>&1 &
  CF=$!
  for i in $(seq 1 40); do
    U=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' tunnel.log | grep -v '^https://api\.' | head -1)
    [ -n "$U" ] && break
    kill -0 $CF 2>/dev/null || break
    sleep 1
  done
  [ -n "$U" ] && break
  kill $CF 2>/dev/null
  sleep 3
done
if [ -z "$U" ]; then
  echo "Tunnel ochilmadi (internet yoki Cloudflare muammosi). Server tunnelsiz yonadi: bot /start ga javob beradi, lekin Mini App ochilmaydi."
else
  echo "Manzil: $U"
  grep -v '^PUBLIC_URL=' .env > .env.tmp; echo "PUBLIC_URL=$U" >> .env.tmp; mv .env.tmp .env
  echo "Tunnel tayyor bo'lishi uchun 20 soniya kutamiz..."
  sleep 20
  echo "Endi bu manzilni Chrome'da tekshir: $U"
fi
python server.py
