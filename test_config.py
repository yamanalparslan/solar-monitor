import os
import logging
from unittest.mock import patch
import pytest

# config modülündeki metotları ve sınıfları içe aktar
from config import _env, _env_bool, _env_int, _env_float, Config, setup_logging, config

def test_env_functions():
    with patch.dict(os.environ, {"TEST_KEY": "123", "TEST_BOOL": "true", "TEST_FLOAT": "12.5"}):
        assert _env("TEST_KEY") == "123"
        assert _env("NON_EXISTENT", "default") == "default"
        
        assert _env_bool("TEST_BOOL") is True
        assert _env_bool("NON_EXISTENT_BOOL", False) is False
        assert _env_bool("TEST_KEY") is False # "123" is not "true", "1", "yes"
        
        assert _env_int("TEST_KEY") == 123
        assert _env_int("NON_EXISTENT_INT", 99) == 99
        assert _env_int("TEST_FLOAT") == 0 # invalid int parse falls back to default 0
        
        assert _env_float("TEST_FLOAT") == 12.5
        assert _env_float("NON_EXISTENT_FLOAT", 1.5) == 1.5

def test_config_dataclass_defaults():
    with patch.dict(os.environ, clear=True):
        # Ortam değişkenleri boşken Config varsayılanları doğru almalı
        c = Config()
        assert c.MODBUS_IP == "127.0.0.1"
        assert c.MODBUS_PORT == 5020
        assert c.SLAVE_IDS == "1,2,3"
        assert c.REFRESH_RATE == 2.0
        assert c.MQTT_ENABLED is False
        assert c.AUTH_ENABLED is True

def test_config_custom_values():
    with patch.dict(os.environ, {
        "MODBUS_IP": "192.168.1.10",
        "MODBUS_PORT": "502",
        "AUTH_ENABLED": "false"
    }):
        c = Config()
        assert c.MODBUS_IP == "192.168.1.10"
        assert c.MODBUS_PORT == 502
        assert c.AUTH_ENABLED is False

def test_setup_logging():
    logger = setup_logging("test_logger")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger"
    
    # Handlers listesi boş olmamalı
    assert len(logger.handlers) > 0
    assert isinstance(logger.handlers[0], logging.StreamHandler)
