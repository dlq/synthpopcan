import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/build_zenodo_depositions.py"
SPEC = importlib.util.spec_from_file_location("build_zenodo_depositions", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_deposition = MODULE.build_deposition


def test_deposition_carries_the_statcan_attribution_notice() -> None:
    deposition = build_deposition(
        "ontario-2021-all-fields", concept_doi="10.5281/zenodo.1234567"
    )
    description = deposition["metadata"]["description"]

    assert "Adapted from Statistics Canada," in description
    assert "does not constitute an endorsement by Statistics Canada" in description
    assert "statcan.gc.ca/en/reference/licence" in description
    assert "not legal anonymization" in description


def test_deposition_links_upward_to_software_and_back_to_source() -> None:
    deposition = build_deposition(
        "montreal-cma-2016-all-fields", concept_doi="10.5281/zenodo.1234567"
    )
    relations = {
        item["relation"]: item["identifier"]
        for item in deposition["metadata"]["related_identifiers"]
    }

    assert relations["isPartOf"] == "10.5281/zenodo.1234567"
    assert relations["isDerivedFrom"].endswith("98M0002X2016001")
    assert "synthpopcan" in relations["isCompiledBy"]


def test_deposition_omits_software_link_when_concept_doi_is_unknown() -> None:
    deposition = build_deposition("ontario-2021-all-fields", concept_doi=None)
    relations = {
        item["relation"] for item in deposition["metadata"]["related_identifiers"]
    }

    assert "isPartOf" not in relations
    assert {"isDerivedFrom", "isCompiledBy"} <= relations


def test_deposition_records_both_checksums_for_integrity() -> None:
    deposition = build_deposition("ontario-2021-all-fields", concept_doi=None)
    payload = deposition["synthpopcan"]

    assert len(payload["sha256"]) == 64
    assert len(payload["uncompressed_sha256"]) == 64
    assert payload["uncompressed_size_bytes"] > payload["size_bytes"]
    assert payload["asset_url"].endswith(".json.gz")


def test_deposition_uses_an_attribution_preserving_licence() -> None:
    deposition = build_deposition("quebec-2016-all-fields", concept_doi=None)

    assert deposition["metadata"]["license"] == "cc-by-4.0"
    assert deposition["metadata"]["access_right"] == "open"
    description = deposition["metadata"]["description"]
    assert "SynthPopCan-authored model material" in description
    assert "does not replace conditions" in description
    assert "Statistics Canada Open Licence" in description


def test_deposition_credits_the_same_authors_as_citation_metadata() -> None:
    """Archived model records must credit the same authors as CITATION.cff."""
    import re
    from pathlib import Path

    deposition = build_deposition("ontario-2021-all-fields", concept_doi=None)
    creators = deposition["metadata"]["creators"]

    assert creators, "model records must name their creators"
    for creator in creators:
        # Never infer an ORCID; only record one supplied by its owner.
        assert set(creator) <= {"name", "affiliation", "orcid"}

    citation = Path("CITATION.cff").read_text()
    families = set(re.findall(r"family-names:\s*(\S+)", citation))
    assert {name["name"].split(",")[0] for name in creators} <= families


def test_deposition_description_does_not_repeat_the_source_title() -> None:
    """The licence paragraph should not restate what attribution already said."""
    deposition = build_deposition("montreal-cma-2016-all-fields", concept_doi=None)
    description = deposition["metadata"]["description"]

    # The product title belongs in the attribution notice only; the licence
    # paragraph links to the source rather than restating it. The catalogue
    # number legitimately recurs inside the link href.
    assert description.count("2016 Census Hierarchical Public Use Microdata File") == 1
    assert "local 2016" not in description
