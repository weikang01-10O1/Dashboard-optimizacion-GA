// ===========================
// Crear mapa (centrado en BIOFARM)
// ===========================
var map = L.map("map").setView([38.831072, -6.782800], 9);

// Guardar capas de ruta actuales
let routeLayers = [];

// Marker registry (id -> Leaflet marker)
let markersById = {};

// Capa de OpenStreetMap
L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        attribution: "&copy; OpenStreetMap contributors"
    }
).addTo(map);

// ===========================
// Ícono personalizado del depósito (BIOFARM)
// Insignia naranja con estrella para distinguirlo de nodos normales
// ===========================
const depotIcon = L.divIcon({
    className: "depot-marker-wrap",
    html: '<div class="depot-marker" title="Depot (BIOFARM)"><span class="depot-star">★</span></div>',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
});

// ===========================
// divIcon del número de paso
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
// Mostrar todos los nodos (registrados en markersById)
// ===========================
function popupHtml(node) {
    const isDepot = node.id === 0;
    return (
        "<b>" + node.name + (isDepot ? " (Depot)" : "") + "</b><br>" +
        "Node ID: " + node.id + "<br>" +
        "Llenado: " + Number(node.fill).toFixed(1) + "%<br>" +
        "Capacidad: " + Number(node.capacity || 0).toFixed(1) + " m&sup3;"
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

// Después de cada optimización, actualizar los popups de marcadores con el nuevo fill
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
// Limpiar ruta anterior
// ===========================
function clearRoute() {
    routeLayers.forEach(layer => map.removeLayer(layer));
    routeLayers = [];
}

// ===========================
// Colocar número de paso en el punto medio de dos coordenadas (con pequeño desplazamiento para evitar solapamiento)
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
// Dibujar ruta optimizada (incluye retorno punteado + numeración de pasos)
// route: campo optimized proveniente de /api/optimize
// ===========================
function drawRoute(routeData, mode = "optimized") {
    clearRoute();

    if (!routeData || !routeData.segments || routeData.segments.length === 0) {
        return;
    }

    const allPoints = [];
    let stepCounter = 0;
    const isTraditional = mode === "traditional";

    routeData.segments.forEach(seg => {
        const fromPoint = [seg.from.lat, seg.from.lon];
        const toPoint = [seg.to.lat, seg.to.lon];
        allPoints.push(fromPoint, toPoint);

        const line = L.polyline([fromPoint, toPoint], {
            color: seg.is_return
                ? (isTraditional ? "#2E7D32" : "#D32F2F")
                : (isTraditional ? "#F57C00" : "#1565C0"),
            weight: 4,
            opacity: 0.9,
            dashArray: seg.is_return ? "8,8" : null,
        }).addTo(map);

        line.bindTooltip(
            (seg.is_return
                ? (isTraditional ? "Traditional return" : "Return to depot")
                : (isTraditional ? "Traditional trip " : "Trip ") + (seg.trip_index + 1)) +
            "<br>" + seg.from.id + " → " + seg.to.id,
            { sticky: true }
        );

        routeLayers.push(line);

        if (seg.to.id !== 0) {
            stepCounter++;
            const midLat = (seg.from.lat + seg.to.lat) / 2;
            const midLon = (seg.from.lon + seg.to.lon) / 2;
            addStepNumber(stepCounter, midLat, midLon);
        }
    });

    if (allPoints.length > 0) {
        const bounds = L.latLngBounds(allPoints);
        map.fitBounds(bounds, { padding: [40, 40] });
    }
}
