# Recogida inteligente de residuos agrícolas

Panel web para la monitorización de contenedores de residuos agrícolas y la optimización
de las rutas de recogida. La aplicación compara, sobre el mismo estado de los contenedores,
la ruta **tradicional** (recogida por nivel de llenado) con la ruta **optimizada** mediante un
**algoritmo genético** (CVRP con selección), mostrando las diferencias en distancia, tiempo,
carga transportada y número de retornos al centro de tratamiento.

El sistema se sirve como aplicación web con **FastAPI** y **Uvicorn**, y se abre directamente
en el navegador.

---

## 1. Requisitos

- **Python 3.11 o superior** (probado con 3.11 y 3.13).
- Un navegador web actualizado.
- Sistema operativo Windows, macOS o Linux.

---

## 2. Instalación de las librerías

Situarse en la carpeta del proyecto (la que contiene `app.py`) y ejecutar:

```bash
pip install -r requirements.txt
```

Las dependencias principales son:

| Librería | Uso |
|---|---|
| `fastapi` | Framework de la API y del panel web |
| `uvicorn` | Servidor ASGI que ejecuta la aplicación |
| `jinja2` | Plantillas HTML del panel |
| `pandas` | Lectura de las matrices de distancias y tiempos (`.xlsx`) |
| `influxdb_client` | Lectura opcional de datos desde InfluxDB 2.7 |

---

## 3. Ejecución de la aplicación

1. Abrir una ventana de **CMD** (o terminal) en la carpeta donde se encuentra `app.py`.
2. Ejecutar:

   ```bash
   uvicorn app:app --reload
   ```

   - `app:app` indica *archivo `app.py` → variable `app`*.
   - `--reload` reinicia el servidor automáticamente al guardar cambios (útil en desarrollo).

3. Cuando la consola muestre el mensaje de arranque, abrir en el navegador:

   **<http://127.0.0.1:8000>**

4. Para detener el servidor, pulsar `Ctrl + C` en la terminal.

> Si el puerto 8000 estuviera ocupado, se puede cambiar con
> `uvicorn app:app --reload --port 8001`.

---

## 4. Uso del panel

- **Panel principal** (`/`): mapa con los contenedores, su nivel de llenado y su estado.
- **Simular aumento de residuos**: incrementa el volumen de cada contenedor de forma aleatoria
  (distribución uniforme entre 0,10 y 0,20 m³) para reproducir el paso del tiempo.
- **Optimizar ruta**: calcula y compara la ruta tradicional frente a la ruta del algoritmo
  genético, y muestra las métricas de ambas.
- **Curva de fitness** (`/fitness`): ventana emergente con la evolución del algoritmo genético.
- **Historial**: cada optimización se guarda en `data/optimization_history.csv` y puede
  consultarse o descargarse desde el panel.
