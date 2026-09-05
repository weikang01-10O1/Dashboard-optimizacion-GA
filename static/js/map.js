// ===========================
// 建立地图（以 BIOFARM 为中心）
// ===========================
var map = L.map("map").setView([38.831072, -6.782800], 9);

// 保存当前路线层
let routeLayers = [];

// Marker registry (id -> Leaflet marker)
let markersById = {};

// OpenStreetMap 图层
L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        attribution: "&copy; OpenStreetMap contributors"
    }
).addTo(map);

// ===========================
// 自定义 depot (BIOFARM) 图标
// 橙色星形徽章，明显区别于普通节点
// ===========================
const depotIcon = L.divIcon({
    className: "depot-marker-wrap",
    html: '<div class="depot-marker" title="Depot (BIOFARM)"><span class="depot-star">★</span></div>',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
});

// ===========================
// 步骤编号 divIcon
// ===========================
function makeStepIcon(num) {
    return L.divIcon({
        className: "step-badge-wrap",
        html: '<div class="step-badge">' + num + "</div>",
        iconSize: [26, 26],
        iconAnchor: [13, 13],
    });
}

// ===========================
// 显示所有节点 (注册到 markersById)
// ===========================
function popupHtml(node) {
    const isDepot = node.id === 0;
    return (
        "<b>" + node.name + (isDepot ? " (Depot)" : "") + "</b><br>" +
        "Node ID: " + node.id + "<br>" +
        "Fill: " + node.fill + "%<br>" +
        "Weight: " + (node.weight || 0) + " kg"
    );
}

nodes.forEach(node => {
    let marker;
    if (node.id === 0) {
        marker = L.marker([node.lat, node.lon], { icon: depotIcon, zIndexOffset: 500 })
            .addTo(map);
    } else {
        marker = L.marker([node.lat, node.lon]).addTo(map);
    }
    marker.bindPopup(popupHtml(node));
    markersById[node.id] = marker;
});

// 每次 optimize 后用新 fill 刷新 marker popup
function refreshMarkerPopups(updatedNodes) {
    if (!updatedNodes) return;
    updatedNodes.forEach(node => {
        const m = markersById[node.id];
        if (m) {
            m.setPopupContent(popupHtml(node));
        }
    });
}

// ===========================
// 清除旧路线
// ===========================
function clearRoute() {
    routeLayers.forEach(layer => map.removeLayer(layer));
    routeLayers = [];
}

// ===========================
// 在两个坐标的中点放一个步骤编号 (偏移一点避免与节点 marker 重叠)
// ===========================
function addStepNumber(num, lat, lon) {
    const icon = makeStepIcon(num);
    const stepMarker = L.marker([lat, lon], {
        icon: icon,
        interactive: false,
        keyboard: false,
        zIndexOffset: 1000,
    }).addTo(map);
    routeLayers.push(stepMarker);
}

// ===========================
// 绘制优化路线（含虚线回程 + 步骤编号）
// route: 来自 /api/optimize 的 optimized 字段
// ===========================
function drawRoute(routeData) {
    clearRoute();

    if (!routeData || !routeData.segments || routeData.segments.length === 0) {
        return;
    }

    const allPoints = [];
    let stepCounter = 0;

    routeData.segments.forEach(seg => {
        const fromPoint = [seg.from.lat, seg.from.lon];
        const toPoint = [seg.to.lat, seg.to.lon];
        allPoints.push(fromPoint, toPoint);

        // 优化路线主体用实线 (蓝色)，回程用虚线 (红色)
        const line = L.polyline([fromPoint, toPoint], {
            color: seg.is_return ? "#D32F2F" : "#1565C0",
            weight: 4,
            opacity: 0.9,
            dashArray: seg.is_return ? "8,8" : null,
        }).addTo(map);

        // 加 tooltip 提示
        line.bindTooltip(
            (seg.is_return ? "Return to depot" : "Trip " + (seg.trip_index + 1)) +
            "<br>" + seg.from.id + " → " + seg.to.id,
            { sticky: true }
        );

        routeLayers.push(line);

        // 在每个非仓库终点的段中点放一个步骤编号徽章
        if (seg.to.id !== 0) {
            stepCounter++;
            const midLat = (seg.from.lat + seg.to.lat) / 2;
            const midLon = (seg.from.lon + seg.to.lon) / 2;
            addStepNumber(stepCounter, midLat, midLon);
        }
    });

    // 自动缩放到整条路线
    if (allPoints.length > 0) {
        const bounds = L.latLngBounds(allPoints);
        map.fitBounds(bounds, { padding: [40, 40] });
    }
}
