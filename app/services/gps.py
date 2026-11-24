"""Servicio de gestión y lectura de GPS del vehículo en tiempo real."""

import time
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class UbicacionVehiculo:
    latitud: float
    longitud: float
    origen: str  # 'traccar', 'webhook_directo', 'taller_base'
    actualizado_hace_seg: float
    descripcion: str
    velocidad_kmh: Optional[float] = None


class GPSService:
    def __init__(self):
        self._pos_cache: Optional[Tuple[float, float]] = None
        self._cache_time: float = 0.0
        self._origen_cache: str = "taller_base"
        self._velocidad_cache: Optional[float] = None
        self._ultima_actualizacion_directa: float = 0.0

    async def obtener_posicion(self, device_id: Optional[str] = None) -> UbicacionVehiculo:
        """Obtiene la posición más reciente del vehículo.

        Prioridad:
        1. Cache en memoria si tiene menos de `settings.gps_cache_ttl_seconds`
        2. Consulta a API de Traccar (si está configurada)
        3. Última posición recibida por webhook directo
        4. Coordenadas de respaldo del taller base
        """
        ahora = time.time()
        ttl = settings.gps_cache_ttl_seconds

        # 1. ¿Cache fresco?
        if self._pos_cache and (ahora - self._cache_time) < ttl:
            return UbicacionVehiculo(
                latitud=self._pos_cache[0],
                longitud=self._pos_cache[1],
                origen=self._origen_cache,
                actualizado_hace_seg=round(ahora - self._cache_time, 1),
                descripcion=f"GPS en vivo ({self._origen_cache})",
                velocidad_kmh=self._velocidad_cache,
            )

        # 2. Consultar Traccar si está configurado
        if settings.gps_base_url and settings.gps_user:
            dev_id = device_id or settings.gps_device_id
            url = f"{settings.gps_base_url}/api/positions"
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(
                        url,
                        params={"deviceId": dev_id},
                        auth=(settings.gps_user, settings.gps_pass),
                    )
                    if resp.status_code == 200:
                        datos = resp.json()
                        if datos and isinstance(datos, list):
                            pos = datos[0]
                            lat = float(pos["latitude"])
                            lng = float(pos["longitude"])
                            speed = float(pos.get("speed", 0)) * 1.852  # Nudos a km/h
                            self._pos_cache = (lat, lng)
                            self._cache_time = ahora
                            self._origen_cache = "traccar"
                            self._velocidad_cache = round(speed, 1)

                            return UbicacionVehiculo(
                                latitud=lat,
                                longitud=lng,
                                origen="traccar",
                                actualizado_hace_seg=0.0,
                                descripcion="GPS Traccar en vivo",
                                velocidad_kmh=round(speed, 1),
                            )
            except Exception as e:
                logger.warning(f"No se pudo consultar servidor Traccar: {e}")

        # 3. ¿Tenemos una posición reciente enviada por webhook directo?
        if self._ultima_actualizacion_directa and (ahora - self._ultima_actualizacion_directa) < 1800:
            # Válida si tiene menos de 30 minutos
            if self._pos_cache:
                return UbicacionVehiculo(
                    latitud=self._pos_cache[0],
                    longitud=self._pos_cache[1],
                    origen="webhook_directo",
                    actualizado_hace_seg=round(ahora - self._ultima_actualizacion_directa, 1),
                    descripcion="GPS Reportado por Técnico (Móvil)",
                    velocidad_kmh=self._velocidad_cache,
                )

        # 4. Fallback: Ubicación del Taller Base
        return UbicacionVehiculo(
            latitud=settings.base_lat,
            longitud=settings.base_lng,
            origen="taller_base",
            actualizado_hace_seg=0.0,
            descripcion=f"Ubicación de Respaldo: {settings.base_nombre}",
            velocidad_kmh=0.0,
        )

    def registrar_posicion_directa(self, lat: float, lng: float, velocidad_kmh: Optional[float] = None) -> UbicacionVehiculo:
        """Permite que el técnico o un tracker envíe sus coordenadas directamente al sistema."""
        ahora = time.time()
        self._pos_cache = (lat, lng)
        self._cache_time = ahora
        self._ultima_actualizacion_directa = ahora
        self._origen_cache = "webhook_directo"
        self._velocidad_cache = velocidad_kmh

        return UbicacionVehiculo(
            latitud=lat,
            longitud=lng,
            origen="webhook_directo",
            actualizado_hace_seg=0.0,
            descripcion="GPS Reportado por Técnico en vivo",
            velocidad_kmh=velocidad_kmh,
        )


gps_service = GPSService()
