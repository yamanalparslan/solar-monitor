#!/usr/bin/env python3
"""
HATA KODU ANALİZ ARACI
Bu script, inverter hata kodlarını bit bazında çözümler
"""

def hata_kodu_analiz(kod_107, kod_111):
    """
    Hata kodlarını 32-bit binary'ye çevirip analiz eder
    """
    print("=" * 60)
    print("🔧 HATA KODU DETAY ANALİZİ")
    print("=" * 60)
    
    # Register 107 Analizi (DC Faults)
    print(f"\n📌 Register 107 (DC Arızaları): {kod_107}")
    print(f"   Binary: {bin(kod_107)[2:].zfill(32)}")
    print(f"   Hex: 0x{kod_107:08X}")
    
    # Bit bazında kontrol (örnek)
    dc_hatalari = {
        0: "PV1 Ters Akım",
        1: "PV2 Ters Akım", 
        2: "PV1 Aşırı Voltaj",
        3: "PV2 Aşırı Voltaj",
        4: "PV1 Düşük Voltaj",
        5: "PV2 Düşük Voltaj",
        6: "DC Bus Aşırı Voltaj",
        7: "DC Bus Düşük Voltaj",
        8: "Topraklama Hatası",
        9: "İzolasyon Hatası",
        10: "PV1 Kısa Devre",
        11: "PV2 Kısa Devre"
    }
    
    print("\n   Aktif Hatalar (Register 107):")
    hata_var = False
    for bit_no, aciklama in dc_hatalari.items():
        if kod_107 & (1 << bit_no):
            print(f"   ⚠️  Bit {bit_no}: {aciklama}")
            hata_var = True
    
    if not hata_var:
        print("   ✅ DC tarafında aktif hata yok")
    
    # Register 111 Analizi (Diğer Alarmlar)
    print(f"\n📌 Register 111 (Sistem Alarmları): {kod_111}")
    print(f"   Binary: {bin(kod_111)[2:].zfill(32)}")
    print(f"   Hex: 0x{kod_111:08X}")
    
    sistem_hatalari = {
        0: "AC Aşırı Voltaj",
        1: "AC Düşük Voltaj",
        2: "AC Frekans Yüksek",
        3: "AC Frekans Düşük",
        4: "Aşırı Isınma",
        5: "Fan Arızası",
        6: "Grid Bağlantı Hatası",
        7: "İletişim Hatası",
        8: "Güç Sınırlama Aktif"
    }
    
    print("\n   Aktif Hatalar (Register 111):")
    hata_var = False
    for bit_no, aciklama in sistem_hatalari.items():
        if kod_111 & (1 << bit_no):
            print(f"   ⚠️  Bit {bit_no}: {aciklama}")
            hata_var = True
    
    if not hata_var:
        print("   ✅ Sistem alarmı yok")
    
    print("\n" + "=" * 60)

# Test
if __name__ == "__main__":
    print("\n🔍 ID 1 İNVERTER HATA ANALİZİ\n")
    hata_kodu_analiz(kod_107=52, kod_111=73)
    
    print("\n\n💡 ÖNERİLER:")
    print("-" * 60)
    print("1. İnverterin kullanım kılavuzundaki hata kod tablosuna bakın")
    print("2. Yukarıdaki bit analizini kullanarak hangi hatanın aktif olduğunu belirleyin")
    print("3. Panel voltajlarını DC multimetre ile ölçün")
    print("4. Topraklama bağlantısını kontrol edin")
    print("5. İnverteri restart edin ve hata devam ederse servis çağırın")
    print("-" * 60)