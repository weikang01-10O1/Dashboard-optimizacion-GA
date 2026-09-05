from dataclasses import dataclass


@dataclass
class Node:

    id: int

    name: str

    lat: float

    lon: float

    # 当前填充率 (%)
    fill: int = 0

    # 垃圾桶总容量 (m³)
    capacity: float = 1.0

    battery: float = 4.2

    rssi: int = -90

    snr: float = 8.0

    visited: bool = False

    status: str = "green"

    @property
    def current_volume(self):
        """
        当前垃圾体积 (m³)
        """
        return round(self.capacity * self.fill / 100, 2)