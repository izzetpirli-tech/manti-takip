import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import os
import smtplib
import threading
import time
import shutil
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

# ---------------------------------------------------------
# GİZLİ GİRİŞ BİLGİLERİ
# ---------------------------------------------------------
GIZLI_KULLANICI = "PATRON"
GIZLI_SIFRE = "13451098618"

# ---------------------------------------------------------
# GLOBAL AYARLAR
# ---------------------------------------------------------
URUN_LISTESI = [
    "Soyalı Bohça", "Soyalı Üçgen", "Soyalı Ufak",
    "Ekstra Özel", "Ekstra Yaş", "İçli Köfte",
    "Ekstra Paket", "Erişte", "Özbek", "El Mantısı"
]
KILO_BUTTONS = [1, 2, 3, 5, 10, 15, 20, 25, 30]
ODEME_TIPLERI = ["Nakit", "Veresiye", "POS", "Hesaba"]

DB_NAME = "manti_takip_v34.db"

# ---------------------------------------------------------
# OTOMATİK YEDEK SİSTEMİ
# ---------------------------------------------------------
YEDEK_SAATI = 0  # Her gece 00:00'da gönderir (Türkiye saati = UTC+3, yani UTC 21:00)

def yedek_mail_gonder():
    """Veritabanını zip'leyip Gmail ile gönderir."""
    gmail_user = os.environ.get("GMAIL_USER", "")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    alici = os.environ.get("YEDEK_EMAIL", gmail_user)

    if not gmail_user or not gmail_pass:
        print("⚠️ Mail bilgileri eksik, yedek gönderilmedi.")
        return False

    if not os.path.exists(DB_NAME):
        print("⚠️ Veritabanı bulunamadı.")
        return False

    try:
        # DB'yi geçici kopyala (okuma güvenliği)
        tarih_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        yedek_adi = f"manti_yedek_{tarih_str}.db"
        shutil.copy2(DB_NAME, yedek_adi)

        # Mail oluştur
        msg = MIMEMultipart()
        msg["From"] = gmail_user
        msg["To"] = alici
        msg["Subject"] = f"🥟 Mantı Takip Otomatik Yedek — {datetime.now().strftime('%d.%m.%Y')}"

        # İstatistik bilgisi
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sevkiyatlar")
        s_count = cur.fetchone()[0]
        cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE urun != 'TAHSİLAT' AND tarih = ?", (datetime.now().strftime("%Y-%m-%d"),))
        bugun_tl = cur.fetchone()[0] or 0
        conn.close()

        body = f"""
Mantı Takip Sistemi — Günlük Otomatik Yedek

📅 Tarih     : {datetime.now().strftime('%d.%m.%Y %H:%M')}
📦 Toplam Kayıt: {s_count}
💰 Bugünkü Ciro: {bugun_tl:,.0f} ₺

Veritabanı ekte bulunmaktadır.
Sakın silme, en son yedek budur.
        """
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # DB dosyasını ekle
        with open(yedek_adi, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={yedek_adi}")
            msg.attach(part)

        # Gönder
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, alici, msg.as_string())

        os.remove(yedek_adi)
        print(f"✅ Yedek maili gönderildi: {alici}")
        return True

    except Exception as e:
        print(f"❌ Mail hatası: {e}")
        try: os.remove(yedek_adi)
        except: pass
        return False


def yedek_scheduler():
    """Arkaplanda çalışır, her gece 23:00'de yedek gönderir."""
    son_gonderilen_gun = None
    while True:
        simdi = datetime.now()
        bugun = simdi.date()
        # UTC+3 offset: Railway UTC'de çalışır, 00:00 TR = 21:00 UTC
        hedef_saat = YEDEK_SAATI - 3  # UTC karşılığı
        if hedef_saat < 0: hedef_saat += 24  # 0-3=21

        if simdi.hour == hedef_saat and son_gonderilen_gun != bugun:
            print(f"🕐 Yedek zamanı geldi: {simdi}")
            basari = yedek_mail_gonder()
            if basari:
                son_gonderilen_gun = bugun
        time.sleep(60)  # Her dakika kontrol et


def yedek_thread_baslat():
    """Scheduler'ı arka planda başlatır (sadece bir kez)."""
    if "yedek_thread_basladi" not in st.session_state:
        t = threading.Thread(target=yedek_scheduler, daemon=True)
        t.start()
        st.session_state.yedek_thread_basladi = True


