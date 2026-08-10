from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from synthpopcan.assurance import verify_run_assurance
from synthpopcan.runs import RUN_SCHEMA_VERSION, RunStore, publish_artifact


def test_run_store_streams_claims_and_records_uploads(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "workspace")
    seed = write_upload(store, "../private/seed.csv", b"id,age\n1,young\n")
    controls = write_upload(
        store,
        "controls.csv",
        b"margin,dimensions,age,count\nage,age,young,1\n",
    )

    manifest = store.create_ipf_run(ipf_request(seed, controls))

    assert manifest["schema_version"] == RUN_SCHEMA_VERSION
    assert manifest["status"] == "queued"
    assert manifest["inputs"][0]["display_name"] == "seed.csv"
    assert store.resolve_managed_path(manifest["inputs"][0]["path"]).read_bytes() == (
        b"id,age\n1,young\n"
    )
    assert len(manifest["inputs"][0]["sha256"]) == 64
    assert store.read_events(manifest["run_id"])[0]["stage"] == "queued"
    with pytest.raises(ValueError, match="already been claimed"):
        store.get_upload(seed, require_unclaimed=True)


def test_upload_writer_rejects_empty_and_oversize_files(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    empty = store.begin_upload("empty.csv", max_bytes=10)
    with pytest.raises(ValueError, match="empty"):
        empty.finish()

    oversized = store.begin_upload("large.csv", max_bytes=3)
    with pytest.raises(ValueError, match="size limit"):
        oversized.write(b"four")
    oversized.abort()
    assert list(store.uploads_dir.glob("*.part")) == []


def test_artifact_publication_checks_cancellation_before_atomic_publish(
    tmp_path: Path,
) -> None:
    source = tmp_path / "work.csv"
    destination = tmp_path / "artifact.csv"
    source.write_bytes(b"value\n1\n")

    def cancelled() -> None:
        raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        publish_artifact(
            tmp_path,
            source,
            destination,
            logical_name="test",
            media_type="text/csv",
            cancel_check=cancelled,
        )

    assert source.is_file()
    assert not destination.exists()
    assert list(tmp_path.glob(".*.publish-*")) == []


def test_artifact_publication_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "work.csv"
    source.write_bytes(b"value\n1\n")
    outside = tmp_path / "outside.csv"

    with pytest.raises(ValueError, match="destination escapes"):
        publish_artifact(
            workspace,
            source,
            outside,
            logical_name="test",
            media_type="text/csv",
        )

    with pytest.raises(ValueError, match="source escapes"):
        publish_artifact(
            workspace,
            outside,
            workspace / "artifact.csv",
            logical_name="test",
            media_type="text/csv",
        )


def test_run_store_rejects_ids_traversal_and_symlink_escape(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "workspace")

    with pytest.raises(ValueError, match="invalid upload ID"):
        store.get_upload("../secret")
    with pytest.raises(ValueError, match="invalid run ID"):
        store.load_run("../secret")
    with pytest.raises(ValueError, match="escapes"):
        store.resolve_managed_path("../secret")
    with pytest.raises(ValueError, match="must be relative"):
        store.resolve_managed_path(str((tmp_path / "absolute.csv").resolve()))

    outside = tmp_path / "outside"
    outside.mkdir()
    link = store.root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(ValueError, match="escapes"):
        store.resolve_managed_path("escape/secret.csv")

    outside_run = outside / "run"
    outside_run.mkdir()
    run_link = store.runs_dir / "20260801T120000Z-abcdef123456"
    try:
        run_link.symlink_to(outside_run, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(ValueError, match="run path escapes"):
        store.run_dir(run_link.name)


def test_run_store_rejects_workspace_subdirectory_symlink_escape(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside-runs"
    outside.mkdir()
    try:
        (workspace / "runs").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")

    with pytest.raises(ValueError, match="runs directory escapes"):
        RunStore(workspace)

    (workspace / "runs").unlink()
    (workspace / "runs").mkdir()
    (workspace / "uploads").rmdir()
    try:
        (workspace / "uploads").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(ValueError, match="uploads directory escapes"):
        RunStore(workspace)


def test_run_store_rejects_atomic_write_and_upload_symlink_escapes(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path / "workspace")
    outside = tmp_path / "outside.json"
    outside.write_text("{}")

    with pytest.raises(ValueError, match="JSON path escapes"):
        store._write_json_atomic(outside, {})  # noqa: SLF001

    upload_id = "a" * 32
    upload_link = store.uploads_dir / f"{upload_id}.bin"
    try:
        upload_link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(ValueError, match="upload path escapes"):
        store._release_upload_claim(  # noqa: SLF001
            {"upload_id": upload_id, "path": "uploads/claimed.bin"}
        )


def test_run_store_validates_persisted_upload_and_manifest_schemas(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path)
    upload_id = write_upload(store, "seed.csv", b"id,age\n1,young\n")
    metadata_path = store.uploads_dir / f"{upload_id}.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["byte_size"] = "not-an-integer"
    metadata_path.write_text(json.dumps(metadata))

    with pytest.raises(ValueError, match="byte_size"):
        store.get_upload(upload_id)

    manifest_store = RunStore(tmp_path / "manifest-workspace")
    seed = write_upload(manifest_store, "seed.csv", b"id,age\n1,young\n")
    controls = write_upload(
        manifest_store,
        "controls.csv",
        b"margin,dimensions,age,count\nage,age,young,1\n",
    )
    manifest = manifest_store.create_ipf_run(ipf_request(seed, controls))
    run_id = str(manifest["run_id"])
    manifest_path = manifest_store.run_dir(run_id) / "run.json"
    persisted = json.loads(manifest_path.read_text())
    persisted["status"] = "mystery"
    manifest_path.write_text(json.dumps(persisted))

    with pytest.raises(ValueError, match="status"):
        manifest_store.load_run(run_id)


def test_run_store_recovers_unfinished_runs_as_interrupted(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    store = RunStore(workspace)
    seed = write_upload(store, "seed.csv", b"id,age\n1,young\n")
    controls = write_upload(
        store,
        "controls.csv",
        b"margin,dimensions,age,count\nage,age,young,1\n",
    )
    manifest = store.create_ipf_run(ipf_request(seed, controls))
    run_id = str(manifest["run_id"])
    store.transition_run(run_id, "running")

    recovered = RunStore(workspace).load_run(run_id)

    assert recovered["status"] == "interrupted"
    assert recovered["finished_at"] is not None
    assert recovered["error"]["kind"] == "interrupted"
    assert recovered["assurance"]["successful"] is False
    assert recovered["assurance"]["terminal_status"] == "interrupted"
    assert RunStore(workspace).verify_assurance(run_id)["passed"] is True
    assert RunStore(workspace).read_events(run_id)[-1]["stage"] == "interrupted"


def test_manifest_updates_are_valid_json_and_transitions_are_checked(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path)
    seed = write_upload(store, "seed.csv", b"id,age\n1,young\n")
    controls = write_upload(
        store,
        "controls.csv",
        b"margin,dimensions,age,count\nage,age,young,1\n",
    )
    manifest = store.create_ipf_run(ipf_request(seed, controls))
    run_id = str(manifest["run_id"])

    updated = store.update_run(run_id, summary={"test": True})

    assert updated["summary"] == {"test": True}
    assert json.loads((store.run_dir(run_id) / "run.json").read_text()) == updated
    with pytest.raises(ValueError, match="invalid run transition"):
        store.transition_run(run_id, "succeeded")


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_terminal_unsuccessful_runs_have_non_success_assurance(
    tmp_path: Path,
    status: str,
) -> None:
    store = RunStore(tmp_path)
    seed = write_upload(store, "seed.csv", b"id,age\n1,young\n")
    controls = write_upload(
        store,
        "controls.csv",
        b"margin,dimensions,age,count\nage,age,young,1\n",
    )
    manifest = store.create_ipf_run(ipf_request(seed, controls))
    run_id = str(manifest["run_id"])
    terminal = store.transition_run(
        run_id,
        status,
        error={"kind": status, "message": f"run {status}"},
    )

    assert terminal["assurance"]["terminal_status"] == status
    assert terminal["assurance"]["successful"] is False
    assert store.verify_assurance(run_id) == {"passed": True, "issues": []}


def test_success_assurance_recomputes_evidence_and_detects_tampering(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path)
    seed = write_upload(store, "seed.csv", b"id,age\n1,young\n")
    controls = write_upload(
        store,
        "controls.csv",
        b"margin,dimensions,age,count\nage,age,young,1\n",
    )
    manifest = store.create_ipf_run(ipf_request(seed, controls))
    run_id = str(manifest["run_id"])
    store.transition_run(run_id, "running")
    source = store.run_dir(run_id) / "work" / "weights.csv"
    source.write_text("id,age,weight\n1,young,1\n")
    artifact = publish_artifact(
        store.root,
        source,
        store.run_dir(run_id) / "artifacts" / "weights.csv",
        logical_name="weights",
        media_type="text/csv",
        row_count=1,
    )
    terminal = store.transition_run(
        run_id,
        "succeeded",
        artifacts=[artifact],
        summary={"converged": True, "iterations": 1},
    )

    assurance = terminal["assurance"]
    assert assurance["schema_version"] == "synthpopcan-assurance-v1"
    assert assurance["successful"] is True
    assert assurance["artifacts"][0]["row_count"] == 1
    assert store.verify_assurance(run_id) == {"passed": True, "issues": []}

    store.resolve_managed_path(artifact["path"]).write_text(
        "id,age,weight\n1,young,2\n"
    )
    verification = store.verify_assurance(run_id)
    assert verification["passed"] is False
    assert any("sha256 does not match" in issue for issue in verification["issues"])


def test_assurance_verifier_reports_contract_mismatches(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    seed = write_upload(store, "seed.csv", b"id,age\n1,young\n")
    controls = write_upload(
        store,
        "controls.csv",
        b"margin,dimensions,age,count\nage,age,young,1\n",
    )
    manifest = store.create_ipf_run(ipf_request(seed, controls))
    terminal = store.transition_run(str(manifest["run_id"]), "cancelled")

    assert verify_run_assurance(
        {**terminal, "assurance": None},
        store.resolve_managed_path,
    ) == {"passed": False, "issues": ["run has no assurance evidence"]}

    malformed = deepcopy(terminal)
    malformed["status"] = "running"
    malformed["request"]["options"]["subsample_seed"] = 99
    malformed["assurance"].update(
        {
            "schema_version": "unknown",
            "run_schema_version": "unknown",
            "synthpopcan_version": "unknown",
            "terminal_status": "failed",
            "successful": True,
            "normalized_request": {},
            "settings": {},
            "random_seeds": {},
            "model": {},
            "inputs": [],
            "artifacts": {},
        }
    )
    verification = verify_run_assurance(malformed, store.resolve_managed_path)

    assert verification["passed"] is False
    assert set(verification["issues"]) >= {
        "unsupported assurance schema",
        "run schema version does not match the run manifest",
        "SynthPopCan version does not match the run manifest",
        "run is not terminal",
        "terminal status does not match the run manifest",
        "successful flag does not match the terminal status",
        "normalized request does not match the run manifest",
        "settings do not match the normalized request",
        "random seeds do not match the normalized request",
        "missing inputs evidence for seed",
        "artifacts evidence is malformed",
        "model identity or checksum does not match",
    }


def test_run_creation_rolls_back_partially_claimed_uploads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RunStore(tmp_path)
    seed = write_upload(store, "seed.csv", b"id,age\n1,young\n")
    controls = write_upload(
        store,
        "controls.csv",
        b"margin,dimensions,age,count\nage,age,young,1\n",
    )
    original_write = store._write_json_atomic
    writes = 0

    def fail_second_claim(path: Path, payload: dict) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("simulated metadata failure")
        original_write(path, payload)

    monkeypatch.setattr(store, "_write_json_atomic", fail_second_claim)

    with pytest.raises(OSError, match="simulated metadata failure"):
        store.create_ipf_run(ipf_request(seed, controls))

    assert store.get_upload(seed, require_unclaimed=True)["claimed_by"] is None
    assert store.get_upload(controls, require_unclaimed=True)["claimed_by"] is None
    assert store.upload_path(seed).is_file()
    assert store.upload_path(controls).is_file()
    assert list(store.runs_dir.iterdir()) == []


def test_small_area_run_claims_control_pack_evidence_as_a_durable_input(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path)
    households = write_upload(
        store,
        "households.csv",
        b"synthetic_household_id,household_size,TENUR\nh1,1,1\n",
    )
    persons = write_upload(
        store,
        "persons.csv",
        b"synthetic_person_id,synthetic_household_id,AGEGRP,GENDER\np1,h1,1,1\n",
    )
    controls = write_upload(store, "controls.csv", b"controls\nplaceholder\n")
    person_controls = write_upload(
        store, "person-controls.csv", b"controls\nplaceholder\n"
    )
    evidence = write_upload(store, "evidence.json", b'{"schema_version":"test"}')

    manifest = store.create_small_area_run(
        {
            "workflow": "small_area",
            "inputs": {
                "candidate_households_upload_id": households,
                "candidate_persons_upload_id": persons,
                "controls_upload_id": controls,
                "person_controls_upload_id": person_controls,
                "control_pack_id": "statcan-2021-core-private-household-da-v1",
                "control_pack_evidence_upload_id": evidence,
            },
            "options": {
                "candidate_households": 1,
                "geography_dimension": "da",
                "geography_column": "da",
            },
        }
    )

    inputs = {item["logical_name"]: item for item in manifest["inputs"]}
    assert inputs["control_pack_evidence"]["path"].endswith(
        "/inputs/control-pack-evidence.json"
    )
    assert manifest["request"]["inputs"]["control_pack_id"] == (
        "statcan-2021-core-private-household-da-v1"
    )
    with pytest.raises(ValueError, match="already been claimed"):
        store.get_upload(evidence, require_unclaimed=True)


def write_upload(store: RunStore, name: str, body: bytes) -> str:
    writer = store.begin_upload(name, max_bytes=max(1, len(body)))
    midpoint = len(body) // 2
    writer.write(body[:midpoint])
    writer.write(body[midpoint:])
    return str(writer.finish()["upload_id"])


def ipf_request(seed_upload_id: str, controls_upload_id: str) -> dict:
    return {
        "workflow": "ipf",
        "inputs": {
            "seed_upload_id": seed_upload_id,
            "controls_upload_id": controls_upload_id,
        },
        "options": {
            "weight_column": None,
            "max_iterations": 100,
            "tolerance": 1e-6,
            "allow_nonconverged": False,
        },
    }
