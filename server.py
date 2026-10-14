import os, json, time, sqlite3, threading, re, copy, hmac, hashlib, urllib.parse, html, base64, sys, math
import requests
from flask import Flask, request, jsonify, send_file, Response
from dotenv import load_dotenv
load_dotenv()
BOT = os.getenv("BOT_TOKEN", ""); MAIN = int(os.getenv("MAIN_ADMIN", "0") or 0)
CK = os.getenv("ANTHROPIC_API_KEY", ""); GK = os.getenv("GEMINI_API_KEY", "")
CM = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
GM = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
URL = os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL", "")
WEBHOOK = os.getenv("USE_WEBHOOK") == "1" or os.getenv("RENDER") == "true"
SECRET = hashlib.sha256(("wh" + BOT).encode()).hexdigest()[:32]
TG = f"https://api.telegram.org/bot{BOT}"

db = sqlite3.connect(os.getenv("DB_PATH", "data.db"), check_same_thread=False); lock = threading.Lock()
def Q(sql, a=()):
    with lock:
        c = db.execute(sql, a); db.commit(); return c.fetchall(), c.lastrowid
for t in ["create table if not exists kv(k text primary key,v text)",
          "create table if not exists users(uid text primary key,first real,last real)",
          "create table if not exists chats(id integer primary key autoincrement,uid text,q text,a text,ts real)",
          "create table if not exists orders(id integer primary key autoincrement,uid text,plan text,price text,contact text,status text,ts real)",
          "create table if not exists admins(id integer primary key)"]: Q(t)
Q("create table if not exists memory(uid text primary key,notes text,n integer)")
Q("create table if not exists forget(uid text primary key,ts real)")
Q("create table if not exists channels(id integer primary key autoincrement,title text,descr text,price text,image blob,ts real)")
try: Q("alter table channels add column kind text default 'channel'")
except Exception: pass
try: Q("alter table chats add column model text")
except Exception: pass
Q("create table if not exists ch_imgs(id integer primary key autoincrement,cid integer,pos integer,data blob)")
Q("insert into ch_imgs(cid,pos,data) select id,0,image from channels where image is not null and id not in (select cid from ch_imgs)")
Q("update channels set image=NULL where image is not null and id in (select cid from ch_imgs)")
for col in ("name", "username"):
    try: Q(f"alter table users add column {col} text")
    except Exception: pass
def touch(uid, now, name=None, uname=None):
    Q("insert into users(uid,first,last,name,username) values(?,?,?,?,?) on conflict(uid) do update set last=?, name=coalesce(?,name), username=coalesce(?,username)",
      (uid, now, now, name, uname, now, name, uname))
Q("create table if not exists wallet(uid text primary key,amount integer default 0)")
Q("create table if not exists ledger(id integer primary key autoincrement,uid text,delta integer,kind text,ref text,note text,ts real)")
Q("create table if not exists topups(id integer primary key autoincrement,uid text,amount integer,status text,contact text,ts real)")
Q("create table if not exists numbers(id integer primary key autoincrement,uid text,country text,cname text,price integer,act text,phone text,code text,status text,created real,expires real)")
for col in ("amount integer", "paid_by text"):
    try: Q("alter table orders add column " + col)
    except Exception: pass
Q("insert or ignore into admins values(?)", (MAIN,))

DEF = {"mq_home": "UlugbekPardayev YOUTUBE AI Chat bot", "mq_course": "Ulugʻbek Pardayev Kurslari",
       "card": "5614 6814 0659 1283", "holder": "", "daily_limit": 10, "pro_limit": 10, "search": 0, "usd_rate": 12500, "num_markup": 30, "num_add": 2000, "img_price": 500, "img_free": 2, "img_ai": 1, "num_on": 0, "num_timeout": 20, "kb": "",
       "plans": [{"id": "free", "name": "BEPUL", "price": "Bepul", "sub": "Tekin dars", "info": "", "design": "green", "icon": "🎁", "badge": "Tekin", "link": "https://t.me/tekindarsyoutube/14"},
                 {"id": "hup", "name": "HUP", "price": "99 000", "sub": "Boshlash uchun", "info": "", "design": "silver", "icon": "🚀", "badge": ""},
                 {"id": "pro", "name": "PRO", "price": "855 000", "sub": "Umrbod kurs + yopiq guruh", "info": "", "design": "red", "icon": "⚡", "badge": "Mashhur"},
                 {"id": "vip", "name": "VIP", "price": "3 200 000", "sub": "To‘liq imkoniyat", "info": "", "design": "gold", "icon": "👑", "badge": "Premium"}]}
FREE = DEF["plans"][0]
DESIGNS = {"silver", "red", "gold", "blue", "green", "purple"}
def cfg():
    r, _ = Q("select v from kv where k='cfg'")
    c = copy.deepcopy(DEF)
    if r:
        x = json.loads(r[0][0]); p = x.pop("plans", None); c.update(x)
        if isinstance(p, list): c["plans"] = p
        elif isinstance(p, dict):
            for y in c["plans"]: y.update(p.get(y["id"], {}))
    if not c.get("free_seeded") and not any(y.get("id") == "free" for y in c["plans"]):
        c["plans"].insert(0, copy.deepcopy(FREE))
    return c
def admins(): return [r[0] for r in Q("select id from admins")[0]]

def tg(m, **p):
    try: return requests.post(f"{TG}/{m}", json=p, timeout=40).json()
    except Exception as e: print("tg error:", e); return {}

def webapp(text, path=""): return {"text": text, "web_app": {"url": URL + path}}
def handle(x):
    m = x.get("message"); cb = x.get("callback_query")
    if m and m.get("text", "").startswith("/start"):
        uid = m["chat"]["id"]; now = time.time()
        touch(str(uid), now, m["from"].get("first_name"), m["from"].get("username"))
        kb = []
        if URL.startswith("https"):
            kb = [[webapp("🤖 Chat botga kirish", "/")]]
        tg("sendMessage", chat_id=uid, text="Assalomu alaykum 👋\nUlugʻbek Pardayev ning Chat bot AI botiga xush kelibsiz!\n\nKirish uchun pastdagi tugmani bosing:" if kb else "Bot ishlayapti, lekin PUBLIC_URL (https) hali sozlanmagan.",
           **({"reply_markup": {"inline_keyboard": kb}} if kb else {}))
    elif m and m.get("text", "").startswith("/admin"):
        cid = m["chat"]["id"]
        if not URL.startswith("https"):
            tg("sendMessage", chat_id=cid, text="PUBLIC_URL (https) hali sozlanmagan. Botni 'bash run.sh' bilan qayta ishga tushiring.")
        elif cid in admins():
            tg("sendMessage", chat_id=cid, text="Admin panel:", reply_markup={"inline_keyboard": [[webapp("⚙️ Ochish", "/admin")]]})
        else:
            tg("sendMessage", chat_id=cid, text=f"Siz admin emassiz.\nSizning Telegram ID raqamingiz: {cid}\n\nAsosiy admin shu raqamni admin panelida qo'shishi kerak.")
    if cb:
        if cb["from"]["id"] not in admins():
            return tg("answerCallbackQuery", callback_query_id=cb["id"], text="Ruxsat yo'q")
        data = cb["data"]
        if data.startswith(("tok:", "tno:")): return topup_decide(cb, data)
        st, oid = data.split(":")
        if st == "x": return tg("answerCallbackQuery", callback_query_id=cb["id"])
        res = order_decide(oid, st)
        if res == "none": return tg("answerCallbackQuery", callback_query_id=cb["id"], text="Topilmadi")
        if res == "done": return tg("answerCallbackQuery", callback_query_id=cb["id"], text="Allaqachon hal qilingan")
        ns = "✅ Tasdiqlandi" if st == "ok" else "❌ Rad etildi"
        tg("answerCallbackQuery", callback_query_id=cb["id"], text=ns)
        tg("editMessageReplyMarkup", chat_id=cb["message"]["chat"]["id"], message_id=cb["message"]["message_id"],
           reply_markup={"inline_keyboard": [[{"text": ns, "callback_data": "x:0"}]]})

def setup():
    tg("setMyDescription", description="Assalomu alaykum 👋\nUlugʻbek Pardayev ning Chat bot AI botiga xush kelibsiz!\n\nFoydalanish uchun START tugmasini bosing.")
    tg("setMyShortDescription", short_description="Ulugʻbek Pardayev — YouTube AI Chat bot")
    if URL.startswith("https"):
        tg("setChatMenuButton", menu_button={"type": "web_app", "text": "Ochish", "web_app": {"url": URL}})

def poll():
    tg("deleteWebhook"); setup(); off = 0
    while True:
        u = tg("getUpdates", offset=off, timeout=25)
        if not u.get("ok"): time.sleep(5); continue
        for x in u.get("result", []):
            off = x["update_id"] + 1
            try: handle(x)
            except Exception as e: print("handle error:", e)

app = Flask(__name__)
def err(t, c=400): return jsonify(error=t), c

@app.get("/")
def idx(): return send_file("index.html")
@app.get("/admin")
def adm(): return send_file("admin.html")
IMG_KEYS = ("logo", "market", "nana", "kurs", "video", "anl")
def img_urls():
    out = {}
    for k in IMG_KEYS:
        r = Q("select v from kv where k=?", ("img_" + k,))[0]
        if r and r[0][0]:
            v = Q("select v from kv where k=?", ("imgv_" + k,))[0]
            out[k] = f"/img/{k}.jpg?v={v[0][0] if v else 0}"
    return out
@app.get("/img/<key>.jpg")
def imgget(key):
    r = Q("select v from kv where k=?", ("img_" + key,))[0] if key in IMG_KEYS else []
    if not r or not r[0][0]: return "", 404
    return Response(base64.b64decode(r[0][0]), mimetype="image/jpeg", headers={"Cache-Control": "public, max-age=604800"})
@app.post("/api/admin/img")
def aimg():
    if not who(): return err("Kirish kerak", 401)
    d = request.json or {}; key = d.get("key")
    if key not in IMG_KEYS: return err("Noto'g'ri joy")
    if d.get("image"):
        mt = re.match(r"data:image/[\w+.-]+;base64,(.+)", d["image"], re.S)
        if not mt: return err("Rasm noto'g'ri")
        try: raw = base64.b64decode(mt[1])
        except Exception: return err("Rasm noto'g'ri")
        if len(raw) > 2000000: return err("Rasm juda katta")
        Q("insert or replace into kv values(?,?)", ("img_" + key, mt[1])); Q("insert or replace into kv values(?,?)", ("imgv_" + key, str(int(time.time()))))
    else:
        Q("delete from kv where k in (?,?)", ("img_" + key, "imgv_" + key))
    return jsonify(ok=1)
