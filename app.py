import csv
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services.node_service import NodeService
from services.simulator_service import SimulatorService

from services.matrix_service import MatrixService
from services.route_service import RouteService
# --------------------------------------------------
# Crear FastAPI
# --------------------------------------------------

app = FastAPI(title="Smart Waste Collection System")


# --------------------------------------------------
# Montar archivos estáticos
# --------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")


# --------------------------------------------------
# HTML Template
# --------------------------------------------------

templates = Jinja2Templates(directory="templates")


# --------------------------------------------------
# Inicializar servicios
# --------------------------------------------------

node_service = NodeService()

simulator = SimulatorService(node_service)

matrix_service = MatrixService()

matrix_service.load()

route_service = RouteService(matrix_service, node_service)


# --------------------------------------------------
# Optimization history persistence
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "optimization_history.csv"
HISTORY_FIELDS = [
    "timestamp",
    "opt_distance",
    "opt_time",
    "opt_load",
    "opt_returns",
    "opt_visited",
    "opt_path",
    "trad_distance",
    "trad_time",
    "trad_load",
    "trad_returns",
    "trad_visited",
    "trad_path",
    "delta_distance",
    "delta_time",
    "delta_load",
    "delta_returns",
]


def append_optimization_record(record):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = HISTORY_FILE.exists()
    with HISTORY_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


def load_optimization_history():
    if not HISTORY_FILE.exists():
        return []
    with HISTORY_FILE.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


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
# Curva de fitness del algoritmo genético (ventana emergente)
# --------------------------------------------------
@app.get("/fitness", response_class=HTMLResponse)
async def fitness(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="fitness_curve.html"
    )


# --------------------------------------------------
# Obtener todos los nodos
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
# Simular aumento de residuos
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

# API de verificación

@app.get("/api/test")
async def test():

    return {
        "nodes": len(node_service.get_nodes()),
        "distance_size": matrix_service.get_distance_matrix().shape,
        "time_size": matrix_service.get_time_matrix().shape
    }


@app.get("/api/optimization-history")
async def optimization_history():
    rows = load_optimization_history()
    return {"count": len(rows), "rows": rows}


@app.get("/api/optimization-history/export")
async def optimization_history_export():
    if not HISTORY_FILE.exists():
        return Response(content="timestamp\n", media_type="text/csv")

    csv_content = HISTORY_FILE.read_text(encoding="utf-8")
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=optimization_history.csv"
        },
    )


@app.get("/api/optimize")
async def optimize():

    # 1) Calcular la ruta tradicional (basada en el fill actual, aún sin reiniciar)
    traditional = route_service.solve_traditional()

    # 2) Ejecutar optimización GA
    optimized = route_service.solve(80)

    # 3) Registrar el resultado de esta optimización
    if optimized.get("success") and traditional.get("success"):
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "opt_distance": optimized.get("total_distance", 0),
            "opt_time": optimized.get("total_time", 0),
            "opt_load": optimized.get("total_load", 0),
            "opt_returns": optimized.get("return_count", 0),
            "opt_visited": len(optimized.get("visited_ids", [])),
            "opt_path": optimized.get("path", ""),
            "trad_distance": traditional.get("total_distance", 0),
            "trad_time": traditional.get("total_time", 0),
            "trad_load": traditional.get("total_load", 0),
            "trad_returns": traditional.get("return_count", 0),
            "trad_visited": len(traditional.get("visited_ids", [])),
            "trad_path": traditional.get("path", ""),
            "delta_distance": round(traditional.get("total_distance", 0) - optimized.get("total_distance", 0), 2),
            "delta_time": round(traditional.get("total_time", 0) - optimized.get("total_time", 0), 2),
            "delta_load": round(traditional.get("total_load", 0) - optimized.get("total_load", 0), 2),
            "delta_returns": traditional.get("return_count", 0) - optimized.get("return_count", 0),
        }
        append_optimization_record(record)

    # 4) Poner en cero el fill de los nodos activos visitados (para visualización y siguiente simulación)
    if optimized.get("success") and not optimized.get("empty"):

        node_service.reset_fills(optimized.get("visited_ids", []))

    return {
        "optimized": optimized,
        "traditional": traditional,
        "nodes": [node.__dict__ for node in node_service.get_nodes()],
    }