"""Interrupted-run restart integrity and transactional failure cases."""

import json
import queue
import threading

import pytest

from synthpopcan.jobs import _small_area_worker
from synthpopcan.runs import RestartError, RunStore


def _upload(store, name, contents):
    writer = store.begin_upload(name, max_bytes=len(contents))
    writer.write(contents)
    return writer.finish()["upload_id"]


def _interrupted(store, *, tamper_before=False, model=False):
    inputs = {"controls_upload_id": _upload(store, "controls.csv", b"control\n1\n")}
    if model:
        inputs["model_id"] = "demo-linked-household-person"
    else:
        inputs["candidate_households_upload_id"] = _upload(store, "hh.csv", b"id\nh1\n")
        inputs["candidate_persons_upload_id"] = _upload(store, "pp.csv", b"id\np1\n")
    original = store.create_small_area_run(
        {"workflow": "small_area", "inputs": inputs, "options": {}}
    )
    run_id = original["run_id"]
    store.transition_run(run_id, "running")
    if tamper_before:
        store.resolve_managed_path(original["inputs"][0]["path"]).write_bytes(
            b"changed\n"
        )
    store.transition_run(run_id, "interrupted")
    return run_id


def test_restart_preserves_old_partial_publication_and_links_new_run(tmp_path):
    store = RunStore(tmp_path)
    run_id = _interrupted(store)
    old_dir = store.run_dir(run_id)
    partial = old_dir / "artifacts" / "households.csv"
    partial.write_text("partially published\n")
    observed = []
    restarted = store.restart_interrupted_small_area(
        run_id, lambda root, paths, request: observed.append((root, paths, request))
    )
    assert restarted["restarted_from"] == run_id
    assert restarted["run_id"] != run_id
    assert restarted["status"] == "queued"
    assert restarted["artifacts"] == []
    assert partial.read_text() == "partially published\n"
    assert store.load_run(run_id)["status"] == "interrupted"
    assert (
        store.read_events(restarted["run_id"])[0]["message"]
        == f"Restarted from {run_id}"
    )
    assert len(observed[0][1]) == len(restarted["inputs"])
    for old, new in zip(
        store.load_run(run_id)["inputs"], restarted["inputs"], strict=True
    ):
        assert old["sha256"] == new["sha256"]
        assert old["path"] != new["path"]
        assert (
            store.resolve_managed_path(new["path"]).read_bytes()
            == store.resolve_managed_path(old["path"]).read_bytes()
        )


@pytest.mark.parametrize("tamper_before", [False, True])
def test_restart_refuses_modified_inputs_even_if_interruption_recorded_them(
    tmp_path, tamper_before
):
    store = RunStore(tmp_path)
    run_id = _interrupted(store, tamper_before=tamper_before)
    if not tamper_before:
        original = store.load_run(run_id)
        store.resolve_managed_path(original["inputs"][0]["path"]).write_bytes(
            b"changed\n"
        )
    with pytest.raises(RestartError, match="changed"):
        store.restart_interrupted_small_area(run_id, lambda *args: None)
    assert len(store.list_runs()) == 1
    assert not list(store.root.glob(".restart-*"))


def test_restart_rejects_invalid_state_and_rolls_back_preflight_failure(tmp_path):
    store = RunStore(tmp_path)
    run_id = _interrupted(store)
    with pytest.raises(ValueError, match="preflight rejected"):
        store.restart_interrupted_small_area(
            run_id,
            lambda *args: (_ for _ in ()).throw(ValueError("preflight rejected")),
        )
    assert len(store.list_runs()) == 1
    assert not list(store.root.glob(".restart-*"))
    store.update_run(run_id, status="succeeded")
    with pytest.raises(RestartError, match="Only interrupted"):
        store.restart_interrupted_small_area(run_id, lambda *args: None)


def test_restart_refuses_different_model_and_version(tmp_path):
    store = RunStore(tmp_path)
    run_id = _interrupted(store, model=True)
    (store.run_dir(run_id) / "work" / "package.json").write_text(
        json.dumps({"different": True})
    )
    with pytest.raises(RestartError, match="model has changed"):
        store.restart_interrupted_small_area(run_id, lambda *args: None)
    store.update_run(run_id, synthpopcan_version="0.0.0")
    with pytest.raises(RestartError, match="different SynthPopCan version"):
        store.restart_interrupted_small_area(run_id, lambda *args: None)


