from __future__ import annotations

import math
import random


def jittered_coords(lat: float, lon: float, max_meters: float) -> tuple[float, float]:
    """Return (lat, lon) offset by a uniform-random vector of length ≤ max_meters."""
    if max_meters <= 0:
        return lat, lon
    theta = random.uniform(0, 2 * math.pi)
    r = max_meters * math.sqrt(random.random())
    d_lat = (r * math.cos(theta)) / 111_000
    d_lon = (r * math.sin(theta)) / (111_000 * math.cos(math.radians(lat)))
    return lat + d_lat, lon + d_lon
