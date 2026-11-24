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
    """Panel de control visual para monitorear el GPS y simular cotizaciones al instante."""
    vehiculo = await gps_service.obtener_posicion()

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ZeroPinchazo - Panel de Cotización y GPS</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body {{ background-color: #f4f6f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            .brand-header {{ background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white; padding: 25px 0; }}
            .card {{ border: none; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            .badge-live {{ animation: pulse 2s infinite; }}
            @keyframes pulse {{
                0% {{ opacity: 1; }}
                50% {{ opacity: 0.4; }}
                100% {{ opacity: 1; }}
            }}
            .phone-preview {{
                background-color: #0c1014;
                border-radius: 24px;
                padding: 15px;
                color: #e9edef;
                font-size: 0.9rem;
                min-height: 250px;
                border: 4px solid #2a3942;
                white-space: pre-line;
            }}
            .whatsapp-msg {{
                background-color: #005c4b;
                border-radius: 8px;
                padding: 12px;
                display: inline-block;
                max-width: 100%;
            }}
        </style>
    </head>
    <body>
        <div class="brand-header text-center">
            <div class="container">
                <h2><i class="fas fa-truck-pickup me-2"></i> ZeroPinchazo</h2>
                <p class="mb-0">Automatización de Cotizaciones Inmediatas según GPS Móvil</p>
            </div>
        </div>

        <div class="container my-4">
            <div class="row g-4">
                <!-- Columna Izquierda: Estado del GPS y Móvil -->
                <div class="col-lg-5">
                    <div class="card p-3 mb-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="mb-0"><i class="fas fa-satellite text-primary me-2"></i> Estado del Móvil</h5>
                            <span class="badge bg-success badge-live">● EN VIVO</span>
                        </div>
                        <p class="text-muted small mb-2">Posición actual del técnico usada para calcular las distancias:</p>
                        <div class="p-3 bg-light rounded-3 mb-3">
                            <div class="row g-2">
                                <div class="col-6"><strong>Latitud:</strong> <span id="gpsLat">{vehiculo.latitud:.5f}</span></div>
                                <div class="col-6"><strong>Longitud:</strong> <span id="gpsLng">{vehiculo.longitud:.5f}</span></div>
                                <div class="col-12"><strong>Fuente:</strong> <span class="badge bg-info text-dark">{vehiculo.descripcion}</span></div>
                            </div>
                        </div>

                        <h6>Simular Nueva Posición del Técnico:</h6>
                        <div class="row g-2 mb-2">
                            <div class="col-6">
                                <input type="number" step="0.0001" id="mockLat" class="form-control form-control-sm" value="{vehiculo.latitud}">
                            </div>
                            <div class="col-6">
                                <input type="number" step="0.0001" id="mockLng" class="form-control form-control-sm" value="{vehiculo.longitud}">
                            </div>
                        </div>
                        <button class="btn btn-outline-primary btn-sm w-100" onclick="actualizarGPSManual()">
                            <i class="fas fa-map-marker-alt me-1"></i> Actualizar Posición del Móvil
                        </button>
                    </div>

                    <!-- Configuración de Tarifas -->
                    <div class="card p-3">
                        <h5><i class="fas fa-calculator text-warning me-2"></i> Tarifa Activa</h5>
                        <ul class="list-group list-group-flush small">
                            <li class="list-group-item d-flex justify-content-between">
                                <span>Salida / Cargo Base:</span> <strong>${settings.cargo_base:,} CLP</strong>
                            </li>
                            <li class="list-group-item d-flex justify-content-between">
                                <span>Km Incluidos:</span> <strong>{settings.km_incluidos} km</strong>
                            </li>
                            <li class="list-group-item d-flex justify-content-between">
                                <span>Valor Km Adicional:</span> <strong>${settings.precio_por_km:,} CLP/km</strong>
                            </li>
                            <li class="list-group-item d-flex justify-content-between">
                                <span>Cobro Mínimo:</span> <strong>${settings.cobro_minimo:,} CLP</strong>
                            </li>
                        </ul>
                    </div>
                </div>

                <!-- Columna Derecha: Probador en Vivo de Cotizaciones -->
                <div class="col-lg-7">
                    <div class="card p-4">
                        <h4><i class="fas fa-bolt text-warning me-2"></i> Simulador Rápido de Cotización</h4>
                        <p class="text-muted small">Escribe una dirección de un cliente o haz clic en los accesos rápidos para ver el cálculo instantáneo.</p>

                        <div class="mb-3">
                            <label class="form-label fw-bold">Dirección del Cliente:</label>
                            <div class="input-group">
                                <input type="text" id="direccionInput" class="form-control" placeholder="Ej: Av. Providencia 1234, Santiago" value="Av. Providencia 1234, Santiago">
                                <button class="btn btn-primary px-4" id="btnCotizar" onclick="ejecutarCotizacion()">
                                    <i class="fas fa-paper-plane me-1"></i> Cotizar
                                </button>
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="form-label small text-muted">Ejemplos rápidos:</label>
                            <div class="d-flex flex-wrap gap-2">
                                <button class="btn btn-sm btn-light border" onclick="setDireccion('Plaza Italia, Santiago')">📍 Plaza Italia</button>
                                <button class="btn btn-sm btn-light border" onclick="setDireccion('Mall Plaza Vespucio, La Florida')">📍 La Florida</button>
                                <button class="btn btn-sm btn-light border" onclick="setDireccion('Av. Las Condes 11000, Las Condes')">📍 Las Condes</button>
                                <button class="btn btn-sm btn-light border" onclick="setDireccion('Plaza de Maipú, Maipú')">📍 Maipú</button>
                            </div>
                        </div>

                        <hr>

                        <h5><i class="fab fa-whatsapp text-success me-2"></i> Respuesta que recibe el cliente por WhatsApp:</h5>
                        <div class="phone-preview mt-2">
                            <div class="whatsapp-msg" id="previewMsg">
                                Presiona "Cotizar" para simular la respuesta inmediata que recibirá el cliente...
                            </div>
                        </div>

                        <div id="metricasCotizacion" class="row text-center mt-3 d-none">
                            <div class="col-4">
                                <div class="p-2 border rounded">
                                    <small class="text-muted d-block">Distancia</small>
                                    <strong class="fs-5" id="resKm">-</strong>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="p-2 border rounded">
                                    <small class="text-muted d-block">Llegada</small>
                                    <strong class="fs-5 text-primary" id="resMin">-</strong>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="p-2 border rounded">
                                    <small class="text-muted d-block">Presupuesto</small>
                                    <strong class="fs-5 text-success" id="resMonto">-</strong>
                                </div>
                            </div>
                        </div>

                    </div>
                </div>
            </div>
        </div>

        <script>
            function setDireccion(dir) {{
                document.getElementById('direccionInput').value = dir;
                ejecutarCotizacion();
            }}

            async function ejecutarCotizacion() {{
                const dir = document.getElementById('direccionInput').value.trim();
                const btn = document.getElementById('btnCotizar');
                const preview = document.getElementById('previewMsg');
                const metricas = document.getElementById('metricasCotizacion');

                if (!dir) return alert('Ingresa una dirección');

                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Calculando...';
                preview.innerText = 'Calculando distancia desde el móvil y consultando tarifas...';

                try {{
                    const resp = await fetch('/api/v1/cotizar', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ direccion: dir }})
                    }});

                    const data = await resp.json();

                    if (!resp.ok) {{
                        preview.innerHTML = '❌ ' + (data.detail || 'Error al cotizar');
                        metricas.classList.add('d-none');
                    }} else {{
                        preview.innerText = data.mensaje;
                        document.getElementById('resKm').innerText = data.km + ' km';
                        document.getElementById('resMin').innerText = '~' + data.minutos + ' min';
                        document.getElementById('resMonto').innerText = data.estimado_formateado;
                        metricas.classList.remove('d-none');
                    }}
                }} catch (e) {{
                    preview.innerText = 'Error de conexión con la API: ' + e;
                }} finally {{
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-paper-plane me-1"></i> Cotizar';
                }}
            }}

            async function actualizarGPSManual() {{
                const lat = parseFloat(document.getElementById('mockLat').value);
                const lng = parseFloat(document.getElementById('mockLng').value);

                try {{
                    const resp = await fetch('/api/v1/gps/update', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            token: '{settings.gps_webhook_secret}',
                            lat: lat,
                            lng: lng
                        }})
                    }});
                    const data = await resp.json();
                    if (resp.ok) {{
                        alert('¡Posición GPS del móvil actualizada con éxito!');
                        document.getElementById('gpsLat').innerText = lat.toFixed(5);
                        document.getElementById('gpsLng').innerText = lng.toFixed(5);
                    }} else {{
                        alert('Error: ' + data.detail);
                    }}
                }} catch (e) {{
                    alert('Error: ' + e);
                }}
            }}

            // Ejecutar cotización inicial automática al cargar
            window.onload = () => ejecutarCotizacion();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