def test_restart_rejects_dangling_model_symlink(tmp_path):
    store = RunStore(tmp_path)
    run_id = _interrupted(store, model=True)
    package = store.run_dir(run_id) / "work" / "package.json"
    package.symlink_to(tmp_path / "missing")
    with pytest.raises(RestartError, match="model path is invalid"):
        store.restart_interrupted_small_area(run_id, lambda *args: None)


def test_restart_rolls_back_failed_atomic_publication(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    run_id = _interrupted(store)

    def fail_rename(*args):
        raise OSError("simulated publication failure")

    monkeypatch.setattr("synthpopcan.runs.os.rename", fail_rename)
    with pytest.raises(OSError, match="publication failure"):
        store.restart_interrupted_small_area(run_id, lambda *args: None)
    assert len(store.list_runs()) == 1
    assert store.load_run(run_id)["status"] == "interrupted"
    assert not list(store.root.glob(".restart-*"))


def test_restart_rejects_input_modified_during_preflight(tmp_path):
    store = RunStore(tmp_path)
    run_id = _interrupted(store)

    def alter_copy(root, paths, request):
        next(iter(paths.values())).write_bytes(b"changed during preflight\n")

    with pytest.raises(RestartError, match="during preflight"):
        store.restart_interrupted_small_area(run_id, alter_copy)
    assert len(store.list_runs()) == 1
    assert not list(store.root.glob(".restart-*"))


def test_restart_never_replaces_an_existing_run(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    run_id = _interrupted(store)
    before = (store.run_dir(run_id) / "run.json").read_bytes()
    monkeypatch.setattr("synthpopcan.runs._new_run_id", lambda: run_id)
    with pytest.raises(FileExistsError, match="already exists"):
        store.restart_interrupted_small_area(run_id, lambda *args: None)
    assert (store.run_dir(run_id) / "run.json").read_bytes() == before
    assert not list(store.root.glob(".restart-*"))


def test_restart_provenance_is_in_terminal_assurance(tmp_path):
    store = RunStore(tmp_path)
    run_id = _interrupted(store)
    new = store.restart_interrupted_small_area(run_id, lambda *args: None)
    store.transition_run(new["run_id"], "running")
    finished = store.transition_run(new["run_id"], "interrupted")
    assert finished["assurance"]["restarted_from"] == run_id
    assert store.verify_assurance(new["run_id"])["passed"]
    store.update_run(new["run_id"], restarted_from="20260101T000000Z-aaaaaaaaaaaa")
    assert not store.verify_assurance(new["run_id"])["passed"]


def test_crash_after_restart_publication_can_be_restarted_again(tmp_path):
    store = RunStore(tmp_path)
    old_id = _interrupted(store)
    queued = store.restart_interrupted_small_area(old_id, lambda *args: None)
    recovered = RunStore(tmp_path)
    interrupted = recovered.load_run(queued["run_id"])
    assert interrupted["status"] == "interrupted"
    retried = recovered.restart_interrupted_small_area(
        queued["run_id"], lambda *args: None
    )
    assert retried["restarted_from"] == queued["run_id"]
    assert recovered.load_run(old_id)["status"] == "interrupted"


def test_restart_worker_rejects_input_tampered_after_publication(tmp_path):
    store = RunStore(tmp_path)
    old_id = _interrupted(store)
    new = store.restart_interrupted_small_area(old_id, lambda *args: None)
    store.resolve_managed_path(new["inputs"][0]["path"]).write_bytes(b"changed\n")
    messages = queue.SimpleQueue()
    _small_area_worker(str(store.root), new["run_id"], new, messages, threading.Event())
    failure = messages.get()
    assert failure["type"] == "failed"
    assert "changed before execution" in failure["error"]["message"]
    assert not list((store.run_dir(new["run_id"]) / "artifacts").iterdir())
