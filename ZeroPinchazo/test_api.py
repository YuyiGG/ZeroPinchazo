"""Pruebas de integración de endpoints FastAPI para ZeroPinchazo."""

import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print("✅ /health OK")


def test_gps_update_and_vehiculo():
    # 1. Actualizar GPS con token correcto
    payload = {
        "token": settings.gps_webhook_secret,
        "lat": -33.4500,
        "lng": -70.6500,
        "velocidad_kmh": 30.5,
    }
    r = client.post("/api/v1/gps/update", json=payload)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # 2. Consultar posición
    r_vehiculo = client.get("/api/v1/vehiculo")
    assert r_vehiculo.status_code == 200
    data = r_vehiculo.json()
    assert data["latitud"] == -33.4500
    assert data["longitud"] == -70.6500
    print("✅ /api/v1/gps/update y /api/v1/vehiculo OK")


def test_cotizar_endpoint():
    # Cotizar por coordenadas directas
    r = client.post(
        "/api/v1/cotizar",
        json={"lat": -33.4200, "lng": -70.6100, "direccion": "Providencia"},
    )
    assert r.status_code == 200
    res = r.json()
    assert res["ok"] is True
    assert res["km"] > 0
    assert res["minutos"] > 0
    assert "estimado" in res
    print(f"✅ /api/v1/cotizar OK: {res['km']} km, {res['minutos']} min, {res['estimado_formateado']}")


def test_whatsapp_webhook_pin():
    # Simular mensaje con PIN GPS de Twilio
    data = {
        "From": "whatsapp:+56987654321",
        "Latitude": "-33.4300",
        "Longitude": "-70.6200",
    }
    r = client.post("/whatsapp", data=data)
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]
    assert "Presupuesto estimado" in r.text
    print("✅ /whatsapp con Pin GPS OK")


def test_whatsapp_webhook_confirmacion():
    # Simular confirmación posterior
    data = {
        "From": "whatsapp:+56987654321",
        "Body": "SI confirmo el servicio",
    }
    r = client.post("/whatsapp", data=data)
    assert r.status_code == 200
    assert "Confirmado" in r.text
    print("✅ /whatsapp con confirmación OK")


if __name__ == "__main__":
    print("🚀 PROBANDO ENDPOINTS HTTP FASTAPI...")
    test_health()
    test_gps_update_and_vehiculo()
    test_cotizar_endpoint()
    test_whatsapp_webhook_pin()
    test_whatsapp_webhook_confirmacion()
    print("🎉 ¡TODOS LOS ENDPOINTS FUNCIONAN AL 100%!")
