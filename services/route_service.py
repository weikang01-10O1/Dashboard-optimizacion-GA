from services.ga_service import GAService
from models.truck import Truck


# --------------------------------------------------
# Ruta tradicional: recorre todos los puntos de recolección (ignorando el umbral)
# La secuencia se determina por vecino más próximo y se mantiene fija en todas las simulaciones
# --------------------------------------------------


class RouteService:
    def __init__(self, matrix_service, node_service):
        self.matrix = matrix_service
        self.node_service = node_service

    # --------------------------------------------------
    # Modelo de datos
    # --------------------------------------------------
    def create_data_model(self, threshold=80):
        active_nodes = self.node_service.get_active_nodes(threshold)
        if not active_nodes:
            raise ValueError("No active nodes available.")
        distance_matrix = self.build_distance_matrix(active_nodes)
        time_matrix = self.build_time_matrix(active_nodes)
        demands = self.build_demand_vector(active_nodes)
        return {
            "distance_matrix": distance_matrix,
            "time_matrix": time_matrix,
            "active_nodes": active_nodes,
            "num_vehicles": 1,
            "depot": 0,
            "demands": demands,
        }

    def build_distance_matrix(self, active_nodes):
        full_matrix = self.matrix.get_distance_matrix()
        ids = [node.id for node in active_nodes]
        matrix = []
        for i in ids:
            row = []
            for j in ids:
                row.append(full_matrix.iloc[i, j])
            matrix.append(row)
        return matrix

    def build_time_matrix(self, active_nodes):
        full_matrix = self.matrix.get_time_matrix()
        ids = [node.id for node in active_nodes]
        matrix = []
        for i in ids:
            row = []
            for j in ids:
                row.append(full_matrix.iloc[i, j])
            matrix.append(row)
        return matrix

    def build_demand_vector(self, active_nodes):
        """
        Demanda de cada nodo (m³).
        demands[0] = 0 (depósito).
        """
        return [0.0] + [round(node.current_volume, 4) for node in active_nodes if node.id != 0]

    # --------------------------------------------------
    # Convertir cromosoma GA multiviaje en lista de trips
    #   chromosome: por ejemplo [3, 1, 0, 5, 2, 0, 4]
    #   retorna: [[0, 3, 1, 0], [0, 5, 2, 0], [0, 4, 0]]
    # --------------------------------------------------
    @staticmethod
    def _chromosome_to_trips(chromosome):
        trips = []
        current = [0]
        load = 0.0
        loads = []
        visits = []

        cur_visits = []
        for gene in chromosome:
            if gene == 0:
                current.append(0)
                trips.append(current)
                loads.append(round(load, 4))
                visits.append(cur_visits)
                current = [0]
                load = 0.0
                cur_visits = []
            else:
                current.append(gene)
                cur_visits.append(gene)
                # load se recalcula después por el llamador según demands; aquí solo es marcador
                load += 0
        if current and len(current) > 1:
            current.append(0)
            trips.append(current)
            loads.append(round(load, 4))
            visits.append(cur_visits)
        return trips, loads, visits

    # --------------------------------------------------
    # Recalcular la carga real de cada viaje usando demands
    # --------------------------------------------------
    @staticmethod
    def _recompute_trip_loads(trips, demands):
        loads = []
        for trip in trips:
            s = 0.0
            for idx in trip[1:-1]:
                s += demands[idx]
            loads.append(round(s, 4))
        return loads

    # --------------------------------------------------
    # Calcular métricas de un viaje con matrices de distancia/tiempo
    # --------------------------------------------------
    @staticmethod
    def _trip_metrics(trip, dist_mat, time_mat):
        d = 0
        t = 0
        for i in range(len(trip) - 1):
            d += dist_mat[trip[i]][trip[i + 1]]
            t += time_mat[trip[i]][trip[i + 1]]
        return d, t

    # --------------------------------------------------
    # Convertir trips en segmentos para dibujo en frontend (incluye marca is_return)
    # El último segmento de cada viaje (retorno al depósito) se muestra punteado
    # --------------------------------------------------
    def _build_segments(self, trips, trip_loads, active_nodes):
        segments = []
        trip_summaries = []
        for trip_idx, (trip, load) in enumerate(zip(trips, trip_loads)):
            trip_nodes_payload = []
            for idx in trip:
                node = active_nodes[idx]
                trip_nodes_payload.append(
                    {
                        "id": node.id,
                        "name": node.name,
                        "lat": node.lat,
                        "lon": node.lon,
                        "fill": node.fill,
                    }
                )
            trip_summaries.append(
                {
                    "trip_index": trip_idx,
                    "load": load,
                    "node_ids": [active_nodes[i].id for i in trip],
                    "nodes": trip_nodes_payload,
                }
            )

            for i in range(len(trip) - 1):
                a = active_nodes[trip[i]]
                b = active_nodes[trip[i + 1]]
                is_return = i == len(trip) - 2
                segments.append(
                    {
                        "from": {"id": a.id, "lat": a.lat, "lon": a.lon},
                        "to": {"id": b.id, "lat": b.lat, "lon": b.lon},
                        "is_return": is_return,
                        "trip_index": trip_idx,
                    }
                )
        return segments, trip_summaries

    # --------------------------------------------------
    # Resumir trips en el objeto final result
    # --------------------------------------------------
    def _summarize(self, trips, trip_loads, active_nodes, distance_matrix, time_matrix, label, visited_ids, extra=None):
        full_path_ids = []
        total_distance = 0
        total_time = 0
        total_load = sum(trip_loads)

        for trip_idx, trip in enumerate(trips):
            d, t = self._trip_metrics(trip, distance_matrix, time_matrix)
            total_distance += d
            total_time += t
            start = 1 if trip_idx > 0 else 0
            for idx in trip[start:]:
                full_path_ids.append(active_nodes[idx].id)

        segments, trip_summaries = self._build_segments(trips, trip_loads, active_nodes)

        result = {
            "label": label,
            "path": "-".join(str(x) for x in full_path_ids),
            "total_distance": round(total_distance, 2),
            "total_time": round(total_time, 2),
            "total_load": round(total_load, 2),
            "return_count": max(0, len(trips) - 1),
            "trip_count": len(trips),
            "visited_ids": visited_ids,
            "trips": trip_summaries,
            "segments": segments,
        }
        if extra:
            result.update(extra)
        return result

    # --------------------------------------------------
    # Ruta optimizada GA (multiviaje, con capacidad incorporada en cromosoma/fitness)
    # --------------------------------------------------
    def solve(self, threshold=80):
        try:
            data = self.create_data_model(threshold)
        except ValueError as e:
            return {"success": False, "message": str(e)}

        active_nodes = data["active_nodes"]
        demands = data["demands"]

        # No hay nodos activos aparte del depósito
        if len(active_nodes) <= 1:
            return {
                "success": True,
                "empty": True,
                "label": "GA Optimized",
                "path": "0-0",
                "total_distance": 0,
                "total_time": 0,
                "total_load": 0,
                "return_count": 0,
                "trip_count": 1,
                "visited_ids": [],
                "trips": [],
                "segments": [],
                "history": [],
                "active_node_ids": [],
            }

        truck = Truck()
        ga = GAService(
            distance_matrix=data["distance_matrix"],
            demands=demands,
            capacity=truck.capacity,
            population_size=120,
            generations=200,
            crossover_rate=0.9,
            mutation_rate=0.3,
            elite_size=2,
            tournament_size=5,
            bit_flip_rate=0.05,
            no_improve_limit=40,
            mandatory_threshold=0.60,
        )
        ga_result = ga.solve()

        # El cromosoma ya incluye separadores 0; quitar los 0 externos (inicio y fin)
        chromosome = ga_result["route"][1:-1]
        trips, _, visits = self._chromosome_to_trips(chromosome)
        trip_loads = self._recompute_trip_loads(trips, demands)
        visited_ids = [active_nodes[i].id for v in visits for i in v]

        summary = self._summarize(
            trips,
            trip_loads,
            active_nodes,
            data["distance_matrix"],
            data["time_matrix"],
            "GA Optimized",
            visited_ids,
            extra={
                "history": ga_result["history"],
                "ga_trip_count": ga_result.get("trip_count", len(trips)),
                "unserved_volume": ga_result.get("unserved_volume", 0),
                "selected_count": ga_result.get("selected_count", len(visited_ids)),
                "objective": ga_result.get("objective"),
            },
        )
        summary["success"] = True
        summary["active_node_ids"] = [n.id for n in active_nodes if n.id != 0]
        return summary

    def _nearest_neighbor_order_ids(self):
        all_nodes = self.node_service.get_nodes()
        non_depot_nodes = [n for n in all_nodes if n.id != 0]
        if not non_depot_nodes:
            return []

        full_dist = self.matrix.get_distance_matrix()
        unvisited = {n.id for n in non_depot_nodes}
        order_ids = []
        current = 0

        while unvisited:
            nxt = min(unvisited, key=lambda nid: full_dist.iloc[current, nid])
            order_ids.append(nxt)
            unvisited.remove(nxt)
            current = nxt

        return order_ids

    # --------------------------------------------------
    # Ruta tradicional: visitar todos los nodos en múltiples viajes (misma regla de capacidad que GA)
    # La secuencia de nodos se genera por vecino más próximo como ruta de referencia fija
    # --------------------------------------------------
    def solve_traditional(self):
        nodes_by_id = {n.id: n for n in self.node_service.get_nodes()}
        ordered_ids = self._nearest_neighbor_order_ids()

        if not ordered_ids:
            return {"success": False, "message": "No nodes for traditional route"}

        active_nodes_view = [self.node_service.get_node_by_id(0)] + [
            nodes_by_id[nid] for nid in ordered_ids
        ]

        full_dist = self.matrix.get_distance_matrix()
        full_time = self.matrix.get_time_matrix()
        ids = [n.id for n in active_nodes_view]
        dist_mat = []
        time_mat = []
        for i in ids:
            row_d = []
            row_t = []
            for j in ids:
                row_d.append(full_dist.iloc[i, j])
                row_t.append(full_time.iloc[i, j])
            dist_mat.append(row_d)
            time_mat.append(row_t)

        demands = [0.0] + [round(node.current_volume, 4) for node in active_nodes_view[1:]]

        # Usar Truck para dividir de forma voraz la secuencia fija
        truck = Truck()
        trips = []
        trip_loads = []
        visits = []
        current = [0]
        cur_load = 0.0
        cur_visits = []
        for idx in range(1, len(active_nodes_view)):
            node = active_nodes_view[idx]
            if not truck.can_collect(node):
                current.append(0)
                trips.append(current)
                trip_loads.append(round(truck.load, 4))
                visits.append(cur_visits)
                truck.reset()
                current = [0]
                cur_load = 0.0
                cur_visits = []
            truck.collect(node)
            current.append(idx)
            cur_visits.append(idx)
        current.append(0)
        trips.append(current)
        trip_loads.append(round(truck.load, 4))
        visits.append(cur_visits)

        visited_ids = [active_nodes_view[i].id for v in visits for i in v]
        summary = self._summarize(
            trips,
            trip_loads,
            active_nodes_view,
            dist_mat,
            time_mat,
            "Traditional",
            visited_ids,
        )
        summary["success"] = True
        return summary
