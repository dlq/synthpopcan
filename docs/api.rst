API Reference
=============

The Python API is still early. Prefer the CLI for ordinary use until the public
library surface is declared stable. This reference documents the modules that
currently contain reusable workflow logic.

This page is generated with Sphinx autodoc, which imports modules and renders
their docstrings and public members. See the Sphinx
`autodoc documentation <https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html>`_
for the underlying mechanism.

Package
-------

.. automodule:: synthpopcan

Controls
--------

.. automodule:: synthpopcan.controls
   :members: ControlCell, ControlMargin, ControlTable, read_control_table, read_control_margins, read_wds_control_table, inspect_wds_zip, build_wds_category_mapping_template, read_census_profile_control_table, inspect_census_profile_characteristics, census_profile_template, read_census_profile_mapping, read_category_mapping, write_control_table
   :show-inheritance:

IPF
---

.. automodule:: synthpopcan.ipf
   :members: IPFMargin, IPFResult, expand_records, integerize_weights, fit_ipf, validate_margin_coverage, weighted_totals, calculate_max_abs_error, category_key
   :show-inheritance:

Microdata
---------

.. automodule:: synthpopcan.microdata
   :members: SeedSample, TreeColumnBlockSpec, TreeColumnSuggestionProfile, read_fixture_seed_sample, read_statcan_2016_hierarchical_seed_sample, export_seed_rows, export_training_rows, export_statcan_2016_person_training_rows, export_statcan_2016_household_training_rows, derive_statcan_2016_household_seed_sample, check_statcan_2016_household_seed_columns, suggest_tree_column_blocks, resolve_tree_column_block_pair, build_tree_geography_feasibility_report
   :show-inheritance:

Statistics Canada
-----------------

.. automodule:: synthpopcan.statcan
   :members: CensusProfileDownload, WDSTableSearchResult, wds_download_url, wds_all_cubes_lite_url, wds_metadata_url, search_wds_tables, fetch_wds_metadata, summarize_wds_metadata, classify_wds_ipf_suitability, extract_wds_dimension_names, extract_wds_dimension_previews, fetch_wds_table, fetch_census_profile_2016, normalize_product_id, normalize_language
   :show-inheritance:

Tree Models
-----------

.. automodule:: synthpopcan.tree
   :members: TreeTrainingSample, TreeModelSpec, TreeGenerationRequest, FrequencyOutcome, FrequencyGroup, FrequencyTreeModel, CartTreeModel, read_tree_training_sample, audit_tree_model, train_cart_model, train_frequency_model, generate_tree_rows, generate_linked_population, validate_linked_population, write_tree_model, read_tree_model, read_frequency_model, read_cart_model, write_generated_rows, parse_conditions
   :show-inheritance:

Validation
----------

.. automodule:: synthpopcan.validation
   :members: build_control_validation_report, build_tree_output_validation_report, comparison_dimensions, build_distribution_comparison
   :show-inheritance:
