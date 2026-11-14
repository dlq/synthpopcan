# Archive Transition Review — 2026-11-14

This review covers the maintainer Zenodo executor, not ordinary population
runs. It reads the existing executor and its local fake-server tests; it does
not contact or modify Zenodo. Operation identities bind the operation, package,
asset and metadata. Checkpoints are separately scoped by API target. Before a
remote mutation, the executor checks the local authority and source evidence,
validates the payload when applicable, and rebinds the remote identity.

| Checkpoint or observation | Permitted next action | Refusal and recovery boundary |
| --- | --- | --- |
| No checkpoint | Persist `action-intent`, then obtain or create a draft for the authorized operation. | Refuse mismatched source identity, execution authority, licensing, payload or predecessor before mutation. |
| `action-intent` | Recover a draft already owned by this operation, or request and claim the specifically authorized new record, existing-record edit, or new-version draft. Persist `created` or `editing`. | An unowned or ambiguously owned draft is not adopted. Narrow historical interrupted-action recovery requires its exact recorded identity and remote snapshot. |
| `created` / `editing` | Re-read and verify the owned draft and bucket. For asset operations, verify any previously uploaded candidate or remove only the verified inherited files allowed by the new-version operation, then upload and verify the candidate; persist `uploaded`. A metadata-only correction keeps the existing asset. | Refuse a changed owner, parent, bucket, unexpected candidate, duplicate file, bad upload checksum, or unauthorized source-file change. |
| `uploaded` | Reverify the remote candidate; update owned metadata, re-read it, verify the complete expected file set, and persist `draft`. | A mismatched candidate or metadata is not overwritten or published. |
| `draft` | Revalidate ownership, metadata and files. Stop at a durable draft unless publication was requested. With publication requested, invoke publish and persist `published`. | Never publish on an ordinary draft-only invocation; reject changed remote state and unrelated files. |
| `published` | Re-read and verify the published record and asset, then persist `verified`. | A local checkpoint alone is not evidence of remote completion. |
| `verified` | Reverify remote completion and identity before returning. | Reject `verified` without its verification flag; only verified production corrections bound to the current authority can enter registry-update evidence. |
| Earlier mutable checkpoint, remote already published | Verify the remote terminal record and expected files; checkpoint `published`, then `verified`, without publishing again. | Refuse identity or file mismatches rather than assuming the prior write succeeded. |
| Unknown or malformed checkpoint state | Stop with an error. | No draft creation, upload, metadata write, deletion or publication is attempted. |

The transition and refusal tests are in
[`test_deposit_zenodo_records.py`](../../tests/test_deposit_zenodo_records.py).
They cover the action-intent ownership proofs and special recovery, a crash
between upload and checkpoint, a crash between publication and checkpoint,
reverification of terminal checkpoints, and refusal of changed predecessor,
bucket, metadata, file and operation identities. The unknown-state case now
fails closed even for draft-only invocations. Four new malformed-state cases
and the complete executor suite passed locally (160 tests).

Decision: **defer `RB12-08` and `RB12-09` from 1.2.0**. The existing executor
has operation-specific ownership checks, exceptional historical recovery and
remote read-after-write verification interleaved with transitions. Extracting
only a subset into a purported pure planner would risk implying that it owns
all authorization decisions; moving all of them deserves an independently
reviewed archive change. The current executor's characterized guards remain in
force, and this release adds no archive operation. The extraction remains
planned, rather than being represented as completed.
