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
