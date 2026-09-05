from services.ga_service import GAService
from models.truck import Truck


# --------------------------------------------------
# 传统路线：按给定顺序遍历所有节点（忽略阈值）
# --------------------------------------------------
TRADITIONAL_ORDER = [
    "BDJ_04",
    "BDJ_03",
    "BDJ_02",
    "BDJ_01",
    "GVA_01",
    "VALZD_01",
    "MTJ_06",
    "ARYSS_01",
    "RGUAD_01",
    "MRIDA_01",
    "ALMDJ_01",
    "ALBA_01",
]


class RouteService:
    def __init__(self, matrix_service, node_service):
        self.matrix = matrix_service
        self.node_service = node_service

    # --------------------------------------------------
    # 数据模型
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
        每个节点的需求 (m³)。
        demands[0] = 0 (depot)。
        """
        return [0.0] + [round(node.current_volume, 4) for node in active_nodes if node.id != 0]

    # --------------------------------------------------
    # 把 GA 多趟染色体拆成 trips 列表
    #   chromosome: 例如 [3, 1, 0, 5, 2, 0, 4]
    #   返回: [[0, 3, 1, 0], [0, 5, 2, 0], [0, 4, 0]]
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
                # load 由调用方事后按 demands 重算，这里只占位
                load += 0
        if current and len(current) > 1:
            current.append(0)
            trips.append(current)
            loads.append(round(load, 4))
            visits.append(cur_visits)
        return trips, loads, visits

    # --------------------------------------------------
    # 用 demands 重算每趟真实装载量
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
    # 用距离/时间矩阵给一趟计算统计
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
    # 把 trips 转成前端画图用的段 (含 is_return 标记)
    # 每趟的最后一段 (回仓库) 为虚线
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
    # 汇总 trips 为最终 result 字段
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
    # GA 优化路线（多趟——把容量编进染色体/适应度）
    # --------------------------------------------------
    def solve(self, threshold=80):
        try:
            data = self.create_data_model(threshold)
        except ValueError as e:
            return {"success": False, "message": str(e)}

        active_nodes = data["active_nodes"]
        demands = data["demands"]

        # 没有除仓库外的活跃节点
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
            generations=400,
        )
        ga_result = ga.solve()

        # 染色体里已含分隔 0，去掉最外层 0（首尾）
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
                "capacity_violation": ga_result.get("capacity_violation", 0),
                "ga_trip_count": ga_result.get("trip_count", len(trips)),
            },
        )
        summary["success"] = True
        summary["active_node_ids"] = [n.id for n in active_nodes if n.id != 0]
        return summary

    # --------------------------------------------------
    # 传统路线：固定顺序遍历所有节点，多趟 (使用 GA 同样的容量规则拆分)
    # --------------------------------------------------
    def solve_traditional(self):
        nodes_by_name = {n.name: n for n in self.node_service.get_nodes()}

        ordered_names = [n for n in TRADITIONAL_ORDER if n in nodes_by_name]
        if not ordered_names:
            return {"success": False, "message": "No nodes for traditional route"}

        active_nodes_view = [self.node_service.get_node_by_id(0)] + [
            nodes_by_name[name] for name in ordered_names
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

        # 用 Truck 贪心拆分固定顺序
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
