"""API FastAPI Principal para ZeroPinchazo - Cotizador de Vulcanización Móvil."""

import os
from xml.sax.saxutils import escape
from typing import Optional
from fastapi import FastAPI, Form, HTTPException, Header, Query
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.services.gps import gps_service
from app.services.routing import routing_service
from app.services.pricing import calcular_presupuesto
from app.services.chatbot import chatbot_service

app = FastAPI(
    title="ZeroPinchazo API",
    description="Sistema de cotización automatizada en tiempo real según GPS del móvil técnico",
    version="1.0.0",
)

# Permitir CORS para desarrollo o integración web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# MODELOS DE ENTRADA Y SALIDA (API REST)
# ============================================================================

class SolicitudCotizacion(BaseModel):
    direccion: Optional[str] = Field(None, description="Dirección textual del cliente")
    lat: Optional[float] = Field(None, description="Latitud directa del cliente (GPS)")
    lng: Optional[float] = Field(None, description="Longitud directa del cliente (GPS)")


class ActualizacionGPS(BaseModel):
    token: str = Field(..., description="Token secreto para autorizar reporte")
    lat: float = Field(..., description="Latitud actual del vehículo")
    lng: float = Field(..., description="Longitud actual del vehículo")
    velocidad_kmh: Optional[float] = Field(None, description="Velocidad en km/h")


# ============================================================================
# ENDPOINTS REST
# ============================================================================

@app.get("/health")
def health_check():
    return {"status": "ok", "app": "ZeroPinchazo", "version": "1.0.0"}


@app.get("/api/v1/vehiculo")
async def obtener_estado_vehiculo():
    """Retorna la posición actual del vehículo técnico."""
    vehiculo = await gps_service.obtener_posicion()
    return {
        "latitud": vehiculo.latitud,
        "longitud": vehiculo.longitud,
        "origen": vehiculo.origen,
        "descripcion": vehiculo.descripcion,
        "actualizado_hace_seg": vehiculo.actualizado_hace_seg,
        "velocidad_kmh": vehiculo.velocidad_kmh,
    }


@app.post("/api/v1/gps/update")
def actualizar_posicion_directa(data: ActualizacionGPS):
    """Permite al técnico o a una app móvil reportar la posición sin servidor Traccar."""
    if data.token != settings.gps_webhook_secret:
        raise HTTPException(status_code=403, detail="Token de autorización inválido")

    pos = gps_service.registrar_posicion_directa(
        lat=data.lat,
        lng=data.lng,
        velocidad_kmh=data.velocidad_kmh,
    )
    return {
        "ok": True,
        "mensaje": "Posición GPS del móvil actualizada correctamente",
        "datos": {
            "lat": pos.latitud,
            "lng": pos.longitud,
            "origen": pos.origen,
        },
    }


@app.post("/cotizar")
@app.post("/api/v1/cotizar")
async def cotizar_servicio(solicitud: SolicitudCotizacion):
    """Calcula la distancia desde el técnico y genera presupuesto estimado."""
    vehiculo = await gps_service.obtener_posicion()
    origen = (vehiculo.latitud, vehiculo.longitud)

    # Determinar coordenadas de destino
    if solicitud.lat is not None and solicitud.lng is not None:
        dest_lat, dest_lng = solicitud.lat, solicitud.lng
        nombre_dest = solicitud.direccion or f"Coordenadas ({dest_lat:.4f}, {dest_lng:.4f})"
    elif solicitud.direccion:
        try:
            dest_lat, dest_lng, nombre_dest = await routing_service.geocodificar_direccion(solicitud.direccion)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Debes enviar 'direccion' o 'lat'/'lng'")

    # Calcular ruta y tiempo
    ruta = await routing_service.calcular_ruta(
        origen=origen,
        destino_lat=dest_lat,
        destino_lng=dest_lng,
        direccion_nombre=nombre_dest,
    )

    # Calcular presupuesto
    presupuesto = calcular_presupuesto(ruta.km, ruta.minutos)

    return {
        "ok": True,
        "requiere_confirmacion": presupuesto.requiere_confirmacion,
        "km": presupuesto.km,
        "minutos": presupuesto.minutos_llegada,
        "estimado": presupuesto.estimado,
        "estimado_formateado": presupuesto.estimado_str,
        "rango": [presupuesto.minimo, presupuesto.maximo],
        "rango_formateado": presupuesto.rango_str,
        "direccion": ruta.direccion_formateada,
        "origen_tecnico": {
            "lat": vehiculo.latitud,
            "lng": vehiculo.longitud,
            "tipo": vehiculo.origen,
            "descripcion": vehiculo.descripcion,
        },
        "destino_cliente": {
            "lat": dest_lat,
            "lng": dest_lng,
        },
        "proveedor_ruta": ruta.proveedor,
        "mensaje": presupuesto.generar_resumen(ruta.direccion_formateada),
    }


# ============================================================================
# WEBHOOK DE WHATSAPP (TWILIO & COMPATIBLES)
# ============================================================================

@app.post("/whatsapp")
async def webhook_whatsapp(
    From: str = Form("whatsapp:+56900000000"),
    Body: Optional[str] = Form(None),
    Latitude: Optional[str] = Form(None),
    Longitude: Optional[str] = Form(None),
):
    """Webhook compatible con Twilio WhatsApp.

    Soporta tanto texto común como el botón nativo de 'Compartir Ubicación' (pin GPS) de WhatsApp.
    """
    lat_cliente = float(Latitude) if (Latitude and Latitude.strip()) else None
    lng_cliente = float(Longitude) if (Longitude and Longitude.strip()) else None

    # Procesar lógica conversacional en el ChatbotService
    respuesta_texto = await chatbot_service.procesar_mensaje_whatsapp(
        remitente=From,
        cuerpo_texto=Body,
        lat_cliente=lat_cliente,
        lng_cliente=lng_cliente,
    )

    # Retornar respuesta en formato TwiML XML para WhatsApp
    xml = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{escape(respuesta_texto)}</Message></Response>"
    return Response(content=xml, media_type="application/xml")


# ============================================================================
# DASHBOARD WEB INTERACTIVO
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard_interactivo():
    """Sirve la interfaz web moderna, clara y amigable de ZeroPinchazo."""
    index_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")
    if not os.path.exists(index_path):
        index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>ZeroPinchazo Móvil</h1><p>Sistema activo.</p>")
