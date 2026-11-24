"""Script de pruebas automatizadas para validar el cotizador ZeroPinchazo."""

import asyncio
from app.config import settings
from app.services.pricing import calcular_presupuesto
from app.services.gps import gps_service
from app.services.routing import routing_service
from app.services.chatbot import chatbot_service


async def probar_tarifas():
    print("\n--- 1. PROBANDO CÁLCULO DE TARIFAS ---")
    
    # Caso 1: 3 km (dentro de km incluidos)
    p1 = calcular_presupuesto(km=3.0, minutos=10)
    print(f"3 km  -> Estimado: {p1.estimado_str} | Rango: {p1.rango_str} | Requiere confirmación: {p1.requiere_confirmacion}")
    assert p1.estimado >= settings.cobro_minimo, "El cobro debe respetar el mínimo"
    assert not p1.requiere_confirmacion

    # Caso 2: 12.5 km (con km extra)
    p2 = calcular_presupuesto(km=12.5, minutos=25)
    print(f"12.5 km -> Estimado: {p2.estimado_str} | Rango: {p2.rango_str} | Km Extra: {p2.km_extra}")
    assert p2.costo_km > 0

    # Caso 3: 70 km (fuera de zona máxima)
    p3 = calcular_presupuesto(km=70.0, minutos=80)
    print(f"70 km -> Requiere confirmación humana: {p3.requiere_confirmacion}")
    assert p3.requiere_confirmacion, "Más de 50km debe requerir confirmación"
    print("✅ Tarifas validadas correctamente.")


async def probar_gps_y_rutas():
    print("\n--- 2. PROBANDO LECTURA DE GPS Y RUTAS ---")
    pos = await gps_service.obtener_posicion()
    print(f"Posición inicial: {pos.latitud}, {pos.longitud} ({pos.descripcion})")

    # Simular reporte de GPS directo del técnico en Plaza Baquedano
    nuevo_gps = gps_service.registrar_posicion_directa(-33.4372, -70.6345, velocidad_kmh=45.0)
    print(f"Nueva posición reportada por técnico: {nuevo_gps.latitud}, {nuevo_gps.longitud}")

    # Calcular ruta hacia Las Condes
    ruta = await routing_service.calcular_ruta(
        origen=(nuevo_gps.latitud, nuevo_gps.longitud),
        destino_lat=-33.4115,
        destino_lng=-70.5785,
        direccion_nombre="Av. Apoquindo 4000, Las Condes",
    )
    print(f"Ruta calculada vía {ruta.proveedor}:")
    print(f"  Distancia: {ruta.km:.1f} km")
    print(f"  Tiempo estimado: ~{ruta.minutos} min")
    assert ruta.km > 0
    assert ruta.minutos > 0
    print("✅ GPS y motor de rutas validados correctamente.")


async def probar_flujo_whatsapp():
    print("\n--- 3. PROBANDO FLUJO CONVERSACIONAL DE WHATSAPP ---")
    cliente_fono = "whatsapp:+56911223344"

    # Paso A: Cliente saluda
    resp_saludo = await chatbot_service.procesar_mensaje_whatsapp(
        remitente=cliente_fono,
        cuerpo_texto="Hola buenas tardes, me quedé en pana con un neumático rajado",
    )
    print("\n[Cliente]: Hola buenas tardes, me quedé en pana con un neumático rajado")
    print(f"[Bot]:\n{resp_saludo}")
    assert "ZeroPinchazo" in resp_saludo
    assert "Ubicación" in resp_saludo

    # Paso B: Cliente envía su pin de GPS de WhatsApp
    print("\n[Cliente envía Pin GPS de WhatsApp: lat=-33.4250, lng=-70.6120]")
    resp_pin = await chatbot_service.procesar_mensaje_whatsapp(
        remitente=cliente_fono,
        cuerpo_texto=None,
        lat_cliente=-33.4250,
        lng_cliente=-70.6120,
    )
    print(f"[Bot]:\n{resp_pin}")
    assert "Presupuesto estimado" in resp_pin
    assert "Responde 'SI'" in resp_pin

    # Paso C: Cliente confirma
    print("\n[Cliente]: SI, por favor vengan lo antes posible")
    resp_confirmacion = await chatbot_service.procesar_mensaje_whatsapp(
        remitente=cliente_fono,
        cuerpo_texto="SI, por favor vengan lo antes posible",
    )
    print(f"[Bot]:\n{resp_confirmacion}")
    assert "Confirmado" in resp_confirmacion
    print("✅ Flujo completo de WhatsApp validado con éxito.")


async def main():
    print("🚀 INICIANDO SUITE DE PRUEBAS ZEROPINCHAZO...")
    await probar_tarifas()
    await probar_gps_y_rutas()
    await probar_flujo_whatsapp()
    print("\n🎉 ¡TODAS LAS PRUEBAS PASARON EXITOSAMENTE!")


if __name__ == "__main__":
    asyncio.run(main())
