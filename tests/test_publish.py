from pipeline.publish import add_gap_distances, centroid, haversine_km, jurisdiction_summary, to_feature

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


def test_jurisdiction_summary_aggregates_all_source_urls():
    """Test that jurisdiction_summary collects all unique source URLs."""
    records = [
        {"jurisdiction": "md", "source_url": "https://pgarcgis.example.com", "retrieved_date": "2026-07-05"},
        {"jurisdiction": "md", "source_url": "https://pgarcgis.example.com", "retrieved_date": "2026-07-05"},
        {"jurisdiction": "md", "source_url": "https://county1.example.com", "retrieved_date": "2026-07-05"},
        {"jurisdiction": "dc", "source_url": "https://dc.gov", "retrieved_date": "2026-07-05"},
    ]
    result = jurisdiction_summary(records)

    # MD should have count 3 with both source URLs preserved in order
    assert result["md"]["count"] == 3
    assert result["md"]["source_urls"] == [
        "https://pgarcgis.example.com",
        "https://county1.example.com"
    ]
    assert result["md"]["retrieved_date"] == "2026-07-05"

    # DC should have count 1
    assert result["dc"]["count"] == 1
    assert result["dc"]["source_urls"] == ["https://dc.gov"]
    assert result["dc"]["retrieved_date"] == "2026-07-05"
