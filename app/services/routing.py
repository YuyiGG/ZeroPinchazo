"""Servicio de geocodificación y cálculo de rutas en tiempo real."""

import logging
from math import ceil, radians, cos, sin, asin, sqrt
from dataclasses import dataclass
from typing import Tuple, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ResultadoRuta:
    km: float
    minutos: int
    direccion_formateada: str
    lat_destino: float
    lng_destino: float
    proveedor: str  # 'google_maps', 'osrm', 'haversine_estimado'


def calcular_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia geodésica en línea recta entre dos puntos en km."""
    r = 6371.0  # Radio de la Tierra en km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2.0) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2.0) ** 2
    c = 2.0 * asin(sqrt(a))
    return r * c


class RoutingService:
    async def geocodificar_direccion(self, direccion: str) -> Tuple[float, float, str]:
        """Convierte una dirección de texto a coordenadas (lat, lng, direccion_formateada).

        Intenta primero Google Maps. Si no hay API Key o falla, usa OpenStreetMap (Nominatim).
        """
        direccion_limpia = direccion.strip()

        # 1. Google Maps Geocoding API
        if settings.google_maps_api_key:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(
                        "https://maps.googleapis.com/maps/api/geocode/json",
                        params={
                            "address": direccion_limpia,
                            "region": "cl",
                            "components": "country:CL",
                            "key": settings.google_maps_api_key,
                        },
                    )
                    data = resp.json()
                    if data.get("status") == "OK" and data.get("results"):
                        res = data["results"][0]
                        loc = res["geometry"]["location"]
                        return float(loc["lat"]), float(loc["lng"]), res.get("formatted_address", direccion_limpia)
            except Exception as e:
                logger.warning(f"Falla en Google Geocoding API: {e}. Probando Nominatim...")

        # 2. Fallback Gratuito: Nominatim (OpenStreetMap)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": direccion_limpia,
                        "countrycodes": "cl",
                        "format": "json",
                        "limit": 1,
                    },
                    headers={"User-Agent": "ZeroPinchazo-Cotizador/1.0 (contacto@zeropinchazo.cl)"},
                )
                if resp.status_code == 200:
                    resultados = resp.json()
                    if resultados and len(resultados) > 0:
                        primero = resultados[0]
                        lat = float(primero["lat"])
                        lng = float(primero["lon"])
                        nombre = primero.get("display_name", direccion_limpia)
                        # Acortar nombre largo de Nominatim
                        partes = [p.strip() for p in nombre.split(",")]
                        nombre_corto = ", ".join(partes[:3]) if len(partes) >= 3 else nombre
                        return lat, lng, nombre_corto
        except Exception as e:
            logger.error(f"Falla en Nominatim Geocoding: {e}")

        raise ValueError(
            f"No pudimos ubicar la dirección '{direccion_limpia}'. Por favor incluye calle, número y comuna."
        )

    async def calcular_ruta(
        self,
        origen: Tuple[float, float],
        destino_lat: float,
        destino_lng: float,
        direccion_nombre: Optional[str] = None,
    ) -> ResultadoRuta:
        """Calcula la distancia real de conducción (km) y tiempo estimado (minutos)."""
        origen_lat, origen_lng = origen

        # 1. Intentar Google Distance Matrix (incluye tráfico en tiempo real)
        if settings.google_maps_api_key:
            try:
                async with httpx.AsyncClient(timeout=4.5) as client:
                    resp = await client.get(
                        "https://maps.googleapis.com/maps/api/distancematrix/json",
                        params={
                            "origins": f"{origen_lat},{origen_lng}",
                            "destinations": f"{destino_lat},{destino_lng}",
                            "mode": "driving",
                            "departure_time": "now",
                            "key": settings.google_maps_api_key,
                        },
                    )
                    data = resp.json()
                    if data.get("status") == "OK" and data.get("rows"):
                        elem = data["rows"][0]["elements"][0]
                        if elem.get("status") == "OK":
                            km = elem["distance"]["value"] / 1000.0
                            segundos = (elem.get("duration_in_traffic") or elem["duration"])["value"]
                            minutos = max(5, ceil(segundos / 60))
                            return ResultadoRuta(
                                km=km,
                                minutos=minutos,
                                direccion_formateada=direccion_nombre or f"{destino_lat:.4f}, {destino_lng:.4f}",
                                lat_destino=destino_lat,
                                lng_destino=destino_lng,
                                proveedor="google_maps",
                            )
            except Exception as e:
                logger.warning(f"Error en Google Distance Matrix: {e}. Probando OSRM...")

        # 2. Fallback OSRM (Open Source Routing Machine - Gratuito por calles reales)
        try:
            osrm_url = f"https://router.project-osrm.org/route/v1/driving/{origen_lng},{origen_lat};{destino_lng},{destino_lat}?overview=false"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(osrm_url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        ruta = data["routes"][0]
                        km = ruta["distance"] / 1000.0
                        # En OSRM agregamos un 15% de margen por semáforos y congestión urbana
                        minutos = max(5, ceil((ruta["duration"] * 1.15) / 60))
                        return ResultadoRuta(
                            km=km,
                            minutos=minutos,
                            direccion_formateada=direccion_nombre or "Ubicación compartida por GPS 📍",
                            lat_destino=destino_lat,
                            lng_destino=destino_lng,
                            proveedor="osrm",
                        )
        except Exception as e:
            logger.error(f"Falla en OSRM Routing: {e}")

        # 3. Fallback de emergencia: Estimación Haversine con factor de curvas y velocidad urbana
        dist_recta = calcular_haversine(origen_lat, origen_lng, destino_lat, destino_lng)
        # En ciudad la ruta real suele ser un 35-40% más larga que la línea recta
        km_estimado = dist_recta * 1.35
        # Velocidad promedio en ciudad en Santiago: ~30-35 km/h
        minutos_estimado = max(8, ceil((km_estimado / 30.0) * 60))

        return ResultadoRuta(
            km=km_estimado,
            minutos=minutos_estimado,
            direccion_formateada=direccion_nombre or f"Ubicación GPS ({destino_lat:.4f}, {destino_lng:.4f})",
            lat_destino=destino_lat,
            lng_destino=destino_lng,
            proveedor="haversine_estimado",
        )


routing_service = RoutingService()
