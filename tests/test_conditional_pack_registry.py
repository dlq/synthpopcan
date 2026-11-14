"""Conditional registry references and immutable published pack definitions."""

import pytest
from pydantic import ValidationError

from synthpopcan import _marital_status_packs
from synthpopcan._conditional_pack_catalogue import (
    DEFINITION_DIGESTS,
    FAMILY_CONCEPTS,
    PROFILE_FAMILIES,
    describe_conditional_pack,
)
from synthpopcan.control_packs import (
    ControlCompatibilityRegistry,
    load_compatibility_registry,
)


@pytest.mark.parametrize("identifier", sorted(DEFINITION_DIGESTS))
def test_conditional_registry_covers_versioned_pack(identifier):
    definition = describe_conditional_pack(identifier)
    registry = load_compatibility_registry()
    entry = next(
        field
        for field in registry.fields
        if field.concept_identifier == FAMILY_CONCEPTS[definition["family"]]
    )
    assert entry.status == "implemented"
    assert identifier in entry.conditional_pack_identifiers
    assert not entry.control_identifiers
    assert definition["source_field"] in getattr(
        entry, f"fields_{definition['census_vintage']}"
    )


@pytest.mark.parametrize("identifier", sorted(DEFINITION_DIGESTS))
def test_changed_crosswalk_is_rejected_for_each_published_pack(identifier, monkeypatch):
    definition = describe_conditional_pack(identifier)
    family = definition["family"]
    module = (
        _marital_status_packs
        if family == "marital_status"
        else PROFILE_FAMILIES[family]
    )
    code, other = next(
        (a, b)
        for a in module.CROSSWALK
        for b in module.CROSSWALK
        if module.CROSSWALK[a] != module.CROSSWALK[b]
    )
    first, second = module.CROSSWALK[code], module.CROSSWALK[other]
    monkeypatch.setitem(module.CROSSWALK, code, second)
    monkeypatch.setitem(module.CROSSWALK, other, first)
    with pytest.raises(ValueError, match="definition digest mismatch"):
        describe_conditional_pack(identifier)


@pytest.mark.parametrize("kind", ["unknown", "wrong-family", "duplicate"])
def test_registry_rejects_bad_conditional_references(kind):
    payload = load_compatibility_registry().model_dump()
    entries = {field["concept_identifier"]: field for field in payload["fields"]}
    marital = entries["person.marital-status"]["conditional_pack_identifiers"]
    if kind == "unknown":
        marital.append("unknown-pack")
    elif kind == "wrong-family":
        marital.append(
            entries["person.education"]["conditional_pack_identifiers"].pop()
        )
    else:
        marital.append(marital[0])
    with pytest.raises(ValidationError, match="conditional pack"):
        ControlCompatibilityRegistry.model_validate(payload)
