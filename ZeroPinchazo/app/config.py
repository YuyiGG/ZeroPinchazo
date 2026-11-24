"""Configuración general y tarifas para ZeroPinchazo."""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Carga variables desde archivo .env si existe
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


@dataclass
class Settings:
    # Google Maps
    google_maps_api_key: str = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

    # GPS Traccar
    gps_base_url: str = os.getenv("GPS_BASE_URL", "").rstrip("/")
    gps_user: str = os.getenv("GPS_USER", "")
    gps_pass: str = os.getenv("GPS_PASS", "")
    gps_device_id: str = os.getenv("GPS_DEVICE_ID", "1")
    gps_cache_ttl_seconds: int = int(os.getenv("GPS_CACHE_TTL_SECONDS", "15"))

    # Webhook GPS directo (para actualizar sin Traccar)
    gps_webhook_secret: str = os.getenv("GPS_WEBHOOK_SECRET", "zeropinchazo_secret_gps")

    # Base del taller (respaldo)
    base_lat: float = float(os.getenv("BASE_LAT", "-33.4489"))
    base_lng: float = float(os.getenv("BASE_LNG", "-70.6693"))
    base_nombre: str = os.getenv("BASE_NOMBRE", "Taller Central")

    # Tarifas (en CLP)
    cargo_base: int = int(os.getenv("TARIFA_CARGO_BASE", "15000"))
    precio_por_km: int = int(os.getenv("TARIFA_PRECIO_KM", "1200"))
    km_incluidos: int = int(os.getenv("TARIFA_KM_INCLUIDOS", "3"))
    cobrar_ida_y_vuelta: bool = os.getenv("TARIFA_COBRAR_IDA_VUELTA", "false").lower() in ("true", "1", "yes")
    cobro_minimo: int = int(os.getenv("TARIFA_COBRO_MINIMO", "18000"))
    redondeo: int = int(os.getenv("TARIFA_REDONDEO", "500"))
    margen_rango: float = float(os.getenv("TARIFA_MARGEN_RANGO", "0.10"))
    km_maximo: float = float(os.getenv("TARIFA_KM_MAXIMO", "50.0"))

    # Notificaciones
    whatsapp_operador: str = os.getenv("WHATSAPP_NOTIFICAR_OPERADOR", "")


settings = Settings()


def formato_clp(monto: int) -> str:
    """Formatea un número entero como moneda chilena (ej: $18.500)."""
    return f"${monto:,.0f}".replace(",", ".")
