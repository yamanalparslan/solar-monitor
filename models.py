"""
Solar Monitor - Veri Modelleri & Hata Kod Haritaları
=====================================================
Modbus register hata kodlarının açıklamalarını ve
veri yapılarını tanımlar.

Kullanım:
    from models import FAULT_MAP_107, FAULT_MAP_111
    aciklama = FAULT_MAP_107.get(bit_no, "Bilinmeyen")
"""

from dataclasses import dataclass, field
from datetime import datetime


# ══════════════════════════════════════════════════════════════
# REGISTER 107 — 32-bit Hata Kodu Haritası (Bit bazlı)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_107: dict[int, str] = {
    0:  "DC Overcurrent Fault [1-1]",
    1:  "DC Overcurrent Fault [1-2]",
    2:  "DC Overcurrent Fault [2-1]",
    3:  "DC Overcurrent Fault [2-2]",
    4:  "DC Overcurrent Fault [3-1]",
    5:  "DC Overcurrent Fault [3-2]",
    6:  "DC Overcurrent Fault [4-1]",
    7:  "DC Overcurrent Fault [4-2]",
    8:  "DC Overcurrent Fault [5-1]",
    9:  "DC Overcurrent Fault [5-2]",
    10: "DC Overcurrent Fault [6-1]",
    11: "DC Overcurrent Fault [6-2]",
    12: "DC Overcurrent Fault [7-1]",
    13: "DC Overcurrent Fault [7-2]",
    14: "DC Overcurrent Fault [8-1]",
    15: "DC Overcurrent Fault [8-2]",
    16: "DC Overcurrent Fault [9-1]",
    17: "DC Overcurrent Fault [9-2]",
    18: "DC Overcurrent Fault [10-1]",
    19: "DC Overcurrent Fault [10-2]",
    20: "DC Overcurrent Fault [11-1]",
    21: "DC Overcurrent Fault [11-2]",
    22: "DC Overcurrent Fault [12-1]",
    23: "DC Overcurrent Fault [12-2]",
}

# ══════════════════════════════════════════════════════════════
# REGISTER 109 — 32-bit Hata Kodu Haritası (Bit bazlı)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_109: dict[int, str] = {
    0:  "Abnormal String Power [1-1]",
    1:  "Abnormal String Power [1-2]",
    2:  "Abnormal String Power [2-1]",
    3:  "Abnormal String Power [2-2]",
    4:  "Abnormal String Power [3-1]",
    5:  "Abnormal String Power [3-2]",
    6:  "Abnormal String Power [4-1]",
    7:  "Abnormal String Power [4-2]",
    8:  "Abnormal String Power [5-1]",
    9:  "Abnormal String Power [5-2]",
    10: "Abnormal String Power [6-1]",
    11: "Abnormal String Power [6-2]",
    12: "Abnormal String Power [7-1]",
    13: "Abnormal String Power [7-2]",
    14: "Abnormal String Power [8-1]",
    15: "Abnormal String Power [8-2]",
    16: "Abnormal String Power [9-1]",
    17: "Abnormal String Power [9-2]",
    18: "Abnormal String Power [10-1]",
    19: "Abnormal String Power [10-2]",
    20: "Abnormal String Power [11-1]",
    21: "Abnormal String Power [11-2]",
    22: "Abnormal String Power [12-1]",
    23: "Abnormal String Power [12-2]",
    24: "Spare",
    25: "Spare",
    26: "Spare",
    27: "Spare",
    28: "Spare",
    29: "Spare",
    30: "Spare",
    31: "Spare",
}

# ══════════════════════════════════════════════════════════════
# REGISTER 111 — 16-bit Hata Kodu Haritası (Bit bazlı)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_111: dict[int, str] = {
    0:  "PV Overvoltage [1]",
    1:  "PV Overvoltage [2]",
    2:  "PV Overvoltage [3]",
    3:  "PV Overvoltage [4]",
    4:  "PV Overvoltage [5]",
    5:  "PV Overvoltage [6]",
    6:  "PV Overvoltage [7]",
    7:  "PV Overvoltage [8]",
    8:  "PV Overvoltage [9]",
    9:  "PV Overvoltage [10]",
    10: "PV Overvoltage [11]",
    11: "PV Overvoltage [12]",
    12: "Spare",
    13: "Spare",
    14: "Spare",
    15: "Spare",
}


