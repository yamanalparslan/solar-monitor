# Solar Monitor ☀️ ⚡

Solar Monitor, endüstriyel güneş enerjisi invertörlerinden (Modbus TCP / RS485 protokolü üzerinden) eşzamanlı olarak telemetri verilerini (Güç, Voltaj, Akım, Sıcaklık ve Hata Kodları) toplayan, veritabanına kaydeden ve izleme panelleri için WebSocket üzerinden canlı bildirimler sunan gelişmiş bir Python servisidir.

## 🌟 Temel Özellikler

- **Çoklu Cihaz ve IP Desteği (Sequential Polling):** RS485 hattında veri çakışmasını (collision) önlemek amacıyla birden fazla invertörü (veya farklı IP adreslerindeki ağ geçitlerini) sırayla ve güvenli bekleme süreleriyle okur.
- **Dinamik Blok Okuma (Dynamic Block Read):** Cihazı yoran "parçalı sorgular" yerine, ortam değişkenlerinde belirtilen register adres aralıklarını otomatik olarak hesaplar ve tüm telemetriyi tek bir paket (blok) halinde okuyarak timeout hatalarını engeller.
- **Hata Toleransı (Retry Mechanism):** Anlık parazitler veya yanıt gecikmelerinde veritabanını sahte "0" değerleriyle doldurmaz; otomatik olarak yeniden dener ve okuma başarısızsa o döngüyü atlar.
- **Çoklu Fabrika (Multi-Site) Desteği:** Tek bir servis üzerinden, veritabanında tanımlı farklı fabrikaların (Örn: Mekanik, Plastik vb.) farklı IP ve konfigürasyonlarını yönetebilir.
- **Otomatik Veri Temizliği (Data Retention):** Veritabanı şişmesini önlemek için belirlenen gün sayısından (`veri_saklama_gun`) eski olan kayıtları otomatik olarak siler.
- **Docker Entegrasyonu:** Tüm sistem bağımlılıklarıyla birlikte izole bir Docker konteyneri olarak tek komutla ayağa kalkar.

---

## 🛠️ Kurulum ve Çalıştırma

### Ön Koşullar
- [Docker](https://docs.docker.com/get-docker/) ve [Docker Compose](https://docs.docker.com/compose/install/) yüklü olmalıdır.

### 1. Projeyi Klonlayın
```bash
git clone [https://github.com/KULLANICI_ADINIZ/solar-monitor.git](https://github.com/KULLANICI_ADINIZ/solar-monitor.git)
cd solar-monitor
2. Ortam Değişkenlerini (Ayarları) Yapılandırın
Proje kök dizininde bulunan .env.example dosyasının adını .env olarak değiştirin veya kopyalayın:

Bash
cp .env.example .env
Ardından .env dosyasını bir metin editörüyle açıp sahanıza uygun parametreleri girin:

Ini, TOML
# --- Modbus Bağlantı Ayarları ---
TARGET_IPS=10.35.14.10,10.35.14.11  # Cihazların veya ağ geçitlerinin IP adresleri
MODBUS_PORT=502                     # Modbus TCP Portu
SLAVE_ID=1                          # Doğrudan IP bağlantılarında genelde 1'dir

# --- Zamanlayıcı ---
REFRESH_RATE=5                      # İki okuma döngüsü arasındaki bekleme süresi (Saniye)

# --- Register Adresleri ---
# NOT: Pymodbus 0-tabanlıdır. Cihaz dokümanındaki adresten 1 eksik girilmelidir.
GUC_ADDR=33
VOLT_ADDR=28
AKIM_ADDR=25
ISI_ADDR=44

# --- Çarpan Katsayıları (Scale) ---
GUC_SCALE=0.1
VOLT_SCALE=0.1
AKIM_SCALE=0.1
ISI_SCALE=0.1

# --- Veritabanı ve Log ---
DB_NAME=solar_log.db
LOG_LEVEL=INFO
3. Docker ile Sistemi Başlatın
Tüm yapılandırmaları tamamladıktan sonra servisi arka planda (detached mode) başlatmak için:

Bash
docker-compose up -d --build
🔍 Logları İzleme ve Sorun Giderme
Sistemin düzgün çalışıp çalışmadığını, verilerin doğru gelip gelmediğini (Örn: V=220.5V  A=15.20A  G=3351.6W) görmek için logları canlı takip edebilirsiniz:

Bash
docker-compose logs -f
Sık Karşılaşılan Durumlar:

[YOK] veya Okuma Hatası: RS485 fiziksel hattınızı, Papatya (Daisy-chain) dizilimini ve hattın başı/sonundaki 120 Ohm sonlandırma dirençlerini kontrol edin.

Sık Sık Veri Kesilmesi: İnvertörler sorgulara yetişemiyor olabilir. .env dosyasındaki REFRESH_RATE değerini 5, 10 veya 15 saniyeye yükselterek hattı rahatlatın.

🏗️ Mimari Yapı
collector.py: Sistemin kalbidir. Modbus TCP bağlantılarını yönetir, okuma döngülerini (polling) çalıştırır ve verileri parse eder.

veritabani.py: SQLite (veya tercih edilen DB) bağlantılarını, kayıt ekleme işlemlerini ve eski verileri temizleme rotinlerini barındırır.

utils.py: Negatif değerler için bit kaydırma (signed 16-bit) ve sıcaklık/ondalık dönüştürme gibi yardımcı matematiksel fonksiyonları içerir.

API ve WebSocket (Varsa): Toplanan veriler WS_NOTIFY_URL üzerinden diğer frontend panellerinin anlık olarak güncellenmesini sağlar.

📄 Lisans
Bu proje özel kullanım için geliştirilmiştir. İzinsiz kopyalanamaz veya ticari amaçlarla dağıtılamaz.