@app.get("/api/config")
def pub():
    c = cfg(); d = {k: c[k] for k in ("mq_home", "mq_course", "card", "holder", "plans")}; d["imgs"] = img_urls(); return jsonify(d)
@app.post("/api/hit")
def hit():
    u = tguser(request.headers.get("X-Init", "")); now = time.time()
    uid = str(u["id"]) if u else str((request.json or {}).get("uid", ""))[:40]
    if uid: touch(uid, now, (u or {}).get("first_name"), (u or {}).get("username"))
    return jsonify(ok=1)

SYS = ("Sen UlugbekPardayev YouTube AI yordamchisisan. YouTube bo'yicha (kanal, video g'oya, sarlavha, SEO, montaj, daromad, o'yin kontenti) javob ber. "
       "Javobni QISQA va aniq qil: ko'pi bilan 8-10 qator, ortiqcha kirish va xulosa yozma. "
       "MUHIM: yulduzcha (*), panjara (#), qalin yoki kursiv belgilarni ishlatma, faqat oddiy matn yoz. "
       "Ro'yxat kerak bo'lsa 1) 2) 3) deb raqamla. Foydalanuvchi qaysi tilda yozsa, shu tilda javob ber. "
       "Agar kim ekaningni yoki qaysi AI modelda ishlashingni so'rashsa: 'Men UlugbekPardayev YouTube AI yordamchisiman' de va qaysi kompaniya yoki model asosida ishlashing haqida ma'lumot berma.")
def clean(t):
    t = re.sub(r"^[ \t]*[*\-][ \t]+", "• ", t, flags=re.M)
    t = re.sub(r"^[ \t]*#+[ \t]*", "", t, flags=re.M)
    return t.replace("*", "").replace("`", "").replace("__", "").strip()
GEMINI_BASE = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
GCM = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
GCS = [{"maxOutputTokens": 1500, "temperature": 0.7, "thinkingConfig": {"thinkingLevel": "low"}}, {"maxOutputTokens": 1500, "temperature": 0.7}]
SEARCH = os.getenv("GEMINI_SEARCH") == "1" or os.getenv("CHAT_SEARCH") == "1"
def gerr(r):
    try: return r.json()["error"]["message"]
    except Exception: return r.text[:200]
def chat_claude(msgs, cont, sysm=None):
    if not CK: raise Exception("Claude: ANTHROPIC_API_KEY .env faylda yo'q")
    body = {"model": CM, "max_tokens": 900, "system": sysm or SYS, "messages": msgs + [{"role": "user", "content": cont}]}
    if SEARCH: body["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=120, headers={"x-api-key": CK, "anthropic-version": "2023-06-01"}, json=body)
    if r.status_code != 200: raise Exception(gerr(r))
    return "".join(b.get("text", "") for b in r.json()["content"] if b["type"] == "text") or "Javob topilmadi"
def chat_gemini(msgs, text, mt, sysm=None, plain=False):
    if not GK: raise Exception("GEMINI_API_KEY yo'q")
    contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} for m in msgs]
    parts = []
    if mt: parts.append({"inline_data": {"mime_type": mt[1], "data": mt[2]}})
    parts.append({"text": text}); contents.append({"role": "user", "parts": parts})
    body = {"systemInstruction": {"parts": [{"text": sysm or SYS}]}, "contents": contents}
    models = [GCM] + [m.strip() for m in os.getenv("GEMINI_CHAT_FALLBACK", "").split(",") if m.strip()]
    want = (SEARCH or bool(cfg().get("search"))) and not plain
    r = None
    for use_search in ([True, False] if want else [False]):
        for model in models:
            url = f"{GEMINI_BASE}/models/{model}:generateContent"
            for attempt in range(3):
                for gc in GCS:
                    b = dict(body); b["generationConfig"] = gc
                    if use_search: b["tools"] = [{"google_search": {}}]
                    r = requests.post(url, headers={"x-goog-api-key": GK}, json=b, timeout=120)
                    if r.status_code != 400: break
                if r.status_code == 200 or r.status_code not in (500, 503): break
                time.sleep(2 * (attempt + 1))
            if r.status_code == 200: break
        if r.status_code == 200: break
    if r.status_code != 200: raise Exception(gerr(r))
    c = (r.json().get("candidates") or [{}])[0]
    return "".join(p.get("text", "") for p in c.get("content", {}).get("parts", [])) or "Javob topilmadi"

OKEY = os.getenv("OPENAI_API_KEY", ""); OBASE = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"); OMODEL = os.getenv("OPENAI_MODEL", "")
def chat_openai(msgs, text, mt, sysm=None, key=None, base=None, model=None, name="OpenAI"):
    key = OKEY if key is None else key; base = base or OBASE; model = model or OMODEL
    if not key: raise Exception(f"{name}: kalit .env faylda yo'q")
    if not model: raise Exception(f"{name}: model nomi .env faylda yo'q")
    content = text
    if mt: content = [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": f"data:{mt[1]};base64,{mt[2]}"}}]
    messages = [{"role": "system", "content": sysm or SYS}] + msgs + [{"role": "user", "content": content}]
    r = None
    for attempt in range(3):
        for extra in ({"reasoning_effort": "low"}, {}):
            r = requests.post(base + "/chat/completions", headers={"Authorization": "Bearer " + key}, timeout=120,
                              json={"model": model, "messages": messages, "max_completion_tokens": 1500, **extra})
            if r.status_code != 400: break
        if r.status_code not in (500, 503): break
        time.sleep(2 * (attempt + 1))
    if r.status_code != 200: raise Exception(f"{name}: " + gerr(r))
    return (r.json()["choices"][0]["message"].get("content") or "").strip() or "Javob topilmadi"
G2KEY = os.getenv("GEMINI_API_KEY_2", ""); G2MODEL = os.getenv("GEMINI_ANALYZE_MODEL", ""); YTKEY = os.getenv("YOUTUBE_API_KEY", "")
GCS2 = [{"maxOutputTokens": 1800, "temperature": 0.5, "thinkingConfig": {"thinkingLevel": "low"}}, {"maxOutputTokens": 1800, "temperature": 0.5}]
def gem_analyze(parts, sysm, tools=None):
    key = G2KEY or GK; model = G2MODEL or GCM
    if not key: raise Exception("GEMINI_API_KEY_2 (yoki GEMINI_API_KEY) .env faylda yo'q")
    body = {"systemInstruction": {"parts": [{"text": sysm}]}, "contents": [{"role": "user", "parts": parts}]}
    r = None
    for attempt in range(3):
        for gc in GCS2:
            b = dict(body); b["generationConfig"] = gc
            if tools: b["tools"] = tools
            r = requests.post(f"{GEMINI_BASE}/models/{model}:generateContent", headers={"x-goog-api-key": key}, json=b, timeout=180)
            if r.status_code != 400: break
        if r.status_code not in (500, 503): break
        time.sleep(2 * (attempt + 1))
    if r.status_code != 200: raise Exception(gerr(r))
    c = (r.json().get("candidates") or [{}])[0]
    return "".join(p.get("text", "") for p in c.get("content", {}).get("parts", [])).strip() or "Javob topilmadi"
ANA_SYS = ("Sen YouTube kanal va videolarni tahlil qiluvchi mutaxassissan. O'zbek tilida, aniq va foydali yoz. "
           "FAQAT senga berilgan ma'lumotga (video, kanal statistikasi, matn) tayan; bilmagan narsangni o'ylab topma, 'ma'lumot yetarli emas' de. "
           "Tuzilma: 1) Umumiy baho 2) Kuchli tomonlari 3) Kamchiliklar 4) Aniq 5 ta tavsiya 5) 3 ta yangi video yoki sarlavha g'oyasi. "
           "Yulduzcha (*), panjara (#) va boshqa belgilarni ishlatma, faqat oddiy matn va 1) 2) 3) raqamlari.")
def yt_get(path, **p):
    r = requests.get("https://www.googleapis.com/youtube/v3/" + path, params={**p, "key": YTKEY}, timeout=30)
    j = r.json()
    if r.status_code != 200: raise Exception("YouTube API: " + str(j.get("error", {}).get("message", r.status_code))[:150])
    return j
def yt_channel_text(url):
    h = re.search(r"youtube\.com/(@[\w.\-]+)", url); cid = re.search(r"youtube\.com/channel/(UC[\w\-]+)", url)
    if h: j = yt_get("channels", part="snippet,statistics,contentDetails", forHandle=h[1])
    elif cid: j = yt_get("channels", part="snippet,statistics,contentDetails", id=cid[1])
    else: raise Exception("Kanal havolasi tushunarsiz (@nom yoki /channel/UC... ko'rinishida bo'lsin)")
    if not j.get("items"): raise Exception("Kanal topilmadi")
    ch = j["items"][0]; sn = ch["snippet"]; st = ch.get("statistics", {})
    out = [f"Kanal: {sn.get('title')}", f"Tavsif: {(sn.get('description') or '')[:400]}", f"Ochilgan: {sn.get('publishedAt', '')[:10]}  Davlat: {sn.get('country', '-')}",
           f"Obunachilar: {st.get('subscriberCount', 'yashirin')}  Jami ko'rishlar: {st.get('viewCount')}  Videolar soni: {st.get('videoCount')}"]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = ",".join(i["contentDetails"]["videoId"] for i in yt_get("playlistItems", part="contentDetails", playlistId=up, maxResults=12).get("items", []))
    if ids:
        out.append("So'nggi videolar:")
        for v in yt_get("videos", part="snippet,statistics", id=ids).get("items", []):
            s2 = v.get("statistics", {}); out.append(f"- {v['snippet']['title'][:90]} | {v['snippet']['publishedAt'][:10]} | ko'rish {s2.get('viewCount', '?')} | like {s2.get('likeCount', '?')} | izoh {s2.get('commentCount', '?')}")
    return "\n".join(out)
def analyze_yt(url, note):
    ask = "Quyidagini tahlil qil." + ((" Qo'shimcha izoh: " + note[:500]) if note else "")
    if re.search(r"(youtube\.com/(watch\?|shorts/|live/)|youtu\.be/)", url):
        try: return gem_analyze([{"file_data": {"file_uri": url}}, {"text": ask + " Bu YouTube videosi."}], ANA_SYS)
        except Exception as e: raise Exception("Videoni ochib bo'lmadi (video ochiq/public bo'lishi kerak): " + str(e)[:150])
    if YTKEY:
        return gem_analyze([{"text": ask + "\n\nKanal ma'lumotlari (YouTube Data API):\n" + yt_channel_text(url)}], ANA_SYS)
    last = None
    for tools in ([{"url_context": {}}, {"google_search": {}}], [{"google_search": {}}]):
        try: return gem_analyze([{"text": ask + "\nKanal havolasi: " + url + "\nAgar kanal haqida ishonchli ma'lumot topa olmasang, buni ochiq ayt."}], ANA_SYS, tools)
        except Exception as e: last = e
    raise Exception("Gemini internet qidiruvi (google_search) bu kalitda ishlamadi: " + str(last)[:150] + ". Kanalni aniq tahlil qilish uchun .env ga YOUTUBE_API_KEY (bepul) qo'ying.")
def hint(e):
    t = str(e).lower()
    for keys, msg in ((("prepayment", "credits are depleted", "billing", "payment"), "Gemini hisobida to'lov/kredit yo'q yoki tugagan. Google AI Studio'da hisobga kredit qo'shish (billing) kerak."),
                      (("api key not valid", "api_key_invalid", "key invalid", "invalid api key", "incorrect api key"), "Kalit noto'g'ri yozilgan yoki o'chirilgan. .env dagi kalitni tekshiring."),
                      (("no longer available", "not found", "is not supported for generatecontent"), "Model nomi eskirgan yoki mavjud emas. .env dagi model nomini AI Studio'dagi hozirgi nomga almashtiring."),
                      (("quota", "rate limit", "resource_exhausted", "429"), "Limit tugagan. Keyinroq urinib ko'ring yoki to'lovni ulang."),
                      (("high demand", "overloaded", "unavailable", "503"), "Xizmat hozir band. Birozdan keyin urinib ko'ring."),
                      (("location", "region", "not supported in your"), "Xizmat bu hududda mavjud emas bo'lishi mumkin.")):
        if any(k in t for k in keys): return "\n\nSabab: " + msg
    return ""
def provider(): return os.getenv("CHAT_PROVIDER") or ("gemini" if GK else "claude")
def chain():
    c = [x.strip() for x in (os.getenv("CHAT_CHAIN") or "").split(",") if x.strip()]
    return c or [provider()]
def run_llm(msgs, ask, mt, cont, sysm, plain=False, providers=None):
    last = None
    for p in (providers or chain()):
        try:
            if p == "gemini": out = chat_gemini(msgs, ask, mt, sysm, plain)
            elif p == "openai": out = chat_openai(msgs, ask, mt, sysm)
            elif p == "claude": out = chat_claude(msgs, cont, sysm)
            else: last = Exception("noma'lum provayder: " + p); continue
            print("AI javob berdi:", p); return out
        except Exception as e:
            last = e; print("provayder xatosi:", p, str(e)[:140])
    raise last or Exception("provayder sozlanmagan")

def uid_of(d):
    u = tguser(request.headers.get("X-Init", ""))
    return str(u["id"]) if u else str(d.get("uid", ""))[:40]
MODELS = [{"id": "plus", "name": "YouTube AI Plus", "icon": "⚡", "limit_key": "daily_limit", "limit_default": 10},
          {"id": "pro", "name": "YouTube AI Pro", "icon": "💎", "limit_key": "pro_limit", "limit_default": 10}]
def pro_provider(): return (os.getenv("PRO_PROVIDER") or "").strip()
def providers_of(mid): return ["gemini"] if mid == "plus" else ([pro_provider()] if pro_provider() else [])
def is_admin(uid): return bool(uid) and uid.isdigit() and int(uid) in admins()
def used_of(uid, mid):
    return Q("select count(*) from chats where uid=? and ts>? and coalesce(model,'plus')=?", (uid, time.time() - 86400, mid))[0][0][0]
def quota_of(uid):
    c = cfg(); adm = is_admin(uid); out = []
    for m in MODELS:
        lim = int(c.get(m["limit_key"], m["limit_default"]) or 0); used = used_of(uid, m["id"]) if uid else 0
        out.append({"id": m["id"], "name": m["name"], "icon": m["icon"], "limit": 0 if adm else lim, "used": used,
                    "left": None if (adm or not lim) else max(0, lim - used),
                    "soon": (m["id"] == "pro" and not pro_provider())})
    return out
def forgot_ts(uid):
    r = Q("select ts from forget where uid=?", (uid,))[0]
    return r[0][0] if r else 0
def history(uid, k=int(os.getenv("HIST_TURNS", "3"))):
    rows = Q("select id,q,a from chats where uid=? and ts>? order by id desc limit ?", (uid, forgot_ts(uid), k))[0][::-1]
    msgs, ids = [], set()
    for i, q, a in rows:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]; ids.add(i)
    return msgs, ids
