from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services.node_service import NodeService
from services.simulator_service import SimulatorService

from services.matrix_service import MatrixService
from services.route_service import RouteService
# --------------------------------------------------
# 建立 FastAPI
# --------------------------------------------------

app = FastAPI(title="Smart Waste Collection System")


# --------------------------------------------------
# 掛載 static
# --------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")


# --------------------------------------------------
# HTML Template
# --------------------------------------------------

templates = Jinja2Templates(directory="templates")


# --------------------------------------------------
# 建立 Service
# --------------------------------------------------

node_service = NodeService()

simulator = SimulatorService(node_service)

matrix_service = MatrixService()

matrix_service.load()

route_service = RouteService(matrix_service, node_service)
# --------------------------------------------------
# Homepage
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "nodes": [
                node.__dict__
                for node in node_service.get_nodes()
            ]
        }
    )


# --------------------------------------------------
# 遗传算法适应度曲线 (弹窗页面)
# --------------------------------------------------
@app.get("/fitness", response_class=HTMLResponse)
async def fitness(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="fitness_curve.html"
    )


# --------------------------------------------------
# 取得所有 Node
# --------------------------------------------------

@app.get("/api/nodes")
async def get_nodes():

    return [

        node.__dict__

        for node in node_service.get_nodes()

    ]


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.get("/api/dashboard")
async def dashboard():

    return node_service.get_statistics()


# --------------------------------------------------
# 模擬垃圾增加
# --------------------------------------------------

@app.post("/api/simulate")
async def simulate():

    simulator.update()

    return {

        "message": "Simulation Updated"

    }

@app.get("/api/distance")
async def distance():

    matrix = matrix_service.get_distance_matrix()

    return matrix.values.tolist()

@app.get("/api/time")
async def time():

    matrix = matrix_service.get_time_matrix()

    return matrix.values.tolist()

#test.model API
@app.get("/api/model")
async def model():

    return route_service.create_data_model()

#检查API

@app.get("/api/test")
async def test():

    return {
        "nodes": len(node_service.get_nodes()),
        "distance_size": matrix_service.get_distance_matrix().shape,
        "time_size": matrix_service.get_time_matrix().shape
    }


@app.get("/api/optimize")
async def optimize():

    # 1) 计算传统路线 (基于当前 fill, 尚未重置)
    traditional = route_service.solve_traditional()

    # 2) 跑 GA 优化
    optimized = route_service.solve(80)

    # 3) 把已访问的 active node 的 fill 清零 (用于前端展示和下次 simulate)
    if optimized.get("success") and not optimized.get("empty"):

        node_service.reset_fills(optimized.get("visited_ids", []))

    return {
        "optimized": optimized,
        "traditional": traditional,
        "nodes": [node.__dict__ for node in node_service.get_nodes()],
    }