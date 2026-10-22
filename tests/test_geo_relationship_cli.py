"""Geography relationship-file CLI success and download failures."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_cli_downloads_2021_relationship_file(tmp_path: Path) -> None:
    from unittest.mock import patch

    from synthpopcan.cli import main as cli_main

    csv_path = tmp_path / "2021_98260004.csv"
    with patch(
        "synthpopcan.statcan.fetch_dgrf_2021", return_value=csv_path
    ) as mock_fetch:
        exit_code = cli_main(["geo", "relationship-file", "--out-dir", str(tmp_path)])

    assert exit_code == 0
    mock_fetch.assert_called_once_with(tmp_path, url=None)


def test_cli_relationship_file_reports_download_error(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    from synthpopcan.cli import main as cli_main

    with patch(
        "synthpopcan.statcan.fetch_dgrf_2021", side_effect=OSError("network error")
    ):
        with pytest.raises(click.ClickException, match="network error"):
            cli_main(["geo", "relationship-file", "--out-dir", str(tmp_path)])
