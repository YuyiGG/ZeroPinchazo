"""Servicio de conversación y procesamiento de WhatsApp para ZeroPinchazo."""

import time
import logging
import re
from dataclasses import dataclass
from typing import Optional, Dict, Tuple

from app.services.gps import gps_service
from app.services.routing import routing_service
from app.services.pricing import calcular_presupuesto, Presupuesto
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EstadoSesion:
    telefono: str
    ultimo_mensaje_ts: float
    estado: str  # 'inicio', 'cotizado', 'confirmado'
    ultima_direccion: Optional[str] = None
    ultimo_presupuesto: Optional[Presupuesto] = None
    lat_cliente: Optional[float] = None
    lng_cliente: Optional[float] = None


class ChatbotService:
    def __init__(self):
        # Memoria en ejecución de conversaciones recientes por teléfono
        self._sesiones: Dict[str, EstadoSesion] = {}

    def _obtener_sesion(self, telefono: str) -> EstadoSesion:
        ahora = time.time()
        sesion = self._sesiones.get(telefono)
        # Si no existe o pasaron más de 2 horas, reiniciamos sesión
        if not sesion or (ahora - sesion.ultimo_mensaje_ts) > 7200:
            sesion = EstadoSesion(
                telefono=telefono,
                ultimo_mensaje_ts=ahora,
                estado="inicio",
            )
            self._sesiones[telefono] = sesion
        else:
            sesion.ultimo_mensaje_ts = ahora
        return sesion

    def _es_confirmacion(self, texto: str) -> bool:
        t = texto.strip().lower()
        # Acepta: "si", "sí", "si, por favor", "sí confirmo", "ok vengan", "dale", etc.
        patron = r'^(s[ií]|ok|dale|confirmo|confirmar|vengan|venga|afirmativo|quiero el servicio)\b'
        return bool(re.search(patron, t))

    def _es_saludo_o_consulta(self, texto: str) -> bool:
        t = texto.strip().lower()
        if not t:
            return True

        palabras_clave = [
            "hola", "buenas", "buenos dias", "buenas tardes", "buenas noches",
            "ayuda", "auxilio", "pana", "pinchazo", "neumatico", "neumático",
            "rueda", "llanta", "parche", "urgente", "emergencia", "socorro",
            "cuanto", "cuánto", "precio", "tarifa", "valor", "cotizar", "info",
            "necesito", "tienen servicio", "disponible", "estan trabajando"
        ]
        
        # Si tiene alguna de estas palabras y NO parece una dirección con calle y número
        tiene_palabra_clave = any(p in t for p in palabras_clave)
        tiene_numero = any(c.isdigit() for c in t)

        # Si saluda o pide ayuda y no tiene numeración, es consulta/saludo seguro
        if tiene_palabra_clave and not tiene_numero:
            return True
        
        # Si es un saludo corto de menos de 15 caracteres
        if len(t) < 15 and ("hola" in t or "buenas" in t):
            return True

        return False

    async def procesar_mensaje_whatsapp(
        self,
        remitente: str,
        cuerpo_texto: Optional[str],
        lat_cliente: Optional[float] = None,
        lng_cliente: Optional[float] = None,
    ) -> str:
        """Procesa un mensaje entrante de Twilio WhatsApp y devuelve la respuesta en texto."""
        sesion = self._obtener_sesion(remitente)
        texto = (cuerpo_texto or "").strip()

        # ---------------------------------------------------------------------
        # CASO 1: EL CLIENTE ENVIÓ SU UBICACIÓN GPS DIRECTA (PIN DE WHATSAPP)
        # ---------------------------------------------------------------------
        if lat_cliente is not None and lng_cliente is not None:
            return await self._cotizar_coordenadas(sesion, lat_cliente, lng_cliente, "Ubicación compartida por GPS 📍")

        # ---------------------------------------------------------------------
        # CASO 2: EL CLIENTE RESPONDE CONFIRMANDO EL SERVICIO ("SI", "CONFIRMAR")
        # ---------------------------------------------------------------------
        if self._es_confirmacion(texto):
            if sesion.estado == "cotizado" and sesion.ultimo_presupuesto:
                sesion.estado = "confirmado"
                p = sesion.ultimo_presupuesto
                
                # Registro y alerta para el operador
                logger.info(
                    f"🔥 ¡SERVICIO CONFIRMADO! Cliente: {remitente} | Destino: {sesion.ultima_direccion} | "
                    f"Monto: {p.estimado_str} | Distancia: {p.km} km | Llegada: ~{p.minutos_llegada} min"
                )

                mensaje_confirmacion = (
                    f"🎉 *¡Servicio Confirmado con Éxito!*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👨‍🔧 Hemos asignado el móvil técnico de *ZeroPinchazo* a tu ubicación.\n"
                    f"⏱️ *Tiempo estimado de llegada:* ~{p.minutos_llegada} minutos.\n"
                    f"💰 *Monto a pagar:* {p.estimado_str} (Efectivo, Transferencia o Tarjeta).\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📞 Un técnico se comunicará contigo si requiere alguna referencia de acceso.\n"
                    f"¡Mantén tu teléfono atento!"
                )
                return mensaje_confirmacion
            else:
                return (
                    "¡Hola! Con gusto te enviamos un técnico. Por favor primero indícanos dónde te encuentras:\n\n"
                    "👉 Comparte tu ubicación en WhatsApp (📎 > Ubicación 📍) o escribe tu dirección (Calle, Número, Comuna)."
                )

        # ---------------------------------------------------------------------
        # CASO 3: MENSAJE GENÉRICO, SALUDO O CONSULTA
        # ---------------------------------------------------------------------
        if self._es_saludo_o_consulta(texto) or not texto:
            return (
                "👋 ¡Hola! Bienvenido a *ZeroPinchazo* - Vulcanización Móvil 🛞⚡\n\n"
                "Para darte el valor exacto y decirte en cuántos minutos llega el técnico a ayudarte:\n\n"
                "📍 *Opción 1 (Más rápida):* Presiona el icono de adjuntar 📎 y selecciona *Ubicación* para enviarnos tu punto actual.\n"
                "📝 *Opción 2:* Escribe tu dirección (ej: *Av. Vicuña Mackenna 4500, Macul*)."
            )

        # ---------------------------------------------------------------------
        # CASO 4: EL CLIENTE ESCRIBIÓ UNA DIRECCIÓN EN TEXTO
        # ---------------------------------------------------------------------
        try:
            lat, lng, dir_formateada = await routing_service.geocodificar_direccion(texto)
            return await self._cotizar_coordenadas(sesion, lat, lng, dir_formateada)
        except ValueError as e:
            logger.warning(f"Error geocodificando '{texto}': {e}")
            return (
                f"⚠️ No pudimos ubicar con certeza la dirección: *'{texto}'*.\n\n"
                f"Por favor especifica: *Calle, Número y Comuna* (ej: *Av. Matta 1234, Santiago Centro*).\n"
                f"O si lo prefieres, compártenos tu ubicación GPS directa mediante el botón de adjuntar 📎 > *Ubicación* 📍."
            )

    async def _cotizar_coordenadas(
        self,
        sesion: EstadoSesion,
        lat_cliente: float,
        lng_cliente: float,
        nombre_direccion: str,
    ) -> str:
        """Obtiene la posición del móvil, calcula la ruta y retorna el mensaje de cotización."""
        vehiculo = await gps_service.obtener_posicion()
        origen = (vehiculo.latitud, vehiculo.longitud)

        resultado_ruta = await routing_service.calcular_ruta(
            origen=origen,
            destino_lat=lat_cliente,
            destino_lng=lng_cliente,
            direccion_nombre=nombre_direccion,
        )

        presupuesto = calcular_presupuesto(resultado_ruta.km, resultado_ruta.minutos)

        # Guardar en la sesión del cliente
        sesion.estado = "cotizado"
        sesion.lat_cliente = lat_cliente
        sesion.lng_cliente = lng_cliente
        sesion.ultima_direccion = resultado_ruta.direccion_formateada
        sesion.ultimo_presupuesto = presupuesto

        return presupuesto.generar_resumen(resultado_ruta.direccion_formateada)


chatbot_service = ChatbotService()
