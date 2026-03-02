# 🥟 Mantı Takip v34 — Railway Kurulum Kılavuzu

## ⚠️ ÖNEMLİ NOT: Veritabanı Kalıcılığı
Railway'in ücretsiz planında **dosya sistemi geçici**dir — uygulama yeniden başlatıldığında `.db` dosyası silinebilir.
Bu sorunu çözmek için **Railway Volume** (kalıcı disk) eklemeniz gerekir (aşağıda açıklandı).

---

## 📋 ADIM ADIM KURULUM

### ADIM 1 — GitHub'a Yükleyin

1. [github.com](https://github.com) adresine gidin ve ücretsiz hesap açın
2. **New repository** butonuna tıklayın
3. Repo adı: `manti-takip` → **Create repository**
4. Bilgisayarınızda **Git Bash** veya terminal açın:

```bash
cd manti_takip_klasoru   # Bu dosyaların bulunduğu klasör

git init
git add .
git commit -m "ilk kurulum"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADINIZ/manti-takip.git
git push -u origin main
```

---

### ADIM 2 — Railway Hesabı Açın

1. [railway.app](https://railway.app) adresine gidin
2. **GitHub ile giriş** yapın (üstteki GitHub hesabınızla)

---

### ADIM 3 — Projeyi Deploy Edin

1. Railway dashboard'da **New Project** tıklayın
2. **Deploy from GitHub repo** seçin
3. `manti-takip` reposunu seçin
4. Railway otomatik olarak `requirements.txt` ve `Procfile` okuyacak, kurulumu başlatacak
5. 2-3 dakika bekleyin — yeşil "Active" yazısı görünce hazır

---

### ADIM 4 — Kalıcı Veritabanı Ekleme (KRİTİK!)

Veritabanınızın silinmemesi için Volume eklemeniz şart:

1. Railway projenizde servisinize tıklayın
2. **Volumes** sekmesine gidin
3. **Add Volume** tıklayın
4. Mount Path: `/app` yazın (veya uygulamanın çalıştığı dizin)
5. Kaydedin

> 💡 Volume eklendikten sonra `manti_takip_v34.db` dosyası bu dizinde kalıcı olarak saklanır.

---

### ADIM 5 — URL Alın

1. Railway'de servisinize tıklayın
2. **Settings** → **Domains** bölümüne gidin
3. **Generate Domain** tıklayın
4. Size `.railway.app` uzantılı bir URL verilecek
5. Bu URL'yi browser'da açın → uygulamanız çalışıyor!

---

## 🔐 GİRİŞ BİLGİLERİ

```
Kullanıcı Adı : PATRON
Şifre         : 13451098618
```

---

## 🔄 Güncelleme Nasıl Yapılır?

`app.py`'de değişiklik yaptıktan sonra:

```bash
git add .
git commit -m "guncelleme"
git push
```

Railway otomatik olarak yeniden deploy eder.

---

## 💰 Railway Fiyatlandırma

- **Hobby Plan**: $5/ay — Volume dahil, 512 MB RAM, sürekli çalışır
- **Free Plan**: Aylık 500 saat, Volume yok (veritabanı sıfırlanır)

**Tavsiye: Hobby Plan alın** — veritabanınız güvende olur.

---

## 📁 Dosya Yapısı

```
manti_takip/
├── app.py              ← Ana uygulama
├── requirements.txt    ← Python paketleri
├── Procfile            ← Başlatma komutu
├── railway.json        ← Railway ayarları
├── .streamlit/
│   └── config.toml    ← Streamlit görsel ayarları
└── .gitignore          ← Git hariç tutulacaklar
```
