# Solar Monitor ☀️ ⚡

Solar Monitor, endüstriyel güneş enerjisi invertörlerinden (Modbus TCP / RS485 protokolü üzerinden) eşzamanlı olarak telemetri verilerini (Güç, Voltaj, Akım, Sıcaklık ve Hata Kodları) toplayan, veritabanına kaydeden ve gelişmiş veri analitiği ile izleme imkanı sunan kapsamlı bir platformdur.

## 🌟 Temel Özellikler

- **Çoklu Cihaz ve Fabrika Desteği:** Aynı anda birden fazla fabrikadaki farklı cihazları izleme ve yönetme yeteneği. Fabrikalar ve cihazlar arası veri karşılaştırma (`8_KARSILASTIR`).
- **Asenkron Veri Toplama:** `collector_async.py` ile yüksek performanslı, non-blocking asenkron veri toplama mimarisi.
- **Hava Durumu Entegrasyonu:** Gerçek zamanlı hava durumu verileri çekerek santral performansı ile meteorolojik şartları korelasyona sokma (`weather.py`).
- **Gelişmiş Raporlama:** Otomatik günlük üretim raporları (`1_GUNLUK_RAPOR`), PDF rapor oluşturma (`6_PDF_RAPOR`) ve geçmiş verileri dışa aktarma (`3_EXPORT`).
- **Alarm ve Bildirimler:** İnvertör hatalarını ve limit aşımı gibi olayları yakalayarak SMS/Email/Telegram ile bildirim gönderme (`2_ALARMLAR`, `notifications.py`).
- **Geleceğe Yönelik Tahmin (Prediction):** Üretim verilerine dayalı geleceğe dönük üretim tahmini (`7_TAHMIN`).
- **Kapsamlı Loglama ve Diagnostics:** Modbus TCP bağlantılarındaki kopmaları yakalamak için detaylı diagnostics (`modbus_diagnostics.py`) ve kullanıcı işlemlerini takip eden Audit Log (`5_AUDIT_LOG`).
- **Sanal İnvertör Simülasyonu:** Geliştirme ve test süreçleri için sanal veri üreten simülasyon modülü (`10_SANAL_INVERTER`).
- **Veritabanı Esnekliği:** SQLite ve PostgreSQL/TimescaleDB desteği ile yüksek performanslı zaman serisi veritabanı altyapısı (`migrate_timescale.py`).
- **CRM Entegrasyonu:** Diğer iç sistemlere (CRM vs.) kolayca gömülebilen (embed) yapı (`crm_embed.py`).
- **Docker ile Kolay Dağıtım:** Tüm modüller Docker container üzerinden tek komutla çalıştırılabilir.

---

## 🛠️ Kurulum ve Çalıştırma

### Ön Koşullar
- [Docker](https://docs.docker.com/get-docker/) ve [Docker Compose](https://docs.docker.com/compose/install/) yüklü olmalıdır.

### 1. Projeyi Klonlayın
```bash
git clone https://github.com/KULLANICI_ADINIZ/solar-monitor.git
cd solar-monitor
```

### 2. Ortam Değişkenlerini (Ayarları) Yapılandırın
Proje kök dizininde bulunan `.env.example` dosyasının adını `.env` olarak değiştirin veya kopyalayın:

```bash
cp .env.example .env
```
Ardından `.env` dosyasını bir metin editörüyle açıp sahanıza uygun parametreleri girin. Gerekirse `config.py` ve `collector_config.py` üzerinden daha detaylı ayarlar yapabilirsiniz.

### 3. Docker ile Sistemi Başlatın
Tüm yapılandırmaları tamamladıktan sonra servisi arka planda (detached mode) başlatmak için:

```bash
docker-compose up -d --build
```

### 🔍 Logları İzleme ve Sorun Giderme
Sistemin düzgün çalışıp çalışmadığını izlemek için:
```bash
docker-compose logs -f
```

Sık Karşılaşılan Durumlar:
- **[YOK] veya Okuma Hatası:** RS485 fiziksel hattınızı ve cihaz IP/Port ayarlarınızı kontrol edin. `test_modbus_diagnostics.py` ile testler yapabilirsiniz.
- **Sık Sık Veri Kesilmesi:** İnvertörler sorgulara yetişemiyor olabilir. `REFRESH_RATE` değerini yükseltin veya asenkron toplayıcıya (`collector_async.py`) geçiş yapın.

## 🏗️ Mimari Yapı ve Sayfalar

- **`collector_async.py` & `collector.py`:** Sistemin kalbidir. Modbus üzerinden verileri toplar.
- **`veritabani.py` & `migrate_timescale.py`:** Zaman serisi (Time-Series) verilerinin yönetimi, eski verilerin otomatik silinmesi.
- **`1_PANEL.py` (Ana İzleme):** Gerçek zamanlı verilerin (Güç, Voltaj, Akım, Üretim) grafiklerle gösterildiği ana Dashboard.
- **`1_GUNLUK_RAPOR.py`:** Gün bazında özet üretim değerlerinin listelenmesi.
- **`2_ALARMLAR.py`:** Hata kodları, limit dışı olayların logları.
- **`3_EXPORT.py`:** CSV ve Excel formatında detaylı veri çıkarma.
- **`5_AUDIT_LOG.py`:** Sistem üzerindeki değişikliklerin (Örn. fabrika ekleme/silme) detaylı takibi.
- **`6_PDF_RAPOR.py`:** Yönetim için profesyonel PDF raporları oluşturma.
- **`7_TAHMIN.py`:** Geçmiş verilere dayalı ML tabanlı üretim tahmini.
- **`8_KARSILASTIR.py`:** Farklı fabrika/inverterler arasındaki üretimin üst üste bindirilerek (overlay) veya yan yana karşılaştırılması.
- **`9_SISTEM.py`:** Veritabanı durumu, sistem kaynak kullanımı gibi teknik ayarların arayüzü.
- **`10_SANAL_INVERTER.py`:** Sistemleri donanım olmadan test etmek için Modbus TCP sunucu simülasyonu.

## 📄 Lisans
Bu proje özel kullanım için geliştirilmiştir. İzinsiz kopyalanamaz veya ticari amaçlarla dağıtılamaz.