// Expuesto para usar en la ventana emergente fitness_curve.html
window.gaHistory = null;
window.gaMeta = {};
window.lastTraditional = null;

// Utilidad: formatear la diferencia numérica con signo
function fmtDelta(a, b, digits) {
    if (typeof a !== "number" || typeof b !== "number") return "—";
    const d = a - b;
    const sign = d > 0 ? "+" : "";
    return sign + d.toFixed(digits);
}

async function loadDashboard() {
    let response = await fetch("/api/dashboard");
    let data = await response.json();

    document.getElementById("nodeCount").innerHTML = data.total;
    document.getElementById("avgFill").innerHTML = data.average.toFixed(1) + "%";
    document.getElementById("critical").innerHTML = data.critical;
}

async function simulate() {
    await fetch("/api/simulate", { method: "POST" });
    loadDashboard();
}

function setText(id, val) {
    document.getElementById(id).innerHTML = val;
}

function numOrDash(v, digits = 2) {
    const n = Number(v);
    if (Number.isNaN(n)) return "—";
    return n.toFixed(digits);
}

async function loadOptimizationHistory() {
    try {
        const response = await fetch("/api/optimization-history");
        const data = await response.json();
        const rows = data.rows || [];

        setText("historyCount", rows.length + " registros");

        const tbody = document.querySelector("#historyTable tbody");
        tbody.innerHTML = "";

        rows.slice().reverse().forEach(r => {
            const tr = document.createElement("tr");
            tr.innerHTML = ""
                + "<td>" + (r.timestamp || "—") + "</td>"
                + "<td>" + numOrDash(r.opt_distance, 2) + "</td>"
                + "<td>" + numOrDash(r.trad_distance, 2) + "</td>"
                + "<td>" + numOrDash(r.delta_distance, 2) + "</td>";
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("No se pudo cargar el historial de optimización", e);
    }
}

function exportOptimizationHistory() {
    window.open("/api/optimization-history/export", "_blank");
}

function fillRouteCard(prefix, data) {
    setText(prefix + "_path", data.path || "—");
    setText(prefix + "_distance", data.total_distance);
    setText(prefix + "_time", data.total_time);
    setText(prefix + "_load", data.total_load);
    setText(prefix + "_returns", data.return_count);
    setText(prefix + "_visited", (data.visited_ids || []).length);
}

function fillComparison(opt, trad) {
    setText("cmp_dist_g", opt.total_distance);
    setText("cmp_dist_t", trad.total_distance);
    setText("cmp_dist_d", fmtDelta(trad.total_distance, opt.total_distance, 2));

    setText("cmp_time_g", opt.total_time);
    setText("cmp_time_t", trad.total_time);
    setText("cmp_time_d", fmtDelta(trad.total_time, opt.total_time, 2));

    setText("cmp_load_g", opt.total_load);
    setText("cmp_load_t", trad.total_load);
    setText("cmp_load_d", fmtDelta(trad.total_load, opt.total_load, 2));

    setText("cmp_ret_g", opt.return_count);
    setText("cmp_ret_t", trad.return_count);
    setText("cmp_ret_d", fmtDelta(trad.return_count, opt.return_count, 0));

    setText("cmp_vis_g", (opt.visited_ids || []).length);
    setText("cmp_vis_t", (trad.visited_ids || []).length);
}

async function optimizeRoute() {
    let response = await fetch("/api/optimize");
    let result = await response.json();

    if (result.error) {
        console.error(result.error);
        return;
    }

    const opt = result.optimized || {};
    const trad = result.traditional || {};
    window.lastTraditional = trad;

    // 1) Dibujar la ruta optimizada (incluye retorno punteado)
    drawRoute(opt, "optimized");

    // 2) Rellenar las dos tarjetas de ruta + tarjeta comparativa
    fillRouteCard("opt", opt);
    fillRouteCard("trad", trad);
    fillComparison(opt, trad);

    // 3) Actualizar popup de fill en marcadores (los visitados ya fueron reiniciados en backend)
    if (result.nodes) {
        refreshMarkerPopups(result.nodes);
    }

    // 4) Exponer datos de fitness a la ventana emergente
    window.gaHistory = opt.history || [];
    window.gaMeta = {
        total_distance: opt.total_distance,
        path: opt.path,
        return_count: opt.return_count,
    };
    try {
        sessionStorage.setItem("ga_history", JSON.stringify(window.gaHistory));
        sessionStorage.setItem("ga_meta", JSON.stringify(window.gaMeta));
    } catch (e) {
        // sessionStorage puede estar deshabilitado; el acceso vía opener sigue funcionando
    }

    // 5) Números de resumen del panel
    setText("total_distance", opt.total_distance + " km");
    setText("total_time", opt.total_time + " min");
    setText("nodes_visited", (opt.visited_ids || []).length);

    // 6) Actualizar historial de optimización
    loadOptimizationHistory();
}

function showTraditionalRoute() {
    if (!window.lastTraditional || !window.lastTraditional.segments || window.lastTraditional.segments.length === 0) {
        alert("Primero haz clic en \"Optimizar Ruta\" para obtener la ruta tradicional y luego visualizarla en el mapa.");
        return;
    }
    drawRoute(window.lastTraditional, "traditional");
}

function openFitnessWindow() {
    if (!window.gaHistory || window.gaHistory.length === 0) {
        alert("Primero haz clic en \"Optimizar Ruta\" y luego abre la curva de fitness.");
        return;
    }
    const w = 960;
    const h = 640;
    const left = (screen.width - w) / 2;
    const top = (screen.height - h) / 2;
    window.open(
        "/fitness",
        "ga_fitness",
        "width=" + w + ",height=" + h + ",left=" + left + ",top=" + top + ",resizable=yes,scrollbars=no"
    );
}

loadDashboard();
loadOptimizationHistory();
setInterval(loadDashboard, 10000);
