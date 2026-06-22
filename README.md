# Sistema de Monitoreo y Gestión Logística de Despacho Seguro — CABA

Aplicación de escritorio desarrollada en Python con Tkinter para la planificación y supervisión de rutas de despacho dentro de la Ciudad Autónoma de Buenos Aires. Integra múltiples APIs externas para ofrecer información en tiempo real sobre condiciones de tráfico, clima y alertas del sistema de transporte público.

---

## Autores

| Nombre | Rol |
|---|---|
| Chaile Thiago | Desarrollo |
| Sabrina De Marco Naón | Desarrollo |
| Ignacio Jericó | Desarrollo |
| Carolina Lobo | Desarrollo |

Proyecto final — Programación sobre Redes

---

## Descripción del problema

En el sector del delivery y la logística, uno de los mayores problemas es el desconocimiento previo de las condiciones exactas a las que se enfrentará el repartidor. Enviar pedidos a ciegas puede derivar en retrasos severos por embotellamientos, o en accidentes físicos si el clima en la zona de destino es peligroso (lluvias fuertes, tormentas).

Esta aplicación centraliza la información necesaria para tomar una decisión informada antes de cada despacho: distancia real de la ruta, tiempo estimado con factor de tráfico según la hora del día, condiciones climáticas en el destino y alertas activas de la red de transporte de Buenos Aires.

---

## Funcionalidades

### Planificador de ruta

- Ingreso de dirección de origen y destino en texto libre (calle, barrio o punto de referencia dentro de CABA).
- Geocodificación automática de ambas direcciones a coordenadas geográficas.
- Cálculo de la ruta óptima por calles con distancia en kilómetros y duración en minutos.
- Ajuste del tiempo estimado según un factor de tráfico calculado a partir de la hora de salida ingresada:

  | Horario | Condición | Factor |
  |---|---|---|
  | 07:00 — 10:00 | Hora pico mañana | x 2.0 |
  | 10:00 — 16:00 | Tráfico normal | x 1.2 |
  | 16:00 — 19:00 | Hora pico tarde | x 2.5 |
  | 19:00 — 07:00 | Tráfico fluido | x 1.0 |

- Visualización de la ruta trazada sobre un mapa interactivo con marcadores de origen y destino.

### Evaluación de condiciones climáticas

- Consulta del clima actual en las coordenadas del destino.
- Clasificación del estado del cielo: Despejado, Lluvioso o Tormenta.
- Alerta de seguridad combinada que considera tanto el tráfico como el clima:
  - **Ruta segura** — condiciones favorables.
  - **Precaución** — lluvia o tráfico alto.
  - **Riesgo alto** — tormenta o tráfico crítico.

### Alertas de transporte GCBA en tiempo real

- Consulta directa a la API oficial de Transporte de la Ciudad de Buenos Aires.
- Muestra todas las alertas de servicio activas en la red de subterráneos: interrupciones, cortes, desvíos y demoras.
- Para cada alerta se presenta el encabezado, la descripción detallada y las líneas afectadas.
- Actualización manual bajo demanda con indicador de estado.

### Historial de despachos

- Registro automático de cada cálculo realizado durante la sesión.
- Muestra hora del cálculo, origen, destino, distancia, tiempo estimado y estado climático.

---

## APIs utilizadas

### API de Transporte — Gobierno de la Ciudad de Buenos Aires

Provee datos en tiempo real del sistema de transporte público de CABA en formato GTFS-RT.

- **URL base:** `https://apitransporte.buenosaires.gob.ar`
- **Endpoint utilizado:** `GET /subtes/serviceAlerts`
- **Autenticación:** query params `client_id` y `client_secret`
- **Documentación oficial:** https://apitransporte.buenosaires.gob.ar/console/

### Nominatim — OpenStreetMap

Servicio de geocodificación que convierte texto (nombre de calle, barrio o lugar) en coordenadas geográficas (latitud y longitud).

- **URL:** `https://nominatim.openstreetmap.org/search`
- **Método:** GET
- **Parámetros clave:** `q` (texto de búsqueda), `format=json`
- **Sin autenticación requerida** (sujeto a política de uso justo)

### OSRM — Open Source Routing Machine

Motor de ruteo de código abierto que calcula rutas por carretera entre dos coordenadas, devolviendo distancia, duración y la geometría del recorrido.

- **URL:** `https://router.project-osrm.org/route/v1/driving/{lon_origen},{lat_origen};{lon_destino},{lat_destino}`
- **Parámetros clave:** `overview=full`, `geometries=geojson`
- **Sin autenticación requerida**

### Open-Meteo

API meteorológica de código abierto que provee datos de clima actuales e históricos sin necesidad de registro.

- **URL:** `https://api.open-meteo.com/v1/forecast`
- **Parámetros clave:** `latitude`, `longitude`, `current=temperature_2m,weather_code`
- **Sin autenticación requerida**
- **Documentación:** https://open-meteo.com/en/docs

---

## Requisitos del sistema

- Python 3.9 o superior
- Conexión a internet activa (todas las APIs son externas)
- Sistema operativo: Windows, macOS o Linux

---

## Instalación de dependencias

Las bibliotecas necesarias no forman parte de la librería estándar de Python y deben instalarse antes de ejecutar la aplicación.

```bash
pip install requests tkintermapview
```

| Biblioteca | Versión mínima | Uso |
|---|---|---|
| `requests` | 2.28 | Llamadas HTTP a todas las APIs |
| `tkintermapview` | 1.15 | Widget de mapa interactivo dentro de Tkinter |
| `tkinter` | (incluida en Python) | Interfaz gráfica de escritorio |

---

## Ejecución

```bash
python centroLogistico.py
```

No se requiere ningún archivo de configuración adicional. Las credenciales de la API GCBA están incluidas directamente en el código.

---

## Estructura del proyecto

```
DeliverysProyect/
    centroLogistico.py      Código fuente completo de la aplicación
    README.md               Este documento
```

---

## Arquitectura de la aplicación

La aplicación está construida sobre un único módulo Python con separación lógica en tres capas:

**Capa de presentación (Tkinter)**
Gestiona la interfaz gráfica: dos pestañas (Planificador y Alertas GCBA), mapa interactivo, campos de entrada, etiquetas de resultado y barra de estado.

**Capa de lógica de negocio**
Funciones puras que calculan el factor de tráfico según la hora, evalúan el nivel de riesgo combinando tráfico y clima, y procesan las respuestas de las APIs para extraer la información relevante.

**Capa de acceso a datos (APIs)**
Todas las llamadas a servicios externos se ejecutan en hilos secundarios (`threading.Thread`) para evitar que la interfaz se congele durante las peticiones de red. Los resultados se devuelven al hilo principal mediante `root.after()`.

---

## Notas sobre los datos

- La geocodificación se restringe automáticamente a `CABA, Argentina` para mejorar la precisión de los resultados.
- El factor de tráfico es una estimación basada en franjas horarias conocidas; no reemplaza un servicio de tráfico en tiempo real.
- Las alertas de la API GCBA corresponden exclusivamente a la red de subterráneos de Buenos Aires.
- El servicio público de OSRM puede presentar latencia variable; para uso en producción se recomienda una instancia propia.
