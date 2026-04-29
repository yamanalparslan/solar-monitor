import pytest
from datetime import datetime

from models import OlcumVerisi, CihazDurumu, FAULT_MAP_107, FAULT_MAP_109, FAULT_MAP_111, FAULT_MAP_112, FAULT_MAP_114, FAULT_MAP_115, FAULT_MAP_116, FAULT_MAP_117, FAULT_MAP_118, FAULT_MAP_119, FAULT_MAP_120, FAULT_MAP_121, FAULT_MAP_122

def test_fault_maps():
    assert len(FAULT_MAP_107) > 0
    assert len(FAULT_MAP_109) > 0
    assert len(FAULT_MAP_111) > 0
    assert len(FAULT_MAP_112) > 0
    assert len(FAULT_MAP_114) > 0
    assert len(FAULT_MAP_115) > 0
    assert len(FAULT_MAP_116) > 0
    assert len(FAULT_MAP_117) > 0
    assert len(FAULT_MAP_118) > 0
    assert len(FAULT_MAP_119) > 0
    assert len(FAULT_MAP_120) > 0
    assert len(FAULT_MAP_121) > 0
    assert len(FAULT_MAP_122) > 0
    assert 0 in FAULT_MAP_107
    assert "DC Overcurrent" in FAULT_MAP_107[0]
    assert 0 in FAULT_MAP_109
    assert "Abnormal String" in FAULT_MAP_109[0]
    assert 0 in FAULT_MAP_112
    assert "String Reverse Connection" in FAULT_MAP_112[0]
    assert 0 in FAULT_MAP_114
    assert "String Current Backfeed" in FAULT_MAP_114[0]
    assert 0 in FAULT_MAP_115
    assert "Low Insulation Resistance MPPT" in FAULT_MAP_115[0]
    assert 0 in FAULT_MAP_116
    assert 0 in FAULT_MAP_117
    assert 0 in FAULT_MAP_118
    assert 0 in FAULT_MAP_119
    assert 0 in FAULT_MAP_120
    assert 0 in FAULT_MAP_121
    assert 0 in FAULT_MAP_122
    assert "Insufficient DC voltage" in FAULT_MAP_122[0]

def test_olcum_verisi_to_dict():
    data = OlcumVerisi(
        slave_id=1,
        guc=100.5,
        voltaj=220.0,
        akim=5.2,
        sicaklik=45.0,
        hata_kodu=0,
        hata_kodu_109=0,
        hata_kodu_111=0,
        hata_kodu_112=0,
        hata_kodu_114=0,
        hata_kodu_115=0,
        hata_kodu_116=0,
        hata_kodu_117=0,
        hata_kodu_118=0,
        hata_kodu_119=0,
        hata_kodu_120=0,
        hata_kodu_121=0,
        hata_kodu_122=0,
        zaman="2026-04-20 12:00:00"
    )
    
    data_dict = data.to_dict()
    assert data_dict["slave_id"] == 1
    assert data_dict["guc"] == 100.5
    assert data_dict["zaman"] == "2026-04-20 12:00:00"

def test_cihaz_durumu_properties():
    # Aktif ve has_error false
    cihaz_normal = CihazDurumu(
        slave_id=1,
        guc=1000.0,
        hata_kodu=0,
        hata_kodu_111=0
    )
    assert cihaz_normal.has_error is False
    assert cihaz_normal.durum_text == "AKTİF"

    # Beklemede (guc 0)
    cihaz_beklemede = CihazDurumu(
        slave_id=2,
        guc=0.0,
        hata_kodu=0,
        hata_kodu_111=0
    )
    assert cihaz_beklemede.has_error is False
    assert cihaz_beklemede.durum_text == "BEKLEMEDE"

    # Arizali
    cihaz_arizali = CihazDurumu(
        slave_id=3,
        guc=0.0,
        hata_kodu=1,
        hata_kodu_109=0,
        hata_kodu_111=0
    )
    assert cihaz_arizali.has_error is True
    assert cihaz_arizali.durum_text == "ARIZA"
    
    cihaz_arizali_109 = CihazDurumu(
        slave_id=4,
        guc=500.0,
        hata_kodu=0,
        hata_kodu_109=2,
        hata_kodu_111=0
    )
    assert cihaz_arizali_109.has_error is True
    assert cihaz_arizali_109.durum_text == "ARIZA"
    
    cihaz_arizali_111 = CihazDurumu(
        slave_id=5,
        guc=500.0,
        hata_kodu=0,
        hata_kodu_109=0,
        hata_kodu_111=5,
        hata_kodu_112=0
    )
    assert cihaz_arizali_111.has_error is True
    assert cihaz_arizali_111.durum_text == "ARIZA"
    
    cihaz_arizali_112 = CihazDurumu(
        slave_id=6,
        guc=500.0,
        hata_kodu=0,
        hata_kodu_109=0,
        hata_kodu_111=0,
        hata_kodu_112=1,
        hata_kodu_114=0
    )
    assert cihaz_arizali_112.has_error is True
    assert cihaz_arizali_112.durum_text == "ARIZA"
    
    cihaz_arizali_114 = CihazDurumu(
        slave_id=7,
        guc=500.0,
        hata_kodu=0,
        hata_kodu_109=0,
        hata_kodu_111=0,
        hata_kodu_112=0,
        hata_kodu_114=8,
        hata_kodu_115=0
    )
    assert cihaz_arizali_114.has_error is True
    assert cihaz_arizali_114.durum_text == "ARIZA"
    
    cihaz_arizali_115 = CihazDurumu(
        slave_id=8,
        guc=500.0,
        hata_kodu=0,
        hata_kodu_109=0,
        hata_kodu_111=0,
        hata_kodu_112=0,
        hata_kodu_114=0,
        hata_kodu_115=1,
        hata_kodu_116=0
    )
    assert cihaz_arizali_115.has_error is True
    assert cihaz_arizali_115.durum_text == "ARIZA"
    
    cihaz_arizali_116 = CihazDurumu(
        slave_id=8,
        guc=500.0,
        hata_kodu=0,
        hata_kodu_109=0,
        hata_kodu_111=0,
        hata_kodu_112=0,
        hata_kodu_114=0,
        hata_kodu_115=0,
        hata_kodu_116=1,
        hata_kodu_117=0,
        hata_kodu_118=0,
        hata_kodu_119=0,
        hata_kodu_120=0,
        hata_kodu_121=0,
        hata_kodu_122=0
    )
    assert cihaz_arizali_116.has_error is True
    assert cihaz_arizali_116.durum_text == "ARIZA"

