# Solar Monitor — Geliştirme ve Düzeltme Önerisi

> İnceleme tarihi: 2026-07-17
> Kapsam: Tüm çekirdek modüller (panel, collector, veritabanı, API, auth, Docker), sayfalar, testler ve CI.

Genel değerlendirme: Proje işlevsel olarak zengin (çoklu fabrika, async Modbus, TimescaleDB, REST+WS API, Prometheus/Grafana, hava durumu korelasyonu) ve mimari kararların çoğu isabetli. Ancak SQLite → PostgreSQL geçişinin artıkları, sessiz veri kaybına yol açabilecek bir saklama (retention) çelişkisi, API'de fabrika parametresi eksikleri ve bakımı zorlaştıran dosya kirliliği var. Aşağıdaki maddeler önem sırasına göre gruplandı.

---

## ✅ UYGULAMA DURUMU (2026-07-20 güncellemesi)

Kritik veri-kaybı ve altyapı düzeltmeleri uygulandı ve canlı sistemde doğrulandı:

- **1.1 Retention çelişkisi** — DÜZELTİLDİ. Canlı DB'de 30 gün → 365 gün; kod her açılışta `retention_policy_senkronize()` ile ayarlardan senkronize ediyor. 3 günlük pencerede canlı doğrulandı (11 Haziran verisi hâlâ duruyor).
- **1.2 Continuous aggregate** — DÜZELTİLDİ (not: view aslında *mevcuttu*, ilk teşhisim yanlıştı). DDL artık autocommit blokunda; `WITH NO DATA` + `if_not_exists` ile güvenli.
- **1.3 None-bağlantı kontrolleri** — tüm veritabani.py fonksiyonlarına eklendi.
- **1.4 / 1.5 / 1.6 API** — fabrika parametreleri, datetime→str, 117–122 alarmları — DÜZELTİLDİ, gerçek isteklerle test edildi.
- **2.1 Sabit '1444' şifresi** — kaldırıldı, rol tabanlı erişime bağlandı.
- **2.3 / 2.4 Compose güvenliği** — PG portu localhost'a alındı, pgdata mount'u yalnız postgres'e.
- **4.1 (kısmi)** — `veritabani-ARGETEST.py` üretim düzeltmesi ana dosyaya taşındı, kopya silindi.
- **5.2 Healthcheck** — veri-tazeliği kontrollü yeniden yazıldı; restart döngüsü giderildi; negatif test ile doğrulandı.
- **6.3 Otomatik yedekleme** — `backup.sh` + `solar-backup` servisi eklendi (günlük pg_dump, 14 gün rotasyon). Test-restore ile geri yüklenebilirliği kanıtlandı.
- **6.5 Timezone** — PostgreSQL Europe/Istanbul'a alındı; ~3 saatlik `NOW()` kayması giderildi.

> ⚠️ **Olay kaydı:** Saatlik özet elle tazelenirken `refresh_continuous_aggregate(..., NULL, NULL)` kullanıldı; bu, ham verisi retention tarafından zaten silinmiş olan 1–11 Haziran aralığının **saatlik özet satırlarını da geri dönülemez sildi**. Ders: continuous aggregate tazelemesi HER ZAMAN açık bir zaman penceresiyle çağrılmalı, asla `NULL, NULL` ile. Bu olay otomatik yedekleme (6.3) ihtiyacını doğruladı.

---

## 1. KRİTİK — Veri kaybı ve sessiz hatalar

### 1.1 TimescaleDB 30 gün retention ↔ `veri_saklama_gun=365` çelişkisi
**Dosya:** `veritabani.py:101`

```python
cursor.execute("SELECT add_retention_policy('olcumler', INTERVAL '30 days');")
```

Ayarlar tablosunda `veri_saklama_gun` varsayılanı **365 gün**, collector da buna göre temizlik yapıyor. Ama `init_db()` her çalıştığında TimescaleDB'ye **30 günlük** bir retention policy eklemeye çalışıyor. Policy bir kez eklendiyse, kullanıcı 365 gün sakladığını sanırken Timescale 30 günden eski her şeyi **sessizce siliyor**. Yıllık üretim raporları ve `7_TAHMIN`/`8_KARSILASTIR` sayfaları için geçmiş veri yok olur.

