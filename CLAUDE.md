# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Kararsızım — Proje Planı ve Claude Code Yönergesi

## Çalışma Notları (koddan doğrulanmış; plan bölümleri aşağıda)

**Durum:** Faz 0–4 tamam (iskelet, custom User, üyelik, anketler, oylama + sonuçlar, tasarım cilası). Supabase projesi `kararsizim` (ref `oyifgrcakokndgaxbmxd`, eu-central-1) açık, migration'lar uygulandı ve tüm `public` tablolarında RLS açık (policy yok, bilerek). Her yeni migration'dan sonra yeni tablolarda RLS açılmalı. Faz 5 (Vercel deploy) henüz başlamadı.

**Komutlar** (Windows; venv Python 3.14, Django 5.2 LTS; linter/formatter yapılandırılmamış):
```bash
.venv/Scripts/python.exe manage.py runserver
.venv/Scripts/python.exe manage.py test                       # tüm testler
.venv/Scripts/python.exe manage.py test accounts.tests.UserModelTests.test_create_superuser   # tek test
.venv/Scripts/python.exe manage.py makemigrations && .venv/Scripts/python.exe manage.py migrate
```

**Ortam / ayarlar (`config/settings.py`):**
- `SECRET_KEY` zorunlu, yoksa `ImproperlyConfigured` fırlatır. Yeni makinede `.env.example` → `.env` kopyala (`.env` gitignore'da, `DEBUG` varsayılanı `False`).
- `DATABASE_URL` yoksa SQLite (`db.sqlite3`). Varsa Supabase transaction pooler ayarları otomatik uygulanır (`CONN_MAX_AGE=0`, `DISABLE_SERVER_SIDE_CURSORS`, `prepare_threshold=None`). Migration'ı direct/session pooler'dan çalıştırmak için `.env`'de `USE_DIRECT_DB=1` ve `DIRECT_DATABASE_URL` ver.
- Statik dosyalar WhiteNoise ile (`CompressedStaticFilesStorage`, manifest yok); `STATICFILES_DIRS=static/`, `STATIC_ROOT=staticfiles/`.

**Mimari notlar:**
- `accounts.User`: `USERNAME_FIELD="email"`. E-posta `UserManager.normalize_email` ve `save()` ile küçük harfe çevrilir; kullanıcı adı benzersizliği büyük/küçük harf duyarsızdır (`UniqueConstraint(Lower("username"))` — `unique=True` ile birlikte). Yeni kayıt yolu eklerken e-posta normalizasyonunu bypass etme (`objects.create_user` ya da `save()` kullan; `bulk_create` normalize etmez).
- `polls`: `Poll`, `Option`, `Vote` (`UniqueConstraint(user, poll)`; oy `update_or_create` ile verilir/değiştirilir). `vote` view'ı POST-only; ziyaretçiyi `redirect_to_login(detay_url)` ile girişe yollar, seçenek `poll.options` içinden aranır (başka anketin seçeneği reddedilir). Sonuçlar (`vote_count`, `percent`, `is_winner`, `voters`) `views._poll_queryset()` + `_decorate_poll()` ile hesaplanır; `Count` ile annotate edilen sorgularda Django `Meta.ordering`'i yok saydığı için sıralama her yerde açıkça verilir. Ana akışta `?sirala=populer` = en çok oy alan. Anket formu (`PollForm`) seçenekleri tekrarlayan `option` girdilerinden `self.data.getlist("option")` ile okur; 2–5 / tekrar / 80 karakter kuralları `clean()` içinde, böylece JS kapalıyken de geçerli. Kayıt `transaction.atomic()` içinde. Ana akış `poll_list` URL adı `home` (LOGIN_REDIRECT_URL vb. buna bağlı). Sayfalama `?sayfa=`.
- Arayüz: tek `static/css/main.css` (tasarım değişkenleri `:root`'ta; `--text-muted` AA kontrastı için plandaki #7A7491'den biraz koyu). Sonuç barı animasyonu saf CSS (`@keyframes bar-grow`, genişlik inline style'dan). `static/js/main.js` Django mesajlarını alt toast'a çevirip kaybolur; JS kapalıysa şerit olarak kalır. 404/403 `base.html`'i extend eder, `500.html` bilerek bağımsızdır (istek context'i yok).
- Çift gönderim koruması: anket formu GET'te `submission_token` (uuid) üretir, `Poll.submission_token` benzersizdir; aynı kodla gelen ikinci istek yeni anket açmaz, mevcut ankete yönlendirir (`PollForm.save` → `(poll, created)`). `main.js` ayrıca tüm POST formlarını tek seferlik kilitler. Yeni "oluştur" formlarında aynı deseni kullan.
- `manage.py test` her zaman SQLite kullanır (settings'te `sys.argv` kontrolü); `.env`'de Supabase olsa bile test gerçek veritabanına dokunmaz.
- Supabase `public` şemasındaki tablolarda RLS kapalıysa anon key ile REST üzerinden okunabilir; yeni tablolar migrate edildikten sonra RLS açılmalı (Django `postgres` rolüyle bağlandığı için etkilenmez).

---

> Bu dosya, **Kararsızım** web uygulamasının tüm detaylarını ve Claude Code ile adım adım geliştirme planını içerir.
> Kullanım önerisi: Bu dosyayı proje köküne `CLAUDE.md` adıyla koy (Claude Code her oturumda otomatik okur). Sonra her fazı, bu dosyanın sonundaki **"Faz Promptları"** bölümündeki hazır promptlarla **tek tek** başlat. Bir faz bitip test edilmeden diğerine geçme.

---

## 1. Proje Özeti

**Proje adı:** Kararsızım
**Amaç:** Kullanıcıların kararsız kaldıkları konularda (ör. "Bugün sinemaya mı gitsem, restorana mı?") anket açıp topluluğa danışabildiği basit bir sosyal anket platformu.

**Temel kurallar:**
- Her anketin **en az 2, en fazla 5** seçeneği vardır.
- **Takip mekanizması yoktur.** Herkes tüm anketleri ve tüm oyları görür (tek, ortak bir akış).
- **Üye olmayanlar** anketleri ve sonuçları görüntüleyebilir.
- **Anket oluşturmak** ve **oy vermek** için üyelik gerekir.
- Kayıtta **e-posta, kullanıcı adı ve parola** alınır.
- Anketlerde ve oylarda **yalnızca kullanıcı adı** görünür; **e-posta asla hiçbir sayfada gösterilmez.**

**Hedef:** Önce çalışan, sade bir **prototip**. Karmaşık teknolojilerden kaçınılacak; sonra adım adım geliştirilecek.

---

## 2. Teknoloji Yığını

| Katman | Teknoloji | Not |
|---|---|---|
| Backend | Python 3.12 + Django 5.x | Django'nun hazır auth, ORM, form, admin özellikleri kullanılacak |
| Veritabanı | Supabase (PostgreSQL) | Yalnızca **Postgres veritabanı** olarak kullanılır. Supabase Auth **kullanılmaz**, kimlik doğrulama Django'da yapılır |
| Frontend | Saf HTML + CSS + JavaScript | Django template'leri ile. Framework yok (React/Vue/Tailwind yok) |
| Statik dosyalar | WhiteNoise | Vercel'de statik dosya servisi için |
| Deployment | Vercel (Python runtime) | Serverless; Django WSGI uygulaması olarak |
| Ortam değişkenleri | `python-dotenv` (lokal), Vercel Environment Variables (prod) | |
| DB bağlantısı | `dj-database-url` + `psycopg[binary]` | `DATABASE_URL` tek değişkenle |

**Bilinçli olarak KULLANILMAYACAKLAR (prototip için):** Django REST Framework, Celery, Redis, Docker, frontend framework'leri, CSS framework'leri, Supabase JS client.

### `requirements.txt` (başlangıç)
```
Django>=5.0,<6.0
psycopg[binary]
dj-database-url
python-dotenv
whitenoise
```

---

## 3. Kritik Teknik Kararlar (Claude Code bunlara uymalı)

1. **Kimlik doğrulama Django'da.** Custom user model proje başında (ilk migration'dan önce) tanımlanacak. Sonradan değiştirmek zordur.
2. **Giriş e-posta + parola ile** yapılır. Kullanıcı adı yalnızca görünen isimdir (benzersiz).
3. **Supabase bağlantısı:** Vercel serverless olduğu için Supabase'in **connection pooler** adresi kullanılacak (Transaction mode, port `6543`). Bu modda:
   - `CONN_MAX_AGE = 0`
   - `DISABLE_SERVER_SIDE_CURSORS = True` (DATABASES ayarında)
   - Migration'ları lokalde çalıştırırken gerekirse **direct connection** (port `5432`) veya Session pooler kullanılabilir. İki URL'yi de `.env` içinde tut: `DATABASE_URL` (pooler) ve `DIRECT_DATABASE_URL` (migration için, opsiyonel).
4. **Lokal geliştirmede** `DATABASE_URL` yoksa SQLite'a düş (hızlı başlangıç için). Ama Faz 0 bitmeden Supabase bağlantısı da test edilmeli.
5. **Session'lar veritabanında** (Django varsayılanı) tutulur; serverless ortamda dosya/bellek tabanlı session kullanılmaz.
6. **Gizli bilgiler koda yazılmaz.** `SECRET_KEY`, `DATABASE_URL`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` ortam değişkeninden okunur. `.env` dosyası `.gitignore`'da olmalı; `.env.example` repoda bulunmalı.
7. **E-posta gizliliği:** Hiçbir template'te `user.email` render edilmez. Kullanıcıya ait gösterimlerde her zaman `user.username` kullanılır. Bunu doğrulayan bir test yazılacak.
8. **Arayüz dili Türkçe**, kod (değişken, fonksiyon, model adları) **İngilizce**. `LANGUAGE_CODE = "tr"`, `TIME_ZONE = "Europe/Istanbul"`.
9. Kod sade, okunabilir ve küçük parçalar halinde olacak. Her faz sonunda uygulama çalışır durumda olmalı.

---

## 4. Proje Yapısı (hedef)

```
kararsizim/
├── CLAUDE.md                 # bu dosya
├── manage.py
├── requirements.txt
├── vercel.json
├── build_files.sh            # (gerekirse) collectstatic için
├── .env.example
├── .gitignore
├── config/                   # Django proje ayarları
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/                 # kullanıcı, kayıt, giriş
│   ├── models.py             # custom User
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   └── tests.py
├── polls/                    # anket, seçenek, oy
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── tests.py
├── templates/
│   ├── base.html
│   ├── partials/             # navbar, poll_card, messages vb.
│   ├── accounts/
│   └── polls/
└── static/
    ├── css/
    │   └── main.css
    ├── js/
    │   ├── create-poll.js    # seçenek ekle/çıkar
    │   └── main.js
    └── img/
```

---

## 5. Veri Modeli

### 5.1 `accounts.User` (AbstractUser'dan türetilir)
| Alan | Tip | Kural |
|---|---|---|
| `email` | EmailField | **unique**, zorunlu, giriş için kullanılır, **asla gösterilmez** |
| `username` | CharField(30) | **unique**, zorunlu, 3–30 karakter, yalnızca harf/rakam/`_`/`.` |
| `password` | (Django) | Django parola doğrulayıcıları aktif |
| `date_joined` | (Django) | |

- `USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = ["username"]`
- Kullanıcı adı karşılaştırması **büyük/küçük harf duyarsız** benzersiz olmalı (`Ahmet` ve `ahmet` aynı anda olamaz). E-posta da küçük harfe normalize edilir.
- Custom `UserManager` (create_user / create_superuser e-posta ile).

### 5.2 `polls.Poll`
| Alan | Tip | Kural |
|---|---|---|
| `author` | FK → User | `on_delete=CASCADE`, `related_name="polls"` |
| `question` | CharField(150) | zorunlu, ör. "Bu akşam ne yapsam?" |
| `description` | TextField(max 500) | opsiyonel, kısa bağlam |
| `created_at` | DateTimeField | `auto_now_add` |

- `Meta.ordering = ["-created_at"]`
- Yardımcı: `total_votes` (annotate ile hesaplanır, alan olarak tutulmaz).

### 5.3 `polls.Option`
| Alan | Tip | Kural |
|---|---|---|
| `poll` | FK → Poll | `CASCADE`, `related_name="options"` |
| `text` | CharField(80) | zorunlu |
| `order` | PositiveSmallIntegerField | gösterim sırası |

- Bir ankette **2–5 seçenek** olmalı (form seviyesinde doğrulanır).
- Aynı ankette **tekrarlanan seçenek metni** olamaz (büyük/küçük harf ve baştaki/sondaki boşluk yok sayılarak).

### 5.4 `polls.Vote`
| Alan | Tip | Kural |
|---|---|---|
| `user` | FK → User | `CASCADE`, `related_name="votes"` |
| `poll` | FK → Poll | `CASCADE`, `related_name="votes"` |
| `option` | FK → Option | `CASCADE`, `related_name="votes"` |
| `created_at` | DateTimeField | `auto_now_add` |
| `updated_at` | DateTimeField | `auto_now` |

- `UniqueConstraint(fields=["user", "poll"])` → **her kullanıcı bir ankete tek oy**.
- Kullanıcı oyunu **değiştirebilir** (update_or_create). Oy geri çekme prototipte yok.
- `option.poll == poll` olduğu view'da doğrulanmalı (başka anketin seçeneğine oy verilemez).
- Kullanıcı **kendi anketine de oy verebilir** (basitlik için; istenirse sonra kapatılır).

---

## 6. Yetki Matrisi

| İşlem | Ziyaretçi | Üye | Anket sahibi |
|---|---|---|---|
| Anket akışını görme | ✅ | ✅ | ✅ |
| Anket detayı + sonuçlar | ✅ | ✅ | ✅ |
| Kimin neye oy verdiğini görme (kullanıcı adı) | ✅ | ✅ | ✅ |
| Kullanıcı profil sayfası (anketleri) | ✅ | ✅ | ✅ |
| Oy verme / oy değiştirme | ❌ → giriş sayfasına yönlendir (`?next=`) | ✅ | ✅ |
| Anket oluşturma | ❌ → giriş sayfasına yönlendir | ✅ | ✅ |
| Anket silme | ❌ | ❌ | ✅ (yalnızca kendi anketi) |
| Anket düzenleme | — | — | ❌ prototipte yok (oylar bozulmasın diye) |

Ziyaretçi bir ankette oy butonunu gördüğünde butonlar pasif değil, tıklanınca "Oy vermek için giriş yap" mesajıyla giriş sayfasına gider ve giriş sonrası aynı ankete geri döner.

---

## 7. Sayfalar ve URL'ler

| URL | View | Açıklama |
|---|---|---|
| `/` | `poll_list` | Ana akış. Tüm anketler, en yeni üstte. Sıralama sekmeleri: **En yeni** / **En çok oy alan**. Sayfa başına 20 anket (pagination) |
| `/anket/yeni/` | `poll_create` | Anket oluşturma formu (login gerekli) |
| `/anket/<int:pk>/` | `poll_detail` | Soru, açıklama, seçenekler, oy formu, sonuç barları, oy verenlerin kullanıcı adları |
| `/anket/<int:pk>/oy/` | `vote` | **Yalnızca POST.** Oy ver/değiştir, sonra detaya redirect |
| `/anket/<int:pk>/sil/` | `poll_delete` | GET: onay sayfası, POST: sil. Yalnızca sahibi |
| `/u/<username>/` | `user_profile` | Kullanıcının açtığı anketler + toplam anket sayısı. **E-posta yok.** Takip butonu yok |
| `/kayit/` | `register` | Kayıt formu |
| `/giris/` | `login` | E-posta + parola ile giriş |
| `/cikis/` | `logout` | **POST** ile çıkış |
| `/admin/` | Django admin | Geliştirici kullanımı |

### 7.1 Ana akış — anket kartı içeriği
- Kullanıcı adı (`@kullaniciadi`, profile link) + göreli zaman ("3 saat önce" — `naturaltime` / `timesince`)
- Soru (büyük, kalın)
- Seçenekler kısa önizleme (ilk 2–3 seçenek, sonucu ince barla)
- Toplam oy sayısı
- Kart tıklanınca detaya gider
- Giriş yapmış kullanıcı oy verdiyse kartta küçük bir "✓ Oy verdin" rozeti

### 7.2 Anket detay sayfası
- **Oy formu:** Seçenekler büyük, tıklanabilir "pill/kart" butonlar (radio input + stilli label). Kullanıcının mevcut oyu seçili görünür; farklı seçeneğe tıklayıp "Oyumu güncelle" diyebilir.
- **Sonuçlar herkese her zaman açık** (oy vermeden de görülür):
  - Her seçenek için yüzde barı + oy sayısı + yüzde
  - En çok oy alan seçenek vurgulu (ör. 👑 veya farklı renk)
  - Toplam oy sayısı
- **Kim neye oy verdi:** Her seçeneğin altında açılır/kapanır listede oy veren kullanıcı adları (`@ahmet`, `@zeynep`...). (Takip yok, sadece şeffaflık.)
- Anket sahibine "Sil" butonu.

### 7.3 Anket oluşturma formu
- Soru (zorunlu, max 150, karakter sayacı)
- Açıklama (opsiyonel, max 500)
- Seçenekler: varsayılan **2 boş alan**. "+ Seçenek ekle" butonu (5'e ulaşınca gizlenir/pasif olur). Her seçeneğin yanında "×" kaldır butonu (2'nin altına düşülemez).
- JS ile dinamik ekleme/çıkarma (`static/js/create-poll.js`). **Doğrulama sunucu tarafında da** yapılır (JS kapalıysa da kurallar geçerli).
- Basit uygulama yöntemi: formda `option_1` … `option_5` alanları, JS bunları göster/gizle yapar; ya da Django `formset` (min_num=2, max_num=5, validate_min/validate_max). Prototip için hangisi daha sadeyse o.
- Kaydetme `transaction.atomic()` içinde (anket + seçenekler birlikte).

### 7.4 Kayıt / Giriş
- Kayıt: kullanıcı adı, e-posta, parola, parola tekrar. Hata mesajları Türkçe ve alan altında.
- Kayıt sonrası otomatik giriş ve ana sayfaya yönlendirme + "Hoş geldin @kullaniciadi!" mesajı.
- Giriş: e-posta + parola. `?next=` parametresine saygı.
- E-posta doğrulama, şifre sıfırlama: **prototipte yok** (Faz 6+).

---

## 8. Tasarım Sistemi

**Hedef his:** Genç, modern, temiz, soft. Açık arka plan; canlı renkler ama üstüne beyaz/pastel ton eklenmiş (yumuşatılmış). Bol boşluk, yuvarlak köşeler, yumuşak gölgeler, hafif mikro animasyonlar.

### 8.1 Renk paleti (CSS değişkenleri — `:root`)
```css
:root {
  /* Zemin */
  --bg:            #FAF7FF;   /* çok açık lila-beyaz */
  --surface:       #FFFFFF;   /* kartlar */
  --surface-soft:  #F3EEFF;   /* ikincil yüzey, input arka planı */
  --border:        #ECE6F7;

  /* Metin */
  --text:          #2A2540;   /* koyu mürdüm, saf siyah değil */
  --text-muted:    #7A7491;

  /* Ana renkler (canlı ama yumuşatılmış) */
  --primary:       #7C5CFF;   /* lavanta mor */
  --primary-soft:  #E9E3FF;
  --pink:          #FF7EB6;
  --pink-soft:     #FFE4F0;
  --mint:          #3DD9A4;
  --mint-soft:     #DDF8EE;
  --sun:           #FFC857;
  --sun-soft:      #FFF3D6;
  --sky:           #5CC8FF;
  --sky-soft:      #DFF4FF;

  /* Durum */
  --danger:        #FF5C7A;
  --success:       #2EC892;

  /* Biçim */
  --radius-sm: 10px;
  --radius:    16px;
  --radius-lg: 24px;
  --shadow:    0 6px 24px rgba(124, 92, 255, 0.08);
  --shadow-hover: 0 10px 32px rgba(124, 92, 255, 0.14);
  --gradient:  linear-gradient(135deg, #7C5CFF 0%, #FF7EB6 100%);
}
```
- **Seçenek renkleri:** 5 seçenek sırayla `primary, pink, mint, sun, sky` renklerini alır (bar dolgusu = ana renk, bar zemini = `-soft` versiyonu).
- Birincil butonlar `--gradient` dolgulu, beyaz yazı, `border-radius: 999px` (pill).

### 8.2 Tipografi
- Font: **"Plus Jakarta Sans"** (Google Fonts), yedek: `system-ui, sans-serif`.
- Ağırlıklar: 400 (gövde), 600 (etiket), 800 (başlık).
- Taban boyut 16px; anket sorusu 1.25–1.5rem, sayfa başlığı 2rem.

### 8.3 Bileşenler
- **Navbar:** beyaz, yapışkan (sticky), hafif alt gölge. Solda logo "kararsızım" (gradyan metin + küçük 🤔 veya ⚖️ ikon). Sağda: ziyaretçiye "Giriş yap" (metin) + "Kayıt ol" (gradyan pill); üyeye "+ Anket aç" (gradyan pill) + `@kullaniciadi` + "Çıkış".
- **Anket kartı:** `--surface`, `--radius-lg`, `--shadow`, 20–24px padding; hover'da 2px yukarı kalkar + `--shadow-hover`.
- **Seçenek butonu (oy verirken):** `--surface-soft` zemin, seçilince ilgili renkte kenarlık + soft dolgu + ✓ ikonu.
- **Sonuç barı:** 10–12px yükseklik, yuvarlak; genişlik yüzdeyle, sayfa yüklenince 0'dan hedefe `transition` ile dolar.
- **Input'lar:** `--surface-soft` zemin, kenarlıksız/ince kenarlık, focus'ta `--primary` halka (`box-shadow: 0 0 0 3px var(--primary-soft)`).
- **Mesajlar (Django messages):** üstte toast/şerit, success = mint-soft, error = pink-soft, birkaç saniye sonra JS ile kaybolur.
- **Boş durum:** Hiç anket yoksa sevimli boş durum: "Henüz kimse kararsız değil 🤷 İlk anketi sen aç!" + buton.
- Emojiler ölçülü kullanılabilir (genç ve samimi ton).

### 8.4 Düzen ve erişilebilirlik
- **Mobil öncelikli** (mobile-first). Akış tek kolon, max genişlik ~680px, ortalı.
- 360px telefon genişliğinde yatay kaydırma olmamalı.
- Renk kontrastı okunabilir olmalı (metin her zaman `--text` veya beyaz-üstü-gradyan).
- Form elemanlarının `label`'ları olmalı; butonlar klavye ile kullanılabilir; `:focus-visible` stilleri var.
- `prefers-reduced-motion` açıksa animasyonlar kapatılır.

### 8.5 Metin tonu (mikro kopya)
Samimi, genç, kısa. Örnekler:
- Ana başlık: "Kararsız mısın? Topluluğa sor."
- Anket oluştur butonu: "Kararımı sor 🚀"
- Oy butonu: "Oyumu ver" / "Oyumu güncelle"
- Oy sonrası mesaj: "Oyun kaydedildi, sağ ol! 💜"
- Giriş gerektiğinde: "Oy vermek için önce giriş yapmalısın."

---

## 9. Güvenlik ve Doğrulama Kontrol Listesi
- [ ] Tüm POST formlarında CSRF token
- [ ] Oy ve silme yalnızca POST
- [ ] `@login_required` (anket oluştur, oy, sil)
- [ ] Silmede sahiplik kontrolü (başkasınınkinde 403/404)
- [ ] Oyda `option.poll_id == poll.id` kontrolü
- [ ] Seçenek sayısı 2–5, boş/tekrarlı seçenek yok (sunucu tarafı)
- [ ] Template otomatik escape (|safe kullanılmayacak)
- [ ] E-posta hiçbir sayfada görünmüyor (test ile)
- [ ] Prod'da `DEBUG=False`, `SECURE_*` ayarları, `CSRF_TRUSTED_ORIGINS` Vercel domainini içeriyor
- [ ] `.env` repoya girmiyor

---

## 10. Test Stratejisi (Django `TestCase`)
Her fazda o fazın testleri yazılır ve `python manage.py test` geçmeden faz bitmiş sayılmaz. Minimum testler:
- Kayıt: geçerli kayıt; tekrarlı e-posta; tekrarlı kullanıcı adı (büyük/küçük harf farklı da olsa).
- Giriş e-posta ile çalışıyor.
- Ziyaretçi akışı ve detayı görebiliyor; anket oluşturamıyor, oy veremiyor (giriş sayfasına yönleniyor).
- Anket oluşturma: 1 seçenek → hata; 6 seçenek → hata; tekrarlı seçenek → hata; 2–5 → başarılı.
- Oy: ilk oy oluşur; ikinci oy günceller (toplam oy sayısı artmaz); başka anketin seçeneğiyle oy reddedilir.
- Silme: sahibi silebilir; başkası silemez.
- **Gizlilik:** Akış, detay ve profil sayfalarının HTML'inde kullanıcının e-postası geçmiyor.

---

## 11. Geliştirme Fazları

### Faz 0 — Proje iskeleti ve veritabanı bağlantısı
- Sanal ortam, `requirements.txt`, Django projesi (`config`), `accounts` ve `polls` app'leri.
- `settings.py`: ortam değişkenleri, `LANGUAGE_CODE="tr"`, `TIME_ZONE="Europe/Istanbul"`, templates/static dizinleri, WhiteNoise, `dj-database-url` (yoksa SQLite'a düş), Supabase pooler için gerekli ayarlar.
- **Custom User modeli** (e-posta ile giriş, benzersiz kullanıcı adı) + manager — **ilk migrate'den önce**.
- `.env.example`, `.gitignore`, temel `base.html` (henüz sade).
- Supabase'e migrate edilip bağlantının çalıştığı doğrulanır; `createsuperuser` ile admin'e giriş.
- **Bitti sayılması için:** `runserver` çalışıyor, admin'e giriş yapılıyor, tablolar Supabase'de görünüyor.

### Faz 1 — Üyelik (kayıt / giriş / çıkış)
- Kayıt formu (kullanıcı adı, e-posta, parola x2) ve doğrulamalar.
- E-posta ile giriş, POST ile çıkış, `?next=` desteği.
- Navbar'da giriş durumuna göre linkler, Django messages gösterimi.
- Basit ama düzgün görünen form sayfaları (tam tasarım Faz 4'te).
- Testler.

### Faz 2 — Anket oluşturma ve listeleme
- `Poll`, `Option` modelleri + admin kaydı.
- Anket oluşturma formu (2–5 seçenek, JS ile ekle/çıkar, sunucu doğrulaması, atomic kayıt).
- Ana akış (en yeni üstte, pagination) ve anket detay sayfası (henüz oylamasız).
- Kullanıcı profil sayfası `/u/<username>/`.
- Anket silme (sahibi).
- Testler.

### Faz 3 — Oylama ve sonuçlar
- `Vote` modeli (user+poll unique).
- Oy verme / değiştirme view'ı (POST), ziyaretçi yönlendirmesi.
- Detayda sonuç barları, yüzdeler, toplam oy, kazanan vurgusu, seçenek başına oy veren kullanıcı adları.
- Akışta kart üzerinde mini sonuç ve "✓ Oy verdin" rozeti; "En çok oy alan" sıralaması.
- Sorgu verimliliği: `annotate(Count(...))`, `prefetch_related("options")`, N+1 sorgudan kaçın.
- Testler (gizlilik testi dahil).

### Faz 4 — Arayüz ve deneyim cilası
- Bölüm 8'deki tasarım sistemini eksiksiz uygula (`main.css` içinde CSS değişkenleri).
- Kart hover efektleri, bar dolma animasyonu, seçenek butonu seçili durumları, toast mesajlar, boş durumlar, karakter sayacı.
- Mobil uyum ve erişilebilirlik kontrolü; `prefers-reduced-motion`.
- Favicon ve sayfa başlıkları (`<title>Anket sorusu · Kararsızım</title>`).
- 404 ve 500 sayfaları markaya uygun.

### Faz 5 — Vercel'e deployment
- `vercel.json` ve WSGI giriş noktası (Vercel'in Python/Django için **güncel** dokümantasyonunu kontrol et; yapılandırma zamanla değişebiliyor).
- Statik dosyalar: `collectstatic` + WhiteNoise (gerekirse `build_files.sh`).
- Vercel Environment Variables: `SECRET_KEY`, `DATABASE_URL` (Supabase pooler, 6543), `DEBUG=False`, `ALLOWED_HOSTS` (`.vercel.app` + varsa domain), `CSRF_TRUSTED_ORIGINS` (`https://<proje>.vercel.app`).
- Migration'lar lokalden prod veritabanına çalıştırılır (Vercel build sırasında migrate çalıştırma).
- Prod güvenlik ayarları: `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
- Canlıda uçtan uca test: kayıt → anket aç → başka hesapla oy ver → sonuçları ziyaretçi olarak gör.
- README: lokal kurulum ve deploy adımları.

### Faz 6+ — Sonraki adımlar (prototip sonrası, şimdilik YAPMA)
- Şifre sıfırlama ve e-posta doğrulama
- Anket bitiş süresi (ör. 24 saat sonra kapanır) ve "Karar verildi" etiketi
- Kategori/etiketler (yemek, eğlence, alışveriş...) ve filtreleme
- Arama
- Anket paylaşım linki + Open Graph önizlemesi
- Oy verme işleminin sayfa yenilemeden (fetch) yapılması
- Hız sınırlama (spam/anket seli önleme), uygunsuz içerik bildirimi
- Seçeneklere görsel ekleme
- Karanlık mod

---

## 12. Claude Code'a Genel Çalışma Kuralları
- Yalnızca **istenen fazı** uygula; sonraki fazlara ait özellikleri ekleme.
- Faza başlamadan önce kısa bir plan çıkar, sonra uygula.
- Yeni bağımlılık eklemeden önce gerçekten gerekli mi düşün; gerekiyorsa `requirements.txt`'e ekle ve nedenini belirt.
- Her faz sonunda: migration'ları oluştur, testleri çalıştır, nasıl manuel test edileceğini kısaca yaz.
- Belirsiz bir nokta olursa bu dosyadaki kurallara uy; dosyada yoksa en basit çözümü seç ve bunu belirt.
- Kullanıcıya görünen tüm metinler Türkçe; kod ve yorumlar İngilizce (veya sade Türkçe yorum olabilir).

---

## 13. Faz Promptları (Claude Code'a sırayla yapıştır)

**Faz 0:**
```
CLAUDE.md dosyasını oku. Sadece "Faz 0 — Proje iskeleti ve veritabanı bağlantısı" kısmını uygula.
Custom User modelini ilk migrate'den önce oluştur. Supabase bağlantısı için .env.example hazırla
ve hangi değerleri nereden alacağımı adım adım anlat. Bitince lokalde çalıştırma ve doğrulama adımlarını yaz.
```

**Faz 1:**
```
CLAUDE.md'ye göre Faz 1'i (üyelik: kayıt, e-posta ile giriş, çıkış) uygula.
Kullanıcı adı ve e-posta büyük/küçük harf duyarsız benzersiz olsun. Bölüm 10'daki ilgili testleri yaz ve çalıştır.
```

**Faz 2:**
```
CLAUDE.md'ye göre Faz 2'yi uygula: Poll ve Option modelleri, 2-5 seçenekli anket oluşturma
(JS ile seçenek ekle/çıkar + sunucu doğrulaması), ana akış, detay sayfası, profil sayfası ve anket silme.
Oylama henüz yok. Testleri yaz ve çalıştır.
```

**Faz 3:**
```
CLAUDE.md'ye göre Faz 3'ü uygula: Vote modeli (kullanıcı başına ankete tek oy, değiştirilebilir),
oy verme view'ı, sonuç barları, yüzdeler, oy veren kullanıcı adları ve "En çok oy alan" sıralaması.
N+1 sorgulardan kaçın. Gizlilik testi dahil testleri yaz ve çalıştır.
```

**Faz 4:**
```
CLAUDE.md Bölüm 8'deki tasarım sistemini tüm sayfalara eksiksiz uygula (Faz 4).
Mobil öncelikli, açık arka planlı, soft ve canlı renkli; hover/animasyon/boş durum/toast detaylarını ekle.
Yeni bir CSS/JS framework kullanma.
```

**Faz 5:**
```
CLAUDE.md'ye göre Faz 5'i uygula: projeyi Vercel'e deploy edilebilir hale getir.
Önce Vercel'in güncel Python/Django dokümantasyonunu kontrol et. vercel.json, statik dosyalar (WhiteNoise),
prod güvenlik ayarları ve README'yi hazırla. Vercel'e girmem gereken ortam değişkenlerini ve
migration'ları prod veritabanına nasıl uygulayacağımı adım adım yaz.
```
