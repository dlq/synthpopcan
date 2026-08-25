# ADR-0015: Require Portable, Inspectable Prepared-Model Runtimes

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decision owners:** Maintainers

## Context

SynthPopCan distributes prepared models so researchers can generate populations
without receiving source microdata or reproducing the model-training
environment. The current conditional-frequency and CART packages store plain
data needed for generation rather than live estimators. CART training uses
scikit-learn, but reading a package and generating records do not.

That separation is easy to lose when considering another model family. Many
machine-learning libraries persist a Python pickle, framework checkpoint, or
other executable object whose behavior depends on a particular library and
runtime. Such artifacts are difficult to inspect independently, unsafe to load
from an untrusted source, brittle across dependency versions, and poorly suited
to long-term scholarly preservation. A trained model can also retain sensitive
detail even when it does not contain obvious source rows.

The project needs requirements that apply to any production model family
without permanently freezing CART as the only acceptable method.

## Decision

Every prepared-model family supported for normal generation or public
distribution must have a versioned, non-executable, portable artifact contract.
Its normal generation runtime must not require the framework used to train the
model.

A supported prepared-model artifact must:

- use declarative data, currently JSON and separately declared tabular assets
  where a future versioned contract justifies them, rather than a pickle,
  framework checkpoint, embedded program, or arbitrary object graph;
- contain the complete model structure, transformations, categories,
  probabilities, parameters, and generation semantics needed for an independent
  implementation to interpret the artifact;
- contain no raw training records or source-row identifiers;
- declare its schema version, model family, field roles, random-seed semantics,
  training and source provenance, release classification, licensing
  presentation, support evidence, and known limitations;
- validate structure, domains, references, and numerical values before any
  generation begins;
- support deterministic seeded generation within the declared runtime contract;
  and
- expose a reviewable explanation of its generation logic and evidence, or
  explicitly document and justify any interpretability tradeoff before that
  model family becomes a supported production path.

Training libraries and other authoring dependencies remain optional. The base
installation must be sufficient to inspect, validate, and generate from every
normally supported published model package. An experimental benchmark may use
an opaque or framework-bound artifact in an isolated research environment, but
that does not make the artifact publishable or establish a public runtime
contract.

Adopting a materially different production model family requires a versioned
artifact design, correctness evidence for an independent runtime or semantic
round trip, disclosure and licensing review, dependency assessment, and a
separate decision when its consequences are not already covered here. CART is
retained for now because it satisfies this boundary and remains interpretable;
this ADR does not claim that CART is statistically superior for every use.

## Alternatives Considered

- **Serialize live scikit-learn or other Python estimators:** rejected because
  pickle-style objects are executable, dependency-coupled, difficult to inspect,
  and unsuitable as durable public research contracts.
- **Require the training framework at generation time:** rejected because
  researchers using reviewed models should not inherit large authoring
  dependencies or framework-version coupling.
- **Allow each model family to define portability informally:** rejected because
  model inspection, release review, security, preservation, and reproducibility
  need one repository-wide boundary.
- **Permanently require CART:** rejected because later evidence may justify
  another model family that still satisfies the portability and reviewability
  requirements.
- **Treat model files as safe because they contain no obvious source CSV:**
  rejected because learned structures, rare paths, transforms, and parameters
  can retain sensitive or identifying detail.

## Consequences

- Published models remain inspectable without executing model-supplied code.
- Generation environments stay smaller and less coupled to authoring tools.
- Independent implementations can validate the meaning of a package rather
  than trusting one library's object deserializer.
- New model families face additional artifact-design, validation, provenance,
  and evidence work before becoming production features.
- Some high-performing framework-native methods may remain benchmark-only when
  no faithful portable runtime exists.
- Portability and inspectability improve review but do not establish
  representativeness, disclosure safety, licensing permission, or fitness for a
  research question.

## Evidence And Related Records

- [CART methodology review](../plans/2026-08-20-cart-methodology-review.md)
- [Tree models documentation](../docs/tree.md)
- [Local source data and reviewed model artifacts](0005-local-source-data-and-reviewed-model-artifacts.md)
- [Prepared-model and source licensing](0014-separate-prepared-model-and-source-licensing.md)
- [`src/synthpopcan/tree.py`](../src/synthpopcan/tree.py)
- [`pyproject.toml`](../pyproject.toml)
- [`tests/test_model_correctness.py`](../tests/test_model_correctness.py)
