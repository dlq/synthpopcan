"""Shared synthetic data and assertions for test_webapi.py."""

from __future__ import annotations

import asyncio
import time

import httpx

from synthpopcan.control_packs import build_control_pack_evidence, load_control_pack
from synthpopcan.controls import read_control_table
from synthpopcan.runs import RunStore


def store_upload(store: RunStore, name: str, body: bytes) -> str:
    writer = store.begin_upload(name, max_bytes=len(body))
    writer.write(body)
    return str(writer.finish()["upload_id"])


async def upload(client: httpx.AsyncClient, name: str, body: bytes) -> str:
    response = await client.post(
        "/api/uploads",
        content=body,
        headers={"x-filename": name, "content-type": "text/csv"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["upload_id"])


async def wait_for_terminal(
    client: httpx.AsyncClient, run_id: str, timeout: float = 10
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = await client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200, response.text
        manifest = response.json()
        if manifest["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            return manifest
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


def ipf_request(seed_upload_id: str, controls_upload_id: str) -> dict:
    return {
        "workflow": "ipf",
        "inputs": {
            "seed_upload_id": seed_upload_id,
            "controls_upload_id": controls_upload_id,
        },
        "options": {},
    }


def seed_csv() -> bytes:
    return b"id,age,sex\n1,young,F\n2,young,M\n3,old,F\n4,old,M\n"


def controls_csv() -> bytes:
    return (
        b"margin,dimensions,age,sex,count\n"
        b"age,age,young,,60\n"
        b"age,age,old,,40\n"
        b"sex,sex,,F,50\n"
        b"sex,sex,,M,50\n"
    )


def control_pack_request(store: RunStore) -> dict:
    pack = load_control_pack("statcan-2021-core-private-household-da-v1")
    candidate_households = store_upload(
        store,
        "candidate-households.csv",
        control_pack_candidate_households_csv(),
    )
    candidate_persons = store_upload(
        store,
        "candidate-persons.csv",
        control_pack_candidate_persons_csv(),
    )
    controls = store_upload(
        store,
        "household-controls.csv",
        control_pack_household_controls_csv(),
    )
    person_controls = store_upload(
        store,
        "person-controls.csv",
        control_pack_person_controls_csv(),
    )
    evidence = build_control_pack_evidence(
        pack,
        read_control_table(store.upload_path(controls)),
        read_control_table(store.upload_path(person_controls)),
        geographies={
            "24660244": {
                "total_population": 15,
                "persons_in_private_households": 15,
            }
        },
        controls_source_revisions=pack.source_revisions,
    )
    evidence_upload = store_upload(
        store,
        "control-pack-evidence.json",
        evidence.model_dump_json(indent=2).encode(),
    )
    return {
        "workflow": "small_area",
        "inputs": {
            "candidate_households_upload_id": candidate_households,
            "candidate_persons_upload_id": candidate_persons,
            "controls_upload_id": controls,
            "person_controls_upload_id": person_controls,
            "control_pack_id": pack.identifier,
            "control_pack_evidence_upload_id": evidence_upload,
        },
        "options": {
            "candidate_households": 5,
            "geography_dimension": "da",
            "geography_column": "DAUID",
        },
    }


def control_pack_candidate_households_csv() -> bytes:
    return (
        b"synthetic_household_id,household_size,TENUR\n"
        b"h1,1,1\n"
        b"h2,2,2\n"
        b"h3,3,1\n"
        b"h4,4,2\n"
        b"h5,5,1\n"
    )


def control_pack_candidate_persons_csv() -> bytes:
    rows = ["synthetic_person_id,synthetic_household_id,AGEGRP,GENDER\n"]
    person_index = 0
    for household_size in range(1, 6):
        for _member in range(household_size):
            age_group = ("1", "4", "14")[person_index % 3]
            gender = ("1", "2")[(person_index // 3) % 2]
            rows.append(f"p{person_index + 1},h{household_size},{age_group},{gender}\n")
            person_index += 1
    return "".join(rows).encode()


def control_pack_household_controls_csv(*, multiplier: int = 1) -> bytes:
    rows = ["margin,dimensions,da,household_size_group,TENUR,count\n"]
    for category in ("1", "2", "3", "4", "5"):
        rows.append(
            f'household size,"da,household_size_group",24660244,{category},,'
            f"{multiplier}\n"
        )
    rows.extend(
        (
            f'tenure,"da,TENUR",24660244,,1,{3 * multiplier}\n',
            f'tenure,"da,TENUR",24660244,,2,{2 * multiplier}\n',
        )
    )
    return "".join(rows).encode()


def control_pack_person_controls_csv() -> bytes:
    rows = ["margin,dimensions,da,age_group_3,GENDER,count\n"]
    for age_group in ("0_14", "15_64", "65_plus"):
        rows.extend(
            (
                f'broad age by gender,"da,age_group_3,GENDER",24660244,'
                f"{age_group},1,3\n",
                f'broad age by gender,"da,age_group_3,GENDER",24660244,'
                f"{age_group},2,2\n",
            )
        )
    return "".join(rows).encode()
