API Reference
=============

The Python API is still early, but the objects on this page are the intended
**public library surface** for scripts, notebooks, and reusable research workflows.
For **beginner workflow examples**, start with :doc:`library-getting-started`; for
**module-level examples**, see :doc:`library`. This page is the generated member
reference.

This page is generated with **Sphinx autodoc**, which imports modules and renders
their docstrings and public members. See the Sphinx
`autodoc documentation <https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html>`_
for the underlying mechanism.

The lower-level sections are **intentionally curated**. They include objects that
are useful for notebooks, scripts, reusable research workflows, and contributor
extensions. CLI callbacks, formatting helpers, web-app internals, benchmark
helpers, and other implementation details are left out even when they are
public-by-name in the source tree.

Stability
---------

Names exported directly from :mod:`synthpopcan` are the stable beginner API and
carry the package's compatibility promise. The curated lower-level names on this
page are supported advanced APIs, but may still evolve before version 1.0. Other
module attributes and ``__all__`` declarations are implementation details unless
they are listed here.

The geography, geodata, generic enrichment, Québec DA proof, and national
small-area APIs were added in ``0.7.0``. Maintained Can-FED and ODEF workflows
were added in ``0.7.2``.

Top-Level Beginner API
----------------------

The top-level package exposes a **small beginner-friendly API** for concise
notebooks and examples:

.. code-block:: python

   import synthpopcan as spc

   controls = spc.read_controls("controls.csv")
   fit = spc.fit_ipf("seed.csv", controls)

The workflow functions and result classes are defined in
:mod:`synthpopcan.api`, then re-exported unchanged from :mod:`synthpopcan`.
Autodoc therefore displays signatures such as
``synthpopcan.api.fit_ipf(...)`` below. Calling ``spc.fit_ipf(...)`` uses that
same supported function; it is the shorter form taught in the beginner guide.

.. automodule:: synthpopcan

Beginner API Members
--------------------

.. automodule:: synthpopcan.api
   :members:
   :show-inheritance:

Local Data and Sources
----------------------

.. automodule:: synthpopcan.localdata
   :members: DataLayoutCheck, inspect_local_data_layout
   :show-inheritance:

.. automodule:: synthpopcan.sources
   :members: inspect_source_root, read_source_schema, read_source_sample
   :show-inheritance:

Geography and Enrichment
------------------------

.. automodule:: synthpopcan.geography
   :members: GeographyUniverse, GeographyIdentity, GeographyRelationship,
             statcan_geography_universe, statcan_geography_identity,
             ensure_geography_compatible, validate_geography_identifiers
   :show-inheritance:

.. automodule:: synthpopcan.enrichment
   :members: SourceProfile, ResourceRecord, EnrichmentLayer,
             EnrichmentManifest, SourceAdapter, acquire_public_resource,
             register_resource, build_enrichment_layer,
             build_enrichment_manifest, import_normalized_layer,
             read_source_profile, read_resource_record,
             read_enrichment_manifest, validate_normalized_layer,
             verify_enrichment_manifest

.. automodule:: synthpopcan.canfed
   :members: CanFedAdapter, can_fed_source_profile,
             normalize_can_fed_archive

.. automodule:: synthpopcan.odef
   :members: OdefAdapter, odef_source_profile, normalize_odef_archive

.. automodule:: synthpopcan.da_proof
   :members: finalize_quebec_da_proof, prepare_quebec_da_proof,
             select_quebec_da_relationships
   :show-inheritance:

.. automodule:: synthpopcan.national_small_area
   :members: NationalSmallAreaJurisdiction,
             CANADA_SMALL_AREA_JURISDICTIONS,
             NationalSmallAreaSpecification, small_area_specification,
             required_2021_profile_keys, national_2021_profile_paths,
             load_2021_small_area_jurisdictions,
             prepare_canada_small_area_plan,
             estimate_national_small_area_storage,
             execute_canada_small_area_plan
   :show-inheritance:

