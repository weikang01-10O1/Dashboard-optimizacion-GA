import random


class SimulatorService:

    def __init__(self,node_service):

        self.node_service=node_service

    def update(self):

        for node in self.node_service.nodes:

            if node.id==0:

                continue

            increase=random.randint(1,4)

            node.fill=min(

                100,

                node.fill+increase

            )

            node.weight=node.fill*10

            node.rssi=random.randint(-120,-90)

            node.snr=round(

                random.uniform(5,10),

                1

            )

            if node.fill<40:

                node.status="green"

            elif node.fill<80:

                node.status="orange"

            else:

                node.status="red"