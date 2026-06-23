# Validate

Validation commands check generated artifacts. They do not prove a synthetic
population is substantively good, but they catch important mechanical and
calibration errors.

## Concept

Use validation as a normal step in every workflow:

- after IPF fitting;
- after expanding rows;
- after linked household/person generation;
- before interpreting or sharing outputs.

Keep validation reports with the run notes.

Validation is both a technical check and a provenance practice. It records what
was checked, against which target, and with what tolerance.

## What Validation Does Not Prove

A passing validation report is not a certificate that the synthetic population is
substantively correct. It proves only that the checks you asked for passed.

Validation can miss:

- uncontrolled relationships, such as income by household type or language by
  age, when those relationships were not part of the check;
- source-universe problems, such as mixing years, geographies, or household and
  person units;
- biased or sparse seed data that still matches simple controls;
- tree models that match their training view but fail against external public
  totals;
- disclosure or interpretive risks that require human review.

Treat validation as evidence in a research note. Pair it with the source
provenance, category mappings, modelling choices, random seeds, and a short
statement of what the output should not be used to claim.

## What a Serious Validation Note Should Include

For exploratory examples, a short pass/fail report may be enough. For a serious
run, keep enough evidence for another reader to understand both the success and
the weak spots:

- total population and household counts by geography;
- absolute and relative error for each controlled margin;
- worst controls and worst geographies, not only overall averages;
- household-size distribution;
- person count per household and orphaned-person checks;
- family/person role consistency where those fields are generated;
- structural-zero and zero-cell diagnostics;
- seed coverage and unused-category notes;
- suppression, rounding, or source-quality notes for public controls;
- random seed, command, package version, and input provenance.

The goal is not to make validation longer for its own sake. The goal is to stop
a neat pass/fail summary from hiding the exact places where the model is weakest.

## Getting Started

Validate fitted weights:

```bash
synthpopcan validate controls \
  --population weights.csv \
  --controls controls.csv \
  --kind weights
```

Validate expanded rows:

```bash
synthpopcan validate controls \
  --population synthetic.csv \
  --controls controls.csv \
  --kind expanded
```

Validate linked household/person rows:

```bash
synthpopcan validate linked-output \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv
```

## Subcommands

### `validate controls`

Compares fitted or expanded output against normalized controls.

Options:

- `--population PATH`: weights or expanded synthetic CSV.
- `--controls PATH`: normalized control CSV.
- `--kind weights|expanded`: artifact type.
- `--weight-field NAME`: weight column for `--kind weights`.
- `--tolerance FLOAT`: allowed difference.
- `--format table|json`: output format.

### `validate linked-output`

Checks that generated person rows point to known generated households and that
household size matches the number of linked people.

Options include:

- `--households PATH`
- `--persons PATH`
- `--household-id-column NAME`
- `--person-household-id-column NAME`
- `--household-size-column NAME`
- `--format table|json`

### `validate tree-output`

Checks flat tree-generated output against a training sample for selected target
columns.

```bash
synthpopcan validate tree-output \
  --generated synthetic-persons.csv \
  --training person-training.csv \
  --target-columns AGEGRP,SEX
```

## Troubleshooting

**Validation fails after IPF:** inspect the fit report first. The fit may not
have converged, or the wrong weight column may have been used.

**Validation fails after expansion:** confirm `ipf expand` used the intended
`--weight-field`.

**Linked validation fails:** check generated household IDs, person household
IDs, and household size fields.

## Further Reading

- Robin Lovelace and Dimitris Ballas,
  [Truncate, replicate, sample](https://arxiv.org/abs/1303.5228),
  for the distinction between continuous IPF weights and expanded integer rows.
- Statistical disclosure context:
  [Statistical disclosure control](https://en.wikipedia.org/wiki/Statistical_disclosure_control).
