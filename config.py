"""
Solar Monitor - Konfigürasyon Yöneticisi
==========================================
.env dosyasından ortam değişkenlerini yükler.
Veritabanı, Modbus, MQTT ve loglama ayarlarını sağlar.

Kullanım:
    from config import config, setup_logging
    logger = setup_logging("modul_adi")
"""

import os
import logging
from dataclasses import dataclass, field

# .env dosyasını yükle (dotenv varsa)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv yoksa os.environ kullanılır


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("true", "1", "yes")


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float = 0.0) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


@dataclass
class Config:
    """Uygulama konfigürasyonu (.env'den yüklenir)."""

    # --- Modbus ---
    MODBUS_IP: str = field(default_factory=lambda: _env("MODBUS_IP", "127.0.0.1"))
    MODBUS_PORT: int = field(default_factory=lambda: _env_int("MODBUS_PORT", 5020))
    SLAVE_IDS: str = field(default_factory=lambda: _env("SLAVE_IDS", "1,2,3"))
    REFRESH_RATE: float = field(default_factory=lambda: _env_float("REFRESH_RATE", 2))

    # --- Register Adresleri ---
    GUC_ADDR: int = field(default_factory=lambda: _env_int("GUC_ADDR", 70))
    VOLT_ADDR: int = field(default_factory=lambda: _env_int("VOLT_ADDR", 71))
    AKIM_ADDR: int = field(default_factory=lambda: _env_int("AKIM_ADDR", 72))
    ISI_ADDR: int = field(default_factory=lambda: _env_int("ISI_ADDR", 74))

    # --- Çarpanlar ---
    GUC_SCALE: float = field(default_factory=lambda: _env_float("GUC_SCALE", 1.0))
    VOLT_SCALE: float = field(default_factory=lambda: _env_float("VOLT_SCALE", 1.0))
    AKIM_SCALE: float = field(default_factory=lambda: _env_float("AKIM_SCALE", 0.1))
    ISI_SCALE: float = field(default_factory=lambda: _env_float("ISI_SCALE", 1.0))

    # --- Veritabanı ---
    DB_NAME: str = field(default_factory=lambda: _env("DB_NAME", "solar_log.db"))

    # --- Loglama ---
    LOG_LEVEL: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))

    # --- MQTT ---
    MQTT_ENABLED: bool = field(default_factory=lambda: _env_bool("MQTT_ENABLED", False))
    MQTT_HOST: str = field(default_factory=lambda: _env("MQTT_HOST", "localhost"))
    MQTT_PORT: int = field(default_factory=lambda: _env_int("MQTT_PORT", 1883))
    MQTT_TOPIC: str = field(default_factory=lambda: _env("MQTT_TOPIC", "solar/telemetry"))

    # --- Authentication ---
    AUTH_ENABLED: bool = field(default_factory=lambda: _env_bool("AUTH_ENABLED", True))
    AUTH_USERNAME: str = field(default_factory=lambda: _env("AUTH_USERNAME", "admin"))
    AUTH_PASSWORD_HASH: str = field(default_factory=lambda: _env("AUTH_PASSWORD_HASH", ""))

    # --- Bildirimler ---
    TELEGRAM_ENABLED: bool = field(default_factory=lambda: _env_bool("TELEGRAM_ENABLED", False))
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN", ""))
    TELEGRAM_CHAT_ID: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID", ""))

    # --- CRM Entegrasyonu ---
    CRM_BASE_URL: str = field(default_factory=lambda: _env("CRM_BASE_URL", "xxxxx"))
    CRM_API_KEY: str = field(default_factory=lambda: _env("CRM_API_KEY", "xxxxx"))
    CRM_API_SECRET: str = field(default_factory=lambda: _env("CRM_API_SECRET", "xxxxx"))
    CRM_TENANT_ID: str = field(default_factory=lambda: _env("CRM_TENANT_ID", "xxxxx"))
    CRM_USERNAME: str = field(default_factory=lambda: _env("CRM_USERNAME", "xxxxx"))
    CRM_PASSWORD: str = field(default_factory=lambda: _env("CRM_PASSWORD", "xxxxx"))
    CRM_ALLOWED_ORIGIN: str = field(default_factory=lambda: _env("CRM_ALLOWED_ORIGIN", "xxxxx"))
    SOLAR_MONITOR_EXTERNAL_URL: str = field(default_factory=lambda: _env("SOLAR_MONITOR_EXTERNAL_URL", "xxxxx"))
    CRM_WEBHOOK_URL: str = field(default_factory=lambda: _env("CRM_WEBHOOK_URL", "xxxxx"))
    CRM_WEBHOOK_SECRET: str = field(default_factory=lambda: _env("CRM_WEBHOOK_SECRET", "xxxxx"))
    CRM_EMBED_MODE: bool = field(default_factory=lambda: _env_bool("CRM_EMBED_MODE", True))


def setup_logging(name: str = "solar_monitor") -> logging.Logger:
    """Modül bazlı logger oluşturur.

    Args:
        name: Logger adı (modül ismi)

    Returns:
        Yapılandırılmış logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
        logger.setLevel(level)

        handler = logging.StreamHandler()
        handler.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Singleton instance
config = Config()
