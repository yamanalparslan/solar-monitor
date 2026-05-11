import asyncio
import logging
import math
import random
import sys  # Sistem platformunu ve stdout ayarlarını kontrol etmek için eklendi
from datetime import datetime
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.server import StartAsyncTcpServer

# --- AYARLAR ---
TEST_IP = "127.0.0.1"
TEST_PORT = 5020

# Simülasyon Parametreleri
MAX_GUC_KAPASITESI = 3000  # 3000 Watt (3kW) panel
TOPLAM_URETIM_WH = 12500   # Sayac 12.5 kWh'den baslasin

# --- FIZIKSEL SIMULASYON MANTIGI ---
def veri_uret():
    global TOPLAM_URETIM_WH
    
    simdi = datetime.now()
    
    # --- YENİ ZAMAN ALGORİTMASI (6 DAKİKALIK DÖNGÜ) ---
    # Hedef: Gerçek hayattaki 6 dakika (360 saniye) = Sanal 24 saat (1440 dakika)
    DONGU_SURESI_SN = 360 
    
    # Şu anki zamanı saniye cinsinden alıp 360'a göre modunu alıyoruz.
    # Bu bize 0 ile 359 arasında sürekli dönen bir sayaç verir.
    toplam_saniye = simdi.minute * 60 + simdi.second
    dongu_saniyesi = toplam_saniye % DONGU_SURESI_SN
    
    # Gerçek saniyeyi sanal dakikaya çevir (Oran: 1440 / 360 = 4)
    # Yani gerçekte 1 saniye geçince, simülasyonda 4 dakika geçecek.
    sanal_zaman = dongu_saniyesi * 4 
    
    # --- UZUN GÜNDÜZ AYARLARI ---
    # Güneş 04:00 (240. dk) doğsun, 20:00 (1200. dk) batsın.
    # Gündüz süresi 16 saat, Gece süresi 8 saat olur.
    GUN_DOGUSU = 240  # 04:00
    GUN_BATIMI = 1200 # 20:00
    
    gunes_faktoru = 0
    
    # Eğer sanal saat gündüz aralığındaysa
    if GUN_DOGUSU < sanal_zaman < GUN_BATIMI:
        # Sinüs dalgası oluştur (0'dan başla, 1'e çık, 0'a in)
        radyan = math.pi * (sanal_zaman - GUN_DOGUSU) / (GUN_BATIMI - GUN_DOGUSU)
        gunes_faktoru = math.sin(radyan)
    
    # Bulut etkisi (Ara sira gunes kapansin - %10 dalgalanma)
    bulut = random.uniform(0.9, 1.0) 
    
    # --- DEGERLERI HESAPLA ---
    
    # GUC (Watt): Kapasite x Gunes x Bulut
    anlik_guc_w = int(MAX_GUC_KAPASITESI * gunes_faktoru * bulut)
    
    # VOLTAJ (V): 220V etrafinda hafif oynar
    voltaj = int(random.uniform(218, 235))
    
    # AKIM (A): Guc / Voltaj (P=V*I)
    if voltaj > 0:
        akim_x10 = int((anlik_guc_w / voltaj) * 10) 
    else:
        akim_x10 = 0
        
    # SICAKLIK (C): 
    # Gece soğusun (15C), Gündüz ısınsın (Maks 55C)
    if anlik_guc_w > 0:
        sicaklik = 25 + int((anlik_guc_w / MAX_GUC_KAPASITESI) * 30)
    else:
        sicaklik = 15 # Gece ortam sıcaklığı
    
    # TOPLAM URETIM (Watt-Saat)
    # Hızlı döngü olduğu için üretimi biraz abartarak ekleyelim ki sayaç dönsün
    TOPLAM_URETIM_WH += anlik_guc_w / 1000 
    
    # Sanal Saati Hesapla (Ekrana yazdırmak için)
    sanal_saat = int(sanal_zaman // 60)
    sanal_dakika = int(sanal_zaman % 60)
    
    # Listeye sanal saati de ekleyelim (Log için)
    return [voltaj, akim_x10, anlik_guc_w, int(TOPLAM_URETIM_WH), sicaklik, f"{sanal_saat:02}:{sanal_dakika:02}"]

# --- MODBUS SUNUCU GOREVI ---
async def veri_guncelleyici(context):
    """Bu fonksiyon her saniye arkaplanda calisip inverter hafizalarini gunceller"""
    SLAVE_IDS = [1, 2, 3]
    while True:
        sanal_saat_str = ""
        for slave_id in SLAVE_IDS:
            veriler = veri_uret()
            sanal_saat_str = veriler[5]
            
            # Modbus'a yazilacak sayisal veriler (Son eleman string oldugu icin onu almiyoruz)
            modbus_verisi = veriler[:5]  # [voltaj, akim_x10, guc, toplam_uretim, sicaklik]
            
            store = context[slave_id]
            
            # Panel ayarlarına uygun register adresleri:
            # Register 70: Güç (W)
            # Register 71: Voltaj (V)
            # Register 72: Akım (A x10)
            # Register 73: Toplam Üretim (Wh)
            # Register 74: Sıcaklık (°C)
            store.setValues(3, 70, [modbus_verisi[2]])  # Güç
            store.setValues(3, 71, [modbus_verisi[0]])  # Voltaj
            store.setValues(3, 72, [modbus_verisi[1]])  # Akım
            store.setValues(3, 73, [modbus_verisi[3]])  # Toplam Üretim
            store.setValues(3, 74, [modbus_verisi[4]])  # Sıcaklık
            
            # Hata register'ları (2 register'lık 32-bit değer)
            store.setValues(3, 107, [0, 0])  # Hata yok
            store.setValues(3, 111, [0, 0])  # Hata yok
            
        # Log basalim (Sadece bir cihazı örnek göstersin, ekran dolmasın)
        print(f"🕒 {sanal_saat_str} | ☀️  (ID:1) Guc: {modbus_verisi[2]} W | 🌡️  Isi: {modbus_verisi[4]} C | ⚡ {modbus_verisi[0]} V")
        
        await asyncio.sleep(1)

async def sunucuyu_calistir():
    # 3 farkli inverter simulasyonu icin 3 ayri hafiza olustur
    slaves = {
        1: ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, [0]*200)),
        2: ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, [0]*200)),
        3: ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, [0]*200))
    }
    context = ModbusServerContext(slaves=slaves, single=False)

    print(f"✅ AKILLI INVERTER DEVREDE ({TEST_IP}:{TEST_PORT}) - Slave ID'ler: 1, 2, 3")
    print("⏳ DÖNGÜ: 6 Dakika (16 Saat Gündüz / 8 Saat Gece)")
    print("-" * 50)

    # Arka plan gorevini baslat (Veri uretimi)
    task = asyncio.create_task(veri_guncelleyici(context))
    
    # Serveri baslat (Pymodbus 3.8.6 API)
    await StartAsyncTcpServer(context=context, address=(TEST_IP, TEST_PORT))

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    try:
        # Windows CMD ekranında emojilerin çökmeye yol açmaması için UTF-8 formatlaması:
        if sys.platform == "win32" and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            
        asyncio.run(sunucuyu_calistir())
    except KeyboardInterrupt:
        print("\nKapatildi.")
    except Exception as e:
        # Farklı bir hata olursa pencere kapanmasın diye bekleterek hatayı ekrana bas:
        print(f"\nSISTEM HATASI: {e}")
        input("Pencereyi kapatmak icin Enter'a basin...")