SynthPopCan Documentation
=========================

SynthPopCan is early-stage tooling for Canadian synthetic population work:
control tables, iterative proportional fitting, Statistics Canada source
inspection, census microdata adapters, linked household/person tree models, and
validation reports.

Most SynthPopCan workflows have the same basic shape. We begin by **inspecting
sources** and deciding which categories, geographies, and constraints are
relevant to the research question. We then **prepare inputs** such as controls,
seed rows, or model packages; **generate outputs** such as weights or linked
household/person rows; **validate the result** against controls and linkage
rules; and **keep the evidence** with the output. The final CSV is only part of
the work: the source notes, category mappings, commands, random seeds, and
validation reports are what make the generated population interpretable.

Start By Task
-------------

If we are new to SynthPopCan, follow these pages in order:

#. Read the :doc:`Introduction <introduction>` to understand what synthetic
   populations are and what SynthPopCan can and cannot claim.
#. Use :doc:`Installation <installation>` to install the package and run a
   small fictional smoke test.
#. Continue to :doc:`Getting Started <getting-started>` to choose a workflow
   and move into the **web app**, **command-line tools**, or **notebook API**.

If SynthPopCan is already installed, we can go directly to
:doc:`Getting Started <getting-started>`.

Most new readers should start with one of these generation workflows:

**IPF from margin tables**
   Use this when we have seed rows and public control totals, or when we want
   to find a Statistics Canada WDS table and turn it into IPF inputs. The
   friendliest surface is the local :doc:`web app <web-app>`. For scripts and
   methods sections, use :doc:`Statistics Canada Sources <statcan>`,
   :doc:`Controls <controls>`, and :doc:`IPF <ipf>`.

**Generate from existing model**
   Use this when we have a prepared household/person model package and want to
   generate linked synthetic households and people. Start with the
   :doc:`web app <web-app>` for a guided local run, or use
   :doc:`Generate From a Model Package <tree-generate>` when we need
   command-line details. :doc:`Tree Models <tree>` is the advanced path for
   training, auditing, and packaging a new model.

**Assign linked output to small areas**
   Use this after generating candidate household/person rows when we also have
   small-area Census Profile controls. Start with
   :doc:`Small-Area Linked Synthesis <small-area>` for the current
   household-first workflow.

If we want to work in a notebook or teaching script, start with
:doc:`Getting Started With the Beginner API <library-getting-started>`. That
page uses ``import synthpopcan as spc`` and keeps **advanced training**,
**auditing**, and **packaging** out of the first path.

If we prefer the command line but want the same beginner lane as the web app,
start with :doc:`Command-Line Getting Started <command-line>`. Its built-in
workflow guides can also remind us of the next command:

.. code-block:: bash

   synthpopcan guide ipf
   synthpopcan guide model
   synthpopcan guide small-area

Advanced source preparation, microdata adapters, model training, audit reports,
and release-readiness checks are still documented, but they come after the
beginner generation workflows.

.. toctree::
   :maxdepth: 2
   :caption: Overview

   introduction
   installation
   getting-started
   field-primer
   glossary
   correctness
   acknowledgments

.. toctree::
   :maxdepth: 2
   :caption: Command Line

   command-line
   data
   statcan
   controls
   ipf
   tree-generate
   small-area
   validate
   microdata
   tree
   web-app

.. toctree::
   :maxdepth: 2
   :caption: Library

   library-getting-started
   library
   api
