from dataclasses import dataclass


@dataclass
class Node:

    id: int

    name: str

    lat: float

    lon: float

    # Nivel de llenado actual (%)
    fill: int = 0

    # Capacidad total del contenedor (m³)
    capacity: float = 1.0

    battery: float = 4.2

    rssi: int = -90

    snr: float = 8.0

    visited: bool = False

    status: str = "green"

    @property
    def current_volume(self):
        """
        Volumen actual de residuos (m³)
        """
        return round(self.capacity * self.fill / 100, 2)