# Solar Monitor — İkinci İnceleme ve Geliştirme Önerisi

> İnceleme tarihi: 2026-08-05
> Önceki rapor: `GELISTIRME_VE_DUZELTME_ONERISI.md` (2026-07-17, 2026-07-20 güncellemeli)
> Kapsam: `veritabani.py`, `collector_async.py`, `api.py`, `auth.py`, `1_PANEL.py`, `healthcheck.py`, Docker/Compose, testler ve CI.

Temmuz raporundaki kritik maddelerin büyük bölümü gerçekten kapanmış. Bu ikinci tur, kapanan işleri doğruladıktan sonra **yeni ortaya çıkan** ve **hâlâ açık** olan konuları ele alıyor. En önemli bulgu, Temmuz'da eklenen bağlantı havuzunun yanlış kullanılıyor olması: havuz sızdırıyor ve yeterli sayıda hata biriktiğinde tüm uygulama tek seferde duruyor.

---

## 🔴 EN KRİTİK BULGU (canlı sistemde doğrulandı)

### `PooledConnectionProxy` atamaları yutuyor — TimescaleDB kurulumu sessizce geri alınıyor

**Dosya:** `veritabani.py` — `PooledConnectionProxy`

Sınıf `__getattr__` tanımlıyor ama **`__setattr__` tanımlamıyordu.** Dolayısıyla:

```python
conn.autocommit = True      # proxy nesnesinde alan olusturur
conn.autocommit             # -> True  (proxy'nin kendi alani okunur)
conn._conn.autocommit       # -> False (gercek psycopg2 baglantisi hic degismedi)
```

Canlı sistemde doğrulandı:

```
baslangic      proxy.autocommit = False | gercek baglanti.autocommit = False
atamadan sonra proxy.autocommit = True  | gercek baglanti.autocommit = False
```

`_timescale_kurulumu()` tam olarak buna dayanıyor: continuous aggregate DDL'i transaction içinde çalışamadığı için `conn.autocommit = True` yapıyor. Atama gerçek bağlantıya geçmediği için **bütün TimescaleDB kurulumu bir transaction içinde koşuyor ve hiç commit edilmiyor** — `conn.close()` → `putconn()` → psycopg2 rollback. Üstelik `conn.autocommit` okunduğunda `True` göründüğü için hiçbir hata üretilmiyordu; hatta `retention_policy_senkronize` "365 gün olarak ayarlandı" mesajını basıp hiçbir şey yapmıyordu.

**Kanıt — temiz veritabanında `init_db()` (düzeltme öncesi):**

| Nesne | Beklenen | Gerçek |
|---|---|---|
| `olcumler` hypertable | var | **yok** |
| `olcumler_saatlik` continuous aggregate | var | **yok** |
| `policy_retention` job | 365 gün | **yok** |

Düzeltmeden sonra aynı temiz kurulum üçünü de oluşturuyor.

**Üretim neden etkilenmemiş:** `solar_db`'de hypertable, continuous aggregate ve 365 günlük retention policy **mevcut** — çünkü bunları `migrate_timescale.py` kurmuş, o da havuzu değil doğrudan `psycopg2.connect()` kullanıyor. Yani üretim şu an iyi durumda; kırık olan şey **her yeni kurulum** ve **çalışma anındaki retention senkronizasyonu**. Temmuz raporunun "kod her açılışta retention'ı ayarlardan senkronize ediyor" maddesi pratikte hiç çalışmıyordu.

**Düzeltme:** Proxy'ye `__setattr__` eklendi; kendi alanları (`_pool`, `_conn`, `_returned`) dışındaki her atama gerçek bağlantıya yönlendiriliyor. Regresyon testi: `test_db_pool.py::test_atama_gercek_baglantiya_yonlendirilir`.

> Yan not: `create_hypertable` çalıştığında TimescaleDB iki uyarı basıyor — `fabrika_id` için `TEXT`, `zaman` için `TIMESTAMPTZ` öneriyor. İkincisi 5. bölümdeki TIMESTAMPTZ maddesini destekliyor.

---

## ✅ UYGULAMA DURUMU (2026-08-05, aynı gün)

Yol haritasının 1., 2. ve 5. maddeleri uygulandı:

- **1.1 Havuz sızıntısı — DÜZELTİLDİ.** 11 fonksiyonun tamamı `finally: conn.close()` kalıbına geçirildi. `init_db` şema kurulumu `_init_db_semasi(conn)` olarak ayrıldı ki DDL hatasında da bağlantı havuza dönsün. `PooledConnectionProxy` sertleştirildi: çift `close()` bağlantıyı havuza iki kez eklemiyor, geri vermeden önce `autocommit` normalize ediliyor. Yazma yollarına (`veri_ekle`, `veri_kaydet`, `ayar_yaz`, `audit_log_kaydet`) açık `rollback` eklendi. Tarama ile doğrulandı: `get_db_connection()` çağıran hiçbir fonksiyonda artık `finally` eksik değil.
- **1.5 `autocommit` sızıntısı — DÜZELTİLDİ.** `retention_policy_senkronize` `finally` bloğunda `autocommit`'i `False`'a çekiyor; ayrıca proxy `close()` içinde ikinci bir savunma katmanı var. (Bu düzeltme ancak yukarıdaki `__setattr__` bulgusuyla birlikte gerçek bir etkiye sahip — öncesinde atamalar gerçek bağlantıya hiç ulaşmıyordu.)
- **Proxy `__setattr__` — DÜZELTİLDİ.** Yukarıdaki "en kritik bulgu" bölümü. Temiz kurulumda hypertable / continuous aggregate / retention policy artık gerçekten oluşuyor; canlı PostgreSQL'e karşı doğrulandı.
- **1.2 Sessiz örnek kaybı — ÖLÇÜLEBİLİR HALE GETİRİLDİ** (kök neden hâlâ açık):
  - Yeni `collector_heartbeat` tablosu: collector cihazlardan cevap alamasa bile her döngüde döngü zamanı, süresi, okunan ve cevapsız cihaz sayısını yazıyor. Her iki collector (`collector_async.py` ve legacy `collector.py`) yazıyor.
  - Yeni `cihaz_durum_log` tablosu: cevapsızlık `hata_log` ile aynı stateful kalıpla tutuluyor — cihaz sustuğunda kayıt açılır, cevap verince kapanır, süren kesinti tek aralık kalır. `olcumler`'e kolon **eklenmedi**, böylece mevcut `AVG`/`COUNT` tabanlı rapor sorguları hiç etkilenmiyor.
  - `cihaz_calisabilirligi(baslangic, bitis, fabrika)`: cihaz başına çalışabilirlik yüzdesi. Canlı PostgreSQL'de doğrulandı (36 saatlik pencerede 11 saatlik kesinti → %69.44; 16 saatlik → %55.56; pencere dışı kesintiler ve ters aralık → boş sonuç).
  - `healthcheck.py` yeniden yazıldı: canlılık ölçütü ölçüm tazeliği değil `collector_heartbeat`. Cihaz sessizliği artık `unhealthy` değil `degraded` (HTTP 200, gövdede `degraded: true`, log satırı `WARN`). Böylece meşru kesintiler yanlış alarm üretmiyor, gerçek arıza (DB erişilemez / collector döngü çevirmiyor) gürültüye karışmıyor. Devrede olmayan ikinci fabrika da kalıcı `unhealthy` üretmiyor.
  - `collector_async.py` döngü süresi `refresh_rate`'i aştığında artık `logger.warning` basıyor — ölçüm aralığının sessizce kaymasını görünür kılar (3.1).
  - Yeni testler: `test_healthcheck.py` (11 test — cihaz sessizliği, collector ölümü, tolerans sınırları, devrede olmayan fabrika) ve `test_collector_heartbeat.py` (14 test — stateful cevapsızlık, döngü sayaçları, döngü başına tek bağlantı).
