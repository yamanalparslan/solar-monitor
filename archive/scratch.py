import veritabani
ayarlar = veritabani.tum_ayarlari_oku("uretim")
print("Uretim ayarları:")
print(ayarlar)
from veritabani import tum_cihazlarin_son_durumu
son_durum = tum_cihazlarin_son_durumu("uretim")
print(f"Uretim son durum {len(son_durum)} kayit: {son_durum}")
