# 🚀 Guía de Despliegue en Vercel (1 Clic) - ZeroPinchazo

Para que tus clientes tengan **cero asperezas** y puedan cotizar y pedir el auxilio en **3 segundos desde cualquier celular**, esta versión está optimizada para publicarse gratis en **Vercel**.

---

## 🌟 Método 1: Arrastrar y Soltar en Vercel (El más fácil)

1. Entra a [vercel.com](https://vercel.com) e inicia sesión con tu cuenta.
2. Si tienes la herramienta Vercel CLI o vinculas tu repositorio GitHub:
   - Sube la carpeta del proyecto a GitHub.
   - En Vercel haz clic en **"Add New Project"** e importa el repositorio.
   - Framework Preset: **Other** (lo detecta automáticamente como sitio estático de alto rendimiento).
   - Haz clic en **Deploy**.

¡En 15 segundos tendrás tu enlace tipo `https://zero-pinchazo.vercel.app` listo para compartir!

---

## ⚡ ¿Cómo funciona la experiencia sin fricción para el usuario?

1. **El cliente entra al link desde su teléfono.**
2. Presiona el botón verde grande: **"Usar Mi Ubicación Actual (1 Clic)"**.
   - El navegador obtiene sus coordenadas exactas por GPS.
3. El sistema traza la ruta real de conducción contra la posición del móvil de la vulcanización usando OSRM.
4. Muestra en pantalla:
   - **Distancia:** ej. `4.2 km`.
   - **Tiempo de llegada:** ej. `~10 min`.
   - **Presupuesto exacto:** ej. `$18.000 CLP`.
   - **Mapa con la ruta visual trazada.**
5. El cliente presiona el botón: **"Enviar Técnico a Mi Ubicación (WhatsApp)"**.
   - Le abre WhatsApp directamente con un mensaje formal precargado listo para enviar:
     > *"👋 ¡Hola ZeroPinchazo! Necesito el auxilio móvil urgente:*  
     > *📍 Ubicación: Av. Providencia 1234*  
     > *📏 Distancia: 4.2 km*  
     > *⏱️ Llegada aproximada: ~10 min*  
     > *💰 Presupuesto cotizado: $18.000 CLP*  
     > *👉 Por favor confirmar despacho del técnico."*

---

## ⚙️ ¿Cómo actualizar las tarifas o la ubicación del técnico?

En la esquina superior derecha de la página hay un icono de ajustes (⚙️ / sliders):
- Puedes cambiar la **posición GPS del móvil técnico** (latitud y longitud).
- Puedes ajustar el **cargo base ($15.000)**, el **precio por km ($1.200)** o el **número de WhatsApp de recepción**.
- Los cambios quedan guardados en tu navegador automáticamente.
