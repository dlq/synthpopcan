import json

import pytest
from click.exceptions import ClickException

from synthpopcan.cli import main
from synthpopcan.sources import _sniff_delimiter, read_source_sample


def test_sources_inspect_counts_files_by_extension(tmp_path, capsys) -> None:
    (tmp_path / "a.csv").write_text("x,y\n1,2\n")
    (tmp_path / "b.txt").write_text("hello\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "c.csv").write_text("x,y\n3,4\n")

    assert main(["data", "inspect", str(tmp_path), "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["files"] == 3
    assert payload["extensions"] == {".csv": 2, ".txt": 1}


def test_sources_schema_reports_csv_columns_and_delimiter(tmp_path, capsys) -> None:
    source = tmp_path / "sample.csv"
    source.write_text("age,sex,count\nold,F,10\n")

    assert main(["data", "schema", str(source), "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["delimiter"] == ","
    assert payload["columns"] == ["age", "sex", "count"]


def test_sources_sample_outputs_limited_rows(tmp_path, capsys) -> None:
    source = tmp_path / "sample.csv"
    source.write_text("age,sex\nold,F\nyoung,M\n")

    assert (
        main(
            [
                "data",
                "sample",
                str(source),
                "--rows",
                "1",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"] == [{"age": "old", "sex": "F"}]


def test_sources_sample_rejects_non_positive_rows(tmp_path) -> None:
    source = tmp_path / "sample.csv"
    source.write_text("age,sex\nold,F\n")

    with pytest.raises(ValueError, match="rows must be at least 1"):
        read_source_sample(source, 0)


def test_sources_sniffs_delimiter_with_suffix_fallbacks(tmp_path) -> None:
    tsv_source = tmp_path / "empty.tsv"
    text_source = tmp_path / "empty.txt"
    tsv_source.write_text("")
    text_source.write_text("")

    assert _sniff_delimiter(tsv_source) == "\t"
    assert _sniff_delimiter(text_source) == ","


def test_sources_sample_requires_private_override(tmp_path) -> None:
    private_dir = tmp_path / "data" / "private"
    private_dir.mkdir(parents=True)
    source = private_dir / "sample.csv"
    source.write_text("age,sex\nold,F\n")

    with pytest.raises(ClickException, match="private data"):
        main(["data", "sample", str(source), "--format", "json"])

    assert (
        main(
            [
                "data",
                "sample",
                str(source),
                "--allow-private",
                "--format",
                "json",
            ]
        )
        == 0
    )


def test_sources_sample_wraps_reader_errors(tmp_path) -> None:
    source = tmp_path / "sample.csv"
    source.write_text("age,sex\nold,F\n")

    with pytest.raises(ClickException, match="rows must be at least 1"):
        main(["data", "sample", str(source), "--rows", "0", "--format", "json"])


def test_sources_schema_reports_missing_file_without_traceback(tmp_path) -> None:
    missing = tmp_path / "missing.csv"

    with pytest.raises(ClickException) as excinfo:
        main(["data", "schema", str(missing)])

    message = str(excinfo.value)
    assert "Could not read" in message
    assert str(missing) in message