- **Yeni:** `db_cursor()` context manager eklendi (`veritabani.py`). Yeni veritabanı fonksiyonları bununla yazılmalı — bağlantıyı her koşulda havuza döndürür, hatada `rollback` yapar, bağlantı yoksa `DBBaglantiYok` yükseltir.
- **4.2 CI kırmızı — DÜZELTİLDİ.** Tam CI komutu (`pytest test_*.py --cov=.`) artık **exit 0**: 32 geçti, 2 atlandı, 34 subtest geçti, %32 kapsama. Yapılanlar:
  - SQLite dönemine ait `test_veritabani_path.py` ve `test_veritabani_ek.py` modül seviyesinde `unittest.SkipTest` ile atlanıyor (neden ve yerine ne yazılması gerektiği dosya başında belgeli).
  - **`collector.py:26` / `collector_async.py:31` — CI'ı kıran asıl sebep (yeni bulgu).** İki modül de import anında `sys.stdout`'u yeni bir `io.TextIOWrapper` ile değiştiriyordu. Bu, pytest'in çıktı yakalamasını bozuyordu: wrapper çöp toplandığında altındaki buffer'ı da kapatıyor ve pytest koşu sonunda `ValueError: I/O operation on closed file` ile çöküyordu. Sonuç yalnızca kırmızı CI değildi — **`test_collector.py` sessizce sıfır test topluyordu**, yani o dosyanın kapsaması aylardır sıfırdı ve kimse görmedi. `sys.stdout.reconfigure(...)` kullanımına geçildi (yeni nesne yaratmıyor, buffer'ı sahiplenmiyor); Windows UTF-8 davranışı korunuyor.
  - `test_collector.py` güncel `read_device` davranışına göre yeniden yazıldı (5 test). Eski testler kaldırılmış iki davranışı doğruluyordu: input-register fallback'i ve `guc = voltaj * akim` sentezi (ikincisi "sahte güç üretilmesini engelledik" notuyla bilinçli olarak kaldırılmış). Yeni testler tek blok okumayı, 32-bit alarm çözümlemesini, sıfır ölçümün atılmasını ve okuma hatasında `None` dönmesini kilitliyor.
  - `test_models.py` üç iddiası düzeltildi: `BEKLEMEDE` → `UYKU` ve `ARIZA` → `ARIZALI` (kodun ve panelin kullandığı sözlük), ayrıca 109 register'ının 1. biti (`Abnormal String Power [1-2]`) severity derecelendirmesinden beri inverteri durdurmadığı için beklenen değer `AKTİF (1 UYARI)` oldu — `has_error` True, `has_critical_or_major_error` False.
  - CI Python sürümü Dockerfile ile hizalandı (3.10 → 3.11).
  - Not: `test_normalize.py` ve `test_otomasyonu.py` test değil, elle çalıştırılan betikler (biri Modbus ağı tarayıcı, diğeri bir fonksiyonun çıktısını basıyor). Sıfır test topluyorlar; koşuyu kırmıyorlar ama `test_` önekinden çıkarılıp `archive/`'e ya da `tools/`'a taşınmaları daha doğru olur.
- **4.3 Bildirilmemiş bağımlılıklar — DÜZELTİLDİ.** `requests` ve `numpy` `requirements.txt`'e eklendi.
- **Yeni test:** `test_db_pool.py` — 10 test, gerçek PostgreSQL gerektirmez. Havuzu ve bağlantıyı taklit edip 17 veritabanı fonksiyonunu hem başarılı hem hatalı sorgu yolunda koşturuyor, her çağrıdan sonra havuzda açık bağlantı kalmadığını doğruluyor. `test_tekrarlanan_hata_havuzu_tuketmez` tam olarak bu arızanın senaryosu: 60 tur boyunca sürekli SQL hatası alıp havuzun hâlâ çalıştığını kontrol ediyor (düzeltme öncesi 20. turda ölürdü).

**Sıcaklık ölçekleme tutarsızlığı (yeni bulgu, düzeltildi).** `test_utils.py`'deki iki hata stale test değil, gerçek bir tutarsızlıktı: `decode_temperature_register` ham 15458 değerini 15.458 °C'ye çözerken (fallback bandı 120 °C), `normalize_temperature_value` aynı büyüklüğü 154.58 °C olarak normalize ediyordu (Temmuz'da `max_c` 120→300 yükseltilmişti). Yani aynı ham değer collector'da 15.458, panelde 154.58 görünüyordu. Çözüm iki ayrı bant: "dokunma" bandı geniş kaldı (300 °C — gerçek aşırı ısınma maskelenmiyor), ölçek düzeltmesi ise normal çalışma bandını (120 °C) kullanıyor. Ek olarak `decode_temperature_register`'ın alt sınırı sabit `-100` yerine `min_c` oldu; `-100 °C` gibi imkânsız bir sonuç artık kayıtlı çarpanın hatalı olduğunu gösterip fallback'i tetikliyor.

Kalan maddeler aşağıda; sıradaki iş yol haritasının 2. maddesi (gece veri boşluğu / restart döngüsü).

---

## 0. Temmuz sonrası doğrulanan durum

Kod üzerinde doğrulanarak kapandığı görülen maddeler:

| Madde | Durum | Kanıt |
|---|---|---|
| 1.1 Retention çelişkisi | Kod doğru ama **çalışmıyordu** → şimdi kapandı | `retention_policy_senkronize()` doğru yazılmış, ama `autocommit` ataması gerçek bağlantıya geçmediği için her çağrı rollback ediliyordu (bkz. en kritik bulgu) |
| 1.2 Continuous aggregate | Kod doğru ama **temiz kurulumda oluşmuyordu** → şimdi kapandı | `_timescale_kurulumu()` doğru; aynı `autocommit` bulgusu yüzünden DDL commit edilmiyordu. Üretimde nesne var çünkü `migrate_timescale.py` kurmuş |
| 1.4–1.6 API eksikleri | Kapandı | `api.py`'de tüm endpointlerde `fabrika` parametresi mevcut |
| 2.3 PG portu | Kapandı | `docker-compose.yml:42` `127.0.0.1:5432:5432` |
| 2.4 `pgdata` mount'u | Kapandı | x-common'dan çıkarılmış, yalnız `solar-postgres`'te |
| 2.5 CORS | Kapandı | `api.py:73` `allow_credentials=False` |
| 3.1 Bağlantı havuzu | Eklendi (ama yanlış kullanılıyor — bkz. 1.1) | `veritabani.py:19` `ThreadedConnectionPool(1, 20)` |
| 3.2 7 gün tablosu | Kapandı | `haftalik_uretim_ozeti()` tek sorgu, `1_PANEL.py:536` kullanıyor |
| 3.3 Cache helper | Kapandı | `1_PANEL.py:579` `_fetch_device_data(..., limit=1440)` |
| 4.1 Depo kirliliği | Kısmen kapandı | tek seferlik scriptler `archive/` altına taşınmış |
| 4.2 Fabrika ID takas hack'i | Kapandı | `collector_async.py`'de takas kodu kalmamış |
| 5.2 Healthcheck veri tazeliği | Kapandı | `healthcheck.py:47` `test_veri_tazeligi()` |
| 6.3 Otomatik yedekleme | Kapandı | `solar-backup` servisi + `backups/` içinde 6 gerçek dump (17 Tem – 5 Ağu) |
| 6.5 Timezone (kısmi) | Kısmen | PG `Europe/Istanbul`; kolonlar hâlâ `TIMESTAMP WITHOUT TIME ZONE` |
| 6.7 API auth şeması | Kapandı | `api.py:87` `APIKeyHeader` + `/docs` Authorize |

Hâlâ açık kalanlar aşağıda yeni bulgularla birlikte, önem sırasına göre listelendi.

---

## 1. KRİTİK

### 1.1 Bağlantı havuzu sızıntısı — 11 fonksiyon `close()`'u `finally` dışında çağırıyor

**Dosya:** `veritabani.py`

Havuz `maxconn=20` ile kuruluyor (`veritabani.py:19-22`). `PooledConnectionProxy.close()` bağlantıyı kapatmıyor, havuza **geri veriyor** (`veritabani.py:40-41`). Dolayısıyla `close()` çağrılmadan çıkılan her yol, havuzdan bir slot kalıcı olarak eksiltir.

Fonksiyon bazında tarama sonucu — `get_db_connection()` çağıran 28 fonksiyondan **11'inde** `close()` `finally` bloğu içinde değil:

| Fonksiyon | Satır | Risk |
|---|---|---|
| `son_verileri_getir` | 502 | `try/except` **hiç yok**; `execute` patlarsa hem sızdırır hem exception panele düşer |
| `karsilastirma_verisi_getir` | 522 | aynı — `try/except` yok |
| `tum_cihazlarin_son_durumu` | 553 | aynı — `try/except` yok |
| `ayar_oku` | 311 | `except` var, `close()` `try` içinde → hata yolunda sızdırır |
| `ayar_yaz` | 325 | aynı |
| `tum_ayarlari_oku` | 342 | aynı |
| `veri_kaydet` | 466 | aynı |
| `saatlik_ozet_getir` | 668 | aynı |
| `audit_log_kaydet` | 887 | aynı |
| `audit_log_getir` | 902 | aynı |
| `init_db` | 61 | aynı |

Bunlar tam olarak en sıcak yollar: panel her fragment yenilemesinde (varsayılan 30 sn) `tum_cihazlarin_son_durumu` + `son_verileri_getir`, collector her 30 saniyede `tum_ayarlari_oku` çağırıyor.

**Etki:** Geçici bir DB kesintisi ya da tek bir SQL hatası 20 kez tekrarlandığında havuzda slot kalmaz. `getconn()` `PoolError` atar, `get_db_connection()` `None` döner ve **panel, API, collector, healthcheck hep birlikte** "veritabanına bağlanılamadı" durumuna geçer. Konteyner yeniden başlatılmadan kendini toparlamaz. Yavaş yavaş biriken, hata anından saatler sonra patlayan bir arıza — teşhisi de zor.

**Öneri:** Tek bir context manager'a geçirip tüm fonksiyonları oradan besleyin:

```python
from contextlib import contextmanager

@contextmanager
def db_cursor(commit=False):
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("DB baglantisi kurulamadi")
    try:
        yield conn.cursor()
        if commit:
            conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()   # havuza geri verir
```

Geçiş sırasında hızlı bir doğrulama: yük altında `SELECT count(*) FROM pg_stat_activity WHERE datname='solar_db';` değerinin zamanla tırmanıp tırmanmadığına bakın.

### 1.2 Sessiz örnek kaybı: 3 inverterin 2'si verisinin ~%75'ini kaybediyor

> ⚠️ **Bu maddenin ilk yazımı yanlıştı — düzeltildi.** İlk versiyonda "gece inverterler kapanınca hiç satır yazılmıyor, healthcheck unhealthy oluyor ve Docker collector'ı her gece sürekli yeniden başlatıyor" yazıyordu. Canlı sistemde ölçtüm, **öyle olmuyor**:
>
> - `docker inspect solar_collector` → `RestartCount=0`, `FailingStreak=0` (17 saat, tam bir gece dahil). Restart döngüsü hiç yaşanmamış.
> - Gece verisi akıyor: 04 Ağu 20:00 – 05 Ağu 05:00 arasında her saat satır var. Güç `0.0` ama **sıcaklık ~40 °C** — inverter beslemede kaldığı için dört değerin hepsi asla sıfır olmuyor, dolayısıyla `all-zero → None` koşulu tetiklenmiyor.
> - Ayrıca **`unhealthy` durumu tek başına konteyneri yeniden başlatmaz.** Docker'ın restart politikası konteynerin *çıkışına* tepki verir, sağlık durumuna değil; unhealthy'de restart Swarm/Kubernetes davranışıdır. Hem bu rapor hem Temmuz raporunun 5.2 maddesi hem de koddaki yorumlar bu varsayımı yanlış kurmuş.
>
> Aşağıdaki asıl bulgu ölçüme dayanıyor.

**Dosyalar:** `collector_async.py:207`, `collector_async.py:413`, `healthcheck.py`

Okuma başarısız olduğunda hiçbir yere kayıt düşmüyor — yalnızca stdout'a basılıyor:

```python
if data:
    veritabani.veri_ekle(...)                    # collector_async.py:413
else:
    print(f"... | [CEVAP YOK]")                  # DB'ye hiçbir sey yazilmaz
```

Canlı sistemde 24 saatlik ölçüm (`refresh_rate=60`, yani cihaz başına beklenen 1440 satır):

| Cihaz | Satır (24s) | Beklenenin oranı | Medyan aralık | Ortalama aralık | En uzun boşluk |
|---|---|---|---|---|---|
| `uretim/1` | 1437 | %100 | 60.0 sn | 60.1 sn | 130 sn |
| `mekanik/1` | **364** | **%25** | 65.6 sn | 237.0 sn | **2341 sn (39 dk)** |
| `uretim/2` | **312** | **%22** | 171.5 sn | 276.5 sn | **1672 sn (28 dk)** |

Collector logunda aynı 24 saatte **1611 `[CEVAP YOK]`** ve **3212 `veri okuma hatasi`** var (zaman aşımı 0 — yani bağlantı kurulup okuma reddediliyor).

**Sonuç:** Üç inverterin ikisi verisinin dörtte üçünü kaybediyor ve **bu hiçbir ekranda görünmüyor.** Veritabanında iz yok, metrik yok, alarm yok; yalnızca `docker logs` içinde. Panel "son veri 14 sn önce" gösterdiği için sistem sağlıklı görünüyor. Bunun iki ölçülebilir zararı var:

1. `gunluk_uretim_hesapla` çalışma süresini `olcum_sayisi * refresh_rate / 3600` ile tahmin ediyor (`veritabani.py`). `mekanik/1` için bu 24 saat yerine ~6 saat verir; `modbus_uretim` register'ı okunamadığı günlerde üretim hesabı doğrudan yanlış çıkar.
2. Kayıp örnekler ortalamaları çarpıtır: 39 dakikalık boşluk içindeki gerçek güç eğrisi hiç kaydedilmiyor.

**Öneri:** Aşağıdaki "Uygulama durumu" bölümünde yapıldı — cevapsızlık `cihaz_durum_log` tablosuna stateful olarak işleniyor, collector her döngüde `collector_heartbeat` yazıyor, healthcheck canlılığı ölçüm akışından ayırıyor. Böylece kayıp ölçülebilir hale geliyor. **Kaybın kök nedeni (gateway/inverter neden okumayı reddediyor) hâlâ açık** — bunun için 3.1'deki gateway bekleme süreleri ve blok okuma stratejisi incelenmeli.

### 1.3 Modbus kayma oto-düzeltmesi üretilmiş değeri gerçek ölçüm gibi kaydediyor

**Dosya:** `collector_async.py:172-199`

Kayma tespit edildiğinde değerler bir adım geri kaydırılıyor; ancak dizinin dışına düşen Akım A için değer **uyduruluyor**:

```python
gercek_akim_a = gercek_akim_b   # "sistemi dengeli varsayiyoruz"  (satır 193)
```

Bu değer diğer ölçümlerle aynı kolona, aynı güvenilirlikle yazılıyor. Raporda, PDF'te, tahmin modelinde ve CRM'e giden API yanıtında ölçülmüş veriden ayırt edilemez. Ayrıca tespit eşiği (`480 ≤ V_ca ≤ 520` **ve** `I_c > 500`) fiziksel olarak gerçekten 500 A'in üzerine çıkan bir tesiste yanlış pozitif üretir.

**Öneri:** `olcumler`'e `veri_kalitesi SMALLINT DEFAULT 0` (0=ölçüldü, 1=kayma düzeltildi, 2=kısmen tahmin edildi) kolonu ekleyip düzeltilen satırları işaretleyin; panelde bu satırları farklı işaretle gösterin. Uydurulmak yerine `NULL` yazmak da bir seçenek — ortalama hesabı `AVG` ile NULL'ları zaten atlar. Ek olarak `logger.warning` şu an `logging.basicConfig(level=logging.ERROR)` (satır 443) ile birlikte görünürlüğü belirsiz; düzeltmenin ne sıklıkta tetiklendiğini sayaç olarak DB'ye yazmak daha güvenilir.

### 1.4 Alarm → bildirim zinciri hâlâ bağlı değil

**Dosyalar:** `notifications.py`, `veritabani.py:362` (`hata_durumu_guncelle`)

Temmuz raporunun "en yüksek fayda/maliyet oranlı iş" dediği madde hâlâ açık. `notifications.py` tam çalışır durumda (Telegram, retry, testleri de var: `test_notifications.py`) ama **hiçbir yerden import edilmiyor**. `hata_durumu_guncelle` yeni alarmı `hata_log`'a `AKTIF` olarak yazıyor, `DUZELDI`ye çekiyor — ve orada bitiyor. Operatör panele bakmadıkça arızayı öğrenmiyor.

**Öneri:** `hata_durumu_guncelle` içindeki iki geçiş noktasına (yeni `AKTIF` INSERT'i ve `DUZELDI` UPDATE'i) bildirim tetikleyin. Bildirimi DB transaction'ı içinde senkron atmayın — `hata_log`'a yazıp `bildirim_gonderildi BOOLEAN DEFAULT FALSE` kolonu ekleyin, collector döngüsünün sonunda gönderilmemişleri toplu geçin. Böylece Telegram/webhook yavaşlığı Modbus döngüsünü bloklamaz ve container yeniden başlarsa bildirim kaybolmaz.

### 1.5 `retention_policy_senkronize` havuza `autocommit=True` bağlantı geri veriyor

**Dosya:** `veritabani.py:267-308`

Fonksiyon kendi bağlantısını aldığında `conn.autocommit = True` yapıyor (satır 280) ve `finally` bloğunda `conn.close()` ile bağlantıyı havuza geri veriyor — **`autocommit` bir daha `False`'a çekilmiyor.** (`_timescale_kurulumu` bunu doğru yapıyor: satır 264.)

Bu bağlantı havuzda kalır ve sonraki kullanan fonksiyon farkında olmadan autocommit modunda çalışır. Etkisi sessiz: `veri_ekle`'nin `except` yolunda yarım kalmış bir işlem geri alınamaz hale gelir, çünkü her `execute` anında commit'lenmiştir.

**Öneri:** `finally` bloğunda `conn.autocommit = False` satırını ekleyin (kapatmadan önce). Daha sağlamı: `PooledConnectionProxy.close()` içinde geri vermeden önce `self._conn.autocommit = False` yaparak durumu normalize edin.

---

## 2. GÜVENLİK

### 2.1 Kodda gömülü yedek admin hash'i

**Dosya:** `auth.py:93`, `auth.py:104-112`

```python
_DEFAULT_ADMIN_HASH = "0139dcacdd93868fd19a701191131882297aab91532bfb7b825b886f19ae7a53"
...
def load_users():
    if os.path.exists(_USERS_JSON_PATH): ...
    return {"admin": {"hash": _DEFAULT_ADMIN_HASH, "role": "admin"}}
```

`data/users.json` yoksa veya okunamazsa (volume mount edilmemiş yeni bir konteyner, bozuk JSON, OneDrive senkronizasyon kilidi) sistem sessizce **kodda yazılı sabit admin şifresine** düşüyor. Hash'te salt yok — `_verify_password`'ün geriye dönük uyumluluk dalı sabit `b'solar_monitor_v2'` salt'ı kullanıyor (satır 82-85), yani repoya erişen biri için offline sözlük saldırısı tek bir PBKDF2 zinciriyle mümkün.

**Öneri:** Fallback'i tamamen kaldırın; `users.json` yoksa **girişi reddedip** loga kritik hata basın ve ilk kullanıcıyı `kurulum_yap.py` oluştursun. Sabit salt'lı eski format desteği artık taşınmıyorsa `_verify_password`'ün `else` dalını da silin.

### 2.2 Sabit zamanlı olmayan sır karşılaştırmaları

- `auth.py:79` → `return expected_hash == hash_hex`
- `auth.py:85` → `return expected_hash == stored_hash`
- `api.py:106,110,119` → API anahtarı `==` ile karşılaştırılıyor

**Öneri:** Üçü de `hmac.compare_digest(a, b)`. PBKDF2 hash karşılaştırması için pratik risk düşük ama API anahtarı ağ üzerinden tekrar tekrar denenebilir bir sır; orada gerçek bir fark var.

### 2.3 Rate-limit anahtarı tek kovaya düşüyor

**Dosya:** `auth.py:46-58`

`_get_client_ip()` yalnızca `X-Forwarded-For` başlığına bakıyor. Panelin önünde reverse proxy yok (`docker-compose.yml:84-85` doğrudan `8501:8501`), yani başlık hiç gelmiyor ve fonksiyon her istemci için `"unknown"` döndürüyor.

Sonuç: `failed_logins` tablosunda **tüm kullanıcılar tek bir `rate_key` paylaşıyor.** Bir kişinin (ya da bir tarayıcı otomatik doldurmasının) art arda hatalı denemesi tüm fabrikayı kilitler. Proxy eklendiği anda ise ters problem: başlık istemci tarafından serbestçe uydurulabildiği için kilit tamamen atlatılır.

**Öneri:** Proxy varsa `X-Forwarded-For`'un **en sağdaki güvenilir** değerini alın ve yalnızca `TRUST_PROXY=true` iken bu başlığa güvenin; aksi halde `st.context.headers`'dan gerçek peer adresini ya da Streamlit session ID'sini anahtar olarak kullanın. Kilit mesajında hangi anahtarın kilitlendiğini loglayın.

### 2.4 Oturum süresi yok

**Dosya:** `auth.py:424-427`

`check_auth()` sadece `st.session_state.get("authenticated")` bakıyor. Sekme açık kaldığı sürece oturum süresiz geçerli — vardiya değişiminde açık kalan operatör ekranı bir sonraki vardiyanın elinde admin yetkisiyle duruyor.

**Öneri:** Girişte `st.session_state["login_time"] = time.time()`, `check_auth()` başında `SESSION_TIMEOUT_MIN` (varsayılan 480 dk, `.env`'den) aşıldıysa state'i temizleyip login ekranına dönün.

### 2.5 `POSTGRES_PASSWORD` varsayılanı hâlâ yerinde

**Dosya:** `docker-compose.yml:46`, `docker-compose.yml:215`, `veritabani.py:16`

Grafana ve MQTT için zorunlu-değişken kalıbı uygulanmış (`${GRAFANA_PASSWORD:?...}`, satır 168; `${MQTT_PASSWORD:?...}`, satır 183) ama Postgres üç yerde `:-solar_pass_2026` varsayılanıyla kalmış. `.env` unutulursa sistem bilinen bir şifreyle ayağa kalkar ve DB portu localhost'ta da olsa host üzerindeki her süreç erişebilir.

**Öneri:** Aynı `:?` kalıbını Postgres'e de uygulayın; `veritabani.py:16`'daki Python tarafı varsayılanını da kaldırıp yokluğunda açık hata verin.

### 2.6 API anahtarları düz metin JSON'da ve her istekte diskten okunuyor

**Dosya:** `api.py:98-113`

`data/api_config.json` her istekte açılıp `json.load` ediliyor. İki sorun: (a) istek başına dosya I/O — `120/minute` limitli endpointlerde gereksiz yük, (b) `data/` dizini x-common üzerinden **tüm** uygulama konteynerlerine mount edilmiş (`docker-compose.yml:22`), yani panel ya da exporter konteynerine giren biri CRM anahtarlarını okuyabilir.

**Öneri:** Dosyayı mtime kontrollü bir cache'e alın; anahtarları düz metin yerine hash'leyip saklayın (doğrulama `compare_digest` ile hash üzerinden). Orta vadede `data/` mount'unu yalnızca ihtiyacı olan servislere verin.

### 2.7 Panel ve API tüm ağa TLS'siz açık

**Dosya:** `docker-compose.yml:85` (`8501:8501`), `:102` (`8503:8503`), `api.py:729` (`host="0.0.0.0"`)

Fabrika ağındaki herkes login sayfasına ve API'ye ulaşabiliyor; şifreler ve `X-API-Key` düz HTTP üzerinde gidiyor.

**Öneri:** Önüne bir reverse proxy (Caddy/nginx) koyup TLS'i orada bitirin — bu aynı zamanda 2.3'teki rate-limit sorununu da doğru `X-Forwarded-For` ile çözer. Proxy'yi kurduğunuzda uygulama portlarını `127.0.0.1`'e alın.

---

## 3. PERFORMANS VE MİMARİ

### 3.1 "Asenkron" collector pratikte seri çalışıyor

**Dosya:** `collector_async.py:107`, `:117-142`, `:366-368`

Kilit **IP başına** oluşturuluyor (`locks[client_key]`, satır 366) ve `read_device_async` gövdesinin **tamamı** `async with lock` içinde (satır 107). Aynı gateway'in arkasındaki tüm slave'ler bu kilidi sırayla bekliyor. Kilit içinde ayrıca sabit beklemeler var:

```
1.5 s  (gateway "nefes alma")
0.5 s  (üretim okuması öncesi)
0.5 s  (güç/ısı okuması öncesi)
0.05 s (alarm okuması öncesi)
≈ 2.55 s + 4-5 Modbus gidiş-dönüşü  →  cihaz başına ~3-4 s
```

3 slave'li tek gateway'de döngü ~10-12 saniye, 8 cihazda 30 saniyeyi aşar. `asyncio.gather` burada paralellik kazandırmıyor — yalnızca *farklı IP'ler* gerçekten eşzamanlı. Döngü `refresh_rate`'i aşarsa `await asyncio.sleep(max(1.0, min_refresh - gecen))` (satır 439) 1 saniyeye düşüyor, yani ölçüm aralığı sessizce kayıyor ve `gunluk_uretim_hesapla`'nın `olcum_sayisi * refresh_rate / 3600` varsayımı (satır 827) bozuluyor — modbus üretim register'ı okunamadığı durumlarda üretim hesabı yanlış çıkar.

**Öneri:**
- Sabit beklemeleri `.env`/`ayarlar`'a taşıyın (`MODBUS_GATEWAY_DELAY_MS` vb.); gateway'iniz dayanıyorsa 1.5 sn ciddi kazanç noktası.
- Kilidi tüm gövde yerine yalnız Modbus çağrılarını saracak şekilde daraltın.
- Gerçek döngü süresini ölçüp loglayın; `refresh_rate`'ten uzun sürüyorsa uyarı basın.
- `gunluk_uretim_hesapla`'da `refresh_rate` varsayımı yerine ölçümler arasındaki gerçek zaman farkını kullanın (`EXTRACT(EPOCH FROM zaman - LAG(zaman) OVER ...)`).

### 3.2 Her döngüde tüm Modbus bağlantıları kapatılıp yeniden kuruluyor

**Dosya:** `collector_async.py:388-391`

```python
for key in list(clients.keys()):
    client_to_close = clients.pop(key)
    client_to_close.close()
```

Cihaz kilitlenmesini önlemek için bilinçli bir karar olduğu belli, ama her döngü baştan TCP handshake + `retries=3` maliyeti demek. Gateway'iniz kalıcı bağlantıyı taşıyabiliyorsa bunu bir ayara bağlayın (`MODBUS_RECONNECT_EVERY_CYCLE=false`) ve yalnız hata sonrası kapatın.

### 3.3 Çift silme: TimescaleDB retention + manuel DELETE

**Dosyalar:** `collector_async.py:292-302` (`otomatik_veri_temizle`), `veritabani.py` (`eski_verileri_temizle`), `veritabani.py:300` (retention policy)

Retention policy artık ayarlardan senkronize edildiği için chunk'ları Timescale zaten düşürüyor. Collector yarım saatte bir ayrıca `DELETE` tabanlı temizlik koşuyor — hypertable üzerinde `DELETE` chunk düşürmeye kıyasla çok pahalı (satır satır tuple, autovacuum yükü) ve silecek bir şey bulamayacağı için tamamen boşa gidiyor.

**Öneri:** `otomatik_veri_temizle`'yi kaldırın, ya da retention policy'nin aktif olmadığı (TimescaleDB uzantısı yüklenemeyen) kurulumlar için yedek yol olarak bırakıp yalnız o durumda çalıştırın.

---

## 4. KOD SAĞLIĞI VE SÜREÇ

### 4.1 Varsayılan register adresleri artık **beş** yerde, üç farklı değerle

Temmuz raporunda üç yerdeydi; sonra `kurulum_yap.py` ve `collector_async.py` içi fallback'ler eklenince dağınıklık arttı:

| Kaynak | guc | volt | akim | isi |
|---|---|---|---|---|
| `veritabani.py:158-161` (DB varsayılan ayarları) | 70 | 71 | 72 | 73 |
| `veritabani.py:355-356` (`tum_ayarlari_oku` hata fallback'i) | 70 | 71 | 72 | 73 |
| `kurulum_yap.py:102-105`, `:177-178` | 70 | 71 | 72 | 73 |
| `collector_config.py:95-98` (env fallback) | 75 | 73 | 70 | 44 |
| `collector_async.py:118,123` (kod içi fallback) | — | 28 | 25 | — |

DB'de kayıt varsa sorun görünmüyor; ama boş bir kuruluma ya da `tum_ayarlari_oku` hata yoluna düştüğünüzde hangi adresin geçerli olacağı belirsiz — ve `collector_async.py`'deki 25/28 değerleri hiçbir yerdeki varsayılanla uyuşmuyor.

**Öneri:** `collector_config.py` içinde tek bir `DEFAULT_REGISTERS` sözlüğü tanımlayıp diğer dört yer oradan import etsin. `collector_async.py`'de `config.get("akim_addr", 25)` yerine `config["akim_addr"]` kullanın — anahtar eksikse sessiz yanlış adres yerine açık hata daha iyi.

### 4.2 CI hâlâ kırmızı — SQLite dönemi testleri duruyor

**Dosyalar:** `test_veritabani_path.py`, `test_veritabani_ek.py`

```python
assert os.path.isabs(veritabani.DB_NAME)          # test_veritabani_path.py:7
self.original_db = veritabani.DB_NAME              # test_veritabani_ek.py:8
```

`veritabani.DB_NAME` ve `BASE_DIR` PostgreSQL geçişinde kaldırıldı; bu iki dosya `AttributeError` ile patlıyor. `.github/workflows/ci.yml:30` `pytest test_*.py` çalıştırdığı için **her push kırmızı** — yani CI şu anda hiçbir regresyonu yakalamıyor, gürültüye dönüşmüş durumda.

Ayrıca CI Python 3.10, Dockerfile 3.11 (Temmuz raporunun 5.1/4 maddesi, hâlâ açık).

**Öneri:** Bu iki dosyayı silin (git geçmişinde duruyorlar), CI'ı yeşile çekin, sonra `services: postgres` (timescaledb image) ile `veri_ekle → son_verileri_getir → gunluk_uretim_hesapla` zincirini gerçek DB'ye karşı test eden yeni bir dosya yazın. CI'da 3.11'e geçin. Yeni testin ilk hedefi 1.1'deki havuz sızıntısı olsun: 25 kez hatalı sorgu koşturup havuzun hâlâ çalıştığını doğrulayan bir test bu hatayı kalıcı olarak kapatır.

### 4.3 `requests` ve `numpy` bildirilmemiş bağımlılıklar

`requirements.txt` içinde ikisi de yok, ama 9 dosya kullanıyor: `collector.py:18`, `collector_config.py:18`, `collector_async.py:22`, `notifications.py:9`, `weather.py:1`, `crm_embed.py:178,270`, `pages/7_TAHMIN.py:3,6`.

Şu an çalışıyor çünkü `streamlit` `requests`'i, `pandas` `numpy`'ı dolaylı olarak kuruyor. Bu iki paketin gelecekteki bir sürümü bağımlılığını değiştirdiğinde build sessizce bozulur.

**Öneri:** `requests>=2.31,<3.0` ve `numpy>=1.24,<3.0` satırlarını ekleyin. Aynı fırsatta `pyproject.toml:8-15`'teki `dependencies` listesi `requirements.txt` ile senkronize değil (fastapi, uvicorn, psycopg2, prometheus_client, paho-mqtt, slowapi, reportlab eksik) — tek kaynağa indirin.

### 4.4 `docker-compose.yml` yorumları bozuk kodlanmış

Dosyadaki Türkçe yorumlar çift kodlanmış UTF-8 olarak duruyor: `TÃ¼m servisleri`, `GÃ¼venlik`, `â”€â”€â”€`. İşlevi etkilemiyor ama dosyayı okunmaz hale getiriyor ve bir sonraki düzenlemede kolayca daha da bozulur.

**Öneri:** Dosyayı UTF-8 olarak bir kez yeniden yazın (yorumları düzelterek) ve `.gitattributes`'a compose dosyaları için `text eol=lf working-tree-encoding=UTF-8` ekleyin.

### 4.5 Docker log rotasyonu yok

`docker-compose.yml`'de hiçbir servis için `logging` sürücüsü tanımlı değil, yani varsayılan `json-file` sınırsız büyüyor. Collector her döngüde her cihaz için `print` + `logger` satırı basıyor (`collector_async.py:405-427`); 1.2'deki gece restart döngüsü bunu ayrıca katlıyor. 7/24 çalışan fabrika kutusunda disk dolması gerçek bir risk.

**Öneri:** `x-common`'a ekleyin:

```yaml
logging:
  driver: json-file
  options:
    max-size: "20m"
    max-file: "5"
```

### 4.6 `veritabani.py` hâlâ `print` ile loglıyor

34 `except` bloğunun neredeyse tamamı `print(f"[WARN] ...")` kalıbında. Diğer modüller `config.setup_logging` kullanıyor. `print` çıktısı seviye, zaman damgası ve modül adı taşımıyor; Docker logunda filtrelenemiyor. Temmuz raporunun 4.6 maddesi hâlâ açık.

**Öneri:** `logger = setup_logging("veritabani")` ekleyip `print` çağrılarını `logger.warning`/`logger.error`'a çevirin. En azından veri yazan yollar (`veri_ekle`, `veri_kaydet`, `hata_durumu_guncelle`) hatayı yutmasın.

### 4.7 `collector.py` — ölü ikinci collector

README ve compose `collector_async.py`'yi ana collector olarak tanımlıyor; `collector.py` (12 KB) hâlâ kökte ve `start_collector.cmd` üzerinden yanlışlıkla çalıştırılabilir. İki collector aynı DB'ye yazarsa ölçümler çiftlenir.

**Öneri:** `archive/`'e taşıyın ya da silin; `start_collector.cmd`'yi `collector_async.py`'ye yönlendirin.

### 4.8 Çalışma kopyası hâlâ OneDrive içinde

Proje yolu: `OneDrive - TESCOM .../Masaüstü/solar-monitor-master`. `data/auth.db` (SQLite, `auth.py:29`) ve `.git` nesneleri senkronizasyon kilitlerine açık; ayrıca `data/auth-ARGETEST.db` gibi çakışma kopyaları oluşmuş — bu tam olarak OneDrive'ın yarattığı sorunun kanıtı. `backups/` içindeki 5 MB'lık dump'lar da her gün OneDrive'a yükleniyor.

**Öneri:** Çalışma kopyasını `C:\dev\solar-monitor` gibi senkronize edilmeyen bir yola taşıyın. Yedeklemeyi git remote + `pg_dump` üstlensin (ikisi de zaten var). `data/auth-ARGETEST.db`'nin gerçekten artık kullanılmadığını doğrulayıp silin.

---

## 5. GELİŞTİRME ÖNERİLERİ (yeni değer)

1. **Çalışabilirlik (availability) ve Performans Oranı (PR) KPI'ı.** 1.2'deki `durum` kolonu geldiğinde cihaz başına "kaç saat cevap verdi / kaç saat vermesi gerekiyordu" hesaplanabilir hale gelir. Buna hava durumu ışınımını (`weather.py` zaten çekiyor) ekleyerek gerçek Performans Oranı (üretilen kWh / teorik kWh) raporlanabilir — santral sağlığının tek en anlamlı göstergesi ve şu an sistemde yok.
2. **İnverter karşılaştırmalı anomali tespiti.** Aynı fabrikada aynı ışınım altında çalışan inverterlerin gücü birbirine yakın olmalı. Saatlik özet üzerinden z-skoru ("bir inverter komşularının medyanının %15 altında ve 3 saatten uzun süredir") hesaplayıp alarm üretin. Hata kodu üretmeden verim kaybeden string/inverter arızalarını yakalar; ek donanım gerekmez, `olcumler_saatlik` view'u zaten hazır.
3. **Tahmin ↔ gerçekleşme sapması (MAPE).** `pages/7_TAHMIN.py`'deki fizik modelinin parametreleri kodda sabit ve tek fabrikaya özel. Bunları fabrika bazlı `ayarlar`'a taşıyıp tahmini gerçek üretimle aynı grafikte gösterin, günlük MAPE'yi kaydedin. Model sapması aynı zamanda kirlenme/gölgelenme sinyalidir.
4. **Grafana'yı doğrudan TimescaleDB'ye bağlayın.** Şu anda tek datasource Prometheus (`grafana/provisioning/datasources/prometheus.yml`), yani yalnız anlık değerler. PostgreSQL datasource'u ekleyip `olcumler_saatlik` üzerinden tarihsel panolar çıkarın; exporter yükü de azalır.
5. **OSOS ↔ Modbus üretim mutabakatı.** `osos_verileri` tablosu ve sayfaları var. Sayaç (OSOS) ile inverter toplamını günlük karşılaştırıp fark yüzdesini raporlayın — sapma hem ölçüm hatasını hem fatura anlaşmazlığını yakalar.
6. **`TIMESTAMPTZ` geçişi.** Kolonlar hâlâ `TIMESTAMP WITHOUT TIME ZONE` (`veritabani.py:84`) ve kod `datetime.now()` (naive) yazıyor. Konteyner TZ'si Istanbul olduğu sürece çalışıyor ama DST geçişinde saat 03:00 civarı çift/eksik kayıt üretir. `healthcheck.py` bu yüzden yaşı Python tarafında hesaplamak zorunda kalmış (satır 52-55) — belirtinin kendisi. Orta vadeli ama bir kez yapılacak iş.
7. **Panel yenileme ayarının anında uygulanması.** `1_PANEL.py:425,575,686` `run_every` değerini script başında okuyor; slider değiştiğinde ancak sonraki tam rerun'da etkili oluyor. Slider `on_change`'inde `st.rerun()` çağırın. (Temmuz 6.6, hâlâ açık.)

---

## Önerilen uygulama sırası

| Sıra | İş | Efor | Etki |
|---|---|---|---|
| ~~1~~ | ~~Havuz sızıntısı + `autocommit` sızıntısı + proxy `__setattr__`~~ | — | **Yapıldı** |
| ~~2~~ | ~~Heartbeat + cevapsızlık logu + healthcheck ayrımı~~ | — | **Yapıldı** (kök neden 9. maddede) |
| 3 | Alarm → Telegram bildirimi (1.4) | ~1 gün | En yüksek operasyonel değer; altyapı hazır |
| 4 | Gömülü admin hash'i + `compare_digest` + oturum süresi (2.1, 2.2, 2.4) | ~yarım gün | Kimlik doğrulamayı gerçekten güvenli yapar |
| 5 | CI'ı yeşile çekme + havuz regresyon testi (4.2) | ~yarım gün | 1. maddenin kalıcılığını garanti eder |
| 6 | Register varsayılanlarını tek kaynağa toplama (4.1) + bildirilmemiş bağımlılıklar (4.3) | ~yarım gün | Kurulum güvenilirliği |
| 7 | Log rotasyonu (4.5) + çift silme kaldırma (3.3) + `collector.py` temizliği (4.7) | ~2 saat | Disk ve DB yükü |
| 8 | Rate-limit anahtarı + reverse proxy/TLS (2.3, 2.7) | ~1 gün | Ağ güvenliği; ikisi birlikte çözülür |
| 9 | **Örnek kaybının kök nedeni** — gateway bekleme süreleri, blok okuma stratejisi, döngü zamanlaması (3.1) | ~1-2 gün | 3 inverterin 2'sinde %75 veri kaybını giderir; artık ölçülebilir |
| 10 | Availability/PR KPI'ı (5.1) + inverter anomali tespiti (5.2) | ~2-3 gün | `cihaz_durum_log` hazır, panel tarafı kaldı |

Kalan işlerde en yüksek değerli iki madde: **9** (gerçek veri kaybı — artık `cihaz_durum_log` ve heartbeat sayaçlarıyla ölçülebilir, "düzeldi mi" sorusu yanıtlanabilir) ve **3** (alarmların operatöre ulaşması).
