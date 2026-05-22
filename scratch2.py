from datetime import datetime, timedelta
import veritabani

secilen_tarih = datetime.now()
grafik_gun = 7

for i in range(grafik_gun - 1, -1, -1):
    gun_tarih = (secilen_tarih - timedelta(days=i)).strftime('%Y-%m-%d')
    uretim = veritabani.gunluk_uretim_hesapla(gun_tarih, slave_id=None, fabrika_id='mekanik')
    print(gun_tarih, uretim)
