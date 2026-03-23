from fastapi import FastAPI, Request, Form, Response, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from fastapi.templating import Jinja2Templates
import sqlite3, os, shutil
from datetime import datetime, timedelta
from typing import Optional
import json

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------
GIZLI_KULLANICI = "PATRON"
GIZLI_SIFRE     = "13451098618"
SESSION_COOKIE  = "manti_session"
DB_NAME         = os.path.join(os.environ.get("DB_PATH", "/data"), "manti_takip_v34.db")

URUN_LISTESI  = ["Soyalı Bohça","Soyalı Üçgen","Soyalı Ufak","Ekstra Özel","Ekstra Yaş","İçli Köfte","Ekstra Paket","Erişte","Özbek","El Mantısı"]
ODEME_TIPLERI = ["Nakit","Veresiye","POS","Hesaba"]
KILO_LISTESI  = [1,2,3,5,10,15,20,25,30]

# ---------------------------------------------------------
# VERİTABANI
# ---------------------------------------------------------
def get_db():
    db_dir = os.path.dirname(DB_NAME)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def db_setup():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sevkiyatlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih TEXT, bayi TEXT, urun TEXT,
        miktar REAL, birim_fiyat REAL, toplam_tutar REAL,
        aciklama TEXT, odeme_tipi TEXT DEFAULT 'Nakit'
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS musteriler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT UNIQUE, kdv_durum TEXT DEFAULT 'Dahil'
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS fiyatlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        musteri_ad TEXT, urun_ad TEXT, fiyat REAL,
        UNIQUE(musteri_ad, urun_ad)
    )""")
    try: cur.execute("ALTER TABLE sevkiyatlar ADD COLUMN odeme_tipi TEXT DEFAULT 'Nakit'")
    except: pass
    conn.commit(); conn.close()

db_setup()

# ---------------------------------------------------------
# YARDIMCI
# ---------------------------------------------------------
def tr_lower(text):
    if not text: return ""
    d = {'I':'ı','İ':'i','Ğ':'ğ','Ü':'ü','Ş':'ş','Ö':'ö','Ç':'ç'}
    for k,v in d.items(): text = str(text).replace(k,v)
    return text.lower()

def tarih_bugun(): return datetime.now().strftime("%Y-%m-%d")

def bu_ay_aralik():
    b = datetime.now().replace(day=1)
    s = (b.replace(day=28)+timedelta(days=4)); s = s.replace(day=1)-timedelta(days=1)
    return b.strftime("%Y-%m-%d"), s.strftime("%Y-%m-%d")

def is_authenticated(request: Request) -> bool:
    return request.cookies.get(SESSION_COOKIE) == "authenticated"

def auth_required(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return None

def ctx(request: Request, **kwargs):
    """Tüm template'lere ortak context."""
    return {"request": request, "urun_listesi": URUN_LISTESI,
            "odeme_tipleri": ODEME_TIPLERI, "kilo_listesi": KILO_LISTESI,
            "tarih_bugun": tarih_bugun(), **kwargs}

def tum_musteriler():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT ad FROM musteriler ORDER BY ad ASC")
    r = [row[0] for row in cur.fetchall()]; conn.close(); return r

def bayi_fiyat(bayi, urun):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT fiyat FROM fiyatlar WHERE musteri_ad=? AND urun_ad=?", (bayi, urun))
    r = cur.fetchone(); conn.close()
    return r[0] if r else 0.0

def bayi_istatistik(bayi):
    conn = get_db(); cur = conn.cursor()
    ay = datetime.now().strftime("%Y-%m")
    yil = datetime.now().strftime("%Y")
    cur.execute("SELECT SUM(miktar), SUM(toplam_tutar) FROM sevkiyatlar WHERE bayi=? AND tarih LIKE ? AND urun != 'TAHSİLAT'", (bayi, f"{ay}%"))
    r_ay = cur.fetchone()
    cur.execute("SELECT SUM(miktar), SUM(toplam_tutar) FROM sevkiyatlar WHERE bayi=? AND tarih LIKE ? AND urun != 'TAHSİLAT'", (bayi, f"{yil}%"))
    r_yil = cur.fetchone(); conn.close()
    return (r_ay[0] or 0, r_ay[1] or 0, r_yil[0] or 0, r_yil[1] or 0)

# ---------------------------------------------------------
# AUTH
# ---------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if is_authenticated(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", ctx(request))