**Öneri:**
- Retention süresini tek kaynaktan yönet: `veri_saklama_gun` ayarını okuyup `add_retention_policy(..., INTERVAL '<gun> days')` olarak uygula; ayar değişince `remove_retention_policy` + yeniden ekle.
- Mevcut kurulumda aktif policy'yi kontrol et: `SELECT * FROM timescaledb_information.jobs WHERE proc_name='policy_retention';`

### 1.2 Continuous aggregate büyük olasılıkla hiç oluşmuyor
**Dosya:** `veritabani.py:79-93`

`CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)` TimescaleDB'de **transaction içinde çalıştırılamaz**. psycopg2 varsayılan olarak implicit transaction açtığı için bu ifade her `init_db()` çağrısında hata verip `except` bloğuna düşüyor; `olcumler_saatlik` view'u muhtemelen hiç oluşmadı. Sonuç: `saatlik_ozet_getir()` her zaman `[]` dönüyor ve uzun tarihli raporlar (PDF, günlük rapor) ham tablodan yavaş sorgularla ya da eksik veriyle çalışıyor.

**Öneri:**
```python
conn.autocommit = True   # sadece bu DDL bloğu için
cursor.execute("CREATE MATERIALIZED VIEW IF NOT EXISTS olcumler_saatlik WITH (timescaledb.continuous) AS ... WITH NO DATA;")
conn.autocommit = False
```
Ayrıca hata mesajını yutmak yerine en az bir kez `logger.error` ile görünür kılın. Kurulum sonrası `\d olcumler_saatlik` ile doğrulayın.

### 1.3 `get_db_connection()` None dönebiliyor ama çoğu fonksiyon kontrol etmiyor
**Dosya:** `veritabani.py` — `init_db` (satır 37), `tum_cihazlarin_son_durumu` (450), `db_temizle`, `eski_verileri_temizle`, `veritabani_istatistikleri`, `tarih_araliginda_ortalamalar`, `gunluk_uretim_hesapla`, `hata_sayilarini_getir`

Bağlantı kurulamazsa fonksiyon `None` dönüyor, ardından `conn.cursor()` → `AttributeError`. Panel fragment'ları içinde bu, kullanıcıya kırmızı exception olarak yansır; API'de 500 üretir. `son_verileri_getir` ve `veri_ekle`'de kontrol var, diğerlerinde yok — tutarsız.

**Öneri:** Tek bir `with db_conn() as cur:` context manager'ı yazıp tüm fonksiyonlarda kullanın (aşağıda 3.1'deki havuz önerisiyle birleştirilebilir).

### 1.4 API'de `fabrika` parametresi eksik olan endpointler
**Dosya:** `api.py:303` ve `api.py:377`

`/api/v1/devices/{id}/history` ve `/api/v1/production/range` endpointleri `veritabani.tarih_araliginda_ortalamalar(...)`'ı **fabrika parametresi olmadan** çağırıyor; fonksiyon varsayılan olarak `"mekanik"`e düşüyor. Üretim fabrikasının geçmiş verisi API üzerinden **hiç alınamıyor** (CRM entegrasyonunu doğrudan etkiler).

**Öneri:** Diğer endpointlerdeki gibi `fabrika: str = Query("mekanik")` ekleyip fonksiyona iletin.

### 1.5 `/devices/{id}/latest` muhtemel 500 hatası (datetime → str)
**Dosya:** `api.py:262` + `veritabani.py:398-416`

`son_verileri_getir` ham `datetime` nesnesi dönüyor (`tum_cihazlarin_son_durumu`'ndaki gibi `str()` çevirimi yok). `DeviceData.zaman: str` alanına `datetime` verildiğinde Pydantic v2 tip zorlaması yapmaz → ValidationError → 500. (FastAPI ≥0.100 requirements'ta, yani Pydantic v2 kurulması muhtemel.)

**Öneri:** `zaman=str(row[0])` yapın ya da modeli `zaman: datetime` olarak tanımlayın. Endpoint'i bir kez gerçek istekle test edin.

### 1.6 `/api/v1/alarms` yalnızca 107–116 registerlarını tarıyor
**Dosya:** `api.py:408-411`

`hata_isimleri` listesi index 12'de (`hata_116`) bitiyor; 117–122 registerlarındaki alarmlar API'den görünmüyor. Panel 13 register'ın hepsini işlerken API eksik rapor veriyor.

