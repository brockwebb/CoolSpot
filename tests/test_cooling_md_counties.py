# tests/test_cooling_md_counties.py
"""Baltimore County is intentionally absent from CASES: its cooling-locations
page (tests/fixtures/md_baltimore_county.html) lists only category links
(library system, senior centers) and phone numbers to "check locations" —
no scrapeable per-center addresses. Per the task-10 drop rule, its parser was
deleted rather than faking records. See .superpowers/sdd/task-10-report.md."""
from pathlib import Path

import pytest
from pipeline.acquire.cooling.md_counties import COUNTY_PARSERS, parse_county
from pipeline.schema import partition_records

FIXTURES = Path(__file__).parent / "fixtures"
CASES = ["anne_arundel", "howard"]


@pytest.mark.parametrize("county", CASES)
def test_county_parser_yields_valid_records(county):
    html = (FIXTURES / f"md_{county}.html").read_text()
    recs = parse_county(county, html, "2026-07-05", f"https://example.gov/{county}")
    assert len(recs) >= 1, f"{county}: parser found no cooling centers in real fixture"
    valid, invalid = partition_records(recs)
    assert invalid == [], f"{county}: schema violations: {[r['_errors'] for r in invalid]}"
    for r in valid:
        assert r["jurisdiction"] == "md"
        assert r["source_url"] == f"https://example.gov/{county}"
        assert any(ch.isdigit() for ch in r["address"]), f"address looks wrong: {r['address']}"


def test_unknown_county_raises():
    with pytest.raises(KeyError):
        parse_county("narnia", "<html></html>", "2026-07-05", "https://example.gov/x")


def test_all_configured_counties_have_parsers():
    assert set(COUNTY_PARSERS) >= set(CASES)


def test_anne_arundel_parser_warns_on_unparseable_name_addr(capsys):
    """Test that Anne Arundel parser prints warning for malformed location lines."""
    # Minimal synthetic HTML: one well-formed facility with valid location link,
    # one with a malformed location link missing the expected "name: address" format.
    html = """
    <div class="paragraph paragraph--type--heading">Heading</div>
    <div class="paragraph paragraph--type--text-editor">Operating Days & Hours: M-F 9-5</div>
    <div class="paragraph paragraph--type--text-editor">
      <a class="icon-link-location">Valid Center: 100 Main St, Annapolis</a>
      <a class="icon-link-location">Malformed Line With No Colon</a>
    </div>
    """
    recs = parse_county("anne_arundel", html, "2026-07-05", "https://example.gov/aa")
    # Well-formed record should parse.
    assert len(recs) >= 1
    # Warning should appear in output.
    captured = capsys.readouterr()
    assert "skipped unparseable" in captured.out
    assert "md_counties[anne_arundel]" in captured.out


def test_anne_arundel_parser_warns_on_unparseable_address(capsys):
    """Test that Anne Arundel parser warns when address regex fails."""
    html = """
    <div class="paragraph paragraph--type--heading">Heading</div>
    <div class="paragraph paragraph--type--text-editor">Operating Days & Hours: M-F 9-5</div>
    <div class="paragraph paragraph--type--text-editor">
      <a class="icon-link-location">Valid Center: 100 Main St, Annapolis</a>
      <a class="icon-link-location">Bad Address: XYZ</a>
    </div>
    """
    recs = parse_county("anne_arundel", html, "2026-07-05", "https://example.gov/aa")
    # Well-formed record should parse.
    assert len(recs) >= 1
    # Warning should appear in output.
    captured = capsys.readouterr()
    assert "skipped unparseable" in captured.out
    assert "md_counties[anne_arundel]" in captured.out


def test_howard_parser_warns_on_unparseable_address(capsys):
    """Test that Howard parser warns when address regex fails."""
    html = """
    <ul type="disc">
      <li>
        <strong>Valid Center</strong>
        <ul>
          <li>Address: 100 Main St, Ellicott City, MD 21043</li>
          <li>Phone Numbers: 410-123-4567</li>
          <li>Hours of Operation: M-F 9-5</li>
        </ul>
      </li>
      <li>
        <strong>Unparseable Center</strong>
        <ul>
          <li>Address: XYZ</li>
          <li>Phone Numbers: 410-987-6543</li>
          <li>Hours of Operation: M-F 9-5</li>
        </ul>
      </li>
    </ul>
    """
    recs = parse_county("howard", html, "2026-07-05", "https://example.gov/howard")
    # Well-formed record should parse.
    assert len(recs) >= 1
    # Warning should appear in output.
    captured = capsys.readouterr()
    assert "skipped unparseable" in captured.out
    assert "md_counties[howard]" in captured.out


def test_howard_parser_warns_on_missing_address(capsys):
    """Test that Howard parser warns when address field is absent."""
    html = """
    <ul type="disc">
      <li>
        <strong>Valid Center</strong>
        <ul>
          <li>Address: 100 Main St, Ellicott City, MD 21043</li>
          <li>Phone Numbers: 410-123-4567</li>
          <li>Hours of Operation: M-F 9-5</li>
        </ul>
      </li>
      <li>
        <strong>No Address Center</strong>
        <ul>
          <li>Phone Numbers: 410-987-6543</li>
          <li>Hours of Operation: M-F 9-5</li>
        </ul>
      </li>
    </ul>
    """
    recs = parse_county("howard", html, "2026-07-05", "https://example.gov/howard")
    # Well-formed record should parse.
    assert len(recs) >= 1
    # Warning should appear in output.
    captured = capsys.readouterr()
    assert "skipped unparseable" in captured.out
    assert "md_counties[howard]" in captured.out


def test_anne_arundel_parser_warns_on_missing_location_div(capsys):
    """Test that Anne Arundel parser warns when location div is missing after hours div."""
    html = """
    <div class="paragraph paragraph--type--heading">Valid Section</div>
    <div class="paragraph paragraph--type--text-editor">Operating Days & Hours: M-F 9-5</div>
    <div class="paragraph paragraph--type--text-editor">
      <a class="icon-link-location">Valid Center: 100 Main St, Annapolis</a>
    </div>
    <div class="paragraph paragraph--type--heading">Police Station Lobbies</div>
    <div class="paragraph paragraph--type--text-editor">Operating Days & Hours: M-F 9-5</div>
    """
    recs = parse_county("anne_arundel", html, "2026-07-05", "https://example.gov/aa")
    # Well-formed record from first section should parse.
    assert len(recs) >= 1
    # Warning should appear in output for missing location div in second section.
    captured = capsys.readouterr()
    assert "skipped section with no location div" in captured.out
    assert "md_counties[anne_arundel]" in captured.out
    assert "Police Station Lobbies" in captured.out


def test_howard_parser_warns_on_missing_nested_ul(capsys):
    """Test that Howard parser warns when nested ul (sub-fields) is missing."""
    html = """
    <ul type="disc">
      <li>
        <strong>Valid Center</strong>
        <ul>
          <li>Address: 100 Main St, Ellicott City, MD 21043</li>
          <li>Phone Numbers: 410-123-4567</li>
          <li>Hours of Operation: M-F 9-5</li>
        </ul>
      </li>
      <li>
        <strong>No Subfields Center</strong>
        <p>Some text but no nested ul</p>
      </li>
    </ul>
    """
    recs = parse_county("howard", html, "2026-07-05", "https://example.gov/howard")
    # Well-formed record should parse.
    assert len(recs) >= 1
    # Warning should appear in output for missing nested ul.
    captured = capsys.readouterr()
    assert "skipped facility with no nested ul" in captured.out
    assert "md_counties[howard]" in captured.out
    assert "No Subfields Center" in captured.out
