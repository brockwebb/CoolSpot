import shapefile  # pyshp
from pipeline.acquire.boundaries import shapefile_to_features


def make_fixture_shp(tmp_path):
    w = shapefile.Writer(str(tmp_path / "fix"), shapeType=shapefile.POLYGON)
    w.field("GEOID", "C", size=11)
    w.poly([[(-77.0123456, 38.9012345), (-77.01, 38.91), (-77.00, 38.90), (-77.0123456, 38.9012345)]])
    w.record("11001000100")
    w.close()
    return tmp_path / "fix.shp"


def test_shapefile_to_features_rounds_coords(tmp_path):
    feats = shapefile_to_features(make_fixture_shp(tmp_path), precision=5)
    assert len(feats) == 1
    f = feats[0]
    assert f["properties"]["GEOID"] == "11001000100"
    ring = f["geometry"]["coordinates"][0]
    assert ring[0] == [-77.01235, 38.90123]  # rounded to 5 decimals


def test_shapefile_to_features_multipolygon_rounding(tmp_path):
    """MultiPolygon geometry with disjoint rings applies rounding at all nesting levels."""
    w = shapefile.Writer(str(tmp_path / "multi"), shapeType=shapefile.POLYGON)
    w.field("GEOID", "C", size=11)
    # Two disjoint rings: first around DC, second around Baltimore (bounding boxes don't overlap)
    ring1 = [(-77.0123456, 38.9012345), (-77.01, 38.91), (-77.00, 38.90), (-77.0123456, 38.9012345)]
    ring2 = [(-76.6234567, 39.2987654), (-76.62, 39.31), (-76.61, 39.30), (-76.6234567, 39.2987654)]
    w.poly([ring1, ring2])
    w.record("11001000200")
    w.close()

    feats = shapefile_to_features(tmp_path / "multi.shp", precision=5)
    assert len(feats) == 1
    f = feats[0]
    assert f["properties"]["GEOID"] == "11001000200"
    geom = f["geometry"]
    # Pyshp emits disjoint rings as MultiPolygon
    assert geom["type"] == "MultiPolygon"
    # Each polygon in the multipolygon should have rounded coordinates at all nesting levels
    coords = geom["coordinates"]
    assert len(coords) == 2  # Two polygons
    # First polygon's first ring's first coordinate
    assert coords[0][0][0] == [-77.01235, 38.90123]
    # Second polygon's first ring's first coordinate
    assert coords[1][0][0] == [-76.62346, 39.29877]


def make_fixture_shp_named(tmp_path):
    w = shapefile.Writer(str(tmp_path / "fixn"), shapeType=shapefile.POLYGON)
    w.field("GEOID", "C", size=11)
    w.field("NAMELSAD", "C", size=40)
    w.field("NAMELSADCO", "C", size=40)
    w.field("STUSPS", "C", size=2)
    w.poly([[(-77.01, 38.90), (-77.01, 38.91), (-77.00, 38.90), (-77.01, 38.90)]])
    w.record("24013505101", "Census Tract 5051.01", "Carroll County", "MD")
    w.close()
    return tmp_path / "fixn.shp"


def test_shapefile_to_features_keeps_identity_fields(tmp_path):
    feats = shapefile_to_features(make_fixture_shp_named(tmp_path), precision=5)
    p = feats[0]["properties"]
    assert p["tract_name"] == "Census Tract 5051.01"
    assert p["county"] == "Carroll County"
    assert p["state_abbr"] == "MD"


def test_shapefile_missing_identity_fields_still_works(tmp_path):
    # the original minimal fixture (GEOID only) must not crash — fields become None
    feats = shapefile_to_features(make_fixture_shp(tmp_path), precision=5)
    p = feats[0]["properties"]
    assert p["GEOID"] == "11001000100"
    assert p["tract_name"] is None and p["county"] is None and p["state_abbr"] is None