@app.post("/login")
async def login_post(request: Request, kullanici: str = Form(...), sifre: str = Form(...)):
    if kullanici.strip() == GIZLI_KULLANICI and sifre.strip() == GIZLI_SIFRE:
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(SESSION_COOKIE, "authenticated", httponly=True, max_age=86400*30)
        return response
    return templates.TemplateResponse("login.html", ctx(request, hata="Kullanıcı adı veya şifre hatalı."))

@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response

# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    bas, bit = bu_ay_aralik()
    cur.execute("SELECT COUNT(*), SUM(miktar), SUM(toplam_tutar) FROM sevkiyatlar WHERE tarih BETWEEN ? AND ? AND urun != 'TAHSİLAT'", (bas, bit))
    r = cur.fetchone()
    cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE tarih BETWEEN ? AND ? AND urun = 'TAHSİLAT'", (bas, bit))
    tah = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM musteriler")
    mus = cur.fetchone()
    cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE tarih = ? AND urun != 'TAHSİLAT'", (tarih_bugun(),))
    bugun = cur.fetchone()
    conn.close()
    return templates.TemplateResponse("dashboard.html", ctx(request,
        ay_ciro=r[2] or 0, ay_kg=r[1] or 0,
        tahsilat=tah[0] or 0, musteri_sayisi=mus[0] or 0,
        bugun_ciro=bugun[0] or 0
    ))

# ---------------------------------------------------------
# SEVKİYAT
# ---------------------------------------------------------
@app.get("/sevkiyat", response_class=HTMLResponse)
async def sevkiyat_get(request: Request, mesaj: str = "", hata: str = ""):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    musteriler = tum_musteriler()
    return templates.TemplateResponse("sevkiyat.html", ctx(request,
        musteriler=musteriler, mesaj=mesaj, hata=hata
    ))

@app.post("/sevkiyat")
async def sevkiyat_post(request: Request,
    tarih: str = Form(...), bayi: str = Form(...),
    urun: str = Form(...), miktar: float = Form(...),
    odeme_tipi: str = Form(...), not_metin: str = Form("")):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    fiyat = bayi_fiyat(bayi, urun)
    if fiyat == 0:
        musteriler = tum_musteriler()
        return templates.TemplateResponse("sevkiyat.html", ctx(request,
            musteriler=musteriler, hata=f"'{bayi}' için '{urun}' fiyatı tanımlı değil!",
            secili_bayi=bayi, secili_urun=urun, secili_odeme=odeme_tipi
        ))
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO sevkiyatlar (tarih,bayi,urun,miktar,birim_fiyat,toplam_tutar,aciklama,odeme_tipi) VALUES (?,?,?,?,?,?,?,?)",
                (tarih, bayi, urun, miktar, fiyat, miktar*fiyat, not_metin, odeme_tipi))
    conn.commit(); conn.close()
    mesaj = f"✓ {bayi} → {urun} → {miktar} KG → {miktar*fiyat:,.2f} TL kaydedildi."
    musteriler = tum_musteriler()
    return templates.TemplateResponse("sevkiyat.html", ctx(request,
        musteriler=musteriler, mesaj=mesaj,
        secili_bayi=bayi, secili_urun=urun, secili_odeme=odeme_tipi
    ))

# ---------------------------------------------------------
# RAPORLAR
# ---------------------------------------------------------
@app.get("/raporlar", response_class=HTMLResponse)
async def raporlar_get(request: Request,
    bas: str = "", bit: str = "", bayi_ara: str = "",
    urun_filtre: str = "TÜM ÜRÜNLER", odeme_filtre: str = "TÜM ÖDEMELER"):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    if not bas and not bit:
        bas, bit = bu_ay_aralik()

    conn = get_db(); cur = conn.cursor()
    query = "SELECT * FROM sevkiyatlar WHERE 1=1"
    params = []
    if bas: query += " AND tarih >= ?"; params.append(bas)
    if bit: query += " AND tarih <= ?"; params.append(bit)
    if urun_filtre != "TÜM ÜRÜNLER": query += " AND urun = ?"; params.append(urun_filtre)
    if odeme_filtre != "TÜM ÖDEMELER": query += " AND odeme_tipi = ?"; params.append(odeme_filtre)
    query += " ORDER BY tarih DESC, id DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]; conn.close()

    if bayi_ara:
        rows = [r for r in rows if tr_lower(bayi_ara) in tr_lower(r["bayi"])]

    kg = sum(r["miktar"] for r in rows if r["urun"] != "TAHSİLAT")
    tl = sum(r["toplam_tutar"] for r in rows)
    t_nakit   = sum(r["toplam_tutar"] for r in rows if r["odeme_tipi"] == "Nakit")
    t_pos     = sum(r["toplam_tutar"] for r in rows if r["odeme_tipi"] == "POS")
    t_hesap   = sum(r["toplam_tutar"] for r in rows if r["odeme_tipi"] == "Hesaba")
    t_veresiye= sum(r["toplam_tutar"] for r in rows if r["odeme_tipi"] == "Veresiye")

    return templates.TemplateResponse("raporlar.html", ctx(request,
        rows=rows, bas=bas, bit=bit, bayi_ara=bayi_ara,
        urun_filtre=urun_filtre, odeme_filtre=odeme_filtre,
        toplam_kg=kg, toplam_tl=tl,
        t_nakit=t_nakit, t_pos=t_pos, t_hesap=t_hesap, t_veresiye=t_veresiye
    ))

