# Solar Monitor - Endüstriyel Invertör Veri Toplayıcı ☀️

Solar Monitor, Modbus (TCP/RS485) protokolü üzerinden endüstriyel güneş enerjisi invertörlerinden (Örn: Pulsar) telemetri verilerini (Voltaj, Akım, Güç, Sıcaklık ve Alarmlar) okuyan, kaydeden ve izlenmesini sağlayan senkron bir Python/Docker servisidir.

## 🚀 Yeni Versiyon Özellikleri

*   **Dinamik Blok Okuma (Dynamic Block Read):** RS485 hattını yoran "parçalı sorgular" yerine, ortam değişkenlerinde (.env) belirtilen adres aralıklarını otomatik hesaplar ve verileri **tek bir paket halinde** okur. Bu sayede timeout, veri kaybı ve sahte 0 değerleri tamamen engellenmiştir.
*   **Sıralı Sorgulama (Sequential Polling):** Half-Duplex RS485 hattında sinyal çakışmasını (collision) önlemek için birden fazla IP adresini sırayla ve güvenli bekleme süreleriyle (inter-frame gap) sorgular.
*   **Hata Toleransı (Fallback & Retry):** Veri okunamadığında veritabanını sahte "0" değerleriyle kirletmez. Belirlenen `max_retries` sayısınca yeniden dener.
*   **Otomatik Temizlik (Retention Policy):** Belirlenen gün sayısından (`veri_saklama_gun`) eski olan logları veritabanından otomatik olarak temizler.
*   **Tamamen Dockerize:** Tek komutla tüm bağımlılıklarıyla birlikte ayağa kalkar.

## 🛠 Kurulum ve Çalıştırma

### 1. Ortam Değişkenlerini Ayarlama
Proje dizininde bulunan `.env.example` dosyasının adını `.env` olarak değiştirin (veya yeni bir `.env` dosyası oluşturun) ve içerisindeki ayarları kendi sahanıza göre düzenleyin:
```ini
# --- Modbus Bağlantısı ---
TARGET_IPS=10.35.14.10, 10.35.14.11
MODBUS_PORT=502
SLAVE_ID=1

# --- Zamanlayıcı ---
# Modbus hattını şişirmemek için min 5 saniye önerilir.
REFRESH_RATE=5

# --- Register Adresleri (Pymodbus 0-Tabanlıdır, Dokümandan 1 eksik girin) ---
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