# ══════════════════════════════════════════════════════════════
# REGISTER 112 — 32-bit Hata Kodu Haritası (Bit bazlı)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_112: dict[int, str] = {
    0:  "String Reverse Connection [1-1]",
    1:  "String Reverse Connection [1-2]",
    2:  "String Reverse Connection [2-1]",
    3:  "String Reverse Connection [2-2]",
    4:  "String Reverse Connection [3-1]",
    5:  "String Reverse Connection [3-2]",
    6:  "String Reverse Connection [4-1]",
    7:  "String Reverse Connection [4-2]",
    8:  "String Reverse Connection [5-1]",
    9:  "String Reverse Connection [5-2]",
    10: "String Reverse Connection [6-1]",
    11: "String Reverse Connection [6-2]",
    12: "String Reverse Connection [7-1]",
    13: "String Reverse Connection [7-2]",
    14: "String Reverse Connection [8-1]",
    15: "String Reverse Connection [8-2]",
    16: "String Reverse Connection [9-1]",
    17: "String Reverse Connection [9-2]",
    18: "String Reverse Connection [10-1]",
    19: "String Reverse Connection [10-2]",
    20: "String Reverse Connection [11-1]",
    21: "String Reverse Connection [11-2]",
    22: "String Reverse Connection [12-1]",
    23: "String Reverse Connection [12-2]",
    24: "Spare",
    25: "Spare",
    26: "Spare",
    27: "Spare",
    28: "Spare",
    29: "Spare",
    30: "Spare",
    31: "Spare",
}


# ══════════════════════════════════════════════════════════════
# REGISTER 114 — 16-bit Hata Kodu Haritası (Bit bazlı)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_114: dict[int, str] = {
    0:  "String Current Backfeed[1]",
    1:  "String Current Backfeed[2]",
    2:  "String Current Backfeed[3]",
    3:  "String Current Backfeed[4]",
    4:  "String Current Backfeed[5]",
    5:  "String Current Backfeed[6]",
    6:  "String Current Backfeed[7]",
    7:  "String Current Backfeed[8]",
    8:  "String Current Backfeed[9]",
    9:  "String Current Backfeed[10]",
    10: "String Current Backfeed[11]",
    11: "String Current Backfeed[12]",
    12: "Spare",
    13: "Spare",
    14: "Spare",
    15: "Spare",
}


# ══════════════════════════════════════════════════════════════
# REGISTER 115 — 16-bit Hata Kodu Haritası (Bit bazlı)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_115: dict[int, str] = {
    0:  "Low Insulation Resistance MPPT[1]",
    1:  "Low Insulation Resistance MPPT[2]",
    2:  "Low Insulation Resistance MPPT[3]",
    3:  "Low Insulation Resistance MPPT[4]",
    4:  "Low Insulation Resistance MPPT[5]",
    5:  "Low Insulation Resistance MPPT[6]",
    6:  "Low Insulation Resistance MPPT[7]",
    7:  "Low Insulation Resistance MPPT[8]",
    8:  "Low Insulation Resistance MPPT[9]",
    9:  "Low Insulation Resistance MPPT[10]",
    10: "Low Insulation Resistance MPPT[11]",
    11: "Low Insulation Resistance MPPT[12]",
    12: "Spare",
    13: "Spare",
    14: "Spare",
    15: "Spare",
}


# ══════════════════════════════════════════════════════════════
# REGISTER 116 — 16-bit Hata Kodu Haritası (Bit bazlı)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_116: dict[int, str] = {
    0:  "Insufficient DC voltage [1]",
    1:  "Insufficient DC voltage [2]",
    2:  "Insufficient DC voltage [3]",
    3:  "Insufficient DC voltage [4]",
    4:  "Insufficient DC voltage [5]",
    5:  "Insufficient DC voltage [6]",
    6:  "Insufficient DC voltage [7]",
    7:  "Insufficient DC voltage [8]",
    8:  "Insufficient DC voltage [9]",
    9:  "Insufficient DC voltage [10]",
    10: "Insufficient DC voltage [11]",
    11: "Insufficient DC voltage [12]",
    12: "Spare",
    13: "Spare",
    14: "Spare",
    15: "Spare",
}



