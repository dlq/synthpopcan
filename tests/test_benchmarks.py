from synthpopcan.benchmarks import build_ipf_benchmark_cases, run_ipf_benchmark


def test_builds_named_ipf_benchmark_cases() -> None:
    cases = build_ipf_benchmark_cases(seed_records=120)

    assert [case.name for case in cases] == [
        "easy_balanced",
        "moderate_three_margin",
        "high_cardinality_inconsistent",
    ]
    assert len(cases[0].records) == 120
    assert cases[0].margin_cell_count == 4
    assert cases[1].margin_cell_count > cases[0].margin_cell_count
    assert cases[2].expected_converged is False


def test_runs_small_ipf_benchmark_case() -> None:
    case = build_ipf_benchmark_cases(seed_records=120)[0]

    result = run_ipf_benchmark(case)

    assert result["case"] == "easy_balanced"
    assert result["seed_records"] == 120
    assert result["margin_cells"] == 4
    assert result["converged"] is True
    assert result["iterations"] > 0
    assert result["fit_seconds"] >= 0
    assert result["expanded_rows"] == 1200