---

## 2. GÜVENLİK

### 2.1 Kodda sabit ayar şifresi: `"1444"`
**Dosya:** `1_PANEL.py:613`

Ayarlar bölümünün 4 haneli şifresi kaynak kodda düz metin. Repo'ya erişen herkes görür; ayrıca gerçek bir güvenlik katmanı değil (auth zaten var).

**Öneri:** Bu ikinci şifreyi tamamen kaldırıp bölümü `user_role == "admin"` koşuluna bağlayın (rol altyapısı zaten mevcut). İlla ayrı PIN istenirse `.env`'den okuyun.

### 2.2 Varsayılan parolalar zinciri
- `veritabani.py:12` → `POSTGRES_PASSWORD` yoksa `"solar_pass_2026"`
- `auth.py:93` → `AUTH_PASSWORD_HASH` yoksa varsayılan şifre `"admin"`
- `config.py:80` → `MQTT_PASSWORD` varsayılanı `"solar_secure"`

**Öneri:** Prod modunda (örn. `ENV=production`) varsayılan parola ile açılmayı reddedin — Grafana için compose'da zaten yaptığınız `:?` zorunlu-değişken kalıbını (`docker-compose.yml:135`) Postgres ve auth için de uygulayın.

### 2.3 PostgreSQL portu tüm ağa açık
**Dosya:** `docker-compose.yml:36-37`

`"5432:5432"` host'un tüm arayüzlerine bağlanıyor; fabrika ağındaki herkes varsayılan parolayla DB'ye erişebilir. Konteynerler arası erişim için port publish etmeye gerek yok.

**Öneri:** Satırı tamamen kaldırın; dışarıdan pgAdmin erişimi gerekiyorsa `"127.0.0.1:5432:5432"` yapın.

### 2.4 `pgdata` volume'u tüm uygulama konteynerlerine mount ediliyor
**Dosya:** `docker-compose.yml:24` (x-common)

`pgdata:/var/lib/postgresql/data` ortak şablonda olduğu için panel/collector/api/healthcheck konteynerlerinin hepsi Postgres'in ham veri dizinini görüyor. Gereksiz ve riskli (yanlış bir script veri dizinini bozabilir).

**Öneri:** `pgdata` satırını x-common'dan çıkarın; yalnızca `solar-postgres` servisinde kalsın.

### 2.5 CORS: `allow_origins=["*"]` + `allow_credentials=True`
**Dosya:** `api.py:66-73`

Bu kombinasyon spec'e aykırı (tarayıcılar `*` + credentials'ı reddeder) ve niyet belirsiz. `CRM_ALLOWED_ORIGIN` set edilmezse her origin'e açılıyor.

**Öneri:** Credentials gerekmediği için `allow_credentials=False` yapın; origin'i zorunlu kılın.

### 2.6 API anahtarı query string'te
**Dosya:** `api.py:83` (`api_key` query paramı) ve `/live?api_key=...`

Query parametreleri proxy/access loglarına ve tarayıcı geçmişine yazılır. WS dashboard için pratik ama sızıntı kanalı.

**Öneri:** Query desteğini yalnızca `/live` için bırakıp dokümante edin ya da kısa ömürlü ayrı bir dashboard token'ı kullanın; diğer tüm endpointlerde yalnız `X-API-Key` kabul edin.

### 2.7 Login arka planı üçüncü taraf siteden yükleniyor
**Dosya:** `auth.py:202`, `1_PANEL.py:52`

`sp.sanayigazetesi.com.tr` üzerindeki görsele hard bağımlılık: kapalı fabrika ağında görsel gelmez, ayrıca her login'de dış siteye istek gider (bilgi sızıntısı sayılmasa da gereksiz iz).

**Öneri:** Görselleri `static/` altına indirip oradan servis edin.

### 2.8 Küçük auth iyileştirmeleri
- `auth.py:271` kullanıcı adı/hash karşılaştırmasında `hmac.compare_digest` kullanın.
- Rate-limit anahtarı `X-Forwarded-For`'a dayanıyor (`auth.py:49`) — spoof edilebilir; reverse proxy yoksa header'a güvenmeyin.
- Oturum süresi (session expiry) yok; `authenticated` state sekme açık kaldıkça sonsuz geçerli. Basit bir `login_time` + timeout kontrolü ekleyin.