WORDS = re.compile(r"\w{4,}")
def recall(uid, text, skip):
    qw = {w.lower() for w in WORDS.findall(text)}
    if not qw: return []
    rows = Q("select id,q,a from chats where uid=? and ts>? order by id desc limit 300", (uid, forgot_ts(uid)))[0]
    sc = []
    for i, q, a in rows:
        if i in skip: continue
        o = len(qw & {w.lower() for w in WORDS.findall(q)})
        if o >= 2 or (o >= 1 and len(qw) <= 2): sc.append((o, i, q, a))
    sc.sort(reverse=True)
    return [(q, a) for _, _, q, a in sc[:1]]

# ---------- Kurs bilimlari: admin panelga yozilgan ma'lumotdan qidirib topadi ----------
def _stem(w): return w.lower()[:5]
def _toks(t): return {_stem(w) for w in re.findall(r"\w{3,}", t or "")}
def course_docs():
    c = cfg(); docs = []
    for p in c["plans"]:
        head = f"KURS: {p.get('name','')} | narxi: {p.get('price','')} so'm | {p.get('sub','')}"
        if p.get("link"): head += f" | havola: {p['link']}"
        docs.append((head + ("\n" + p["info"] if p.get("info") else ""), p.get("name", "")))
    kb = (c.get("kb") or "").strip()
    if kb:
        buf = ""
        for para in re.split(r"\n\s*\n", kb):
            para = para.strip()
            if not para: continue
            if len(buf) + len(para) < 700: buf += ("\n\n" if buf else "") + para
            else:
                if buf: docs.append((buf, ""))
                while len(para) > 900: docs.append((para[:900], "")); para = para[900:]
                buf = para
        if buf: docs.append((buf, ""))
    return docs
def course_ctx(text):
    docs = course_docs()
    if not docs: return ""
    total = sum(len(d[0]) for d in docs)
    if total <= 7000: picked = [d[0] for d in docs]
    else:
        q = _toks(text); sc = []
        for i, (d, name) in enumerate(docs):
            t = _toks(d); o = len(q & t) + (3 if name and _stem(name) in q else 0)
            sc.append((o, -i, d))
        sc.sort(reverse=True); picked = [d[0].split("\n")[0] for d in docs[:len(cfg()["plans"])]]; size = sum(len(x) for x in picked)
        for o, _, d in sc:
            if o <= 0: break
            if size + len(d) > 6500: continue
            picked.append(d); size += len(d)
    return ("\n\nKURS HAQIDA RASMIY MA'LUMOT (admin kiritgan). Foydalanuvchi kurs, narx, dars, tarif, to'lov yoki kimligingiz haqida so'rasa, "
            "FAQAT shu ma'lumotga tayanib TO'LIQ va aniq javob ber (narx, nimalar kiradi, qanday olinadi). Ma'lumotda yo'q narsani o'ylab topma: "
            "'Bu haqda aniq ma'lumotim yo'q, admin bilan bog'laning' de. Kurs savollarida javob uzunligi 15 qatorgacha bo'lishi mumkin.\n\n"
            + "\n---\n".join(picked))

def build_sys(uid, text, ids):
    out = SYS + course_ctx(text)
    if not uid: return out
    n = Q("select notes from memory where uid=?", (uid,))[0]
    if n and n[0][0]: out += "\n\nFoydalanuvchi haqida eslab qolingan ma'lumotlar (kerak bo'lsa ishlat, har safar aytib o'tirma):\n" + n[0][0]
    rc = recall(uid, text, ids)
    if rc: out += "\n\nOldingi suhbatlardan mos o'rinlar:\n" + "\n".join(f"- Savol: {q[:150]}\n  Javob: {a[:250]}" for q, a in rc)
    return out
def remember(uid):
    try:
        r = Q("select n from memory where uid=?", (uid,))[0]; n = (r[0][0] if r else 0) + 1
        if not r: Q("insert into memory values(?,?,?)", (uid, "", n))
        else: Q("update memory set n=? where uid=?", (n, uid))
        if n % 4 or os.getenv("MEMORY_NOTES", "1") == "0": return
        notes = Q("select notes from memory where uid=?", (uid,))[0][0][0] or ""
        convo = "\n".join(("Foydalanuvchi: " if m["role"] == "user" else "Bot: ") + m["content"][:300] for m in history(uid)[0])
        prompt = ("Quyida foydalanuvchi haqida hozirgi qisqa yozuv va yangi suhbat bor. Foydalanuvchi haqidagi MUHIM doimiy faktlarni "
                  "(kanal nomi yoki mavzusi, maqsadi, darajasi, qiziqishlari, tili) yangilab, 400 belgidan oshmaydigan qisqa ro'yxat qilib yoz. "
                  "Parol, karta raqami, telefon kabi shaxsiy sirlarni yozma. Faqat yozuvning o'zini qaytar.\n\n"
                  f"Hozirgi yozuv:\n{notes or '(bo`sh)'}\n\nSuhbat:\n{convo}")
        sm = "Sen qisqa yozuv yurituvchi yordamchisan."
        new = run_llm([], prompt, None, [{"type": "text", "text": prompt}], sm, True, ["gemini"])
        Q("update memory set notes=? where uid=?", (clean(new)[:500], uid))
    except Exception as e: print("memory error:", e)

