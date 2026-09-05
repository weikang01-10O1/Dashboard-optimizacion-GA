import pandas as pd


class CoordinateService:

    def __init__(self):
        self.file = "data/coordenadas.xlsx"

    def load_nodes(self):

        df = pd.read_excel(self.file)

        nodes = []

        for idx, row in df.iterrows():

            node = {
                "id": idx,
                "name": row["Nombre"],
                "lat": float(row["Latitud"]),
                "lon": float(row["Longitud"]),

                # Rellenado del contenedor（%）
                "fill": 0,

                # Capacidad del contenedor（m³）
                "capacity": 1.0,

                # Estado del contenedor
                "status": "green",

                # Visitado o no 
                "visited": False
            }

            nodes.append(node)

        return nodes