---

## 3. PERFORMANS

### 3.1 Bağlantı havuzu yok — her sorgu yeni TCP + auth
**Dosya:** `veritabani.py:6-26` (tüm fonksiyonlar)

Her fonksiyon `psycopg2.connect()` ile sıfırdan bağlantı açıp kapatıyor. Panel bir fragment yenilemesinde onlarca kez bağlanıyor.

**Öneri:** `psycopg2.pool.ThreadedConnectionPool` (min 1, max 10) + context manager:
```python
@contextmanager
def db_conn():
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        _pool.putconn(conn)
```
1.3'teki None-kontrol sorununu da aynı yerde çözer.

### 3.2 "Son 7 gün üretim" tablosu: cihaz sayısı × 7 × 2 sorgu
**Dosya:** `1_PANEL.py:419-449`

Her cihaz için 7 gün ayrı ayrı `gunluk_uretim_hesapla` çağrılıyor; bu fonksiyon da içeride ayrıca `tum_ayarlari_oku` ile ikinci bir bağlantı açıyor. 8 cihazda fragment başına **~120 bağlantı/sorgu**, her 30 saniyede bir.

**Öneri:** Tek sorguya indirin:
```sql
SELECT slave_id, date_trunc('day', zaman) AS gun,
       MAX(modbus_uretim) AS uretim, AVG(guc) AS ort_guc, COUNT(*) AS n
FROM olcumler
WHERE fabrika_id = %s AND zaman >= NOW() - INTERVAL '7 days'
GROUP BY slave_id, gun;
```
ve sonucu `@st.cache_data(ttl=300)` ile önbelleğe alın (geçmiş günler zaten değişmez).

### 3.3 Tanımlı cache helper kullanılmıyor
**Dosya:** `1_PANEL.py:102-105` vs `1_PANEL.py:461`