@app.post("/api/chat")
def chat():
    d = request.json or {}; text = str(d.get("message", ""))[:4000]; img = d.get("image"); uid = uid_of(d)
    if uid: msgs, ids = history(uid)
    else:
        msgs = [{"role": h["role"], "content": str(h["content"])[:3000]} for h in (d.get("hist") or [])[-8:]
                if h.get("role") in ("user", "assistant")]; ids = set()
    while msgs and msgs[0]["role"] != "user": msgs.pop(0)
    mid = d.get("model") if d.get("model") in ("plus", "pro") else "plus"
    m = next(x for x in MODELS if x["id"] == mid)
    if not providers_of(mid):
        return jsonify(reply=f"{m['name']} tez orada ishga tushadi. Hozircha YouTube AI Plus dan foydalaning.", models=quota_of(uid))
    lim = int(cfg().get(m["limit_key"], m["limit_default"]) or 0)
    if lim and uid and not is_admin(uid) and used_of(uid, mid) >= lim:
        return jsonify(reply=f"{m['name']} uchun kunlik limit tugadi: 24 soatda {lim} tagacha savol berish mumkin." + ("\n\nYouTube AI Plus bilan davom etishingiz mumkin." if mid == "pro" else " Keyinroq yana yozing."), models=quota_of(uid))
    ask = text or "Bu rasmni tahlil qil"
    cont = []
    mt = re.match(r"data:(image/[\w+.-]+);base64,(.+)", img or "", re.S)
    if mt: cont.append({"type": "image", "source": {"type": "base64", "media_type": mt[1], "data": mt[2]}})
    cont.append({"type": "text", "text": ask})
    sysm = build_sys(uid, ask, ids)
    try:
        a = run_llm(msgs, ask, mt, cont, sysm, providers=providers_of(mid))
    except Exception as e:
        return jsonify(reply="⚠️ " + m["name"] + " hozir javob bera olmadi: " + str(e)[:200] + hint(e) + ("\n\nYouTube AI Plus ni tanlab ko'ring." if mid == "pro" else ""), models=quota_of(uid))
    a = clean(a)
    Q("insert into chats(uid,q,a,ts,model) values(?,?,?,?,?)", (uid, text or "[rasm]", a, time.time(), mid))
    if uid: threading.Thread(target=remember, args=(uid,), daemon=True).start()
    return jsonify(reply=a, by=m["icon"] + " " + m["name"], model=mid, models=quota_of(uid))

