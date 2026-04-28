"""
Solar Monitor - RESTful API Modülü
====================================
CRM ve dış sistemlerin Solar Monitor verilerine erişmesi için
FastAPI tabanlı RESTful API sunucusu.

Endpointler:
    GET  /api/v1/status                     → Sistem durumu
    GET  /api/v1/devices                    → Tüm cihazların anlık durumu
    GET  /api/v1/devices/{id}/latest        → Cihazın son verileri
    GET  /api/v1/devices/{id}/history       → Tarih aralığında geçmiş
    GET  /api/v1/production/daily           → Günlük üretim raporu
    GET  /api/v1/production/range           → Tarih aralığı üretim
    GET  /api/v1/alarms                     → Aktif alarmlar
    GET  /api/v1/stats                      → DB istatistikleri
    WS   /ws/live                           → WebSocket canlı veri
    POST /ws/notify                         → Collector bildirimi
    GET  /live                              → Canlı dashboard HTML

CRM Entegrasyonu:
    CRM sisteminiz bu API'yi çağırarak Solar Monitor DB'sindeki
    tüm verilere erişebilir. API_KEY ile basit yetkilendirme yapılır.

    Örnek CRM çağrısı:
        GET http://SUNUCU_IP:8503/api/v1/devices
        Header: X-API-Key: xxxxx  (.env'deki CRM_API_KEY)
"""

from fastapi import FastAPI, HTTPException, Query, Depends, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import os
import asyncio
import uvicorn
import veritabani
from websocket_manager import manager as ws_manager

