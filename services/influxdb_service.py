"""
Servicio de extracción de datos desde InfluxDB 2.7.

Extrae los datos de los contenedores (fill, node id, peso, batería, señal,
coordenadas y marca de tiempo) desde un bucket de InfluxDB 2.7 y los
transforma en un formato compatible con NodeService.
"""

import os
from datetime import datetime

from influxdb_client import InfluxDBClient

# Configuración por variables de entorno (más seguro que hardcodear credenciales)
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "")

# Rango por defecto: últimas 24 horas
DEFAULT_RANGE_HOURS = int(os.getenv("INFLUXDB_RANGE_HOURS", "24"))


class InfluxDBService:
    """Lectura de datos de contenedores desde InfluxDB 2.7."""

    # Campos devueltos por la consulta
    FIELDS = [
        "fill",
        "weight",
        "battery",
        "rssi",
        "snr",
        "capacity",
        "lat",
        "lon",
    ]

    def __init__(
        self,
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
        bucket=INFLUXDB_BUCKET,
    ):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket

    def _client(self):
        """Crear cliente de InfluxDB a partir de la configuración."""
        if not self.token or not self.org or not self.bucket:
            raise ValueError(
                "Faltan credenciales de InfluxDB: define INFLUXDB_TOKEN, "
                "INFLUXDB_ORG e INFLUXDB_BUCKET."
            )
        return InfluxDBClient(url=self.url, token=self.token, org=self.org)

    def _build_query(self, range_hours):
        """
        Construir consulta Flux.
        Devuelve el último valor de cada campo, agrupado por node_id.
        """
        return f'''
from(bucket: "{self.bucket}")
  |> range(start: -{range_hours}h)
  |> filter(fn: (r) => r["_measurement"] == "waste_container")
  |> filter(fn: (r) => {self._field_filter()})
  |> last()
'''

    def _field_filter(self):
        """Condición OR de la lista de campos (sintaxis válida en Flux)."""
        return " or ".join(f'r["_field"] == "{f}"' for f in self.FIELDS)

    def fetch_latest(self, range_hours=DEFAULT_RANGE_HOURS):
        """
        Extraer últimos valores de cada contenedor.

        Retorna una lista de diccionarios:
        [
            {
                "node_id": 1,
                "name": "BDJ_04",
                "fill": 85.0,
                "capacity": 1.0,
                "lat": 38.83,
                "lon": -6.78,
                "time": datetime(...)
            },
            ...
        ]
        """
        query = self._build_query(range_hours)
        nodes = {}

        with self._client() as client:
            tables = client.query_api().query(query, org=self.org)

            for table in tables:
                for record in table.records:
                    node_id = self._parse_node_id(record)
                    if node_id is None:
                        continue

                    if node_id not in nodes:
                        nodes[node_id] = {
                            "node_id": node_id,
                            "name": record.values.get("name") or f"NODE_{node_id}",
                            "time": record.get_time(),
                        }

                    field = record.get_field()
                    value = record.get_value()
                    if field in self.FIELDS:
                        nodes[node_id][field] = value

        return list(nodes.values())

    def fetch_history(self, node_id, field="fill", range_hours=DEFAULT_RANGE_HOURS):
        """
        Extraer histórico de un campo para un contenedor concreto.

        Retorna lista de {"time": datetime, "value": float}.
        """
        query = f'''
from(bucket: "{self.bucket}")
  |> range(start: -{range_hours}h)
  |> filter(fn: (r) => r["_measurement"] == "waste_container")
  |> filter(fn: (r) => r["node_id"] == "{node_id}")
  |> filter(fn: (r) => r["_field"] == "{field}")
  |> sort(columns: ["_time"])
'''

        history = []
        with self._client() as client:
            tables = client.query_api().query(query, org=self.org)
            for table in tables:
                for record in table.records:
                    history.append(
                        {
                            "time": record.get_time(),
                            "value": record.get_value(),
                        }
                    )
        return history

    @staticmethod
    def _parse_node_id(record):
        """Convertir la etiqueta node_id a entero si es posible."""
        raw = record.values.get("node_id")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def to_node_updates(records):
        """
        Convertir registros de InfluxDB a actualizaciones de nodos.

        Devuelve {node_id: {"fill": ..., "weight": ...}} listo para que
        NodeService sincronice el estado de los contenedores.
        """
        updates = {}
        for r in records:
            updates[r["node_id"]] = {
                "fill": r.get("fill"),
                "weight": r.get("weight"),
                "battery": r.get("battery"),
            }
        return updates


if __name__ == "__main__":
    # Ejemplo de uso (no se ejecuta al importar el módulo)
    service = InfluxDBService()
    data = service.fetch_latest()
    print(f"Registros extraídos: {len(data)}")
    print(f"Consulta ejecutada: {datetime.now().isoformat(timespec='seconds')}")
    for item in data[:10]:
        print(item)
