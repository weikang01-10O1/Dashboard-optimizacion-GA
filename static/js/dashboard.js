// 暴露给 fitness_curve.html 弹窗使用
window.gaHistory = null;
window.gaMeta = {};

// 通用：把数字格式化为带符号的差值字符串
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

    // 1) 画优化路线（含虚线回程）
    drawRoute(opt);

    // 2) 填充两个路线卡 + 对比卡
    fillRouteCard("opt", opt);
    fillRouteCard("trad", trad);
    fillComparison(opt, trad);

    // 3) 刷新 marker 的 fill popup (已访问的 fill 已被后端清零)
    if (result.nodes) {
        refreshMarkerPopups(result.nodes);
    }

    // 4) 暴露 fitness 数据给弹窗
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
        // sessionStorage may be disabled; opener-based access still works
    }

    // 5) dashboard 总览数字
    setText("total_distance", opt.total_distance + " km");
    setText("total_time", opt.total_time + " min");
    setText("nodes_visited", (opt.visited_ids || []).length);
}

function openFitnessWindow() {
    if (!window.gaHistory || window.gaHistory.length === 0) {
        alert("请先点击 \"Optimize Route\"，再打开适应度曲线。");
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
setInterval(loadDashboard, 10000);
