import pytest
from unittest.mock import patch, MagicMock

from notifications import NotificationManager

@patch('notifications.config')
def test_send_alert_disabled(mock_config):
    mock_config.TELEGRAM_ENABLED = False
    
    nm = NotificationManager()
    # Eger sistem kapaliysa gondermeyi red edip False dönmeli
    assert nm.send_alert("Test Başlık", "Test Gövde") is False

@patch('notifications.config')
@patch('notifications.requests.post')
def test_send_alert_success(mock_post, mock_config):
    # Telegram acik ve valid ayarlar verildi
    mock_config.TELEGRAM_ENABLED = True
    mock_config.TELEGRAM_BOT_TOKEN = "TEST_TOKEN"
    mock_config.TELEGRAM_CHAT_ID = "TEST_CHAT_ID"
    
    # API'nin 200 basarili bir yanit urettigini simule edelim
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    
    nm = NotificationManager()
    
    # Bu durumda gondermenin basarili (True) donmesi lazim
    result = nm.send_alert("Cihaz Ariza", "ID 1 koptu")
    assert result is True
    
    # Payload formatini dogrula
    call_args = mock_post.call_args[1]
    assert call_args["json"]["chat_id"] == "TEST_CHAT_ID"
    assert "SOLAR UYARI" in call_args["json"]["text"]

@patch('notifications.config')
@patch('notifications.requests.post')
def test_send_alert_api_error(mock_post, mock_config):
    # Ayarlar dogru ama Telegram karsi taraftan hata uretti
    mock_config.TELEGRAM_ENABLED = True
    mock_config.TELEGRAM_BOT_TOKEN = "TEST"
    mock_config.TELEGRAM_CHAT_ID = "TEST"
    
    mock_response = MagicMock()
    mock_response.status_code = 401 # Yetkisiz Hatasi
    mock_post.return_value = mock_response
    
    nm = NotificationManager()
    assert nm.send_alert("Uyarı", "Hatalı çağrı") is False