@app.get("/raporlar/sil/{kayit_id}")
async def rapor_sil(request: Request, kayit_id: int,
    bas: str = "", bit: str = "", bayi_ara: str = ""):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM sevkiyatlar WHERE id=?", (kayit_id,))
    conn.commit(); conn.close()
    return RedirectResponse(f"/raporlar?bas={bas}&bit={bit}&bayi_ara={bayi_ara}", status_code=302)

@app.post("/raporlar/duzenle/{kayit_id}")
async def rapor_duzenle(request: Request, kayit_id: int,
    tarih: str = Form(...), bayi: str = Form(...), urun: str = Form(...),
    miktar: float = Form(0), birim_fiyat: float = Form(0),
    toplam_tutar: float = Form(...), odeme_tipi: str = Form(...),
    aciklama: str = Form(""), bas: str = Form(""), bit: str = Form("")):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT urun FROM sevkiyatlar WHERE id=?", (kayit_id,))
    row = cur.fetchone()
    if row and row[0] == "TAHSİLAT":
        cur.execute("UPDATE sevkiyatlar SET tarih=?,bayi=?,toplam_tutar=?,aciklama=?,odeme_tipi=? WHERE id=?",
                    (tarih, bayi, toplam_tutar, aciklama, odeme_tipi, kayit_id))
    else:
        tutar = miktar * birim_fiyat
        cur.execute("UPDATE sevkiyatlar SET tarih=?,bayi=?,urun=?,miktar=?,birim_fiyat=?,toplam_tutar=?,aciklama=?,odeme_tipi=? WHERE id=?",
                    (tarih, bayi, urun, miktar, birim_fiyat, tutar, aciklama, odeme_tipi, kayit_id))
    conn.commit(); conn.close()
    return RedirectResponse(f"/raporlar?bas={bas}&bit={bit}", status_code=302)

# ---------------------------------------------------------
# MÜŞTERİ YÖNETİMİ
# ---------------------------------------------------------
@app.get("/musteriler", response_class=HTMLResponse)
async def musteriler_get(request: Request, ara: str = "", mesaj: str = ""):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    if ara:
        cur.execute("SELECT ad, kdv_durum FROM musteriler WHERE ad LIKE ? ORDER BY ad", (f"%{ara}%",))
    else:
        cur.execute("SELECT ad, kdv_durum FROM musteriler ORDER BY ad")
    musteriler = [dict(r) for r in cur.fetchall()]; conn.close()
    return templates.TemplateResponse("musteriler.html", ctx(request,
        musteriler=musteriler, ara=ara, mesaj=mesaj
    ))

@app.post("/musteriler/ekle")
async def musteri_ekle(request: Request, ad: str = Form(...), kdv_durum: str = Form("Dahil")):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO musteriler (ad, kdv_durum) VALUES (?,?)", (ad.strip(), kdv_durum))
        conn.commit(); mesaj = f"✓ {ad} eklendi."
    except: mesaj = "Bu isimde müşteri zaten var."
    conn.close()
    return RedirectResponse(f"/musteriler?mesaj={mesaj}", status_code=302)

@app.post("/musteriler/guncelle/{eski_ad}")
async def musteri_guncelle(request: Request, eski_ad: str,
    yeni_ad: str = Form(...), kdv_durum: str = Form("Dahil")):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE musteriler SET ad=?, kdv_durum=? WHERE ad=?", (yeni_ad, kdv_durum, eski_ad))
    if yeni_ad != eski_ad:
        cur.execute("UPDATE sevkiyatlar SET bayi=? WHERE bayi=?", (yeni_ad, eski_ad))
        cur.execute("UPDATE fiyatlar SET musteri_ad=? WHERE musteri_ad=?", (yeni_ad, eski_ad))
    conn.commit(); conn.close()
    return RedirectResponse(f"/musteriler?mesaj=Güncellendi.", status_code=302)

