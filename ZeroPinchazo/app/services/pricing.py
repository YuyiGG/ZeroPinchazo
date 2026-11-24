"""Servicio de cálculo de tarifas y presupuestos para vulcanización móvil."""

from math import ceil
from dataclasses import dataclass
from typing import Tuple
from app.config import settings, formato_clp


@dataclass
class Presupuesto:
    km: float
    minutos_llegada: int
    estimado: int
    minimo: int
    maximo: int
    cargo_base: int
    costo_km: int
    km_extra: float
    requiere_confirmacion: bool
    estimado_str: str
    rango_str: str

    def generar_resumen(self, direccion_o_punto: str) -> str:
        """Genera un mensaje comercial claro, empático y persuasivo para el cliente."""
        if self.requiere_confirmacion:
            return (
                f"📍 *Ubicación detectada:* {direccion_o_punto}\n\n"
                f"⚠️ Notamos que te encuentras a *{self.km:.1f} km* (fuera de nuestro radio estándar de 24/7).\n"
                f"Para no darte un valor impreciso, un asesor técnico te responderá en este chat en breve "
                f"con la disponibilidad de ruta y tarifa especial."
            )

        return (
            f"🚗 *ZeroPinchazo Móvil - Cotización Inmediata*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 *Destino:* {direccion_o_punto}\n"
            f"📏 *Distancia técnico:* {self.km:.1f} km\n"
            f"⏱️ *Tiempo estimado de llegada:* ~{self.minutos_llegada} min\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Presupuesto estimado:* *{self.estimado_str}*\n"
            f"   (Rango estimado: {self.rango_str})\n\n"
            f"Incluye salida del móvil técnico y diagnóstico/reparación básica in situ.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"¿Deseas despachar la unidad a tu ubicación?\n"
            f"👉 *Responde 'SI' para confirmar el envío del técnico.*"
        )


def redondear(valor: float, paso: int) -> int:
    """Redondea hacia arriba al múltiplo del paso especificado."""
    return int(ceil(valor / paso) * paso)


def calcular_presupuesto(km: float, minutos: int) -> Presupuesto:
    """Calcula el presupuesto basado en los kilómetros calculados."""
    # Validación de distancia máxima
    requiere_confirmacion = km > settings.km_maximo

    # Cálculo de distancia facturable
    factor_viaje = 2 if settings.cobrar_ida_y_vuelta else 1
    km_facturables = km * factor_viaje
    km_extra = max(0.0, km_facturables - settings.km_incluidos)

    costo_km = km_extra * settings.precio_por_km
    subtotal = settings.cargo_base + costo_km
    monto_bruto = max(subtotal, settings.cobro_minimo)

    # Redondeos y rangos comerciales
    paso = settings.redondeo
    estimado = redondear(monto_bruto, paso)
    minimo = redondear(monto_bruto * (1.0 - settings.margen_rango), paso)
    maximo = redondear(monto_bruto * (1.0 + settings.margen_rango), paso)

    return Presupuesto(
        km=round(km, 1),
        minutos_llegada=minutos,
        estimado=estimado,
        minimo=minimo,
        maximo=maximo,
        cargo_base=settings.cargo_base,
        costo_km=int(round(costo_km)),
        km_extra=round(km_extra, 1),
        requiere_confirmacion=requiere_confirmacion,
        estimado_str=formato_clp(estimado),
        rango_str=f"{formato_clp(minimo)} a {formato_clp(maximo)}",
    )
