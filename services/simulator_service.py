import random


class SimulatorService:

    def __init__(self,node_service):

        self.node_service=node_service

    def update(self):

        for node in self.node_service.nodes:

            if node.id==0:

                continue

            # Incremento de residuos: distribución uniforme (0.10, 0.20) m³

            MIN_INCREASE_M3=0.10

            MAX_INCREASE_M3=0.20

            increase_m3=random.uniform(MIN_INCREASE_M3,MAX_INCREASE_M3)

            # Conversión a % del contenedor (0.10 m³ = 10% si la capacidad es 1 m³)

            capacity=node.capacity if node.capacity else 1.0

            increase_percent=increase_m3/capacity*100

            node.fill=min(

                100,

                round(node.fill+increase_percent,1)

            )

            node.rssi=random.randint(-120,-90)

            node.snr=round(

                random.uniform(5,10),

                1

            )

            if node.fill<40:

                node.status="green"

            elif node.fill<70:

                node.status="orange"

            else:

                node.status="red"