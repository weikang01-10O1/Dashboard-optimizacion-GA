import random

from models.node import Node
from services.coordinate_service import CoordinateService


class NodeService:

    def __init__(self):

        coordinate_service = CoordinateService()

        coordinates = coordinate_service.load_nodes()

        self.nodes = []

        for c in coordinates:

            node = Node(
                id=c["id"],
                name=c["name"],
                lat=c["lat"],
                lon=c["lon"],
                capacity=c["capacity"]
            )

            if node.id == 0:
                node.fill = 0
            else:
                node.fill = random.randint(10, 40)

            self.nodes.append(node)

    # ===== Método obligatorio =====

    def get_nodes(self):
        return self.nodes

    # ===== Estadísticas del panel =====

    def get_statistics(self):

        total = len(self.nodes)

        average = sum(node.fill for node in self.nodes) / total

        critical = len(
            [node for node in self.nodes if node.fill >= 85]
        )

        return {
            "total": total,
            "average": average,
            "critical": critical
        }

    # Función añadida en NodeService
    def get_active_nodes(self, threshold=85):

        active = []

        for node in self.nodes:

        # BIOFARM siempre se mantiene
            if node.id == 0:
                active.append(node)
                continue

            if node.fill >= threshold:
                active.append(node)

        return active

    def get_total_volume(self):

        return round(

            sum(node.current_volume for node in self.nodes),

            2)

    # ===== Reiniciar fill de nodos visitados =====

    def reset_fills(self, visited_ids):

        """Poner en cero el fill de nodos visitados; los no visitados se mantienen igual"""

        visited_set = set(visited_ids or [])

        for node in self.nodes:

            if node.id in visited_set and node.id != 0:

                node.fill = 0

    def get_node_by_id(self, node_id):

        for node in self.nodes:

            if node.id == node_id:

                return node

        return None
