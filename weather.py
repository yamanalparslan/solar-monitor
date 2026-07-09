import requests
import streamlit as st
import pandas as pd
from datetime import timedelta

@st.cache_data(ttl=timedelta(minutes=15), show_spinner=False)
def _fetch_current_weather_cached(lat: float, lon: float):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,cloud_cover,direct_normal_irradiance,weather_code",
        "timezone": "auto"
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    current = data.get("current", {})
    
    weather_code = current.get("weather_code", 0)
    weather_desc = "Açık"
    icon = "☀️"
    if weather_code in [1, 2, 3]:
        weather_desc = "Parçalı Bulutlu"
        icon = "⛅"
    elif weather_code in [45, 48]:
        weather_desc = "Sisli"
        icon = "🌫️"
    elif weather_code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
        weather_desc = "Yağmurlu"
        icon = "🌧️"
    elif weather_code in [71, 73, 75, 77, 85, 86]:
        weather_desc = "Karlı"
        icon = "❄️"
    elif weather_code in [95, 96, 99]:
        weather_desc = "Fırtınalı"
        icon = "⛈️"
        
    return {
        "temp": current.get("temperature_2m", 0),
        "cloud_cover": current.get("cloud_cover", 0),
        "irradiance": current.get("direct_normal_irradiance", 0),
        "desc": weather_desc,
        "icon": icon
    }

def get_current_weather(lat: float, lon: float):
    """
    Fetches current weather data from Open-Meteo.
    Returns a dict with temperature, cloud_cover, and direct_normal_irradiance.
    """
    try:
        return _fetch_current_weather_cached(lat, lon)
    except Exception as e:
        print(f"[WEATHER API ERROR] {e}")
        return None

@st.cache_data(ttl=timedelta(minutes=30), show_spinner=False)
def _fetch_historical_irradiance_cached(lat: float, lon: float, past_days: int = 2):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "direct_normal_irradiance",
        "past_days": past_days,
        "forecast_days": 1,
        "timezone": "auto"
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    irradiance = hourly.get("direct_normal_irradiance", [])
    
    if not times or not irradiance:
        return pd.DataFrame()
        
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(times),
        "irradiance": irradiance
    })
    
    return df

def get_historical_irradiance(lat: float, lon: float, past_days: int = 2):
    """
    Fetches hourly historical irradiance data from Open-Meteo.
    Returns a pandas DataFrame with timestamps and irradiance.
    """
    try:
        return _fetch_historical_irradiance_cached(lat, lon, past_days)
    except Exception as e:
        print(f"[WEATHER API ERROR] {e}")
        return pd.DataFrame()