@app.get("/musteriler/sil/{ad}")
async def musteri_sil(request: Request, ad: str):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM musteriler WHERE ad=?", (ad,))
    conn.commit(); conn.close()
    return RedirectResponse("/musteriler?mesaj=Silindi.", status_code=302)

@app.get("/musteriler/fiyatlar/{ad}", response_class=HTMLResponse)
async def musteri_fiyatlar(request: Request, ad: str):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT urun_ad, fiyat FROM fiyatlar WHERE musteri_ad=? ORDER BY urun_ad", (ad,))
    fiyatlar = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT kdv_durum FROM musteriler WHERE ad=?", (ad,))
    mus = cur.fetchone(); conn.close()
    kdv = mus[0] if mus else "Dahil"
    return templates.TemplateResponse("musteri_fiyat.html", ctx(request,
        musteri_ad=ad, fiyatlar=fiyatlar, kdv=kdv
    ))

@app.post("/musteriler/fiyat-kaydet/{ad}")
async def fiyat_kaydet(request: Request, ad: str,
    urun_ad: str = Form(...), fiyat: float = Form(...)):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO fiyatlar (id,musteri_ad,urun_ad,fiyat) VALUES ((SELECT id FROM fiyatlar WHERE musteri_ad=? AND urun_ad=?),?,?,?)",
                (ad, urun_ad, ad, urun_ad, fiyat))
    conn.commit(); conn.close()
    return RedirectResponse(f"/musteriler/fiyatlar/{ad}", status_code=302)

@app.get("/musteriler/fiyat-sil/{ad}/{urun_ad}")
async def fiyat_sil(request: Request, ad: str, urun_ad: str):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM fiyatlar WHERE musteri_ad=? AND urun_ad=?", (ad, urun_ad))
    conn.commit(); conn.close()
    return RedirectResponse(f"/musteriler/fiyatlar/{ad}", status_code=302)

# ---------------------------------------------------------
# TAHSİLAT
# ---------------------------------------------------------
@app.get("/tahsilat", response_class=HTMLResponse)
async def tahsilat_get(request: Request, mesaj: str = ""):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    musteriler = tum_musteriler()
    return templates.TemplateResponse("tahsilat.html", ctx(request,
        musteriler=musteriler, mesaj=mesaj
    ))

@app.post("/tahsilat")
async def tahsilat_post(request: Request,
    tarih: str = Form(...), bayi: str = Form(...),
    tutar: float = Form(...), odeme_tipi: str = Form(...),
    not_metin: str = Form("")):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO sevkiyatlar (tarih,bayi,urun,miktar,birim_fiyat,toplam_tutar,aciklama,odeme_tipi) VALUES (?,?,?,?,?,?,?,?)",
                (tarih, bayi, "TAHSİLAT", 0, 0, tutar, not_metin, odeme_tipi))
    conn.commit(); conn.close()
    # Bakiye hesapla
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE bayi=? AND urun != 'TAHSİLAT'", (bayi,))
    toplam_satis = cur.fetchone()[0] or 0
    cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE bayi=? AND urun = 'TAHSİLAT'", (bayi,))
    toplam_tah = cur.fetchone()[0] or 0
    conn.close()
    bakiye = toplam_satis - toplam_tah
    mesaj = f"✓ {bayi} → {tutar:,.2f} TL tahsilat eklendi. Güncel bakiye: {bakiye:,.2f} TL"
    musteriler = tum_musteriler()
    return templates.TemplateResponse("tahsilat.html", ctx(request,
        musteriler=musteriler, mesaj=mesaj, secili_bayi=bayi
    ))