@app.post("/api/analyze")
def analyze():
    d = request.json or {}; uid = uid_of(d); url = str(d.get("url", "")).strip()[:300]; note = str(d.get("note", "")).strip()
    if not re.match(r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/", url): return err("YouTube havolasini yuboring (youtube.com yoki youtu.be)")
    m = MODELS[0]; lim = int(cfg().get(m["limit_key"], m["limit_default"]) or 0)
    if lim and uid and not is_admin(uid) and used_of(uid, "plus") >= lim:
        return jsonify(reply=f"YouTube AI Plus uchun kunlik limit tugadi: 24 soatda {lim} tagacha savol yoki tahlil qilish mumkin.", models=quota_of(uid))
    try: a = clean(analyze_yt(url, note))
    except Exception as e: return jsonify(reply="⚠️ Tahlil qilib bo'lmadi: " + str(e)[:450] + hint(e), models=quota_of(uid))
    Q("insert into chats(uid,q,a,ts,model) values(?,?,?,?,?)", (uid, "[Tahlil] " + url, a, time.time(), "plus"))
    return jsonify(reply=a, models=quota_of(uid))
@app.get("/api/models")
def models():
    resp = jsonify(quota_of(uid_of({"uid": request.args.get("uid", "")}))); resp.headers["Cache-Control"] = "no-store"; return resp
@app.post("/api/forget")
def forget():
    uid = uid_of(request.json or {})
    if uid:
        Q("insert or replace into forget values(?,?)", (uid, time.time())); Q("delete from memory where uid=?", (uid,))
    return jsonify(ok=1)

HFK = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY") or ""
HFM = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
HF_URL = os.getenv("HF_IMAGE_URL", "")  # ixtiyoriy: to'liq manzilni qo'lda berish
RATIO_WH = {"16:9": (1024, 576), "1:1": (1024, 1024), "9:16": (576, 1024), "4:3": (1024, 768), "3:4": (768, 1024)}
def img_provider(): return (os.getenv("IMAGE_PROVIDER") or "gemini").lower()

def image_hf(prompt, ratio):
    w, h = RATIO_WH.get(ratio, (1024, 576))
    urls = [HF_URL] if HF_URL else [f"https://router.huggingface.co/hf-inference/models/{HFM}",
                                    f"https://router.huggingface.co/together/v1/images/generations"]
    last = ""
    for u in urls:
        try:
            if "together" in u:
                r = requests.post(u, timeout=120, headers={"Authorization": f"Bearer {HFK}"},
                                  json={"model": HFM, "prompt": prompt, "width": w, "height": h, "steps": 4, "response_format": "base64"})
                if r.ok:
                    b = (r.json().get("data") or [{}])[0].get("b64_json")
                    if b: return "data:image/jpeg;base64," + b
            else:
                r = requests.post(u, timeout=120, headers={"Authorization": f"Bearer {HFK}", "Accept": "image/png"},
                                  json={"inputs": prompt, "parameters": {"width": w, "height": h}})
                ct = r.headers.get("content-type", "")
                if r.ok and ct.startswith("image/"):
                    return f"data:{ct.split(';')[0]};base64," + base64.b64encode(r.content).decode()
            last = f"{r.status_code}: {r.text[:200]}"
        except Exception as e:
            last = str(e)[:200]
    raise Exception(last or "HF javob bermadi")

# ---- Rasm: 2 ta bepul, keyin pullik (balansdan) ----
def img_conf():
    c = cfg(); return int(c.get("img_free", 2) or 0), int(c.get("img_price", 500) or 0)
GIMG = [m.strip() for m in ([os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")] +
        os.getenv("GEMINI_IMAGE_FALLBACK", "gemini-3.1-flash-image-preview,gemini-2.5-flash-image").split(",")) if m.strip()]
Q("create table if not exists imgfree(uid text primary key,used integer default 0)")

def img_free_left(uid):
    r = Q("select used from imgfree where uid=?", (uid,))[0]; return max(0, img_conf()[0] - (r[0][0] if r else 0))
def img_take_free(uid):
    lim = img_conf()[0]
    with lock:
        db.execute("insert or ignore into imgfree(uid,used) values(?,0)", (uid,))
        c = db.execute("update imgfree set used=used+1 where uid=? and used<?", (uid, lim)); db.commit()
        return c.rowcount > 0
def img_give_free(uid): Q("update imgfree set used=max(used-1,0) where uid=?", (uid,))
def img_info(uid):
    fr, pr = img_conf(); return {"free_left": img_free_left(uid), "free_total": fr, "price": pr, "balance": bal(uid)}

IK = os.getenv("GEMINI_IMAGE_API_KEY") or GK  # rasm uchun alohida kalit (bo'lmasa GEMINI_API_KEY)
CFA = os.getenv("CF_ACCOUNT_ID", ""); CFT = os.getenv("CF_API_TOKEN", "")
CFM = os.getenv("CF_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
def image_cf(prompt, ratio):
    if not (CFA and CFT): raise Exception("CF_ACCOUNT_ID yoki CF_API_TOKEN .env faylda yo'q")
    w, h = RATIO_WH.get(ratio, (1024, 576)); url = f"https://api.cloudflare.com/client/v4/accounts/{CFA}/ai/run/{CFM}"
    last = ""
    for body in ({"prompt": prompt, "steps": 6, "width": w, "height": h}, {"prompt": prompt, "steps": 6}):
        r = requests.post(url, headers={"Authorization": f"Bearer {CFT}"}, json=body, timeout=120)
        try: j = r.json()
        except Exception: j = {}
        img = ((j.get("result") or {}).get("image")) if isinstance(j, dict) else None
        if r.ok and img: return "data:image/jpeg;base64," + img
        last = f"{r.status_code}: " + str((j.get("errors") or j) if isinstance(j, dict) else j)[:200]
        if r.status_code not in (400, 422): break
    raise Exception("Cloudflare " + last)

def image_gemini(prompt, ratio):
    if not IK: raise Exception("GEMINI_IMAGE_API_KEY (yoki GEMINI_API_KEY) .env faylda yo'q")
    last = ""
    for model in GIMG:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", timeout=120,
                          headers={"x-goog-api-key": IK},
                          json={"contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"imageConfig": {"aspectRatio": ratio}}})
        try: j = r.json()
        except Exception: j = {}
        for c in j.get("candidates", []):
            for p in c.get("content", {}).get("parts", []):
                i = p.get("inlineData") or p.get("inline_data")
                if i: return f"data:{i.get('mimeType') or i.get('mime_type')};base64,{i['data']}"
        msg = (j.get("error") or {}).get("message") or (j.get("promptFeedback") or {}).get("blockReason") or "javobda rasm yo'q"
        last = f"{model}: {msg}"; print("[image] gemini:", last, flush=True)
        if r.status_code == 404 or "not found" in str(msg).lower() or "not supported" in str(msg).lower(): continue
        break
    raise Exception(last[:250])

@app.get("/api/imginfo")
def imginfo():
    uid = tuid()
    if not uid: return err("Faqat Telegram ichidagi Mini App'da ishlaydi", 401)
    return nostore(img_info(uid))

IMG_SYS = ("You are an expert prompt writer for the FLUX image model, specialised in viral YouTube thumbnails for an AMERICAN audience (MrBeast-style). "
           "The user describes in Uzbek (or any language) what they need. Reply with ONE English image prompt only: no explanations, no quotes, max 70 words. "
           "Rules: one clear main subject, strong exaggerated facial emotion if a person is present, bright saturated colors, high contrast, dramatic rim lighting, "
           "shallow depth of field, ultra detailed, sharp focus, professional photo look, composition matching the given aspect ratio, "
           "leave clean empty space on one side for the title text. Do NOT put any text, letters, numbers, logos or watermarks in the image. Keep the user's idea exactly.")
def to_en_prompt(text, ratio):
    if not cfg().get("img_ai", 1): return text
    try:
        out = re.sub(r"\s+", " ", chat_gemini([], f"Aspect ratio: {ratio}\nUser idea: {text}", None, IMG_SYS, plain=True)).strip().strip("\"'`")[:700]
        if len(out) >= 10 and not out.startswith("Javob topilmadi"): return out
    except Exception as e: print("[image] prompt o'girish xatosi:", str(e)[:150], flush=True)
    return text

@app.post("/api/image")
def image():
    d = request.json or {}
    uid = tuid()
    if not uid: return err("Rasm yaratish faqat Telegram ichidagi Mini App'da ishlaydi", 401)
    prompt = str(d.get("prompt", "")).strip()[:1500]; ratio = d.get("ratio", "16:9")
    if ratio not in RATIO_WH: ratio = "16:9"
    if not prompt: return err("Rasm g'oyasini yozing")
    price = img_conf()[1]
    free = img_take_free(uid)
    if not free and not adjust(uid, -price, "image", note="Rasm yaratish"):
        return err(f"Balans yetarli emas. Rasm narxi {money(price)} so'm, balansingiz {money(bal(uid))} so'm. Balansni to'ldiring.", 402)
    try:
        pen = to_en_prompt(prompt, ratio)
        print("[image] provayder:", img_provider(), "| uid:", uid, "| bepul:", bool(free), "| prompt:", pen[:120], flush=True)
        out = {"hf": image_hf, "cf": image_cf}.get(img_provider(), image_gemini)(pen, ratio)
    except Exception as e:
        if free: img_give_free(uid)
        else: adjust(uid, price, "refund", note="Rasm yaratilmadi, pul qaytarildi")
        print("[image] xato:", e, flush=True)
        return err(("Rasm yaratilmadi, hech narsa yechilmadi. " + str(e))[:300], 400)
    return jsonify(image=out, prompt_en=pen, free_used=bool(free), **img_info(uid))

@app.get("/api/history")
def api_history():
    uid = uid_of({"uid": request.args.get("uid", "")})
    if not uid: return nostore({"items": []})
    rows = Q("select q,a from chats where uid=? and ts>? order by id desc limit 40", (uid, forgot_ts(uid)))[0][::-1]
    return nostore({"items": [{"q": q, "a": a} for q, a in rows]})

def tgphoto(chat, data, caption, kb):
    try:
        requests.post(f"{TG}/sendPhoto", data={"chat_id": chat, "caption": caption, "parse_mode": "HTML", "reply_markup": json.dumps(kb)},
                      files={"photo": ("chek.jpg", data)}, timeout=60)
    except Exception as e: print("photo error:", e)

@app.post("/api/order")
def order():
    d = request.json or {}; u = tguser(request.headers.get("X-Init", ""))
    mt = re.match(r"data:image/[\w+.-]+;base64,(.+)", d.get("receipt") or "", re.S)
    if not mt: return err("Chek rasmi kerak")
    try: photo = base64.b64decode(mt[1])
    except Exception: return err("Rasm noto'g'ri")
    if len(photo) > 6000000: return err("Rasm juda katta")
    if u:
        i = u["id"]; uid = str(i); name = html.escape(u.get("first_name", "") or "Foydalanuvchi")
        wu = f'<a href="tg://user?id={i}">{name}</a>' + (" (@" + html.escape(u["username"]) + ")" if u.get("username") else "") + f" · ID {i}"
        contact = ("@" + u["username"] + " " if u.get("username") else "") + f"{u.get('first_name', '')} (ID {i})"
    else:
        uid = str(d.get("uid", ""))[:40]; wu = "Telegramdan tashqari (brauzer)"; contact = "brauzer"
    _, oid = Q("insert into orders(uid,plan,price,contact,status,ts) values(?,?,?,?,?,?)",
               (uid, str(d.get("plan", ""))[:30], str(d.get("price", ""))[:20], contact[:60], "new", time.time()))
    cap = f"🧾 <b>Yangi to'lov #{oid}</b>\nKurs: <b>{html.escape(str(d.get('plan', '')))}</b> ({html.escape(str(d.get('price', '')))} so'm)\nFoydalanuvchi: {wu}"
    kb = {"inline_keyboard": [[{"text": "✅ Tasdiqlash", "callback_data": f"ok:{oid}"}, {"text": "❌ Rad etish", "callback_data": f"no:{oid}"}]]}
    for a in admins(): tgphoto(a, photo, cap, kb)
    return jsonify(ok=1)

# ---------- Admin ----------
def tguser(init):
    try:
        d = dict(urllib.parse.parse_qsl(init, keep_blank_values=True)); h = d.pop("hash")
        chk = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
        sec = hmac.new(b"WebAppData", BOT.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(hmac.new(sec, chk.encode(), hashlib.sha256).hexdigest(), h): return None
        if time.time() - int(d.get("auth_date", 0)) > 86400: return None
        return json.loads(d["user"])
    except Exception: return None
def who():
    u = tguser(request.headers.get("X-Init", "")); return u["id"] if u and u["id"] in admins() else None

@app.get("/api/admin/data")
def adata():
    me = who()
    if not me: return err("Kirish kerak", 401)
    n = time.time()
    cnt = lambda s, a=(): Q(s, a)[0][0][0]
    od = [dict(zip(("id", "uid", "plan", "price", "contact", "status", "ts"), r)) for r in Q("select * from orders order by id desc limit 15")[0]]
    return jsonify(main=me == MAIN, users=cnt("select count(*) from users"), online=cnt("select count(*) from users where last>?", (n - 120,)),
                   chats=cnt("select count(*) from chats"), orders=od, orders_total=cnt("select count(*) from orders"), orders_new=cnt("select count(*) from orders where status in ('new','paid')"), admins=admins(), cfg=cfg(), imgs=img_urls())
@app.post("/api/admin/cfg")
def acfg():
    if not who(): return err("Kirish kerak", 401)
    d = request.json or {}; c = cfg()
    if "search" in d: c["search"] = 1 if str(d["search"]).lower() in ("1", "true") else 0
    if "num_on" in d: c["num_on"] = 1 if str(d["num_on"]).lower() in ("1", "true") else 0
    if "img_ai" in d: c["img_ai"] = 1 if str(d["img_ai"]).lower() in ("1", "true") else 0
    for nk, lo, hi in (("usd_rate", 1, 1000000), ("num_markup", 0, 500), ("num_timeout", 3, 60), ("num_add", 0, 10000000), ("img_price", 0, 1000000), ("img_free", 0, 100)):
        if nk in d:
            try: c[nk] = max(lo, min(int(float(d[nk])), hi))
            except Exception: pass
    for lk in ("daily_limit", "pro_limit"):
        if lk in d:
            try: c[lk] = max(0, min(int(d[lk] or 0), 1000))
            except Exception: pass
    for k in ("mq_home", "mq_course", "card", "holder"):
        if k in d: c[k] = str(d[k])[:200]
    if "kb" in d: c["kb"] = str(d["kb"])[:40000]
    if isinstance(d.get("plans"), list):
        out = []
        for p in d["plans"][:12]:
            pid = re.sub(r"[^a-z0-9]", "", str(p.get("id", "")).lower())[:20] or "p" + str(int(time.time() * 1000))[-8:]
            out.append({"id": pid, "name": str(p.get("name", ""))[:30] or "Kurs", "price": str(p.get("price", ""))[:20],
                        "sub": str(p.get("sub", ""))[:80], "info": str(p.get("info", ""))[:5000],
                        "design": p.get("design") if p.get("design") in DESIGNS else "red",
                        "icon": str(p.get("icon", ""))[:4], "badge": str(p.get("badge", ""))[:20], "link": str(p.get("link", ""))[:300]})
        c["plans"] = out; c["free_seeded"] = True
    Q("insert or replace into kv values('cfg',?)", (json.dumps(c),)); return jsonify(ok=1)
@app.post("/api/admin/admin")
def aadm():
    if who() != MAIN: return err("Faqat asosiy admin", 403)
    d = request.json or {}
    raw = str(d.get("id", "")).strip()
    if raw.lstrip("@").isdigit() and not raw.startswith("@"): i = int(raw)
    else:
        un = raw.lstrip("@").strip()
        r = Q("select uid from users where lower(username)=lower(?)", (un,))[0] if un else []
        if not r or not str(r[0][0]).isdigit():
            return err("@" + un + " topilmadi. Bu odam botga /start bosib, Mini App'ni bir marta ochgan bo'lishi kerak. Yoki uning raqamli ID sini yozing (u botga /admin yozsa, bot ID ni yuboradi).")
        i = int(r[0][0])
    if d.get("del"):
        if i != MAIN: Q("delete from admins where id=?", (i,))
    else: Q("insert or ignore into admins values(?)", (i,))
    return jsonify(ok=1)


def rows(sql, keys, a=()): return [dict(zip(keys, r)) for r in Q(sql, a)[0]]
@app.get("/api/admin/users")
def ausers():
    if not who(): return err("Kirish kerak", 401)
    return jsonify(rows("select u.uid,u.name,u.username,u.first,u.last,(select count(*) from chats c where c.uid=u.uid),(select count(*) from orders o where o.uid=u.uid),coalesce((select amount from wallet w where w.uid=u.uid),0) from users u order by u.last desc limit 300",
                        ("uid", "name", "username", "first", "last", "chats", "orders", "bal")))
@app.get("/api/admin/chats")
def achats():
    if not who(): return err("Kirish kerak", 401)
    try: lim = max(1, min(int(request.args.get("limit", 40)), 200))
    except Exception: lim = 40
    return jsonify(rows("select c.id,c.uid,c.q,c.a,c.ts,u.name,u.username,coalesce(c.model,'plus') from chats c left join users u on u.uid=c.uid order by c.id desc limit ?",
                        ("id", "uid", "q", "a", "ts", "name", "username", "model"), (lim,)))
@app.get("/api/admin/orders")
def aorders():
    if not who(): return err("Kirish kerak", 401)
    return jsonify(rows("select o.id,o.uid,o.plan,o.price,o.contact,o.status,o.ts,u.name,u.username from orders o left join users u on u.uid=o.uid order by o.id desc limit 100",
                        ("id", "uid", "plan", "price", "contact", "status", "ts", "name", "username")))
@app.post("/api/admin/order")
def adecide():
    if not who(): return err("Kirish kerak", 401)
    d = request.json or {}; st = d.get("st")
    if st not in ("ok", "no"): return err("Noto'g'ri")
    res = order_decide(d.get("id"), st)
    if res == "none": return err("Topilmadi", 404)
    if res == "done": return err("Allaqachon hal qilingan")
    return jsonify(ok=1)

# ---------- Balans, hamyon, raqamlar ----------
def Qc(sql, a=()):
    with lock:
        c = db.execute(sql, a); db.commit(); return c.rowcount
def bal(uid):
    r = Q("select amount from wallet where uid=?", (uid,))[0]; return r[0][0] if r else 0
def adjust(uid, delta, kind, ref="", note=""):
    with lock:
        cur = db.execute("select amount from wallet where uid=?", (uid,)).fetchone()
        have = cur[0] if cur else 0
        if have + delta < 0: return False
        if cur: db.execute("update wallet set amount=amount+? where uid=?", (delta, uid))
        else: db.execute("insert into wallet(uid,amount) values(?,?)", (uid, delta))
        db.execute("insert into ledger(uid,delta,kind,ref,note,ts) values(?,?,?,?,?,?)", (uid, delta, kind, str(ref), note, time.time()))
        db.commit(); return True
def money(n): return f"{int(n or 0):,}".replace(",", " ")
def digits(t):
    d = re.sub(r"\D", "", str(t or "")); return int(d) if d else 0
def tuid():
    u = tguser(request.headers.get("X-Init", "")); return str(u["id"]) if u else None
def user_label(u):
    i = u["id"]; name = html.escape(u.get("first_name", "") or "Foydalanuvchi")
    return f'<a href="tg://user?id={i}">{name}</a>' + (" (@" + html.escape(u["username"]) + ")" if u.get("username") else "") + f" · ID {i}"
def nostore(j):
    r = jsonify(j); r.headers["Cache-Control"] = "no-store"; return r
def notify(uid, text):
    if str(uid).isdigit(): tg("sendMessage", chat_id=int(uid), text=text)

def order_decide(oid, st):
    cur = Q("select uid,plan,status,amount from orders where id=?", (oid,))[0]
    if not cur: return "none"
    uid, plan, status, amount = cur[0]
    if Qc("update orders set status=? where id=? and status in ('new','paid')", (st, oid)) != 1: return "done"
    if st == "no" and status == "paid" and amount: adjust(uid, int(amount), "refund", "o" + str(oid), "Buyurtma bekor qilindi")
    if st == "ok": notify(uid, f"✅ Buyurtmangiz bajarildi: {plan} 🎉" if status == "paid" else f"✅ To'lovingiz tasdiqlandi! {plan} kursiga xush kelibsiz 🎉\nAdmin tez orada yopiq guruhga qo'shadi.")
    else: notify(uid, f"❌ Buyurtmangiz bekor qilindi, {money(amount)} so'm balansingizga qaytarildi." if status == "paid" else "❌ To'lovingiz tasdiqlanmadi. Iltimos, admin bilan bog'laning.")
    return "ok"
def topup_apply(tid, yes):
    cur = Q("select uid,amount from topups where id=?", (tid,))[0]
    if not cur: return "none"
    uid, amount = cur[0]
    if Qc("update topups set status=? where id=? and status='new'", ("ok" if yes else "no", tid)) != 1: return "done"
    if yes:
        adjust(uid, amount, "topup", "t" + str(tid), "Balans to'ldirildi")
        notify(uid, f"✅ Balansingiz {money(amount)} so'mga to'ldirildi.\nHozirgi balans: {money(bal(uid))} so'm")
    else: notify(uid, "❌ Balans to'ldirish so'rovi rad etildi. Savol bo'lsa admin bilan bog'laning.")
    return "ok"
def topup_decide(cb, data):
    st, tid = data.split(":"); yes = st == "tok"
    res = topup_apply(tid, yes)
    if res == "none": return tg("answerCallbackQuery", callback_query_id=cb["id"], text="Topilmadi")
    if res == "done": return tg("answerCallbackQuery", callback_query_id=cb["id"], text="Allaqachon hal qilingan")
    ns = "✅ Tasdiqlandi" if yes else "❌ Rad etildi"
    tg("answerCallbackQuery", callback_query_id=cb["id"], text=ns)
    tg("editMessageReplyMarkup", chat_id=cb["message"]["chat"]["id"], message_id=cb["message"]["message_id"],
       reply_markup={"inline_keyboard": [[{"text": ns, "callback_data": "x:0"}]]})

@app.get("/api/wallet")
def wallet():
    uid = tuid()
    if not uid: return err("Balans faqat Telegram ichidagi Mini App'da ishlaydi", 401)
    led = [dict(zip(("delta", "kind", "note", "ts"), r)) for r in Q("select delta,kind,note,ts from ledger where uid=? order by id desc limit 15", (uid,))[0]]
    c = cfg(); return nostore({"balance": bal(uid), "ledger": led, "card": c["card"], "holder": c["holder"]})
@app.post("/api/topup")
def topup():
    u = tguser(request.headers.get("X-Init", ""))
    if not u: return err("Telegram ichidagi Mini App'da oching", 401)
    d = request.json or {}; amount = digits(d.get("amount"))
    if amount < 5000 or amount > 20000000: return err("Summa 5 000 dan 20 000 000 so'mgacha bo'lsin")
    mt = re.match(r"data:image/[\w+.-]+;base64,(.+)", d.get("receipt") or "", re.S)
    if not mt: return err("Chek rasmi kerak")
    try: photo = base64.b64decode(mt[1])
    except Exception: return err("Rasm noto'g'ri")
    if len(photo) > 6000000: return err("Rasm juda katta")
    uid = str(u["id"])
    _, tid = Q("insert into topups(uid,amount,status,contact,ts) values(?,?,?,?,?)", (uid, amount, "new", u.get("first_name", ""), time.time()))
    cap = f"💰 <b>Balans to'ldirish #{tid}</b>\nSumma: <b>{money(amount)} so'm</b>\nFoydalanuvchi: {user_label(u)}"
    kb = {"inline_keyboard": [[{"text": "✅ Tasdiqlash", "callback_data": f"tok:{tid}"}, {"text": "❌ Rad etish", "callback_data": f"tno:{tid}"}]]}
    for a in admins(): tgphoto(a, photo, cap, kb)
    return jsonify(ok=1, id=tid)
@app.post("/api/pay")
def paybal():
    u = tguser(request.headers.get("X-Init", ""))
    if not u: return err("Telegram ichidagi Mini App'da oching", 401)
    item = str((request.json or {}).get("item", "")); uid = str(u["id"])
    if item.startswith("ch") and item[2:].isdigit():
        r = Q("select title,descr,price,coalesce(kind,'channel') from channels where id=?", (int(item[2:]),))[0]
        if not r: return err("Topilmadi", 404)
        name = ("Video: " if r[0][3] == "video" else "Kanal: ") + (r[0][0] or (r[0][1] or "")[:18] or "YouTube"); price_txt = r[0][2]
    else:
        p = next((x for x in cfg()["plans"] if x["id"] == item), None)
        if not p or p.get("link"): return err("Topilmadi", 404)
        name = p["name"]; price_txt = p["price"]
    amount = digits(price_txt)
    if amount <= 0: return err("Bu mahsulotning narxi belgilanmagan")
    if not adjust(uid, -amount, "buy", item, name): return jsonify(error="Balans yetmaydi", need=amount, balance=bal(uid)), 402
    contact = ("@" + u["username"] + " " if u.get("username") else "") + f"{u.get('first_name', '')} (ID {u['id']})"
    _, oid = Q("insert into orders(uid,plan,price,contact,status,ts,amount,paid_by) values(?,?,?,?,?,?,?,?)", (uid, name[:30], str(price_txt)[:20], contact[:60], "paid", time.time(), amount, "balance"))
    kb = {"inline_keyboard": [[{"text": "✅ Topshirildi", "callback_data": f"ok:{oid}"}, {"text": "❌ Bekor qilish (pul qaytadi)", "callback_data": f"no:{oid}"}]]}
    for a in admins(): tg("sendMessage", chat_id=a, parse_mode="HTML", reply_markup=kb, text=f"💰 <b>Balansdan to'landi #{oid}</b>\n{html.escape(name)} ({money(amount)} so'm)\nFoydalanuvchi: {user_label(u)}")
    return jsonify(ok=1, balance=bal(uid), order=oid)

# --- raqam xizmati (provayder) ---
class FakeProv:
    """Faqat sinash uchun: NUM_PROVIDER=fake"""
    born = {}
    def prices(self): return [{"country": "uz", "name": "O'zbekiston", "usd": 0.35, "count": 120}, {"country": "ru", "name": "Rossiya", "usd": 0.18, "count": 800}, {"country": "us", "name": "AQSH", "usd": 0.60, "count": 40}]
    def buy(self, country):
        act = "f" + str(int(time.time() * 1000)); FakeProv.born[act] = time.time(); return {"act": act, "phone": "+998901234567" if country == "uz" else "+79001234567"}
    def status(self, act):
        if time.time() - FakeProv.born.get(act, 0) > float(os.getenv("FAKE_DELAY", "6")): return {"state": "code", "code": "482915"}
        return {"state": "waiting"}
    def cancel(self, act): return True
    def finish(self, act): pass

class SmsActProv:
    """SMS-Activate protokoli (handler_api.php). Ko'p saytlar shu usulda ishlaydi (sms-activate, smshub, grizzlysms va b.).
    .env: NUM_API_URL, NUM_API_KEY, NUM_SERVICE (Google = go), NUM_PRICE_TO_USD (narx dollarda bo'lmasa, dollarga o'tkazish koeffitsienti)"""
    def __init__(self):
        self.url = os.getenv("NUM_API_URL", "").strip(); self.key = os.getenv("NUM_API_KEY", "").strip()
        self.srv = os.getenv("NUM_SERVICE", "go").strip(); self.k = float(os.getenv("NUM_PRICE_TO_USD", "1") or 1)
    def call(self, action, **p):
        r = requests.get(self.url, params={"api_key": self.key, "action": action, **p}, timeout=30)
        return r.text.strip()
    def prices(self):
        names = {}
        try:
            for cid, v in json.loads(self.call("getCountries")).items():
                names[str(cid)] = v.get("eng") or v.get("rus") or ("Davlat " + str(cid))
        except Exception: pass
        j = json.loads(self.call("getPrices", service=self.srv)); out = []
        for cid, svc in j.items():
            x = svc.get(self.srv) if isinstance(svc, dict) else None
            if not x: continue
            cost = float(x.get("cost", 0) or 0); cnt = int(x.get("count", x.get("physicalCount", 0)) or 0)
            if cost > 0 and cnt > 0: out.append({"country": str(cid), "name": names.get(str(cid), "Davlat " + str(cid)), "usd": cost * self.k, "count": cnt})
        return out
    def buy(self, country):
        t = self.call("getNumber", service=self.srv, country=country)
        if t.startswith("ACCESS_NUMBER"):
            _, act, phone = t.split(":")[:3]; return {"act": act, "phone": "+" + phone.lstrip("+")}
        raise Exception({"NO_NUMBERS": "Hozir bu davlatda raqam yo'q", "NO_BALANCE": "Provayder hisobida pul yetmaydi"}.get(t, t[:80]))
    def status(self, act):
        t = self.call("getStatus", id=act)
        if t.startswith("STATUS_OK"): return {"state": "code", "code": t.split(":", 1)[1]}
        return {"state": "waiting"}
    def cancel(self, act): return self.call("setStatus", id=act, status=8).startswith("ACCESS_CANCEL")
    def finish(self, act): self.call("setStatus", id=act, status=6)
ISO5 = {"russia": "ru", "ukraine": "ua", "kazakhstan": "kz", "england": "gb", "usa": "us", "uzbekistan": "uz", "kyrgyzstan": "kg", "tajikistan": "tj",
        "turkey": "tr", "india": "in", "indonesia": "id", "philippines": "ph", "vietnam": "vn", "thailand": "th", "malaysia": "my", "china": "cn",
        "poland": "pl", "germany": "de", "france": "fr", "spain": "es", "italy": "it", "netherlands": "nl", "canada": "ca", "brazil": "br",
        "mexico": "mx", "egypt": "eg", "nigeria": "ng", "kenya": "ke", "pakistan": "pk", "bangladesh": "bd", "georgia": "ge", "armenia": "am",
        "azerbaijan": "az", "belarus": "by", "moldova": "md", "romania": "ro", "bulgaria": "bg", "israel": "il", "japan": "jp", "southkorea": "kr"}
class FiveSimProv:
    """5sim.net (v1 API). .env: NUM_PROVIDER=5sim, NUM_API_KEY=eyJ... (birinchi, JWT kalit), NUM_SERVICE=google, NUM_PRICE_TO_USD=1"""
    base = "https://5sim.net/v1"; ops = {}
    def __init__(self):
        self.key = os.getenv("NUM_API_KEY", "").strip(); self.srv = os.getenv("NUM_SERVICE", "google").strip() or "google"
        self.k = float(os.getenv("NUM_PRICE_TO_USD", "1") or 1)
    def get(self, path, auth=True, **p):
        h = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 Chrome/124.0 Mobile Safari/537.36"}
        if auth: h["Authorization"] = "Bearer " + self.key
        url = self.base + path
        try:
            r = requests.get(url, headers=h, params=p, timeout=30); code, text = r.status_code, r.text
        except Exception as e1:
            import subprocess
            if p: url += "?" + urllib.parse.urlencode(p)
            cmd = ["curl", "-s", "-m", "30", "-w", "\n%{http_code}", "-H", "Accept: application/json", "-A", h["User-Agent"]]
            if auth: cmd += ["-H", "Authorization: Bearer " + self.key]
            try: out = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=40).stdout
            except Exception: raise Exception("5sim ga ulanib bo'lmadi: " + str(e1)[:80])
            text, _, c = out.rpartition("\n")
            if not c.strip().isdigit() or c.strip() == "000": raise Exception("5sim ga ulanib bo'lmadi: " + str(e1)[:80])
            code = int(c)
        if code != 200: raise Exception((text or str(code)).strip()[:100])
        try: return json.loads(text)
        except Exception: return text
    def prices(self):
        j = self.get("/guest/prices", auth=False, product=self.srv).get(self.srv, {}); out = []
        for country, ops in j.items():
            ok = {o: v for o, v in ops.items() if isinstance(v, dict) and (v.get("count") or 0) > 0 and (v.get("cost") or 0) > 0}
            if not ok: continue
            op = "any" if "any" in ok else min(ok, key=lambda o: ok[o]["cost"])
            FiveSimProv.ops[country] = op
            out.append({"country": country, "name": country.replace("_", " ").title(), "iso": ISO5.get(country),
                        "usd": float(ok[op]["cost"]) * self.k, "count": int(ok[op]["count"])})
        return out
    def buy(self, country):
        op = FiveSimProv.ops.get(country, "any")
        j = self.get(f"/user/buy/activation/{country}/{op}/{self.srv}")
        if not isinstance(j, dict) or not j.get("id"): raise Exception("Raqam berilmadi: " + str(j)[:80])
        return {"act": str(j["id"]), "phone": str(j.get("phone", ""))}
    def status(self, act):
        j = self.get(f"/user/check/{act}")
        for m in (j.get("sms") or []) if isinstance(j, dict) else []:
            if m.get("code"): return {"state": "code", "code": str(m["code"])}
        return {"state": "waiting"}
    def cancel(self, act):
        try: self.get(f"/user/cancel/{act}"); return True
        except Exception as e:
            if "order has sms" in str(e).lower() or "sms" in str(e).lower(): return False
            raise
    def finish(self, act): self.get(f"/user/finish/{act}")
    def balance(self): return self.get("/user/profile").get("balance")

def prov():
    if (os.getenv("NUM_PROVIDER") or "").lower() == "fake": return FakeProv()
    if (os.getenv("NUM_PROVIDER") or "").lower() in ("5sim", "fivesim") and os.getenv("NUM_API_KEY"): return FiveSimProv()
    if os.getenv("NUM_API_URL") and os.getenv("NUM_API_KEY"): return SmsActProv()
    raise Exception("Raqam xizmati hali ulanmagan (provayder sozlanmagan)")
_pc = {"t": 0, "v": []}
def flag(cc):
    cc = (cc or "").upper()
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in cc) if len(cc) == 2 and cc.isalpha() else "🌍"
def num_prices():
    if time.time() - _pc["t"] > 60: _pc["v"] = prov().prices(); _pc["t"] = time.time()
    c = cfg(); out = []
    for p in _pc["v"]:
        som = int(math.ceil((p["usd"] * c["usd_rate"] + c.get("num_add", 0)) / 100.0)) * 100
        out.append({"country": p["country"], "name": p["name"], "flag": flag(p.get("iso") or p["country"]), "price": som, "count": p.get("count")})
    out.sort(key=lambda x: x["price"]); return out
def num_done(nid, code):
    r = Q("select uid,act,phone from numbers where id=?", (nid,))[0]
    if r and Qc("update numbers set status='done', code=? where id=? and status='waiting'", (code, nid)) == 1:
        try: prov().finish(r[0][1])
        except Exception: pass
        notify(r[0][0], f"📩 SMS kod keldi: {code}\nRaqam: {r[0][2]}")
def num_refund(nid):
    r = Q("select uid,act,price,status from numbers where id=?", (nid,))[0]
    if not r: return False, "Topilmadi"
    uid, act, price, status = r[0]
    if status != "waiting": return False, "Allaqachon yakunlangan"
    try: st = prov().status(act)
    except Exception: st = {"state": "waiting"}
    if st.get("state") == "code": num_done(nid, st["code"]); return False, "SMS allaqachon keldi: kod " + str(st["code"])
    try: ok = prov().cancel(act)
    except Exception as e: return False, "Bekor qilib bo'lmadi: " + str(e)[:100]
    if not ok: return False, "Xizmat hozir bekor qilishga ruxsat bermayapti. Birozdan keyin urinib ko'ring."
    if Qc("update numbers set status='cancelled' where id=? and status='waiting'", (nid,)) == 1:
        adjust(uid, int(price), "refund", "n" + str(nid), "Raqam bekor qilindi"); return True, "Pul balansga qaytarildi"
    return False, "Allaqachon yakunlangan"
def sweeper():
    while True:
        time.sleep(30)
        try:
            for nid, uid in Q("select id,uid from numbers where status='waiting' and expires<?", (time.time(),))[0]:
                ok, _ = num_refund(nid)
                if ok: notify(uid, "⏰ Vaqt tugadi, SMS kelmadi. Pul balansingizga qaytarildi.")
        except Exception as e: print("sweeper xatosi:", e)
@app.get("/api/numbers")
def numbers_list():
    c = cfg()
    if not c.get("num_on"): return nostore({"on": False})
    try: lst = num_prices()
    except Exception as e: return nostore({"on": False, "msg": str(e)[:150]})
    uid = tuid(); return nostore({"on": True, "list": lst, "balance": bal(uid) if uid else None})
@app.post("/api/number/buy")
def num_buy():
    uid = tuid()
    if not uid: return err("Telegram ichidagi Mini App'da oching", 401)
    c = cfg()
    if not c.get("num_on"): return err("Raqam xizmati hozircha yopiq")
    if Q("select count(*) from numbers where uid=? and status='waiting'", (uid,))[0][0][0] >= 1: return err("Sizda kutilayotgan raqam bor. Avval uni tugating yoki bekor qiling")
    country = str((request.json or {}).get("country", ""))
    try: pr = next((x for x in num_prices() if x["country"] == country), None)
    except Exception as e: return err("Xizmatga ulanib bo'lmadi: " + str(e)[:120], 502)
    if not pr: return err("Bu davlat hozir mavjud emas")
    if not adjust(uid, -pr["price"], "number", country, pr["name"]): return jsonify(error="Balans yetmaydi", need=pr["price"], balance=bal(uid)), 402
    try: r = prov().buy(country)
    except Exception as e:
        adjust(uid, pr["price"], "refund", "buyfail", "Raqam olinmadi"); return err("Raqam olib bo'lmadi: " + str(e)[:150] + " (pul qaytarildi)", 502)
    now = time.time(); exp = now + int(c.get("num_timeout", 20)) * 60
    _, nid = Q("insert into numbers(uid,country,cname,price,act,phone,status,created,expires) values(?,?,?,?,?,?,?,?,?)", (uid, country, pr["name"], pr["price"], r["act"], r["phone"], "waiting", now, exp))
    return jsonify(id=nid, phone=r["phone"], cname=pr["name"], flag=pr["flag"], price=pr["price"], left=int(exp - now), balance=bal(uid))
def num_view(nid, uid):
    r = Q("select uid,status,code,phone,expires,cname,country,price from numbers where id=?", (nid,))[0]
    if not r or r[0][0] != uid: return None
    _, status, code, phone, exp, cname, country, price = r[0]
    return {"id": nid, "status": status, "code": code, "phone": phone, "left": max(0, int(exp - time.time())), "cname": cname, "flag": flag(country), "price": price}
@app.get("/api/number/status")
def num_status():
    uid = tuid()
    if not uid: return err("Telegram ichidagi Mini App'da oching", 401)
    try: nid = int(request.args.get("id", 0))
    except Exception: nid = 0
    v = num_view(nid, uid)
    if not v: return err("Topilmadi", 404)
    if v["status"] == "waiting":
        r = Q("select act,expires from numbers where id=?", (nid,))[0][0]
        if time.time() > r[1]: ok, msg = num_refund(nid); v = num_view(nid, uid); v["msg"] = msg
        else:
            try: st = prov().status(r[0])
            except Exception: st = {"state": "waiting"}
            if st.get("state") == "code": num_done(nid, st["code"]); v = num_view(nid, uid)
    v["balance"] = bal(uid); return nostore(v)
@app.post("/api/number/cancel")
def num_cancel():
    uid = tuid()
    if not uid: return err("Telegram ichidagi Mini App'da oching", 401)
    try: nid = int((request.json or {}).get("id", 0))
    except Exception: nid = 0
    if not num_view(nid, uid): return err("Topilmadi", 404)
    ok, msg = num_refund(nid); return jsonify(ok=ok, msg=msg, balance=bal(uid))
@app.get("/api/number/active")
def num_active():
    uid = tuid()
    if not uid: return nostore({"active": None})
    r = Q("select id from numbers where uid=? and status='waiting' order by id desc limit 1", (uid,))[0]
    return nostore({"active": num_view(r[0][0], uid) if r else None})

# --- admin: balans va to'lovlar ---
@app.post("/api/admin/balance")
def abalance():
    if who() != MAIN: return err("Faqat asosiy admin", 403)
    d = request.json or {}; uid = str(d.get("uid", ""))
    try: delta = int(float(d.get("delta")))
    except Exception: return err("Summa noto'g'ri")
    if not uid or not delta: return err("Foydalanuvchi va summa kerak")
    if not adjust(uid, delta, "admin", "a", str(d.get("note", ""))[:60] or "Admin o'zgartirdi"): return err("Balans manfiy bo'lib qoladi")
    notify(uid, f"💰 Balansingiz {'+' if delta > 0 else ''}{money(delta)} so'mga o'zgartirildi. Hozirgi balans: {money(bal(uid))} so'm")
    return jsonify(ok=1, balance=bal(uid))
@app.get("/api/admin/money")
def amoney():
    if not who(): return err("Kirish kerak", 401)
    return nostore({"topups": rows("select t.id,t.uid,t.amount,t.status,t.ts,u.name,u.username from topups t left join users u on u.uid=t.uid order by t.id desc limit 50", ("id", "uid", "amount", "status", "ts", "name", "username")),
                    "numbers": rows("select n.id,n.uid,n.cname,n.price,n.phone,n.status,n.created,u.name,u.username from numbers n left join users u on u.uid=n.uid order by n.id desc limit 50", ("id", "uid", "cname", "price", "phone", "status", "ts", "name", "username"))})
@app.post("/api/admin/topup")
def atopup():
    if not who(): return err("Kirish kerak", 401)
    d = request.json or {}; res = topup_apply(d.get("id"), d.get("st") == "ok")
    if res == "none": return err("Topilmadi", 404)
    if res == "done": return err("Allaqachon hal qilingan")
    return jsonify(ok=1)

CH_SQL = "select id,title,descr,price,ts,coalesce(kind,'channel') from channels where coalesce(kind,'channel')=? order by id"
def chlist():
    kind = "video" if request.args.get("kind") == "video" else "channel"
    ims = {}
    for iid, cid in Q("select id,cid from ch_imgs order by cid,pos,id")[0]: ims.setdefault(cid, []).append(iid)
    out = []
    for r in Q(CH_SQL, (kind,))[0]:
        ids = ims.get(r[0], [])
        out.append({"id": r[0], "title": r[1] or "", "descr": r[2] or "", "price": r[3] or "", "kind": r[5] or "channel",
                    "imgids": ids, "imgs": [f"/chi/{i}.jpg" for i in ids], "img": (f"/chi/{ids[0]}.jpg" if ids else None)})
    resp = jsonify(out); resp.headers["Cache-Control"] = "no-store"; return resp
@app.get("/api/channels")
def channels(): return chlist()
@app.get("/ch/<int:cid>.jpg")
def chimg(cid):
    r = Q("select data from ch_imgs where cid=? order by pos,id limit 1", (cid,))[0]
    if not r or not r[0][0]: return "", 404
    return Response(r[0][0], mimetype="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})
@app.get("/chi/<int:iid>.jpg")
def chimgi(iid):
    r = Q("select data from ch_imgs where id=?", (iid,))[0]
    if not r or not r[0][0]: return "", 404
    return Response(r[0][0], mimetype="image/jpeg", headers={"Cache-Control": "public, max-age=604800"})
@app.get("/api/admin/channels")
def achannels():
    if not who(): return err("Kirish kerak", 401)
    return chlist()
@app.post("/api/admin/channel")
def achannel():
    if not who(): return err("Kirish kerak", 401)
    d = request.json or {}
    title = str(d.get("title", ""))[:80]; descr = str(d.get("descr", ""))[:3000]; price = str(d.get("price", ""))[:30]
    items = d.get("imgs") or []
    if not isinstance(items, list) or len(items) > 10: return err("Ko'pi bilan 10 ta rasm qo'yish mumkin")
    new, keep = [], []
    for n, it in enumerate(items):
        if isinstance(it, dict) and it.get("id"):
            try: keep.append((n, int(it["id"])))
            except Exception: pass
            continue
        raw = it.get("data") if isinstance(it, dict) else it
        mt = re.match(r"data:image/[\w+.-]+;base64,(.+)", raw or "", re.S)
        if not mt: continue
        try: b = base64.b64decode(mt[1])
        except Exception: return err("Rasm noto'g'ri")
        if len(b) > 3000000: return err("Rasm juda katta")
        new.append((n, b))
    cid = d.get("id"); now = time.time()
    if cid:
        if not Q("select id from channels where id=?", (cid,))[0]: return err("Topilmadi", 404)
        Q("update channels set title=?,descr=?,price=?,ts=? where id=?", (title, descr, price, now, cid))
        have = {r[0] for r in Q("select id from ch_imgs where cid=?", (cid,))[0]}
        keep = [(n, i) for n, i in keep if i in have]
        for i in have - {i for _, i in keep}: Q("delete from ch_imgs where id=?", (i,))
    else:
        if not (title or descr or price or new): return err("Bo'sh e'lon saqlanmaydi")
        _, cid = Q("insert into channels(title,descr,price,ts,kind) values(?,?,?,?,?)", (title, descr, price, now, "video" if d.get("kind") == "video" else "channel"))
    for n, i in keep: Q("update ch_imgs set pos=? where id=? and cid=?", (n, i, cid))
    for n, b in new: Q("insert into ch_imgs(cid,pos,data) values(?,?,?)", (cid, n, b))
    return jsonify(ok=1)
@app.post("/api/admin/channel/delete")
def adelch():
    if not who(): return err("Kirish kerak", 401)
    cid = (request.json or {}).get("id"); Q("delete from ch_imgs where cid=?", (cid,)); Q("delete from channels where id=?", (cid,)); return jsonify(ok=1)

def selfcheck():
    def t(name, fn):
        try: print("✅", name, "ishlayapti →", (fn() or "")[:60].replace("\n", " "))
        except Exception as e: print("❌", name, "ISHLAMAYAPTI:", str(e)[:220] + hint(e).replace("\n\n", "\n   "))
    def yt():
        if not YTKEY: raise Exception("YOUTUBE_API_KEY yo'q (ixtiyoriy)")
        yt_get("videos", part="id", id="dQw4w9WgXcQ"); return "ok"
    q = "Salom, bir so'z bilan javob ber"
    print("Tekshirilmoqda...")
    t("Plus (Gemini 1-kalit, model " + GCM + ")", lambda: chat_gemini([], q, None, SYS))
    t("Tahlil (Gemini " + ("2-kalit" if G2KEY else "1-kalit, GEMINI_API_KEY_2 yo'q") + ", model " + (G2MODEL or GCM) + ")", lambda: gem_analyze([{"text": q}], SYS))
    t("Qidiruv vositasi (Gemini google_search)", lambda: gem_analyze([{"text": "Bugun sana nechanchi? Qisqa javob ber"}], SYS, [{"google_search": {}}]))
    if pro_provider(): t("Pro (" + pro_provider() + ")", lambda: run_llm([], q, None, [{"type": "text", "text": q}], SYS, False, [pro_provider()]))
    else: print("ℹ️ Pro: hali ulanmagan (tez orada)")
    t("YouTube Data API", yt)
def start_webhook():
    setup()
    if URL.startswith("https"):
        r = tg("setWebhook", url=f"{URL}/tg/{SECRET}", allowed_updates=["message", "callback_query"])
        print("webhook:", r.get("ok"), r.get("description", ""))
@app.post("/tg/<sec>")
def tgwebhook(sec):
    if sec != SECRET: return "", 404
    try: handle(request.get_json(silent=True) or {})
    except Exception as e: print("webhook xatosi:", e)
    return "ok"
CHECK = len(sys.argv) > 1 and sys.argv[1] == "check"
if BOT and not CHECK: threading.Thread(target=(start_webhook if WEBHOOK else poll), daemon=True).start()
if not CHECK: threading.Thread(target=sweeper, daemon=True).start()
if __name__ == "__main__":
    if CHECK: selfcheck()
    else: app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
