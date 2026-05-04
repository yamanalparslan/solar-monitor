import time
from pymodbus.client import ModbusTcpClient

# AYARLAR
TARGET_IP = "10.35.14.10"
PORT = 502
TARAMA_ARALIGI = range(1, 10) # 1'den 9'a kadar olan ID'leri tara

def cihazlari_tara():
    print(f"[*] Modbus Agi Taraniyor ({TARGET_IP})...")
    print("-" * 40)
    
    client = ModbusTcpClient(TARGET_IP, port=PORT, timeout=0.5) # Kisa timeout
    client.connect()

    bulunanlar = []

    for slave_id in TARAMA_ARALIGI:
        print(f"Sorgulaniyor: ID {slave_id}...", end=" ")
        
        # Basit bir okuma denemesi (Orn: Voltaj adresi 71)
        try:
            rr = client.read_holding_registers(71, count=1, slave=slave_id)
            if not rr.isError():
                print("[+] BULUNDU!")
                bulunanlar.append(slave_id)
            else:
                print("[-] Cevap Yok")
        except Exception as e:
            print(f"Hata: {e}")
            
    client.close()
    
    print("-" * 40)
    print(f"[SONUC] Toplam {len(bulunanlar)} cihaz bulundu.")
    print(f"[LISTE] Bulunan ID'ler: {bulunanlar}")

if __name__ == "__main__":
    cihazlari_tara()