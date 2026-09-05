from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2


class RouteService:
    def __init__(self, matrix_service, node_service):
        self.matrix = matrix_service
        self.node_service = node_service

    def create_data_model(self, threshold=80):
        active_nodes = self.node_service.get_active_nodes(threshold)
        if not active_nodes:
            raise ValueError("No active nodes available.")
        distance_matrix = self.build_distance_matrix(active_nodes)
        time_matrix = self.build_time_matrix(active_nodes)
        return {
            "distance_matrix": distance_matrix,
            "time_matrix": time_matrix,
            "active_nodes": active_nodes,
            "num_vehicles": 1,
            "depot": 0  # 假设 active_nodes[0] 为仓库节点
        }

    def build_distance_matrix(self, active_nodes):
        full_matrix = self.matrix.get_distance_matrix()
        ids = [node.id for node in active_nodes]
        # 若 full_matrix 不是 DataFrame，可改用普通列表访问
        matrix = []
        for i in ids:
            row = []
            for j in ids:
                row.append(full_matrix.iloc[i, j])  # 假设支持 iloc
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

    def solve(self, threshold=80):
        try:
            data = self.create_data_model(threshold)
        except ValueError as e:
            return {"success": False, "message": str(e)}

        manager = pywrapcp.RoutingIndexManager(
            len(data["distance_matrix"]),
            data["num_vehicles"],
            data["depot"]
        )
        routing = pywrapcp.RoutingModel(manager)

        # 定义回调（闭包）
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return data["distance_matrix"][from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )

        solution = routing.SolveWithParameters(search_parameters)

        if solution is None:
            return {"success": False, "message": "No feasible route found."}

        # 提取路径
        index = routing.Start(0)
        route = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route.append(node)
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))

        # 计算总距离
        total_distance = 0
        for i in range(len(route) - 1):
            total_distance += data["distance_matrix"][route[i]][route[i + 1]]

        # 计算总时间
        total_time = 0
        for i in range(len(route) - 1):
            total_time += data["time_matrix"][route[i]][route[i+1]]

        # 转换为实际节点对象
        real_route = [data["active_nodes"][manager.IndexToNode(idx)] for idx in route]

        return {"success": True, 
            "route": [
                {
                    "id": node.id,
                    "name": node.name,
                    "fill": node.fill,
                    "lat": node.lat,
                    "lon": node.lon
                }
                for node in real_route
            ],
            "total_distance": round(total_distance, 2),
            
            "total_time": round(total_time, 2),

            "nodes_visited": len(real_route) - 2
        }