@app.get("/tahsilat/rapor", response_class=HTMLResponse)
async def tahsilat_rapor(request: Request, bas: str = "", bit: str = ""):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    if not bas and not bit: bas, bit = bu_ay_aralik()
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT odeme_tipi, SUM(toplam_tutar) FROM sevkiyatlar WHERE tarih >= ? AND tarih <= ? GROUP BY odeme_tipi", (bas, bit))
    veriler = dict(cur.fetchall())
    # Müşteri bakiyeleri
    cur.execute("SELECT DISTINCT bayi FROM sevkiyatlar ORDER BY bayi")
    bayiler = [r[0] for r in cur.fetchall()]
    bakiyeler = []
    for b in bayiler:
        cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE bayi=? AND urun != 'TAHSİLAT'", (b,))
        s = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE bayi=? AND urun = 'TAHSİLAT'", (b,))
        t = cur.fetchone()[0] or 0
        if s > 0 or t > 0:
            bakiyeler.append({"bayi": b, "satis": s, "tahsilat": t, "bakiye": s - t})
    bakiyeler.sort(key=lambda x: x["bakiye"], reverse=True)
    conn.close()
    return templates.TemplateResponse("tahsilat_rapor.html", ctx(request,
        bas=bas, bit=bit, veriler=veriler, bakiyeler=bakiyeler,
        toplam=sum(veriler.values())
    ))

# ---------------------------------------------------------
# ANALİZLER
# ---------------------------------------------------------
@app.get("/analizler", response_class=HTMLResponse)
async def analizler(request: Request):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    bugun = datetime.now()
    bu_bas = bugun.replace(day=1).strftime("%Y-%m-%d")
    gecen_son = bugun.replace(day=1) - timedelta(days=1)
    gec_bas = gecen_son.replace(day=1).strftime("%Y-%m-%d")
    gec_son = gecen_son.strftime("%Y-%m-%d")

    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT ad FROM musteriler")
    musteriler = [r[0] for r in cur.fetchall()]
    veriler = []
    for m in musteriler:
        cur.execute("SELECT SUM(miktar) FROM sevkiyatlar WHERE bayi=? AND tarih BETWEEN ? AND ? AND urun != 'TAHSİLAT'", (m, gec_bas, gec_son))
        g = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(miktar) FROM sevkiyatlar WHERE bayi=? AND tarih >= ? AND urun != 'TAHSİLAT'", (m, bu_bas))
        b = cur.fetchone()[0] or 0
        if g == 0 and b == 0: continue
        fark = b - g
        pct = ((b-g)/g)*100 if g > 0 else (100 if b > 0 else 0)
        veriler.append({"bayi": m, "gecen": g, "bu_ay": b, "fark": fark, "pct": pct})
    conn.close()
    dusus   = sorted([v for v in veriler if v["fark"] < 0], key=lambda x: x["fark"])
    yukselis= sorted([v for v in veriler if v["fark"] >= 0], key=lambda x: x["fark"], reverse=True)
    return templates.TemplateResponse("analizler.html", ctx(request,
        dusus=dusus, yukselis=yukselis,
        bu_ay_str=bugun.strftime("%B %Y"),
        gec_ay_str=gecen_son.strftime("%B %Y")
    ))

# ---------------------------------------------------------
# API - Müşteri fiyat sorgula (AJAX)
# ---------------------------------------------------------
@app.get("/api/fiyat")
async def api_fiyat(request: Request, bayi: str, urun: str):
    if not is_authenticated(request): return JSONResponse({"hata": "yetkisiz"}, status_code=401)
    fiyat = bayi_fiyat(bayi, urun)
    ay_kg, ay_tl, yil_kg, yil_tl = bayi_istatistik(bayi)
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT kdv_durum FROM musteriler WHERE ad=?", (bayi,))
    r = cur.fetchone(); conn.close()
    return JSONResponse({
        "fiyat": fiyat, "kdv": r[0] if r else "Dahil",
        "ay_kg": ay_kg, "ay_tl": ay_tl, "yil_kg": yil_kg, "yil_tl": yil_tl
    })

@app.get("/api/musteriler")
async def api_musteriler(request: Request, q: str = ""):
    if not is_authenticated(request): return JSONResponse([])
    musteriler = tum_musteriler()
    if q:
        musteriler = [m for m in musteriler if tr_lower(q) in tr_lower(m)]
    return JSONResponse(musteriler[:20])

# ---------------------------------------------------------
# VERİTABANI YÜKLE
# ---------------------------------------------------------
@app.post("/sistem/db-yukle")
async def db_yukle(request: Request, dosya: UploadFile = File(...)):
    if not is_authenticated(request): return RedirectResponse("/login", status_code=302)
    if os.path.exists(DB_NAME):
        shutil.copy2(DB_NAME, DB_NAME + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    db_dir = os.path.dirname(DB_NAME)
    if db_dir: os.makedirs(db_dir, exist_ok=True)
    with open(DB_NAME, "wb") as f:
        f.write(await dosya.read())
    return RedirectResponse("/?mesaj=Veritabani yuklendi", status_code=302)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