# ══════════════════════════════════════════════════════════════
# REGISTER 117-122 — 16-bit Hata Kodu Haritaları (12 Byte Blok)
# ══════════════════════════════════════════════════════════════
FAULT_MAP_117: dict[int, str] = {
    0:  "DC-side SPD alarm (Major)",
    1:  "Fan abnormal",
    2:  "Internal_MPPT_Error",
    3:  "MPPT Temperature anomaly Warning",
    4:  "MPPT Temperature anomaly Major",
    5:  "Service Request",
    6:  "Grid Undervoltage",
    7:  "Grid Overvoltage",
    8:  "High Humidity",
    9:  "Output Overcurrent",
    10: "Abnormal Residual Current",
    11: "AC-side Low Insulation Resistance",
    12: "DC injection current out of permissible range",
    13: "AC Cable Fault",
    14: "DC Overvoltage",
    15: "Low Cabinet Temperature",
}

FAULT_MAP_118: dict[int, str] = {
    0:  "ICU-MPPT Communication Fault",
    1:  "AC instantaneous overcurrent",
    2:  "Grid overfrequency",
    3:  "Grid underfrequency",
    4:  "Grid power outage",
    5:  "High Board Temperature",
    6:  "Grid abnormal",
    7:  "10-minute grid overvoltage",
    8:  "Grid voltage unbalance",
    9:  "Temperature anomaly Major",
    10: "Cabinet OverTemperature Major",
    11: "AC-side SPD alarm",
    12: "Self Diagnosis Test Abnormal",
    13: "Cabinet OverTemperature Warning",
    14: "Derating Occured Temperature",
    15: "Temperature anomaly Warning",
}

FAULT_MAP_119: dict[int, str] = {
    0:  "Curve Data Communication Fault",
    1:  "Spare",
    2:  "Spare",
    3:  "Spare",
    4:  "Spare",
    5:  "Spare",
    6:  "Spare",
    7:  "Spare",
    8:  "Spare",
    9:  "Spare",
    10: "Spare",
    11: "Spare",
    12: "Spare",
    13: "Spare",
    14: "Spare",
    15: "Spare",
}

FAULT_MAP_120: dict[int, str] = {
    0:  "Internal Fan Error [1]",
    1:  "Internal Fan Error [2]",
    2:  "Internal Fan Error [3]",
    3:  "Fan Error [1]",
    4:  "Fan Error [2]",
    5:  "Fan Error [3]",
    6:  "Fan Error [4]",
    7:  "Fan Error [5]",
    8:  "Fan Error [6]",
    9:  "MPPT_SPDUp",
    10: "MPPT_SPDDown",
    11: "MPPT_DC_Bus_High",
    12: "MPPT_DC_Bus_Low",
    13: "MPPT_Slave_ModbusError",
    14: "MPPT_FPSU_ModbusError",
    15: "MPPT_PrechargeError",
}

FAULT_MAP_121: dict[int, str] = {
    0:  "MPPT_YK Lower Current Sensor Fault",
    1:  "MPPT_YK Upper Current Sensor Fault",
    2:  "MPPT_EMC Current Sensor Fault",
    3:  "DC_Undervoltage",
    4:  "DC_Bus_Unbalance",
    5:  "INV_DriverFault",
    6:  "INV_DriverNotReady",
    7:  "INV_OverVoltage",
    8:  "INV_CalibrationError",
    9:  "Continuous Abnormal Residual Current",
    10: "30mA Sudden Abnormal Residual Current",
    11: "60mA Sudden Abnormal Residual Current",
    12: "150mA Sudden Abnormal Residual Current",
    13: "INV_PrechargeFailed",
    14: "Residual Current Sensor Fault",
    15: "GridSynchTest",
}

