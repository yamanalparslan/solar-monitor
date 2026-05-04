"""
Solar Monitor - MQTT Listener
==============================
Uzak sensörlerden veya Modbus dışı bağımsız cihazlardan gelen verileri
Mosquitto broker üzerinden dinler ve SQLite veritabanımıza köprüler.
"""

import paho.mqtt.client as mqtt
import json
import logging
import veritabani
from config import config, setup_logging

logger = setup_logging("mqtt_listener")

def on_connect(client, userdata, flags, rc):
    """Broker bağlantısı kurulduğunda tetiklenir."""
    if rc == 0:
        logger.info(f"MQTT Broker'a ({config.MQTT_HOST}:{config.MQTT_PORT}) baglanti kuruldu.")
        # Doğrudan belirlenen topic'e abone ol (config.MQTT_TOPIC veya solar/telemetry/# etc.)
        client.subscribe(config.MQTT_TOPIC)
        logger.info(f"Abone olundu: '{config.MQTT_TOPIC}'")
    else:
        logger.error(f"Baglanti hatasi, RC Kodu: {rc}")

def on_message(client, userdata, msg):
    """Herhangi bir kanaldan mesaj geldiğinde tetiklenir."""
    try:
        payload = msg.payload.decode('utf-8')
        logger.debug(f"Mesaj Alindi [{msg.topic}]: {payload}")
        
        # Beklenen JSON Formatı:
        # {"slave_id": 10, "guc": 1500, "voltaj": 220, "akim": 6.8, "sicaklik": 45.2, "hata_kodu": 0, "hata_kodu_193": 0}
        veri = json.loads(payload)
        
        slave_id = veri.get("slave_id")
        if slave_id is None:
            logger.warning("Mesaj islenemedi: 'slave_id' eksik.")
            return

        # Zorunlu alanları default 0 ile geçir (dict.get kullanarak)
        data = {
            "guc": float(veri.get("guc", 0)),
            "voltaj": float(veri.get("voltaj", 0)),
            "akim": float(veri.get("akim", 0)),
            "sicaklik": float(veri.get("sicaklik", 0)),
            "hata_kodu": int(veri.get("hata_kodu", 0)),
            "hata_kodu_193": int(veri.get("hata_kodu_193", 0))
        }

        # Veritabanına yaz
        veritabani.veri_ekle(slave_id, data)
        logger.info(f"MQTT Verisi (ID {slave_id}) DB'ye Eklendi.")
        
    except json.JSONDecodeError:
        logger.error(f"Gelen isimsiz payload gecerli bir JSON degil: {msg.payload}")
    except Exception as e:
        logger.error(f"MQTT isleme hatasi: {e}")

def start_mqtt_listener():
    """MQTT istemcisini başlatıp broker'ı dinlemeye alır."""
    if not config.MQTT_ENABLED:
        logger.warning("Ayarlarda MQTT_ENABLED = False. Dinleyici baslatilmayacak.")
        return

    veritabani.init_db()
    
    # İstemci ayarları
    client = mqtt.Client(client_id="SolarMonitor_Server", clean_session=True)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(config.MQTT_HOST, config.MQTT_PORT, 60)
        
        # loop_forever threadi kitler ve sürekli arkada dinler.
        client.loop_forever()
    except ConnectionRefusedError:
        logger.critical(f"Broker'a erisilemiyor: {config.MQTT_HOST}:{config.MQTT_PORT}")
    except Exception as e:
        logger.error(f"MQTT Baslatma Hatasi: {e}")

if __name__ == "__main__":
    start_mqtt_listener()
