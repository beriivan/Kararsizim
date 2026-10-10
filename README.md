# Kararsızım

Kararsız kaldığın konularda anket açıp topluluğa danıştığın basit bir sosyal anket platformu.
Üye olmayanlar anketleri ve sonuçları görür; anket açmak ve oy vermek için üyelik gerekir.
E-posta adresleri hiçbir sayfada gösterilmez, yalnızca kullanıcı adı görünür.

**Teknoloji:** Python + Django 5.2, Supabase (yalnızca PostgreSQL), saf HTML/CSS/JS, WhiteNoise, Vercel.

Ayrıntılı plan, veri modeli ve tasarım kararları için [CLAUDE.md](CLAUDE.md) dosyasına bak.

---

## Yerelde çalıştırma

Gereksinim: Python 3.12 veya üstü (3.14 ile de denendi).

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
cp .env.example .env                                           # sonra .env'i düzenle
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py createsuperuser             # isteğe bağlı, /admin/ için
.venv/Scripts/python.exe manage.py runserver
```

Uygulama `http://127.0.0.1:8000/` adresinde açılır.

`.env` içinde en az şunlar olmalı:

```
SECRET_KEY=...        # python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
DEBUG=True
```

`DATABASE_URL` boşsa yerel SQLite (`db.sqlite3`) kullanılır. Supabase için aşağıya bak.

### Testler

```bash
.venv/Scripts/python.exe manage.py test                                  # hepsi
.venv/Scripts/python.exe manage.py test polls.tests.VoteTests            # tek sınıf
```

Testler her zaman geçici bir SQLite veritabanı kullanır; `.env`'de Supabase olsa bile gerçek veriye dokunmaz.

---

## Supabase (veritabanı)

Supabase yalnızca Postgres olarak kullanılır; kimlik doğrulama Django'dadır.

1. Supabase'te proje aç, veritabanı şifreni kaydet.
2. Projede **Connect** → **Connection string → URI** bölümünden iki adres al:
   - **Transaction pooler** (port `6543`) → `DATABASE_URL` (uygulama ve Vercel bunu kullanır)
   - **Session pooler** (port `5432`) → `DIRECT_DATABASE_URL` (yalnızca migration için)
3. `.env` içine yaz ve migration'ı direct adresten çalıştır:

```
DATABASE_URL=postgresql://postgres.<proje-ref>:<ŞİFRE>@aws-1-<bölge>.pooler.supabase.com:6543/postgres
DIRECT_DATABASE_URL=postgresql://postgres.<proje-ref>:<ŞİFRE>@aws-1-<bölge>.pooler.supabase.com:5432/postgres
USE_DIRECT_DB=1
```

> `USE_DIRECT_DB=1` iken uygulama `DIRECT_DATABASE_URL`'i kullanır. Vercel'de bu değişkeni **koyma**.

### Yeni tabloda RLS (önemli)

Django tabloları Supabase'in `public` şemasında oluşur. RLS kapalıysa anon key ile REST üzerinden
okunabilirler (e-posta ve parola özetleri dahil). Her yeni `migrate` sonrası yeni tablolarda RLS'i aç:

```sql
ALTER TABLE "public"."<tablo_adi>" ENABLE ROW LEVEL SECURITY;
```

Policy yazmana gerek yok. Django tabloların sahibi `postgres` rolüyle bağlandığı için etkilenmez.

---

## Vercel'e deploy

Vercel, Django'yu `config/settings.py` içindeki `WSGI_APPLICATION` üzerinden kendiliğinden bulur
(ayrı `vercel.json` gerekmez). Python sürümü `.python-version` dosyasından okunur (`3.12`).

1. Kodu GitHub'a gönder.
2. [vercel.com/new](https://vercel.com/new) üzerinden GitHub reposunu içe aktar. Framework olarak Django algılanmalı.
3. **Environment Variables** bölümüne şunları ekle (Production için):

| Değişken | Değer |
|---|---|
| `SECRET_KEY` | Yeni, rastgele bir anahtar. Yerelde kullandığını **kullanma**. |
| `DATABASE_URL` | Supabase **Transaction pooler** adresi (`:6543`, şifre dahil) |
| `DEBUG` | `False` |

   İsteğe bağlı: kendi alan adın varsa `ALLOWED_HOSTS` (ör. `kararsizim.com`) ve
   `CSRF_TRUSTED_ORIGINS` (ör. `https://kararsizim.com`). `*.vercel.app` adresleri
   Vercel'in sistem değişkenlerinden (`VERCEL_URL` vb.) otomatik tanınır.
   `USE_DIRECT_DB` ve `DIRECT_DATABASE_URL` eklenmez.

4. **Deploy** et.

### Migration'lar

Vercel build sırasında migration **çalıştırılmaz**. Şemayı değiştirdiğinde migration'ı kendi bilgisayarından,
`.env`'deki Supabase bilgileriyle çalıştır:

```bash
.venv/Scripts/python.exe manage.py migrate
```

Sonra yeni tablolarda RLS'i aç (yukarıya bak), ardından kodu push'la.

### Canlı doğrulama

1. Canlı adreste kayıt ol.
2. Anket aç.
3. Başka bir hesapla (ya da gizli pencerede ikinci bir kayıtla) oy ver.
4. Çıkış yapıp ziyaretçi olarak sonuçları gör.
5. Hiçbir sayfada e-posta adresinin görünmediğini kontrol et.

### Sorun giderme

- **`DisallowedHost` / 400:** Alan adı `ALLOWED_HOSTS`'ta yok. Özel alan adı kullanıyorsan ekle.
- **`CSRF verification failed`:** Alan adı `CSRF_TRUSTED_ORIGINS`'te yok (`https://` ile birlikte).
- **Statik dosyalar yüklenmiyor:** WhiteNoise dosyaları `static/` klasöründen kendisi bulur; `static/` klasörünün repoda olduğundan emin ol.
- **Veritabanına bağlanamıyor:** `DATABASE_URL`'in transaction pooler (`:6543`) olduğunu ve şifrede özel karakter (`@ # / :`) bulunmadığını kontrol et.
- **Supabase projesi duraklatılmış:** Ücretsiz planda 7 gün kullanılmazsa proje durur; panelden yeniden başlat.

### Demo verisi

Ekran görüntüsü/deneme için işaretli demo kullanıcılar ve oylar ekleyebilirsin
(e-postaları `@demo.invalid` ile biter, parolaları yoktur, kimse giriş yapamaz):

```bash
.venv/Scripts/python.exe manage.py demo_data add      # ekle
.venv/Scripts/python.exe manage.py demo_data remove   # sil (oylarıyla birlikte)
```

> Canlıya almadan önce `demo_data remove` çalıştır, yoksa gerçek ziyaretçiler sahte oyları görür.

---

## Yapı

```
config/     Django ayarları, URL'ler, WSGI
accounts/   Özel kullanıcı modeli (e-posta ile giriş), kayıt/giriş/çıkış
polls/      Anket, seçenek, oy; akış, detay, profil, silme
templates/  base.html, partials/, accounts/, polls/, 404/403/500
static/     css/main.css, js/create-poll.js, js/main.js, img/favicon.svg
```