FAULT_MAP_122: dict[int, str] = {
    0:  "INV_DiagnosticTest",
    1:  "RelayFault",
    2:  "INV_SensorOvercurrent",
    3:  "INV_ControlCardOvercurrent",
    4:  "Spare",
    5:  "Spare",
    6:  "Spare",
    7:  "Spare",
    8:  "Spare",
    9:  "Spare",
    10: "Spare",
    11: "Spare",
    12: "Spare",
    13: "Spare",
    14: "Spare",
    15: "Spare",
}


# ══════════════════════════════════════════════════════════════
# VERİ YAPILARI
# ══════════════════════════════════════════════════════════════

@dataclass
class OlcumVerisi:
    """Tek bir ölçüm kaydını temsil eder."""
    slave_id: int = 0
    guc: float = 0.0
    voltaj: float = 0.0
    akim: float = 0.0
    sicaklik: float = 0.0
    hata_kodu: int = 0
    hata_kodu_109: int = 0
    hata_kodu_111: int = 0
    hata_kodu_112: int = 0
    hata_kodu_114: int = 0
    hata_kodu_115: int = 0
    hata_kodu_116: int = 0
    hata_kodu_117: int = 0
    hata_kodu_118: int = 0
    hata_kodu_119: int = 0
    hata_kodu_120: int = 0
    hata_kodu_121: int = 0
    hata_kodu_122: int = 0
    zaman: str = ""

    def to_dict(self) -> dict:
        return {
            "slave_id": self.slave_id,
            "guc": self.guc,
            "voltaj": self.voltaj,
            "akim": self.akim,
            "sicaklik": self.sicaklik,
            "hata_kodu": self.hata_kodu,
            "hata_kodu_109": self.hata_kodu_109,
            "hata_kodu_111": self.hata_kodu_111,
            "hata_kodu_112": self.hata_kodu_112,
            "hata_kodu_114": self.hata_kodu_114,
            "hata_kodu_115": self.hata_kodu_115,
            "hata_kodu_116": self.hata_kodu_116,
            "hata_kodu_117": self.hata_kodu_117,
            "hata_kodu_118": self.hata_kodu_118,
            "hata_kodu_119": self.hata_kodu_119,
            "hata_kodu_120": self.hata_kodu_120,
            "hata_kodu_121": self.hata_kodu_121,
            "hata_kodu_122": self.hata_kodu_122,
            "zaman": self.zaman or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }


@dataclass
class CihazDurumu:
    """Bir cihazın anlık durumunu temsil eder."""
    slave_id: int = 0
    son_zaman: str = ""
    guc: float = 0.0
    voltaj: float = 0.0
    akim: float = 0.0
    sicaklik: float = 0.0
    hata_kodu: int = 0
    hata_kodu_109: int = 0
    hata_kodu_111: int = 0
    hata_kodu_112: int = 0
    hata_kodu_114: int = 0
    hata_kodu_115: int = 0
    hata_kodu_116: int = 0
    hata_kodu_117: int = 0
    hata_kodu_118: int = 0
    hata_kodu_119: int = 0
    hata_kodu_120: int = 0
    hata_kodu_121: int = 0
    hata_kodu_122: int = 0
    aktif: bool = False

    @property
    def has_error(self) -> bool:
        return self.hata_kodu != 0 or self.hata_kodu_109 != 0 or self.hata_kodu_111 != 0 or self.hata_kodu_112 != 0 or self.hata_kodu_114 != 0 or self.hata_kodu_115 != 0 or self.hata_kodu_116 != 0 or self.hata_kodu_117 != 0 or self.hata_kodu_118 != 0 or self.hata_kodu_119 != 0 or self.hata_kodu_120 != 0 or self.hata_kodu_121 != 0 or self.hata_kodu_122 != 0

    @property
    def durum_text(self) -> str:
        if self.has_error:
            return "ARIZA"
        elif self.guc > 0:
            return "AKTİF"
        return "BEKLEMEDE"


