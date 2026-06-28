SynthPopCan Documentation
=========================

.. image:: ../assets/branding/logo/synthpopcan-logo-512.png
   :alt: SynthPopCan logo
   :width: 220px
   :align: center

SynthPopCan is early-stage tooling for Canadian synthetic population work:
control tables, iterative proportional fitting, Statistics Canada source
inspection, census microdata adapters, linked household/person tree models, and
validation reports.

Start By Task
-------------

Most new users should start with one of two generation workflows:

**IPF from margin tables**
   Use this when you have seed rows and public control totals, or when you want
   to find a Statistics Canada WDS table and turn it into IPF inputs. The
   friendliest surface is the local :doc:`web app <web-app>`. For scripts and
   methods sections, use :doc:`Statistics Canada Sources <statcan>`,
   :doc:`Controls <controls>`, and :doc:`IPF <ipf>`.

**Generate from existing model**
   Use this when you have a prepared household/person model package and want to
   generate linked synthetic households and people. Start with the
   :doc:`web app <web-app>` for a guided local run, or use
   :doc:`Tree Models <tree>` when you need command-line details.

**Assign linked output to small areas**
   Use this after generating candidate household/person rows when you also have
   small-area Census Profile controls. Start with
   :doc:`Small-Area Linked Synthesis <small-area>` for the current
   household-first workflow.

If you want to work in a notebook or teaching script, start with
:doc:`Getting Started With the Beginner API <library-getting-started>`. That
page uses ``import synthpopcan as spc`` and keeps advanced training, auditing,
and packaging out of the first path.

If you prefer the command line but want the same beginner lane as the web app,
run:

.. code-block:: bash

   synthpopcan guide ipf
   synthpopcan guide model

Advanced source preparation, microdata adapters, model training, audit reports,
and release-readiness checks are still documented, but they come after the
beginner generation workflows.

.. toctree::
   :maxdepth: 2
   :caption: Overview

   introduction
   acknowledgments
   field-primer
   installation

.. toctree::
   :maxdepth: 2
   :caption: Beginner Workflows

   web-app
   ipf
   controls
   statcan
   tree-generate
   small-area
   validate

.. toctree::
   :maxdepth: 2
   :caption: Advanced Workflows

   microdata
   tree
   data

.. toctree::
   :maxdepth: 2
   :caption: Library

   library-getting-started
   library
   api

