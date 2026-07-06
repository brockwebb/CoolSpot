from pipeline.publish import add_gap_distances, centroid, haversine_km, to_feature

REC = {"id": "dc-1", "name": "X", "address": "1 Main St", "city": "Washington", "state": "DC",
       "jurisdiction": "dc", "source_url": "https://e.gov", "retrieved_date": "2026-07-05",
       "lat": 38.9, "lon": -77.0, "hours": "9-5"}


def test_to_feature_moves_coords_to_geometry():
    f = to_feature(REC)
    assert f["geometry"] == {"type": "Point", "coordinates": [-77.0, 38.9]}
    assert "lat" not in f["properties"] and f["properties"]["hours"] == "9-5"


def test_haversine_known_distance():
    # DC to Baltimore ~ 56 km
    assert 50 < haversine_km(38.9047, -77.0164, 39.2904, -76.6122) < 62


def test_centroid_of_square():
    feat = {"geometry": {"type": "Polygon",
            "coordinates": [[[-77.0, 38.0], [-77.0, 38.2], [-76.8, 38.2], [-76.8, 38.0], [-77.0, 38.0]]]}}
    lat, lon = centroid(feat)
    assert abs(lat - 38.08) < 0.1 and abs(lon + 76.92) < 0.1


def test_add_gap_distances():
    tract_fc = {"features": [{"geometry": {"type": "Polygon",
        "coordinates": [[[-77.0, 38.9], [-77.0, 38.91], [-76.99, 38.91], [-76.99, 38.9], [-77.0, 38.9]]]},
        "properties": {"GEOID": "x"}}]}
    add_gap_distances(tract_fc, [(38.905, -76.995)])
    assert tract_fc["features"][0]["properties"]["nearest_cc_km"] < 2.0
