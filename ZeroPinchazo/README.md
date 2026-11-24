# 🛞 ZeroPinchazo - Cotizador Automático de Vulcanización Móvil en Tiempo Real

Sistema de respuesta inmediata para cotizar servicios de vulcanización a domicilio o emergencias en ruta según la **ubicación GPS en tiempo real del vehículo técnico** y la **ubicación del cliente**.

---

## ⚡ ¿Por qué esta solución resuelve la pérdida de clientes?

En una vulcanización móvil, un cliente en pana necesita una respuesta en menos de **30 segundos**:
1. **Antes:** El cliente escribe por WhatsApp -> El operador llama al técnico para preguntar dónde anda -> El técnico va manejando y no contesta -> Pasan 10 a 20 minutos -> El cliente ya llamó a otra vulcanización y se perdió la venta.
2. **Con ZeroPinchazo:** El cliente envía su ubicación por WhatsApp (pin GPS o dirección) -> El sistema consulta el GPS del móvil en milisegundos -> Calcula distancia y tiempo de llegada por ruta real -> Genera el presupuesto exacto en CLP y responde **en 2 segundos**.
3. **Confirmación Inmediata:** Si el cliente responde *"SÍ"*, el sistema confirma el pedido y alerta al técnico con la ruta lista.

---

## 🏗️ Arquitectura del Sistema

```
[Cliente WhatsApp] 
        │ (Pin GPS 📍 o "Av. Providencia 1234")
        ▼
   [Twilio / Meta]
        │ Webhook POST /whatsapp
        ▼
   [ZeroPinchazo API (FastAPI)]
        ├── 1. Lee GPS del Móvil (Traccar o Webhook directo)
        ├── 2. Calcula Ruta y Tráfico (Google Maps / Fallback OSRM gratuito)
        ├── 3. Aplica Matriz de Tarifas (Base + Km Extra + Redondeo CLP)
        └── 4. Guarda sesión y responde TwiML en < 1 segundo
```

---

## 📦 Estructura del Proyecto

```
ZeroPinchazo/
├── app/
│   ├── __init__.py
│   ├── config.py           # Tarifas del negocio y variables de entorno
│   ├── main.py             # Endpoints FastAPI y Webhook de WhatsApp
│   └── services/
│       ├── gps.py          # Conector Traccar + Webhook directo + Taller base
│       ├── routing.py      # Google Maps + Fallback gratuito OSRM/Nominatim
│       ├── pricing.py      # Algoritmo de tarifas, redondeo y rangos CLP
│       └── chatbot.py      # Inteligencia de conversación y estados WhatsApp
├── static/                 # Recursos visuales del dashboard
├── .env.example            # Plantilla de variables de entorno
├── requirements.txt        # Dependencias de Python
├── test_system.py          # Pruebas automatizadas de lógica y conversación
├── test_api.py             # Pruebas automatizadas de endpoints HTTP
└── README.md               # Documentación y guía de despliegue
```

---

## ⚙️ Configuración (.env)

Crea un archivo `.env` basado en `.env.example`:

```bash
# Google Maps (Opcional: Si se deja vacío, el sistema usa OSRM + OpenStreetMap 100% gratis)
GOOGLE_MAPS_API_KEY=

# Servidor GPS Traccar (Opcional si usas reporte directo por celular)
GPS_BASE_URL=https://tu-servidor-traccar.cl
GPS_USER=usuario_traccar
GPS_PASS=clave_traccar
GPS_DEVICE_ID=1

# Token secreto para que el técnico reporte GPS directo desde su celular
GPS_WEBHOOK_SECRET=zeropinchazo_secret_gps

# Ubicación del Taller Central (Respaldo si el GPS estuviera apagado)
BASE_LAT=-33.4489
BASE_LNG=-70.6693
BASE_NOMBRE="Taller Central ZeroPinchazo"

# Tarifas en CLP
TARIFA_CARGO_BASE=15000       # Salida técnica base
TARIFA_PRECIO_KM=1200         # Valor adicional por km
TARIFA_KM_INCLUIDOS=3         # Km incluidos en el cargo base
TARIFA_COBRAR_IDA_VUELTA=false
TARIFA_COBRO_MINIMO=18000
TARIFA_REDONDEO=500
TARIFA_MARGEN_RANGO=0.10      # +-10%
TARIFA_KM_MAXIMO=50           # Sobre esto deriva a un asesor humano
```

---

## 🛰️ ¿Cómo conectar el GPS del vehículo?

El sistema soporta **3 formas distintas de saber dónde está el técnico**:

### Opción A: Con Servidor Traccar (Dispositivo GPS Físico en la camioneta)
Si tu vehículo tiene un GPS (Coban, Teltonika, Concox, Sinotrack) conectado a un servidor Traccar:
- Configura `GPS_BASE_URL`, `GPS_USER`, `GPS_PASS` y `GPS_DEVICE_ID`.
- El sistema consulta automáticamente las coordenadas cada 15 segundos con cache en memoria.

### Opción B: Gratis desde el Celular del Técnico (Sin Servidor Traccar)
El técnico puede reportar su ubicación directamente enviando un HTTP POST a tu servidor:
- **Endpoint:** `POST /api/v1/gps/update`
- **Body JSON:**
  ```json
  {
    "token": "zeropinchazo_secret_gps",
    "lat": -33.4372,
    "lng": -70.6345,
    "velocidad_kmh": 45.0
  }
  ```
- *Tip práctico:* Puedes instalar en el teléfono Android del técnico una app gratuita de envío de ubicación periódica (como **Traccar Client** o **GPS Logger**) configurada hacia este webhook.

### Opción C: Taller Base (Failsafe)
Si el GPS se queda sin batería o no hay señal, el sistema automáticamente calcula desde las coordenadas del taller base fijadas en `BASE_LAT` y `BASE_LNG`. ¡Nunca se pierde una cotización!

---

## 📲 ¿Cómo conectar WhatsApp (Twilio)?

1. Entra a tu consola de **Twilio** > **Develop** > **Messaging** > **Try it out** > **Send a WhatsApp message**.
2. En la configuración del Sandbox de WhatsApp (o tu número oficial de producción):
   - **WHEN A MESSAGE COMES IN:** selecciona `HTTP POST`.
   - **URL:** `https://tu-dominio-o-ngrok.com/whatsapp`
3. ¡Listo! Cualquier mensaje o pin de ubicación que mande un cliente será respondido instantáneamente.

---

## 🚀 Puesta en Marcha Local

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Ejecutar pruebas unitarias
```bash
python test_system.py
python test_api.py
```

### 3. Levantar el servidor
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Abrir el Dashboard en el navegador
Ingresa a `http://localhost:8000`:
- Podrás ver el estado del GPS del técnico en vivo.
- Podrás cambiar la posición del móvil para simular que está en distintas comunas.
- Podrás probar cómo respondería el bot de WhatsApp con direcciones reales de Santiago.
- Documentación Swagger interactiva en `http://localhost:8000/docs`.
