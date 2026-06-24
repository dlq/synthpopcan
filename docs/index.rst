SynthPopCan Documentation
=========================

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

If you want to work in a notebook or teaching script, start with
:doc:`Getting Started With the Beginner API <library-getting-started>`. That
page uses ``import synthpopcan as spc`` and keeps advanced training, auditing,
and packaging out of the first path.

Advanced source preparation, microdata adapters, model training, audit reports,
and release-readiness checks are still documented, but they come after the
beginner generation workflows.

.. toctree::
   :maxdepth: 2
   :caption: Overview

   introduction
   field-primer
   installation

.. toctree::
   :maxdepth: 2
   :caption: Beginner Workflows

   web-app
   ipf
   controls
   statcan

.. toctree::
   :maxdepth: 2
   :caption: Advanced Workflows

   microdata
   tree
   validate
   data
   sources

.. toctree::
   :maxdepth: 2
   :caption: Library

   library-getting-started
   library
   api
