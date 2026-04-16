import math

from talenta_bot.session import jittered_coords


def test_jittered_coords_within_radius():
    base_lat, base_long = -6.2, 106.8
    max_m = 5.0
    for _ in range(500):
        lat, lon = jittered_coords(base_lat, base_long, max_m)
        d_lat = (lat - base_lat) * 111_000
        d_lon = (lon - base_long) * 111_000 * math.cos(math.radians(base_lat))
        dist = math.hypot(d_lat, d_lon)
        assert dist <= max_m + 0.01, dist


def test_jittered_coords_zero_is_exact():
    lat, lon = jittered_coords(-6.2, 106.8, 0)
    assert (lat, lon) == (-6.2, 106.8)
