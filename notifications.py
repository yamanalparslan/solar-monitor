"""
Solar Monitor - Bildirim Yönetimi
==========================
Kritik durumlarda veya anomalilerde kullanıcıları bilgilendirir.
Telegram arayüzü entegrasyonu sunar.
"""

import logging
import requests
from config import config, setup_logging

logger = setup_logging("notifications")

class NotificationManager:
    def __init__(self):
        self.enabled = config.TELEGRAM_ENABLED
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_alert(self, subject: str, message: str) -> bool:
        """
        Telegram üzerine uyarı bildirimleri yollar.
        
        Args:
            subject: Uyarı Başlığı
            message: Hata detayı
        Returns:
            bool: Gönderim başarı durumu
        """
        formatted_msg = f"⚠️ *SOLAR UYARI: {subject}*\n\n{message}"
        
        # Log default
        logger.info(f"Bildirim Kuyruguna Eklendi: {subject}")
        
        if not self.enabled:
            logger.debug("Telegram ayarlari aktif degil. Sadece loglandi.")
            return False
            
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram aktif fakat token veya chat ID bulunamadi.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": formatted_msg,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=5)
            if response.status_code == 200:
                logger.info("Telegram bildirimi basariyla gonderildi.")
                return True
            else:
                logger.error(f"Telegram API hatası: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram bildirim denemesi sirasinda hata: {e}")
            return False

# Pratik kullanim icin singleton instance
notifier = NotificationManager()