`_fetch_device_data` (30 sn cache'li) tanımlanmış ama `render_tek_cihaz_grafikleri` doğrudan `veritabani.son_verileri_getir(sel_id, limit=2880, ...)` çağırıyor — her yenilemede 2880 satır çekiliyor.

**Öneri:** Helper'ı kullanın; ayrıca grafikte yalnız bugünkü aralık gösterildiği için sorguya `WHERE zaman >= CURRENT_DATE` koşulu ekleyip satır sayısını düşürün.

### 3.4 Raporlar continuous aggregate kullanmalı
1.2 düzeltilince `1_GUNLUK_RAPOR`, `6_PDF_RAPOR` ve `8_KARSILASTIR` uzun aralıklarda `olcumler_saatlik`'ten okumalı; `saatlik_ozet_getir` fonksiyonu hazır ama view yoksa boşuna var.

---

## 4. MİMARİ / KOD SAĞLIĞI

### 4.1 Depo kirliliği — tek seferlik scriptler ve kopya dosyalar
Kökte artık işlevi kalmamış dosyalar birikmiş:

- **Tek seferlik dönüştürme scriptleri:** `_fix_emoji.py`, `add_top_nav.py`, `move_sidebar.py`, `remove_sidebar.py`, `replace_colors.py`, `strip_brackets.py`, `swap_db_ids.py`, `fix_mekanik.py`, `apply_addr_patch.py`, `scratch.py`, `scratch2.py`
- **Eski sürümler:** `collector.py` (README "async ana collector" diyor), `Izleme_Paneli.py` (eski giriş sayfası)
- **Kopya:** `veritabani-ARGETEST.py` — git'e ekli değil ama içinde **ana dosyada olmayan gerçek bir düzeltme var** (`MAX(CASE WHEN guc > 0 THEN modbus_uretim ELSE 0 END)` — cihaz kapalıyken gelen sahte üretim değerini eliyor). Bu fix `veritabani.py`'ye taşınmalı, kopya silinmeli.

**Öneri:** Düzeltmeyi birleştirin; tarihi değeri olan scriptleri `archive/` klasörüne taşıyın ya da silin (git geçmişinde zaten duruyorlar).

### 4.2 "uretim" fabrikası ID 1↔2 takas hack'i
**Dosya:** `collector_async.py:376-382`

Sahadaki kablolama/adres uyuşmazlığı kodun içine gömülmüş. Yeni cihaz eklendiğinde ya da adresleme düzeldiğinde unutulup yanlış cihaza veri yazılır.

**Öneri:** Ayarlar tablosuna fabrika bazlı `id_mapping` (örn. `{"1":2,"2":1}`) ekleyin; collector bunu okusun. Boşsa birebir eşleme.

### 4.3 Varsayılan register adresleri üç yerde üç farklı değer
- `veritabani.py:155-158`: guc=70, volt=71, akim=72, isi=73
- `collector_config.py:95-98`: guc=75, volt=73, akim=70, isi=44
- `1_PANEL.py:712-754`: guc=75, volt=73, akim=70, isi=93

DB'de kayıt varsa sorun çıkmıyor ama temiz kurulumda hangi adresin geçerli olacağı belirsiz.

**Öneri:** Varsayılanları tek bir sabite (`collector_config.DEFAULTS`) toplayın; diğer iki yer oradan import etsin.

### 4.4 Index tabanlı tuple erişimi ve padding hack'i
`1_PANEL.py:346-348` ve `prometheus_exporter.py:40-41`'de aynı `padded_row + [0]*...` kalıbı kopyalanmış; `api.py` satırları `row[6]`, `row[17]` gibi sihirli indekslerle dolu. Şemaya kolon eklendiğinde sessizce kayar.

**Öneri:** `veritabani.py` sorgularında `DictCursor` kullanıp dict dönün ya da `CihazDurumu.from_row(row)` gibi tek bir fabrika metodu yazıp padding'i oraya alın.

### 4.5 Konfigürasyon öncelik karmaşası
Üç ayrı kaynak var: `.env` (`config.py`), DB `ayarlar` tablosu ve `collector_config.load_config` (ikisini karışık okuyor: `TARGET_DEVICES_*` env öncelikli, adres/scale DB öncelikli). Panelden IP değiştiren kullanıcı, env'de `TARGET_DEVICES_MEKANIK` tanımlıysa değişikliğin etkisiz kaldığını fark edemez.

**Öneri:** Öncelik sırasını README'ye yazın ve panelde env override aktifken ilgili alanları "env dosyasından yönetiliyor" uyarısıyla kilitleyin.

### 4.6 Sessiz `except` blokları ve print/logging karışımı
`veritabani.py` hataları `print` ile, collector `logger` ile yazıyor; birçok yerde `except Exception: pass`. Docker loglarında sorun ayıklamayı zorlaştırıyor.

**Öneri:** `veritabani.py`'ye de `setup_logging("veritabani")` bağlayın; en azından veri yazan yollarda (veri_ekle, hata_durumu_guncelle) hatayı yutmayın.

### 4.7 OneDrive içinde çalışma riski
Proje `OneDrive` altında: `data/auth.db` (SQLite) ve git nesneleri senkronizasyon sırasında kilitlenme/bozulma riski taşır; Docker volume mount performansı da düşer.

**Öneri:** Çalışma kopyasını OneDrive dışına (örn. `C:\dev\solar-monitor`) taşıyıp yedeklemeyi git remote + pg_dump ile yapın.

---

## 5. TEST ve CI

### 5.1 Testler SQLite dönemine ait — CI büyük olasılıkla kırmızı
**Dosyalar:** `test_veritabani_path.py` (`veritabani.DB_NAME`/`BASE_DIR` artık yok), `test_veritabani_ek.py`, `test_config.py` vb. Mayıs'ta yazılmış, Temmuz'daki PostgreSQL geçişinden sonra güncellenmemiş. `.github/workflows/ci.yml` `pytest test_*.py` çalıştırıyor; import aşamasında patlar.

**Öneri (aşamalı):**
1. Kırık DB testlerini silin ya da `@pytest.mark.skip("PG migrasyonu sonrası yeniden yazılacak")` işaretleyin — CI'ı önce yeşile çekin.
2. Saf fonksiyon testlerini koruyun (`test_utils.py`, `test_normalize.py`, `test_models.py` değerli).
3. DB katmanı için CI'da `services: postgres` (timescaledb image) tanımlayıp `veri_ekle → son_verileri_getir → gunluk_uretim_hesapla` zincirini gerçek PG'ye karşı test edin.
4. CI Python sürümünü Dockerfile ile hizalayın (CI 3.10, Docker 3.11).

### 5.2 Healthcheck collector'ı izlemiyor
`healthcheck.py` DB bağlantısı + Modbus TCP probe yapıyor; ama en sık görülen arıza "collector çalışıyor görünüyor, veri yazmıyor" durumu (panelde de bu uyarı var).

**Öneri:** Healthcheck'e "son ölçüm yaşı" kuralı ekleyin: `MAX(zaman)` şu andan `2 × refresh_rate`'ten eskiyse exit 1. Böylece Docker `restart` politikası collector'ı otomatik toparlar.

---

## 6. GELİŞTİRME ÖNERİLERİ (yeni değer katacak işler)

1. **Alarm → bildirim entegrasyonu:** `notifications.py` (Telegram) mevcut ama `hata_durumu_guncelle` akışına bağlı değil. Yeni bir alarm `AKTIF` olduğunda (ve `DUZELDI`ye geçtiğinde) Telegram/webhook bildirimi atın. Altyapının %90'ı hazır; en yüksek fayda/maliyet oranlı iş bu.
2. **Tahmin ↔ gerçekleşme karşılaştırması:** `7_TAHMIN` fizik tabanlı modeli güzel; ancak parametreler (`PANEL_COUNT=415`, koordinatlar, 250 kW limit) kodda sabit ve tek fabrikaya özel. Bunları fabrika bazlı `ayarlar` tablosuna taşıyın ve tahmini geçmiş gerçek üretimle aynı grafikte gösterip model sapmasını (MAPE) raporlayın. İsterseniz POA ışınım hesabı için `pvlib` ekleyin.
3. **Otomatik yedekleme:** `backups/` klasörü var ama dolduran yok. Compose'a günlük `pg_dump` alan küçük bir cron servisi ekleyin (`pg_dump -Fc solar_db > backups/solar_$(date +%F).dump`, 14 gün rotasyon).
4. **Grafana'yı doğrudan Timescale'e bağlayın:** Şu an metrik akışı Prometheus üzerinden anlık değerlerle sınırlı. PostgreSQL datasource ile hypertable'dan tarihsel grafikler almak hem daha zengin hem exporter yükünü azaltır.
5. **Timezone doğruluğu:** Kolonlar `TIMESTAMP` (without time zone) ve kod `datetime.now()` (naive) kullanıyor. Konteyner TZ=Europe/Istanbul olduğu sürece çalışır ama DST/sunucu taşıma senaryolarında kayar. Orta vadede `TIMESTAMPTZ` + `datetime.now(timezone.utc)`'a geçin.
6. **Panel yenileme ayarının anında uygulanması:** `st.fragment(run_every=...)` değeri script başında okunuyor; slider değişince ancak bir sonraki tam rerun'da etkili oluyor. Slider değişiminde `st.rerun()` çağırın.
7. **API dokümantasyonuna auth şeması:** `fastapi.security.APIKeyHeader` tanımlarsanız `/docs` sayfasında "Authorize" butonu çıkar; CRM ekibinin işini kolaylaştırır.

---

## Önerilen uygulama sırası (yol haritası)

| Sıra | İş | Efor | Etki |
|---|---|---|---|
| 1 | Retention çelişkisi (1.1) + continuous aggregate (1.2) | ~yarım gün | Veri kaybını durdurur |
| 2 | API fabrika paramları + latest/alarms düzeltmeleri (1.4–1.6) | ~yarım gün | CRM entegrasyonu düzelir |
| 3 | Compose güvenlik düzeltmeleri (2.3, 2.4) + sabit şifre kaldırma (2.1) | ~2 saat | Saha güvenliği |
| 4 | ARGETEST fix'ini birleştir + script temizliği (4.1) | ~2 saat | Bakım kolaylığı |
| 5 | Bağlantı havuzu + 7 gün tablosu tek sorgu (3.1, 3.2) | ~1 gün | Panel hızı, DB yükü |
| 6 | CI'ı yeşile çekme + PG'li testler (5.1) | ~1 gün | Regresyon güvencesi |
| 7 | Alarm → Telegram bildirimi (6.1) | ~1 gün | Operasyonel değer |
| 8 | Yedekleme + healthcheck veri-yaşı kuralı (6.3, 5.2) | ~yarım gün | Dayanıklılık |

Toplamda ~5 iş günlük bir sprint ile hem kritik riskler kapanır hem de sistem operasyonel olarak belirgin şekilde güçlenir.