# .env yükle
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(
    title="Solar Monitoring API",
    description="Endüstriyel Güneş Enerjisi Panel ve İnverter Takip Sistemi — CRM Entegrasyon API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS — CRM'den erişim izni ───
allowed_origin = os.getenv("CRM_ALLOWED_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin] if allowed_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB başlat
veritabani.init_db()


# ─────────────────────────────────────────────
# API Key Doğrulama (basit)
# ─────────────────────────────────────────────

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """API Key doğrulama.

    .env'de CRM_API_KEY=xxxxx olarak ayarlayın.
    xxxxx veya boş ise doğrulama atlanır (geliştirme modu).
    """
    expected_key = os.getenv("CRM_API_KEY", "xxxxx")

    # Key ayarlanmamışsa doğrulama yapma (geliştirme modu)
    if not expected_key or expected_key == "xxxxx":
        return True

    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Geçersiz API anahtarı")
    return True


# ─────────────────────────────────────────────
# Response Modelleri
# ─────────────────────────────────────────────

class SystemStatus(BaseModel):
    status: str
    active_devices: int
    last_data_time: Optional[str] = None
    db_size_mb: Optional[float] = None

class DeviceSummary(BaseModel):
    slave_id: int
    son_zaman: Optional[str] = None
    guc: float = 0
    voltaj: float = 0
    akim: float = 0
    sicaklik: float = 0
    hata_kodu: int = 0
    durum: str = "BILINMIYOR"

class DeviceData(BaseModel):
    zaman: str
    guc: float
    voltaj: float
    akim: float
    sicaklik: float
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

class DailyProduction(BaseModel):
    tarih: str
    slave_id: Optional[int] = None
    uretim_wh: float = 0
    uretim_kwh: float = 0
    ort_guc: float = 0
    calisma_suresi_saat: float = 0

class DateRangeStats(BaseModel):
    baslangic: str
    bitis: str
    slave_id: Optional[int] = None
    ort_guc: float = 0
    ort_voltaj: float = 0
    ort_akim: float = 0
    ort_sicaklik: float = 0
    max_guc: float = 0
    min_guc: float = 0
    toplam_olcum: int = 0

class AlarmInfo(BaseModel):
    slave_id: int
    zaman: str
    hata_kodlari: dict


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/", tags=["Sağlık"])
def root():
    """API sağlık kontrolü."""
    return {
        "message": "Solar Monitoring API Aktif",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": [
            "/api/v1/status",
            "/api/v1/devices",
            "/api/v1/devices/{slave_id}/latest",
            "/api/v1/devices/{slave_id}/history",
            "/api/v1/production/daily",
            "/api/v1/production/range",
            "/api/v1/alarms",
            "/api/v1/stats",
        ]
    }


# ── 1. Sistem Durumu ──

@app.get("/api/v1/status", response_model=SystemStatus, tags=["Sistem"])
def get_system_status(fabrika: str = Query("mekanik", description="Fabrika ID"), _=Depends(verify_api_key)):
    """Sistem genel durumu — CRM ana sayfa widget'ı için ideal."""
    durum = veritabani.tum_cihazlarin_son_durumu(fabrika)
    istatistik = veritabani.veritabani_istatistikleri(fabrika)

    last_time = None
    if durum:
        times = [r[1] for r in durum if r[1]]
        if times:
            last_time = max(times)

    return SystemStatus(
        status="healthy" if durum else "no_data",
        active_devices=len(durum),
        last_data_time=last_time,
        db_size_mb=istatistik["db_boyut_mb"] if istatistik else None,
    )


# ── 2. Tüm Cihazların Anlık Durumu ──

@app.get("/api/v1/devices", response_model=List[DeviceSummary], tags=["Cihaz"])
def get_all_devices(fabrika: str = Query("mekanik", description="Fabrika ID"), _=Depends(verify_api_key)):
    """Tüm inverterlerin anlık durumunu döner."""
    rows = veritabani.tum_cihazlarin_son_durumu(fabrika)
    if not rows:
        return []

    devices = []
    for row in rows:
        guc = float(row[2]) if row[2] else 0
        hata = (row[6] if len(row) > 6 and row[6] else 0)

        if hata:
            durum = "ARIZA"
        elif guc > 0:
            durum = "AKTIF"
        else:
            durum = "BEKLEMEDE"

        devices.append(DeviceSummary(
            slave_id=row[0],
            son_zaman=row[1],
            guc=guc,
            voltaj=round(float(row[3]), 1) if row[3] else 0,
            akim=round(float(row[4]), 2) if row[4] else 0,
            sicaklik=round(float(row[5]), 1) if row[5] else 0,
            hata_kodu=hata,
            durum=durum,
        ))
    return devices


# ── 3. Tekil Cihaz Son Veriler ──

@app.get("/api/v1/devices/{slave_id}/latest", response_model=List[DeviceData], tags=["Cihaz"])
def get_device_latest(slave_id: int, limit: int = Query(10, ge=1, le=1000), fabrika: str = Query("mekanik"), _=Depends(verify_api_key)):
    """Belirtilen inverter için son N ölçüm verisini döner."""
    veriler = veritabani.son_verileri_getir(slave_id, limit=limit, fabrika_id=fabrika)
    if not veriler:
        raise HTTPException(status_code=404, detail=f"Cihaz ID {slave_id} bulunamadı veya veri yok.")

    response = []
    for row in veriler:
        response.append(DeviceData(
            zaman=row[0],
            guc=float(row[1] or 0),
            voltaj=float(row[2] or 0),
            akim=float(row[3] or 0),
            sicaklik=float(row[4] or 0),
            hata_kodu=int(row[5] or 0),
            hata_kodu_109=int(row[6] or 0) if len(row) > 6 else 0,
            hata_kodu_111=int(row[7] or 0) if len(row) > 7 else 0,
            hata_kodu_112=int(row[8] or 0) if len(row) > 8 else 0,
            hata_kodu_114=int(row[9] or 0) if len(row) > 9 else 0,
            hata_kodu_115=int(row[10] or 0) if len(row) > 10 else 0,
            hata_kodu_116=int(row[11] or 0) if len(row) > 11 else 0,
            hata_kodu_117=int(row[12] or 0) if len(row) > 12 else 0,
            hata_kodu_118=int(row[13] or 0) if len(row) > 13 else 0,
            hata_kodu_119=int(row[14] or 0) if len(row) > 14 else 0,
            hata_kodu_120=int(row[15] or 0) if len(row) > 15 else 0,
            hata_kodu_121=int(row[16] or 0) if len(row) > 16 else 0,
            hata_kodu_122=int(row[17] or 0) if len(row) > 17 else 0,
        ))
    return response


# ── 4. Tarih Aralığında Geçmiş Veri ──

@app.get("/api/v1/devices/{slave_id}/history", response_model=DateRangeStats, tags=["Cihaz"])
def get_device_history(
    slave_id: int,
    baslangic: date = Query(..., description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis: date = Query(..., description="Bitiş tarihi (YYYY-MM-DD)"),
    _=Depends(verify_api_key),
):
    """Belirtilen tarih aralığında ortalama/min/max değerleri döner.

    CRM'de rapor ve grafik oluşturmak için bu endpoint'i kullanın.

    Örnek CRM çağrısı:
        GET http://SUNUCU_IP:8503/api/v1/devices/1/history?baslangic=2026-04-01&bitis=2026-04-28
        Header: X-API-Key: xxxxx
    """
    sonuc = veritabani.tarih_araliginda_ortalamalar(str(baslangic), str(bitis), slave_id)
    if not sonuc or sonuc.get("toplam_olcum", 0) == 0:
        raise HTTPException(status_code=404, detail="Bu tarih aralığında veri bulunamadı.")

    return DateRangeStats(
        baslangic=str(baslangic),
        bitis=str(bitis),
        slave_id=slave_id,
        ort_guc=round(sonuc["ort_guc"], 2),
        ort_voltaj=round(sonuc["ort_voltaj"], 2),
        ort_akim=round(sonuc["ort_akim"], 2),
        ort_sicaklik=round(sonuc["ort_sicaklik"], 2),
        max_guc=round(sonuc["max_guc"], 2),
        min_guc=round(sonuc["min_guc"], 2),
        toplam_olcum=sonuc["toplam_olcum"],
    )


# ── 5. Günlük Üretim Raporu ──

@app.get("/api/v1/production/daily", response_model=DailyProduction, tags=["Üretim"])
def get_daily_production(
    tarih: date = Query(None, description="Tarih (YYYY-MM-DD), boş bırakılırsa bugün"),
    slave_id: Optional[int] = Query(None, description="İnverter ID (boş = tümü)"),
    fabrika: str = Query("mekanik", description="Fabrika ID"),
    _=Depends(verify_api_key),
):
    """Belirtilen gün için üretim raporu (Wh / kWh).

    CRM'de günlük üretim kartı/widget göstermek için ideal.

    Örnek CRM çağrısı:
        GET http://SUNUCU_IP:8503/api/v1/production/daily?tarih=2026-04-28
        GET http://SUNUCU_IP:8503/api/v1/production/daily?tarih=2026-04-28&slave_id=1
        Header: X-API-Key: xxxxx
    """
    if tarih is None:
        tarih = date.today()

    sonuc = veritabani.gunluk_uretim_hesapla(str(tarih), slave_id, fabrika_id=fabrika)
    if not sonuc:
        raise HTTPException(status_code=404, detail="Bu tarih için üretim verisi bulunamadı.")

    return DailyProduction(
        tarih=str(tarih),
        slave_id=slave_id,
        uretim_wh=sonuc["uretim_wh"],
        uretim_kwh=sonuc["uretim_kwh"],
        ort_guc=sonuc["ort_guc"],
        calisma_suresi_saat=sonuc["calisma_suresi_saat"],
    )


# ── 6. Tarih Aralığı Üretim İstatistikleri ──

@app.get("/api/v1/production/range", response_model=DateRangeStats, tags=["Üretim"])
def get_production_range(
    baslangic: date = Query(..., description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis: date = Query(..., description="Bitiş tarihi (YYYY-MM-DD)"),
    slave_id: Optional[int] = Query(None, description="İnverter ID (boş = tümü)"),
    _=Depends(verify_api_key),
):
    """Tarih aralığında toplam üretim istatistikleri.

    CRM'de aylık/haftalık rapor için bu endpoint'i kullanın.

    Örnek CRM çağrısı:
        GET http://SUNUCU_IP:8503/api/v1/production/range?baslangic=2026-04-01&bitis=2026-04-30
        Header: X-API-Key: xxxxx
    """
    sonuc = veritabani.tarih_araliginda_ortalamalar(str(baslangic), str(bitis), slave_id)
    if not sonuc or sonuc.get("toplam_olcum", 0) == 0:
        raise HTTPException(status_code=404, detail="Bu tarih aralığında veri bulunamadı.")

    return DateRangeStats(
        baslangic=str(baslangic),
        bitis=str(bitis),
        slave_id=slave_id,
        ort_guc=round(sonuc["ort_guc"], 2),
        ort_voltaj=round(sonuc["ort_voltaj"], 2),
        ort_akim=round(sonuc["ort_akim"], 2),
        ort_sicaklik=round(sonuc["ort_sicaklik"], 2),
        max_guc=round(sonuc["max_guc"], 2),
        min_guc=round(sonuc["min_guc"], 2),
        toplam_olcum=sonuc["toplam_olcum"],
    )


# ── 7. Aktif Alarmlar ──

@app.get("/api/v1/alarms", response_model=List[AlarmInfo], tags=["Alarm"])
def get_active_alarms(fabrika: str = Query("mekanik", description="Fabrika ID"), _=Depends(verify_api_key)):
    """Aktif hata kodu olan cihazları listeler."""
    rows = veritabani.tum_cihazlarin_son_durumu(fabrika)
    if not rows:
        return []

    alarms = []
    for row in rows:
        hata_kodlari = {}
        hata_isimleri = [
            (6, "hata_107"), (7, "hata_109"), (8, "hata_111"),
            (9, "hata_112"), (10, "hata_114"), (11, "hata_115"), (12, "hata_116"),
        ]
        for idx, isim in hata_isimleri:
            if len(row) > idx and row[idx] and row[idx] != 0:
                hata_kodlari[isim] = row[idx]

        if hata_kodlari:
            alarms.append(AlarmInfo(
                slave_id=row[0],
                zaman=row[1] or "",
                hata_kodlari=hata_kodlari,
            ))

    return alarms


# ── 8. DB İstatistikleri ──

@app.get("/api/v1/stats", tags=["Sistem"])
def get_db_stats(fabrika: str = Query("mekanik", description="Fabrika ID"), _=Depends(verify_api_key)):
    """Veritabanı istatistikleri — kayıt sayısı, boyut, tarih aralığı."""
    istatistik = veritabani.veritabani_istatistikleri(fabrika)
    if not istatistik:
        raise HTTPException(status_code=500, detail="İstatistik alınamadı.")

    return {
        "toplam_kayit": istatistik["toplam_kayit"],
        "ilk_kayit": istatistik["ilk_kayit"],
        "son_kayit": istatistik["son_kayit"],
        "db_boyut_mb": istatistik["db_boyut_mb"],
        "cihaz_detay": [
            {
                "slave_id": c[0],
                "kayit_sayisi": c[1],
                "ilk_kayit": c[2],
                "son_kayit": c[3],
            }
            for c in istatistik.get("cihaz_istatistik", [])
        ],
    }


# ─────────────────────────────────────────────
# WebSocket Canlı Veri
# ─────────────────────────────────────────────

def _build_ws_payload() -> dict:
    """DB'den güncel veriyi okuyup WebSocket payload'ı oluşturur."""
    from veritabani import FABRIKALAR
    all_data = {}
    for fab_id in FABRIKALAR:
        rows = veritabani.tum_cihazlarin_son_durumu(fab_id)
        devices = []
        for row in rows:
            guc = float(row[2]) if row[2] else 0
            hata = (row[6] if len(row) > 6 and row[6] else 0)
            devices.append({
                "slave_id": row[0],
                "son_zaman": row[1],
                "guc": guc,
                "voltaj": round(float(row[3]), 1) if row[3] else 0,
                "akim": round(float(row[4]), 2) if row[4] else 0,
                "sicaklik": round(float(row[5]), 1) if row[5] else 0,
                "hata_kodu": hata,
            })
        all_data[fab_id] = devices
    return {
        "type": "update",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fabrikalar": all_data,
        "client_count": ws_manager.client_count,
    }


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """WebSocket canlı veri endpointi.

    Bağlantı kurulduğunda anlık veriyi gönderir,
    sonra collector'dan bildirim gelene kadar veya
    periyodik olarak güncelleme yapar.

    Bağlantı: ws://SUNUCU_IP:8503/ws/live
    """
    await ws_manager.connect(ws)

    # İlk bağlantıda anlık veriyi gönder
    try:
        initial = _build_ws_payload()
        initial["type"] = "initial"
        await ws_manager.send_personal(ws, initial)
    except Exception:
        pass

    # Bağlantı açık kaldığı sürece ping/pong bekle
    try:
        while True:
            # İstemciden mesaj bekle (ping/pong veya komut)
            data = await ws.receive_text()
            # İstemci "refresh" gönderirse anlık veri döndür
            if data == "refresh":
                payload = _build_ws_payload()
                await ws_manager.send_personal(ws, payload)
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)


@app.post("/ws/notify", tags=["WebSocket"])
async def ws_notify():
    """Collector'dan bildirim alır ve tüm WS istemcilerine yayınlar.

    Collector veri yazdıktan sonra bu endpoint'e POST yapar.
    API, DB'den güncel veriyi okuyup bağlı tüm istemcilere push eder.

    Bu endpoint API Key gerektirmez (iç ağ iletişimi).
    """
    if ws_manager.client_count == 0:
        return {"status": "no_clients", "clients": 0}

    payload = _build_ws_payload()
    await ws_manager.broadcast(payload)

    return {"status": "broadcast_sent", "clients": ws_manager.client_count}


# ─── Canlı Dashboard HTML ───

@app.get("/live", response_class=HTMLResponse, tags=["Dashboard"])
async def live_dashboard():
    """WebSocket canlı izleme dashboard'u.

    Tarayıcıdan http://SUNUCU_IP:8503/live açarak
    gerçek zamanlı inverter verilerini izleyebilirsiniz.
    """
    html_path = os.path.join(os.path.dirname(__file__), "static", "live_dashboard.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dashboard dosyası bulunamadı")


# ─────────────────────────────────────────────
# Sunucu Başlatma
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8503))
    print(f"[*] Solar Monitor API başlatılıyor — port {port}")
    print(f"[*] Docs: http://localhost:{port}/docs")
    print(f"[*] Live: http://localhost:{port}/live")
    print(f"[*] WS:   ws://localhost:{port}/ws/live")
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