# ---------------------------------------------------------
# CSS
# ---------------------------------------------------------
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    .stApp {
        background: #0F1117;
        color: #E8E8E8;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #1A1D27 !important;
        border-right: 1px solid #2D3748;
    }
    section[data-testid="stSidebar"] .stRadio label {
        color: #A0AEC0 !important;
        font-size: 14px;
        padding: 6px 0;
    }
    section[data-testid="stSidebar"] .stRadio label:hover {
        color: #fff !important;
    }

    /* Metric Cards */
    div[data-testid="metric-container"] {
        background: #1A1D27;
        border: 1px solid #2D3748;
        border-radius: 8px;
        padding: 16px;
    }
    div[data-testid="metric-container"] label {
        color: #A0AEC0 !important;
        font-size: 12px;
        font-family: 'IBM Plex Mono', monospace;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    div[data-testid="metric-container"] [data-testid="metric-value"] {
        color: #F6E05E !important;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 24px !important;
        font-weight: 700;
    }

    /* Inputs */
    .stTextInput > div > div > input,
    .stSelectbox > div > div,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {
        background: #1A1D27 !important;
        border: 1px solid #2D3748 !important;
        color: #E8E8E8 !important;
        border-radius: 6px;
    }
    .stSelectbox > div > div {
        background: #1A1D27 !important;
        color: #E8E8E8 !important;
    }

    /* Buttons */
    .stButton > button {
        background: #2D3748;
        color: #E8E8E8;
        border: none;
        border-radius: 6px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: all 0.15s ease;
    }
    .stButton > button:hover {
        background: #4A5568;
        color: #fff;
    }

    /* Headers */
    h1, h2, h3 {
        font-family: 'IBM Plex Mono', monospace;
        font-weight: 700;
        color: #F6E05E;
        letter-spacing: -0.5px;
    }
    h1 { font-size: 28px; border-bottom: 2px solid #F6E05E; padding-bottom: 10px; margin-bottom: 24px; }
    h2 { font-size: 20px; color: #CBD5E0; }
    h3 { font-size: 16px; color: #A0AEC0; }

    /* Tables */
    .stDataFrame { border: 1px solid #2D3748; border-radius: 8px; overflow: hidden; }
    thead tr th { background: #2D3748 !important; color: #F6E05E !important; font-family: 'IBM Plex Mono', monospace !important; }
    tbody tr:nth-child(even) { background: #1A1D27 !important; }
    tbody tr:nth-child(odd) { background: #0F1117 !important; }

    /* Info/warning/success banners */
    .stAlert { border-radius: 8px; border: none; }

    /* Card-like container */
    .card {
        background: #1A1D27;
        border: 1px solid #2D3748;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 16px;
    }
    .card-title {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 13px;
        color: #F6E05E;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 12px;
    }

    /* Status tags */
    .tag {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-family: 'IBM Plex Mono', monospace;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .tag-nakit { background: #276749; color: #9AE6B4; }
    .tag-pos { background: #1A365D; color: #90CDF4; }
    .tag-hesaba { background: #44337A; color: #D6BCFA; }
    .tag-veresiye { background: #742A2A; color: #FC8181; }
    .tag-tahsilat { background: #276749; color: #9AE6B4; }

    /* Number display */
    .big-number {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 32px;
        font-weight: 700;
        color: #F6E05E;
    }
    .sub-text {
        font-size: 12px;
        color: #718096;
        font-family: 'IBM Plex Mono', monospace;
    }

    /* Login box */
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        background: #1A1D27;
        border: 1px solid #2D3748;
        border-radius: 12px;
        padding: 40px;
    }

    /* Green CTA button */
    .btn-green > button { background: #276749 !important; color: #9AE6B4 !important; }
    .btn-green > button:hover { background: #22543D !important; }
    .btn-red > button { background: #742A2A !important; color: #FC8181 !important; }
    .btn-red > button:hover { background: #63171B !important; }
    .btn-yellow > button { background: #744210 !important; color: #F6E05E !important; }
    .btn-yellow > button:hover { background: #652B19 !important; }

    div[data-testid="stSidebarNav"] { display: none; }

    /* Divider */
    hr { border-color: #2D3748; margin: 20px 0; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# VERİTABANI
# ---------------------------------------------------------
def get_db():
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

def odeme_renk(odeme):
    m = {"Nakit":"tag-nakit","POS":"tag-pos","Hesaba":"tag-hesaba","Veresiye":"tag-veresiye","TAHSİLAT":"tag-tahsilat"}
    return m.get(odeme, "")

# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------
def init_session():
    defaults = {
        "authenticated": False,
        "calisma_tarihi": tarih_bugun(),
        "secili_urun": URUN_LISTESI[0],
        "secili_odeme": ODEME_TIPLERI[0],
        "secili_tahsilat_tipi": "Nakit",
        "aktif_sayfa": "Dashboard",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ---------------------------------------------------------
# SAYFA: GİRİŞ
# ---------------------------------------------------------
def sayfa_giris():
    st.markdown("""
    <div style="max-width:420px;margin:60px auto;">
    <div style="background:#1A1D27;border:1px solid #2D3748;border-radius:12px;padding:40px;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:700;color:#F6E05E;margin-bottom:6px;">
    MANTI TAKİP SİSTEMİ
    </div>
    <div style="color:#718096;font-size:13px;margin-bottom:32px;font-family:'IBM Plex Mono',monospace;">
    v34 · Üretim Modülü
    </div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Sistem Girişi")
        kullanici = st.text_input("Kullanıcı Adı", placeholder="Kullanıcı adı")
        sifre = st.text_input("Şifre", type="password", placeholder="••••••••")
        if st.button("GİRİŞ YAP", use_container_width=True):
            if kullanici.strip() == GIZLI_KULLANICI and sifre.strip() == GIZLI_SIFRE:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Kullanıcı adı veya şifre hatalı.")

# ---------------------------------------------------------
# SAYFA: DASHBOARD
# ---------------------------------------------------------
def sayfa_dashboard():
    st.markdown("# PATRON KONTROL MERKEZİ")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="card"><div class="card-title">📅 Çalışma Tarihi Kilitleme</div></div>', unsafe_allow_html=True)
        tc1, tc2 = st.columns([3,1])
        with tc1:
            yeni_tarih = st.text_input("Çalışma Tarihi", value=st.session_state.calisma_tarihi, label_visibility="collapsed")
        with tc2:
            if st.button("Kilitle", use_container_width=True):
                st.session_state.calisma_tarihi = yeni_tarih
                st.success(f"✓ {yeni_tarih} kilitlendi")

    with col_b:
        st.markdown('<div class="card"><div class="card-title">🔍 Hızlı Fiyat Sorgu</div></div>', unsafe_allow_html=True)
        musteriler = tum_musteriler()
        hq1, hq2 = st.columns(2)
        with hq1:
            urun_sec = st.selectbox("Ürün", URUN_LISTESI, label_visibility="collapsed")
        with hq2:
            bayi_sec = st.selectbox("Müşteri", ["-- Seçin --"] + musteriler, label_visibility="collapsed")
        if bayi_sec != "-- Seçin --":
            f = bayi_fiyat(bayi_sec, urun_sec)
            st.markdown(f'<div class="big-number">{"---" if f==0 else f"{f:.2f} TL"}</div><div class="sub-text">{bayi_sec} / {urun_sec}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 Bu Ay Özet")
    conn = get_db(); cur = conn.cursor()
    bas, bit = bu_ay_aralik()
    cur.execute("SELECT COUNT(*), SUM(miktar), SUM(toplam_tutar) FROM sevkiyatlar WHERE tarih BETWEEN ? AND ? AND urun != 'TAHSİLAT'", (bas, bit))
    r = cur.fetchone()
    cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE tarih BETWEEN ? AND ? AND urun = 'TAHSİLAT'", (bas, bit))
    tahsilat_r = cur.fetchone()
    cur.execute("SELECT COUNT(DISTINCT id) FROM musteriler")
    mus_r = cur.fetchone(); conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bu Ay Sevkiyat", f"{r[2] or 0:,.0f} ₺")
    c2.metric("Toplam KG", f"{r[1] or 0:.1f} kg")
    c3.metric("Tahsilat", f"{tahsilat_r[0] or 0:,.0f} ₺")
    c4.metric("Müşteri Sayısı", f"{mus_r[0] or 0}")

    st.markdown("---")
    st.markdown("### 🚀 Hızlı Erişim")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    pages = [
        ("📦 Sevkiyat", "Sevkiyat Girişi", m1),
        ("📄 Raporlar", "Raporlar", m2),
        ("👥 Müşteriler", "Müşteri Yönetimi", m3),
        ("📈 Analizler", "Analizler", m4),
        ("💰 Tahsilat Raporu", "Tahsilat Raporu", m5),
        ("💸 Tahsilat Ekle", "Tahsilat Girişi", m6),
    ]
    for label, page, col in pages:
        with col:
            if st.button(label, use_container_width=True):
                st.session_state.aktif_sayfa = page
                st.rerun()

# ---------------------------------------------------------
# SAYFA: SEVKİYAT GİRİŞİ
# ---------------------------------------------------------
def sayfa_sevkiyat():
    st.markdown("# 📦 SEVKİYAT GİRİŞİ")
    musteriler = tum_musteriler()

    left, right = st.columns([3, 1])

    with left:
        col1, col2 = st.columns(2)
        with col1:
            tarih = st.text_input("Tarih", value=st.session_state.calisma_tarihi)
        with col2:
            bayi = st.selectbox("Müşteri / Bayi", ["-- Seçin --"] + musteriler)

        st.markdown("**Ürün Seçimi**")
        urun_cols = st.columns(5)
        for i, urun in enumerate(URUN_LISTESI):
            with urun_cols[i % 5]:
                secili = st.session_state.secili_urun == urun
                btn_style = "btn-yellow" if secili else ""
                st.markdown(f'<div class="{btn_style}">', unsafe_allow_html=True)
                if st.button(urun, use_container_width=True, key=f"urun_{i}"):
                    st.session_state.secili_urun = urun
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(f"**Seçili Ürün:** `{st.session_state.secili_urun}`")

        st.markdown("**Ödeme Tipi**")
        odeme_cols = st.columns(4)
        for i, odeme in enumerate(ODEME_TIPLERI):
            with odeme_cols[i]:
                if st.button(odeme, use_container_width=True, key=f"odeme_{i}",
                             type="primary" if st.session_state.secili_odeme == odeme else "secondary"):
                    st.session_state.secili_odeme = odeme
                    st.rerun()

        st.markdown("**Hızlı Miktar (KG)**")
        kilo_cols = st.columns(len(KILO_BUTTONS))
        for i, kg in enumerate(KILO_BUTTONS):
            with kilo_cols[i]:
                if st.button(str(kg), use_container_width=True, key=f"kg_{i}"):
                    st.session_state["miktar_input"] = float(kg)
                    st.rerun()

        col_m, col_n = st.columns([1, 2])
        with col_m:
            miktar = st.number_input("Manuel KG", min_value=0.0, step=0.5,
                                     value=st.session_state.get("miktar_input", 0.0), format="%.2f")
        with col_n:
            not_metin = st.text_input("Not (opsiyonel)", "")

        st.markdown('<div class="btn-green">', unsafe_allow_html=True)
        kaydet_btn = st.button("💾 KAYDET", use_container_width=True, type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

        if kaydet_btn:
            if bayi == "-- Seçin --":
                st.error("Müşteri seçin!")
            elif miktar <= 0:
                st.error("Geçerli miktar girin!")
            else:
                urun = st.session_state.secili_urun
                fiyat = bayi_fiyat(bayi, urun)
                if fiyat == 0:
                    st.warning(f"⚠️ {bayi} için '{urun}' fiyatı tanımlı değil! Lütfen Müşteri Yönetimi'nden fiyat tanımlayın.")
                else:
                    conn = get_db(); cur = conn.cursor()
                    cur.execute("""INSERT INTO sevkiyatlar (tarih, bayi, urun, miktar, birim_fiyat, toplam_tutar, aciklama, odeme_tipi)
                                   VALUES (?,?,?,?,?,?,?,?)""",
                                (tarih, bayi, urun, miktar, fiyat, miktar * fiyat, not_metin, st.session_state.secili_odeme))
                    conn.commit(); conn.close()
                    st.success(f"✓ Kaydedildi: {bayi} → {urun} → {miktar} KG → {miktar*fiyat:,.2f} TL")
                    st.session_state["miktar_input"] = 0.0

    with right:
        st.markdown("**Müşteri Bilgisi**")
        if bayi != "-- Seçin --":
            urun = st.session_state.secili_urun
            fiyat = bayi_fiyat(bayi, urun)
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT kdv_durum FROM musteriler WHERE ad=?", (bayi,))
            kdv_r = cur.fetchone(); conn.close()
            kdv = kdv_r[0] if kdv_r else "Dahil"

            st.markdown(f"""
            <div class="card">
            <div class="card-title">{bayi}</div>
            <div style="font-size:28px;font-family:'IBM Plex Mono',monospace;color:#F6E05E;font-weight:700;">{fiyat:.2f} TL</div>
            <div class="sub-text">{urun}</div>
            <div style="margin-top:8px;font-size:12px;color:{'#9AE6B4' if kdv=='Dahil' else '#F6AD55'};">KDV {kdv}</div>
            </div>
            """, unsafe_allow_html=True)

            ay_kg, ay_tl, yil_kg, yil_tl = bayi_istatistik(bayi)
            st.markdown(f"""
            <div class="card">
            <div class="card-title">Canlı Karne</div>
            <div class="sub-text">Bu Ay</div>
            <div style="font-size:16px;font-family:'IBM Plex Mono',monospace;font-weight:600;color:#90CDF4;">{ay_kg:.1f} KG · {ay_tl:,.0f} ₺</div>
            <div class="sub-text" style="margin-top:10px;">Bu Yıl</div>
            <div style="font-size:16px;font-family:'IBM Plex Mono',monospace;font-weight:600;color:#9AE6B4;">{yil_kg:.1f} KG · {yil_tl:,.0f} ₺</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("**Fiyat Güncelle**")
            yeni_fiyat = st.number_input("Yeni Fiyat", min_value=0.0, value=fiyat, step=0.5, format="%.2f")
            if st.button("Fiyatı Güncelle"):
                conn = get_db(); cur = conn.cursor()
                cur.execute("""INSERT OR REPLACE INTO fiyatlar (id, musteri_ad, urun_ad, fiyat)
                               VALUES ((SELECT id FROM fiyatlar WHERE musteri_ad=? AND urun_ad=?), ?, ?, ?)""",
                            (bayi, urun, bayi, urun, yeni_fiyat))
                conn.commit(); conn.close()
                st.success("Fiyat güncellendi!")
                st.rerun()

# ---------------------------------------------------------
# SAYFA: RAPORLAR
# ---------------------------------------------------------
def sayfa_rapor():
    st.markdown("# 📄 RAPORLAR & VERİ YÖNETİMİ")

    with st.expander("🔍 Filtreler", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            bas = st.text_input("Başlangıç Tarihi", value=bu_ay_aralik()[0])
        with c2:
            bit = st.text_input("Bitiş Tarihi", value=bu_ay_aralik()[1])
        with c3:
            urun_filtre = st.selectbox("Ürün", ["TÜM ÜRÜNLER"] + URUN_LISTESI)
        with c4:
            odeme_filtre = st.selectbox("Ödeme", ["TÜM ÖDEMELER"] + ODEME_TIPLERI)

        bf1, bf2, bf3 = st.columns([3, 1, 1])
        with bf1:
            bayi_ara = st.text_input("Müşteri Ara", "")
        with bf2:
            if st.button("Bugün", use_container_width=True):
                bas = tarih_bugun(); bit = tarih_bugun()
        with bf3:
            if st.button("Bu Ay", use_container_width=True):
                bas, bit = bu_ay_aralik()

    # Sorgu
    conn = get_db(); cur = conn.cursor()
    query = "SELECT * FROM sevkiyatlar WHERE 1=1"
    params = []
    if bas: query += " AND tarih >= ?"; params.append(bas)
    if bit: query += " AND tarih <= ?"; params.append(bit)
    if urun_filtre != "TÜM ÜRÜNLER": query += " AND urun = ?"; params.append(urun_filtre)
    if odeme_filtre != "TÜM ÖDEMELER": query += " AND odeme_tipi = ?"; params.append(odeme_filtre)
    query += " ORDER BY tarih DESC, id DESC"
    cur.execute(query, params); rows = cur.fetchall(); conn.close()

    if bayi_ara:
        rows = [r for r in rows if tr_lower(bayi_ara) in tr_lower(r["bayi"])]

    if not rows:
        st.info("Kayıt bulunamadı."); return

    # Özet metrikler
    kg = sum(r["miktar"] for r in rows if r["urun"] != "TAHSİLAT")
    tl = sum(r["toplam_tutar"] for r in rows)
    t_nakit = sum(r["toplam_tutar"] for r in rows if r["odeme_tipi"] == "Nakit")
    t_pos = sum(r["toplam_tutar"] for r in rows if r["odeme_tipi"] == "POS")
    t_hesap = sum(r["toplam_tutar"] for r in rows if r["odeme_tipi"] == "Hesaba")
    t_veresiye = sum(r["toplam_tutar"] for r in rows if r["odeme_tipi"] == "Veresiye")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Toplam Ciro", f"{tl:,.0f} ₺")
    c2.metric("Toplam KG", f"{kg:.1f}")
    c3.metric("Nakit", f"{t_nakit:,.0f} ₺")
    c4.metric("POS", f"{t_pos:,.0f} ₺")
    c5.metric("Veresiye", f"{t_veresiye:,.0f} ₺")

    st.markdown("---")

    # Tablo
    df = pd.DataFrame([dict(r) for r in rows])
    df = df[["id", "tarih", "bayi", "urun", "miktar", "birim_fiyat", "toplam_tutar", "odeme_tipi", "aciklama"]]
    df.columns = ["ID", "Tarih", "Bayi", "Ürün", "KG", "Birim Fiyat", "Tutar", "Ödeme", "Not"]
    df["KG"] = df["KG"].apply(lambda x: f"{x:.2f}" if x else "---")
    df["Birim Fiyat"] = df["Birim Fiyat"].apply(lambda x: f"{x:.2f}" if x else "---")
    df["Tutar"] = df["Tutar"].apply(lambda x: f"{x:,.2f} ₺")

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### ✏️ Kayıt Düzenle / Sil")

    kayit_id = st.number_input("Düzenlenecek Kayıt ID", min_value=1, step=1, format="%d")
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM sevkiyatlar WHERE id=?", (int(kayit_id),))
    secili = cur.fetchone(); conn.close()

    if secili:
        musteriler = tum_musteriler()
        is_tahsilat = secili["urun"] == "TAHSİLAT"

        ec1, ec2 = st.columns(2)
        with ec1:
            e_tarih = st.text_input("Tarih", value=secili["tarih"], key="edit_tarih")
            e_bayi_idx = musteriler.index(secili["bayi"]) if secili["bayi"] in musteriler else 0
            e_bayi = st.selectbox("Bayi", musteriler, index=e_bayi_idx, key="edit_bayi")
            if not is_tahsilat:
                e_urun_idx = URUN_LISTESI.index(secili["urun"]) if secili["urun"] in URUN_LISTESI else 0
                e_urun = st.selectbox("Ürün", URUN_LISTESI, index=e_urun_idx, key="edit_urun")
            else:
                st.info("Bu kayıt TAHSİLAT")
        with ec2:
            if not is_tahsilat:
                e_miktar = st.number_input("Miktar", value=float(secili["miktar"] or 0), step=0.5, format="%.2f", key="edit_miktar")
                e_fiyat = st.number_input("Birim Fiyat", value=float(secili["birim_fiyat"] or 0), step=0.5, format="%.2f", key="edit_fiyat")
            e_tutar = st.number_input("Tutar", value=float(secili["toplam_tutar"] or 0), step=0.5, format="%.2f", key="edit_tutar",
                                       disabled=not is_tahsilat)
            e_odeme_idx = ODEME_TIPLERI.index(secili["odeme_tipi"]) if secili["odeme_tipi"] in ODEME_TIPLERI else 0
            e_odeme = st.selectbox("Ödeme", ODEME_TIPLERI, index=e_odeme_idx, key="edit_odeme")
            e_not = st.text_input("Not", value=secili["aciklama"] or "", key="edit_not")

        col_guncelle, col_sil = st.columns(2)
        with col_guncelle:
            if st.button("✅ GÜNCELLE", use_container_width=True):
                conn = get_db(); cur = conn.cursor()
                if is_tahsilat:
                    cur.execute("""UPDATE sevkiyatlar SET tarih=?, bayi=?, toplam_tutar=?, aciklama=?, odeme_tipi=? WHERE id=?""",
                                (e_tarih, e_bayi, e_tutar, e_not, e_odeme, int(kayit_id)))
                else:
                    cur.execute("""UPDATE sevkiyatlar SET tarih=?, bayi=?, urun=?, miktar=?, birim_fiyat=?, toplam_tutar=?, aciklama=?, odeme_tipi=? WHERE id=?""",
                                (e_tarih, e_bayi, e_urun, e_miktar, e_fiyat, e_miktar*e_fiyat, e_not, e_odeme, int(kayit_id)))
                conn.commit(); conn.close()
                st.success("Kayıt güncellendi!"); st.rerun()
        with col_sil:
            if st.button("🗑️ SİL", use_container_width=True, type="secondary"):
                conn = get_db(); cur = conn.cursor()
                cur.execute("DELETE FROM sevkiyatlar WHERE id=?", (int(kayit_id),))
                conn.commit(); conn.close()
                st.success("Kayıt silindi!"); st.rerun()

# ---------------------------------------------------------
# SAYFA: MÜŞTERİ YÖNETİMİ
# ---------------------------------------------------------
def sayfa_musteri():
    st.markdown("# 👥 MÜŞTERİ YÖNETİMİ")

    left, right = st.columns([1, 2])

    with left:
        st.markdown("**Yeni Müşteri Ekle**")
        mus_ad = st.text_input("Müşteri Adı")
        kdv = st.selectbox("KDV Durumu", ["Dahil", "Hariç"])
        if st.button("KAYDET", use_container_width=True):
            if mus_ad.strip():
                conn = get_db(); cur = conn.cursor()
                try:
                    cur.execute("INSERT INTO musteriler (ad, kdv_durum) VALUES (?, ?)", (mus_ad.strip(), kdv))
                    conn.commit(); st.success(f"✓ {mus_ad} eklendi!")
                except Exception as e:
                    st.error(f"Hata: {e}")
                conn.close(); st.rerun()

        st.markdown("---")
        st.markdown("**Excel'den Toplu Yükle**")
        uploaded = st.file_uploader("Excel dosyası (.xlsx)", type=["xlsx"])
        if uploaded:
            df = pd.read_excel(uploaded, header=None); conn = get_db(); cur = conn.cursor(); e = 0
            for _, row in df.iterrows():
                if str(row[0]) != 'nan':
                    try:
                        cur.execute("INSERT INTO musteriler (ad, kdv_durum) VALUES (?, 'Dahil')", (str(row[0]).strip(),)); e += 1
                    except: pass
            conn.commit(); conn.close(); st.success(f"✓ {e} müşteri eklendi!"); st.rerun()

    with right:
        st.markdown("**Müşteri Listesi**")
        ara = st.text_input("Ara", "", placeholder="Müşteri adı ara...")
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT ad, kdv_durum FROM musteriler ORDER BY ad ASC")
        mus_list = cur.fetchall(); conn.close()
        if ara:
            mus_list = [m for m in mus_list if tr_lower(ara) in tr_lower(m[0])]

        if mus_list:
            df_mus = pd.DataFrame(mus_list, columns=["Müşteri Adı", "KDV"])
            st.dataframe(df_mus, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("**Müşteri Düzenle / Sil**")
        musteriler = tum_musteriler()
        if musteriler:
            sec_mus = st.selectbox("Müşteri Seç", musteriler)
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT kdv_durum FROM musteriler WHERE ad=?", (sec_mus,))
            kdv_r = cur.fetchone(); conn.close()
            eski_kdv = kdv_r[0] if kdv_r else "Dahil"

            yeni_ad = st.text_input("Yeni Ad", value=sec_mus)
            yeni_kdv = st.selectbox("KDV", ["Dahil", "Hariç"], index=0 if eski_kdv == "Dahil" else 1)

            st.markdown("**Bu Müşterinin Ürün Fiyatları**")
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT urun_ad, fiyat FROM fiyatlar WHERE musteri_ad=? ORDER BY urun_ad", (sec_mus,))
            fiyatlar = cur.fetchall(); conn.close()
            if fiyatlar:
                df_fiyat = pd.DataFrame(fiyatlar, columns=["Ürün", "Fiyat (TL)"])
                df_fiyat["Fiyat (TL)"] = df_fiyat["Fiyat (TL)"].apply(lambda x: f"{x:.2f}")
                st.dataframe(df_fiyat, use_container_width=True, hide_index=True)

            st.markdown("**Fiyat Tanımla**")
            fp1, fp2, fp3 = st.columns(3)
            with fp1:
                fiyat_urun = st.selectbox("Ürün", URUN_LISTESI, key="f_urun")
            with fp2:
                fiyat_deger = st.number_input("Fiyat", min_value=0.0, step=0.5, format="%.2f", key="f_deger")
            with fp3:
                if st.button("Fiyat Kaydet", use_container_width=True):
                    conn = get_db(); cur = conn.cursor()
                    cur.execute("""INSERT OR REPLACE INTO fiyatlar (id, musteri_ad, urun_ad, fiyat)
                                   VALUES ((SELECT id FROM fiyatlar WHERE musteri_ad=? AND urun_ad=?), ?, ?, ?)""",
                                (sec_mus, fiyat_urun, sec_mus, fiyat_urun, fiyat_deger))
                    conn.commit(); conn.close(); st.success("Fiyat kaydedildi!"); st.rerun()

            gu1, gu2 = st.columns(2)
            with gu1:
                if st.button("GÜNCELLE", use_container_width=True):
                    conn = get_db(); cur = conn.cursor()
                    cur.execute("UPDATE musteriler SET ad=?, kdv_durum=? WHERE ad=?", (yeni_ad, yeni_kdv, sec_mus))
                    if yeni_ad != sec_mus:
                        cur.execute("UPDATE sevkiyatlar SET bayi=? WHERE bayi=?", (yeni_ad, sec_mus))
                        cur.execute("UPDATE fiyatlar SET musteri_ad=? WHERE musteri_ad=?", (yeni_ad, sec_mus))
                    conn.commit(); conn.close(); st.success("Güncellendi!"); st.rerun()
            with gu2:
                if st.button("SİL", use_container_width=True, type="secondary"):
                    conn = get_db(); cur = conn.cursor()
                    cur.execute("DELETE FROM musteriler WHERE ad=?", (sec_mus,))
                    conn.commit(); conn.close(); st.success("Silindi!"); st.rerun()

# ---------------------------------------------------------
# SAYFA: TAHSİLAT GİRİŞİ
# ---------------------------------------------------------
def sayfa_tahsilat_giris():
    st.markdown("# 💸 TAHSİLAT GİRİŞİ")
    musteriler = tum_musteriler()

    col1, col2 = st.columns([2, 1])
    with col1:
        t_tarih = st.text_input("Tarih", value=st.session_state.calisma_tarihi)
        t_bayi = st.selectbox("Müşteri", ["-- Seçin --"] + musteriler)
        t_tutar = st.number_input("Tutar (TL)", min_value=0.0, step=0.5, format="%.2f")
        st.markdown("**Ödeme Tipi**")
        t_cols = st.columns(4)
        for i, tip in enumerate(ODEME_TIPLERI):
            with t_cols[i]:
                if st.button(tip, use_container_width=True, key=f"tah_tip_{i}",
                             type="primary" if st.session_state.secili_tahsilat_tipi == tip else "secondary"):
                    st.session_state.secili_tahsilat_tipi = tip; st.rerun()
        t_not = st.text_input("Not", "")

        if st.button("💾 TAHSİLAT KAYDET", use_container_width=True, type="primary"):
            if t_bayi == "-- Seçin --":
                st.error("Müşteri seçin!")
            elif t_tutar <= 0:
                st.error("Tutar girin!")
            else:
                conn = get_db(); cur = conn.cursor()
                cur.execute("""INSERT INTO sevkiyatlar (tarih, bayi, urun, miktar, birim_fiyat, toplam_tutar, aciklama, odeme_tipi)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (t_tarih, t_bayi, "TAHSİLAT", 0, 0, t_tutar, t_not, st.session_state.secili_tahsilat_tipi))
                conn.commit(); conn.close()
                st.success(f"✓ {t_bayi} hesabına {t_tutar:,.2f} ₺ tahsilat eklendi!"); st.rerun()

    with col2:
        st.markdown(f"**Seçili Ödeme:** `{st.session_state.secili_tahsilat_tipi}`")
        if t_bayi != "-- Seçin --":
            ay_kg, ay_tl, yil_kg, yil_tl = bayi_istatistik(t_bayi)
            conn = get_db(); cur = conn.cursor()
            cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE bayi=? AND urun='TAHSİLAT'", (t_bayi,))
            tah_r = cur.fetchone(); conn.close()
            toplam_tah = tah_r[0] or 0
            st.markdown(f"""
            <div class="card">
            <div class="card-title">{t_bayi}</div>
            <div class="sub-text">Bu Ay Sevkiyat</div>
            <div style="font-size:18px;font-family:'IBM Plex Mono',monospace;color:#F6E05E;">{ay_tl:,.0f} ₺</div>
            <div class="sub-text" style="margin-top:8px;">Toplam Tahsilat</div>
            <div style="font-size:18px;font-family:'IBM Plex Mono',monospace;color:#9AE6B4;">{toplam_tah:,.0f} ₺</div>
            <div class="sub-text" style="margin-top:8px;">Tahmini Bakiye</div>
            <div style="font-size:20px;font-family:'IBM Plex Mono',monospace;font-weight:700;color:#FC8181;">{yil_tl - toplam_tah:,.0f} ₺</div>
            </div>
            """, unsafe_allow_html=True)

# ---------------------------------------------------------
# SAYFA: TAHSİLAT RAPORU
# ---------------------------------------------------------
def sayfa_tahsilat_rapor():
    st.markdown("# 💰 TAHSİLAT RAPORU")

    bas_def, bit_def = bu_ay_aralik()
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: bas = st.text_input("Başlangıç", value=bas_def)
    with c2: bit = st.text_input("Bitiş", value=bit_def)
    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("HESAPLA", use_container_width=True):
            pass  # re-runs automatically

    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT odeme_tipi, SUM(toplam_tutar) FROM sevkiyatlar WHERE tarih >= ? AND tarih <= ? GROUP BY odeme_tipi", (bas, bit))
    veriler = dict(cur.fetchall()); conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 NAKİT", f"{veriler.get('Nakit', 0):,.2f} ₺")
    c2.metric("💳 POS", f"{veriler.get('POS', 0):,.2f} ₺")
    c3.metric("🏦 HESAP", f"{veriler.get('Hesaba', 0):,.2f} ₺")
    c4.metric("📋 VERESİYE", f"{veriler.get('Veresiye', 0):,.2f} ₺")

    toplam = sum(veriler.values())
    st.markdown(f'<div class="big-number" style="margin-top:24px;">GENEL CİRO: {toplam:,.2f} ₺</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Müşteri Bazlı Bakiye")
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT DISTINCT bayi FROM sevkiyatlar ORDER BY bayi")
    bayiler = [r[0] for r in cur.fetchall()]; conn.close()

    rows = []
    for b in bayiler:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE bayi=? AND urun != 'TAHSİLAT'", (b,))
        s = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(toplam_tutar) FROM sevkiyatlar WHERE bayi=? AND urun = 'TAHSİLAT'", (b,))
        t = cur.fetchone()[0] or 0
        conn.close()
        if s > 0 or t > 0:
            rows.append({"Müşteri": b, "Toplam Satış": f"{s:,.0f} ₺", "Tahsilat": f"{t:,.0f} ₺", "Bakiye": f"{s-t:,.0f} ₺"})

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# SAYFA: ANALİZLER
# ---------------------------------------------------------
def sayfa_analiz():
    st.markdown("# 📈 PERFORMANS ANALİZİ")

    bugun = datetime.now()
    bu_bas = bugun.replace(day=1).strftime("%Y-%m-%d")
    gecen_son = (bugun.replace(day=1) - timedelta(days=1))
    gec_bas = gecen_son.replace(day=1).strftime("%Y-%m-%d")
    gec_son = gecen_son.strftime("%Y-%m-%d")
    bu_son, _ = bu_ay_aralik(); bu_son = bu_son  # reuse

    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT ad FROM musteriler")
    musteriler = [r[0] for r in cur.fetchall()]; conn.close()

    veriler = []
    for m in musteriler:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT SUM(miktar) FROM sevkiyatlar WHERE bayi=? AND tarih BETWEEN ? AND ? AND urun != 'TAHSİLAT'", (m, gec_bas, gec_son))
        g = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(miktar) FROM sevkiyatlar WHERE bayi=? AND tarih >= ? AND urun != 'TAHSİLAT'", (m, bu_bas))
        b = cur.fetchone()[0] or 0
        conn.close()
        if g == 0 and b == 0: continue
        fark = b - g
        pct = ((b - g) / g) * 100 if g > 0 else (100 if b > 0 else 0)
        veriler.append({"Müşteri": m, "Geçen Ay (KG)": f"{g:.1f}", "Bu Ay (KG)": f"{b:.1f}", "Fark": f"{fark:.1f}", "Değişim %": f"{pct:.1f}%", "_fark": fark})

    dusus = [v for v in veriler if v["_fark"] < 0]
    yukselis = [v for v in veriler if v["_fark"] >= 0]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📉 Düşenler (Alarm)")
        if dusus:
            df = pd.DataFrame(dusus).drop(columns=["_fark"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Düşen müşteri yok!")

    with col2:
        st.markdown("### 📈 Yükselenler (Yıldızlar)")
        if yukselis:
            df = pd.DataFrame(yukselis).drop(columns=["_fark"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Yükselen müşteri yok!")

# ---------------------------------------------------------
# ANA UYGULAMA
# ---------------------------------------------------------
def main():
    st.set_page_config(
        page_title="Mantı Takip v34",
        page_icon="🥟",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_css()
    db_setup()
    init_session()

    if not st.session_state.authenticated:
        sayfa_giris()
        return

    # Yedek thread'i başlat (arkaplanda sessizce çalışır)
    yedek_thread_baslat()

    # Sidebar navigasyon
    with st.sidebar:
        st.markdown("""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:700;color:#F6E05E;padding:16px 0 8px 0;">
        🥟 MANTI TAKİP
        </div>
        <div style="font-size:11px;color:#718096;font-family:'IBM Plex Mono',monospace;margin-bottom:20px;">
        v34 · Üretim Sistemi
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f'<div style="font-size:11px;color:#A0AEC0;margin-bottom:16px;">📅 Aktif Tarih: <b style="color:#F6E05E;">{st.session_state.calisma_tarihi}</b></div>', unsafe_allow_html=True)

        sayfalar = [
            "Dashboard",
            "Sevkiyat Girişi",
            "Raporlar",
            "Müşteri Yönetimi",
            "Tahsilat Girişi",
            "Tahsilat Raporu",
            "Analizler",
        ]
        secim = st.radio("", sayfalar,
                         index=sayfalar.index(st.session_state.aktif_sayfa) if st.session_state.aktif_sayfa in sayfalar else 0,
                         label_visibility="collapsed")
        st.session_state.aktif_sayfa = secim

        st.markdown("---")
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state.authenticated = False; st.rerun()

        st.markdown("---")
        st.markdown('<div style="font-size:11px;color:#718096;margin-bottom:6px;">💾 Yedek Sistemi</div>', unsafe_allow_html=True)
        if st.button("📧 Şimdi Yedek Gönder", use_container_width=True):
            with st.spinner("Gönderiliyor..."):
                ok = yedek_mail_gonder()
            if ok:
                st.success("✅ Yedek gönderildi!")
            else:
                st.error("❌ Hata! ENV ayarlarını kontrol edin.")

    # Sayfa yönlendirmesi
    page = st.session_state.aktif_sayfa
    if page == "Dashboard": sayfa_dashboard()
    elif page == "Sevkiyat Girişi": sayfa_sevkiyat()
    elif page == "Raporlar": sayfa_rapor()
    elif page == "Müşteri Yönetimi": sayfa_musteri()
    elif page == "Tahsilat Girişi": sayfa_tahsilat_giris()
    elif page == "Tahsilat Raporu": sayfa_tahsilat_rapor()
    elif page == "Analizler": sayfa_analiz()

if __name__ == "__main__":
    main()