.. automodule:: synthpopcan.national_execution
   :members: NationalBatchRunConfiguration,
             prepare_national_candidate_pools,
             find_cached_national_candidate_pools,
             reset_nonconverged_national_batches,
             run_national_cached_batch,
             build_national_geography_summary
   :show-inheritance:

.. automodule:: synthpopcan.geodata
   :members: load_geodata_catalogue, fetch_display_boundaries,
             geodata_cache_dir

Controls
--------

.. automodule:: synthpopcan.controls
   :members: ControlCell, ControlMargin, ControlTable, read_control_table,
             read_control_margins, read_wds_control_table, inspect_wds_zip,
             build_wds_category_mapping_template,
             read_census_profile_control_table,
             inspect_census_profile_characteristics, census_profile_template,
             read_census_profile_mapping, read_category_mapping,
             write_control_table
   :show-inheritance:

IPF
---

.. automodule:: synthpopcan.ipf
   :members: IPFMargin, IPFResult, expand_records, integerize_weights,
             fit_ipf, validate_margin_coverage, weighted_totals,
             calculate_max_abs_error
   :show-inheritance:

Microdata
---------

.. automodule:: synthpopcan.microdata
   :members: SeedSample, TreeColumnBlockSpec, TreeColumnSuggestionProfile,
             read_fixture_seed_sample,
             read_statcan_2016_hierarchical_seed_sample, export_seed_rows,
             export_training_rows, export_statcan_2016_person_training_rows,
             export_statcan_2016_household_training_rows,
             derive_statcan_2016_household_seed_sample,
             check_statcan_2016_household_seed_columns,
             suggest_tree_column_blocks, resolve_tree_column_block_pair,
             build_tree_geography_feasibility_report
   :show-inheritance:

Statistics Canada
-----------------

.. automodule:: synthpopcan.statcan
   :members: BoundaryDownload, CensusProfileDownload, WDSTableSearchResult,
             get_boundary_download, fetch_boundary_zip, fetch_dgrf_2021,
             wds_download_url,
             wds_all_cubes_lite_url, wds_metadata_url, search_wds_tables,
             fetch_wds_metadata, summarize_wds_metadata,
             classify_wds_ipf_suitability, extract_wds_dimension_names,
             extract_wds_dimension_previews, fetch_wds_table,
             fetch_census_profile, fetch_census_profile_2016,
             normalize_product_id,
             normalize_language
   :show-inheritance:

Small-Area Synthesis
--------------------

.. automodule:: synthpopcan.small_area_synthesis
   :members: GeographyHouseholdFit, controls_by_geography,
             check_small_area_calibration_inputs,
             check_linked_person_calibration_inputs,
             fit_households_by_geography, fit_linked_by_geography,
             estimate_small_area_run, realize_linked_geography_population,
             calibrate_linked_household_csvs
   :show-inheritance:

Small-Area Control Preparation
------------------------------

.. automodule:: synthpopcan.small_area_controls
   :members: extract_controls_from_profile, scale_and_validate_controls,
             recode_household_size, write_controls_csv,
             write_recoded_candidates
   :show-inheritance:

Small-Area Mapping
------------------

.. automodule:: synthpopcan.map_render
   :members: prepare_boundaries_geojson, filter_boundaries_geojson,
             partition_boundaries_geojson, render_synthesis_map,
             prepare_national_map_statistics, render_national_plan_map
   :show-inheritance:

Tree Models
-----------

.. automodule:: synthpopcan.tree
   :members: TreeTrainingSample, TreeModelSpec, TreeGenerationRequest,
             FrequencyOutcome, FrequencyGroup, FrequencyTreeModel,
             CartTreeModel, read_tree_training_sample, audit_tree_model,
             train_cart_model, train_frequency_model, generate_tree_rows,
             generate_linked_population, validate_linked_population,
             write_tree_model, read_tree_model, read_frequency_model,
             read_cart_model, write_generated_rows
   :show-inheritance:

Validation
----------

.. automodule:: synthpopcan.validation
   :members: build_control_validation_report,
             build_tree_output_validation_report, comparison_dimensions,
             build_distribution_comparison
   :show-inheritance:
