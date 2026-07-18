import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_pumf_metadata.py"
_SPEC = importlib.util.spec_from_file_location("prepare_pumf_metadata", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
parse_spss_metadata = _MODULE.parse_spss_metadata


def test_parses_pumf_fixed_widths_and_wrapped_labels() -> None:
    text = """
DATA LIST FILE=DATA/
   HH_ID 1-6  GENDER 7  WEIGHT 8-23 .
FORMATS
  WEIGHT (F16.12) / .
VARIABLE LABELS
   HH_ID 'Household unique identifier'
   GENDER 'Gender of person ' +
   '(binary)'
   WEIGHT 'Survey weight'
VALUE LABELS
   GENDER 1 'Man' 2 'Woman' .
"""

    assert parse_spss_metadata(text) == {
        "HH_ID": {
            "fixed_width": {"start": 1, "end": 6, "width": 6},
            "label": "Household unique identifier",
        },
        "GENDER": {
            "fixed_width": {"start": 7, "end": 7, "width": 1},
            "label": "Gender of person (binary)",
        },
        "WEIGHT": {
            "fixed_width": {"start": 8, "end": 23, "width": 16},
            "label": "Survey weight",
        },
    }


def test_rejects_incomplete_spss_program() -> None:
    with pytest.raises(ValueError, match="DATA LIST"):
        parse_spss_metadata("VARIABLE LABELS")
