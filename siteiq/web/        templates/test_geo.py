import math

from siteiq.core.geo import bearing, dominant_axis, haversine_mi, walk_minutes


def test_haversine_known_distance():
    # Times Square to the Empire State Building is roughly 0.8 miles.
    d = haversine_mi(40.7580, -73.9855, 40.7484, -73.9857)
    assert 0.6 < d < 1.0


def test_haversine_same_point_is_zero():
    assert haversine_mi(40.75, -73.99, 40.75, -73.99) == 0


def test_walk_minutes_scales_with_distance():
    assert walk_minutes(0.5) > walk_minutes(0.1)
    assert walk_minutes(0.1) >= 1


def test_bearing_north_is_zero():
    b = bearing(40.75, -73.99, 40.76, -73.99)
    assert b < 5 or b > 355


def test_dominant_axis_needs_minimum_points():
    # Fewer than 4 nearby points is not enough evidence to infer a street axis.
    few_points = [{"lat": 40.7505, "lon": -73.9970}, {"lat": 40.7506, "lon": -73.9969}]
    assert dominant_axis(few_points, 40.7505, -73.9971) is None


def test_dominant_axis_finds_a_line():
    lat, lon = 40.7505, -73.9971
    # Points strung out along a north-south line, spaced to fall inside the
    # function's real capture window (roughly 26 to 317 feet from the site).
    points = [{"lat": lat + 0.00006 * i, "lon": lon} for i in range(2, 9)]
    axis = dominant_axis(points, lat, lon)
    assert axis is not None
    # North-south axis should land near 0/180 degrees, not east-west (90).
    assert axis < 25 or axis > 155
