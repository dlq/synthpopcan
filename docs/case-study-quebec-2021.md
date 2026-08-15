# Quebec 2021: a bilingual reproducible case study

This case study generates a small linked household/person population with the
released `quebec-2021-all-fields` model. It gives an English and French account
of the same run so that the commands, evidence, and cautions remain identical
across both versions.

Cette étude de cas produit une petite population liée de ménages et de personnes
à l'aide du modèle publié `quebec-2021-all-fields`. Les versions française et
anglaise décrivent la même exécution; les commandes, les éléments de preuve et
les mises en garde sont donc identiques.

## Reproducibility record / Fiche de reproductibilité

| Item / Élément | Pinned value / Valeur fixée |
| --- | --- |
| Model / Modèle | `quebec-2021-all-fields` |
| Model release / Version du modèle | `v0.6.0` |
| Geography / Géographie | Quebec, province code 24 / Québec, code de province 24 |
| Census vintage / Millésime du recensement | 2021 |
| Source | [Statistics Canada, 2021 Census Hierarchical Public Use Microdata File, version 2 (98M0001X2021002)](https://www150.statcan.gc.ca/n1/en/catalogue/98M0001X2021002) / [Statistique Canada, Fichier hiérarchique de microdonnées à grande diffusion du Recensement de 2021, version 2 (98M0001X2021002)](https://www150.statcan.gc.ca/n1/fr/catalogue/98M0001X2021002) |
| Source licence / Licence de la source | [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence) / [Licence ouverte de Statistique Canada](https://www.statcan.gc.ca/fr/avis/licence-ouverte) |
| Prepared-model policy / Politique du modèle préparé | Accepted [ADR-0014](https://github.com/dlq/synthpopcan/blob/main/adr/0014-separate-prepared-model-and-source-licensing.md): scoped CC BY 4.0 for original rights the author controls, cumulative with the source conditions / ADR-0014 acceptée : CC BY 4.0 limitée aux droits originaux contrôlés par l'auteur, cumulativement avec les conditions de la source |
| Model DOI / DOI du modèle | [10.5281/zenodo.21461615](https://doi.org/10.5281/zenodo.21461615) (concept DOI / DOI conceptuel) |
| Downloaded gzip SHA-256 / SHA-256 du fichier gzip téléchargé | `39787ecc6449dff9ca0e99c4b6bc62d7b0eb7a45607a91f8cdadd70edcb3391f` |
| Uncompressed JSON SHA-256 / SHA-256 du fichier JSON décompressé | `df75b07d25753a6a0e0a2d82a91ad17485f8cb4710fa5df9e3a45b27519aab48` |
| Random seed / Graine aléatoire | `20210921` |
| Requested size / Taille demandée | 1,000 households / 1 000 ménages |
| Output / Sortie | `quebec-2021-case-study/` |

The concept DOI identifies the model record; the release version and both
checksums above pin the exact artifact used here. `models fetch` verifies the
compressed download and the uncompressed package before installing it in the
local cache.

Le DOI conceptuel identifie la fiche du modèle; la version et les deux sommes de
contrôle ci-dessus fixent l'artéfact exact utilisé ici. La commande `models fetch` vérifie le téléchargement compressé et le paquet décompressé avant de
l'installer dans le cache local.

## Commands / Commandes

The first command requires network access once. The remaining commands use the
verified local model cache. Run them from a new working directory with enough
space for the 106 MB uncompressed package and the generated CSV files.

La première commande nécessite un accès réseau une seule fois. Les commandes
suivantes utilisent le cache local vérifié. Exécutez-les dans un nouveau dossier
de travail ayant assez d'espace pour le paquet décompressé de 106 Mo et les
fichiers CSV produits.

```bash
synthpopcan models fetch quebec-2021-all-fields
synthpopcan models show quebec-2021-all-fields --format json \
  > quebec-2021-model-metadata.json
synthpopcan models build inspect quebec-2021-all-fields --format json \
  > quebec-2021-model-inspection.json
synthpopcan models generate quebec-2021-all-fields \
  --households 1000 \
  --out quebec-2021-case-study/ \
  --random-seed 20210921
synthpopcan validate linked quebec-2021-case-study/ --format json \
  > quebec-2021-case-study/validation.json
```

`models show` records catalogue provenance, vintage, DOI, review status, and
known limitations. `models build inspect` reports the package's actual schema,
conditioning structure, columns, and embedded audits. Generation writes
`households.csv`, `persons.csv`, and `manifest.json`; the manifest records the
requested and effective seed. The final command checks household identifiers,
person-to-household links, duplicates, and household-size consistency, then
saves its report as `validation.json`.

`models show` consigne la provenance du catalogue, le millésime, le DOI, l'état
de la révision et les limites connues. `models build inspect` décrit le schéma
réel du paquet, sa structure de conditionnement, ses colonnes et ses audits
intégrés. La production crée `households.csv`, `persons.csv` et `manifest.json`;
le manifeste consigne la graine demandée et la graine réellement utilisée. La
dernière commande vérifie les identifiants des ménages, les liens entre personnes
et ménages, les doublons et la cohérence de la taille des ménages, puis
enregistre son rapport dans `validation.json`.

Re-running with the same installed SynthPopCan version, model checksum, command,
and seed should reproduce the generated rows. Record the SynthPopCan version
with `synthpopcan --version` when citing a real analysis.

Une nouvelle exécution avec la même version installée de SynthPopCan, la même
somme de contrôle du modèle, la même commande et la même graine devrait
reproduire les lignes générées. Pour une analyse réelle, consignez la version de
SynthPopCan avec `synthpopcan --version`.

## English interpretation and limits

This is a provincial, model-based sample of synthetic households and people.
The requested household count is fixed, while the number of people follows the
modelled household-size distribution. The package is trained from the 2021
hierarchical PUMF and is not calibrated to small-area Census controls. Values
retain source codes that require the PUMF metadata for interpretation. Sparse
geographies may use privacy-safe CART models rather than direct conditional
frequencies. Human review is still required before publication or substantive
use.

A passing `validate linked` report establishes only mechanical linkage
consistency:

- The output is **not a simulation** of social processes, behaviour, or change
  over time; it is a generated cross-sectional population artifact.
- It supports **no causal claim**. Associations in generated rows do not
  identify causes or effects.
- It is **not a fitness-for-use claim**. Users must evaluate geography, fields,
  controls, error, and limitations for their own research question.
- It is **not a non-disclosure guarantee or disclosure-risk certification**.
  The package contains no raw PUMF rows or source identifiers and has passed the
  project's screening, but a human disclosure review remains necessary.

Do not present generated rows as real people, real households, confidential
Statistics Canada records, official estimates, or Statistics Canada-endorsed
results. For estimates below the province, continue with the reviewed
{doc}`small-area` workflow and suitable 2021 controls.

## Interprétation et limites en français

Il s'agit d'un échantillon provincial de ménages et de personnes synthétiques,
produit par un modèle. Le nombre de ménages demandé est fixe, tandis que le
nombre de personnes découle de la distribution modélisée de la taille des
ménages. Le paquet est entraîné à partir du FMGD hiérarchique de 2021 et n'est
pas étalonné selon des contrôles du Recensement à petite échelle géographique.
Les valeurs conservent les codes de la source, qui doivent être interprétés à
l'aide des métadonnées du FMGD. Pour certaines géographies peu représentées, le
modèle peut utiliser des arbres CART respectueux de la confidentialité plutôt
que des fréquences conditionnelles directes. Une révision humaine demeure
nécessaire avant toute publication ou utilisation substantielle.

La réussite de `validate linked` établit uniquement la cohérence mécanique des
liens :

- La sortie **n'est pas une simulation** de processus sociaux, de comportements
  ou de changements dans le temps; c'est un artéfact transversal produit par un
  modèle.
- Elle ne justifie **aucune affirmation causale**. Les associations observées
  dans les lignes synthétiques n'identifient ni causes ni effets.
- Elle ne constitue **aucune garantie d'aptitude à l'usage**. Il revient à
  l'utilisateur d'évaluer la géographie, les champs, les contrôles, les erreurs
  et les limites selon sa question de recherche.
- Elle ne constitue **ni une garantie de non-divulgation ni une certification
  du risque de divulgation**. Le paquet ne contient aucune ligne brute du FMGD
  ni aucun identifiant de source et il a réussi les contrôles du projet, mais
  une révision humaine du risque de divulgation demeure nécessaire.

Ne présentez pas les lignes produites comme des personnes ou des ménages réels,
des dossiers confidentiels de Statistique Canada, des estimations officielles ou
des résultats approuvés par Statistique Canada. Pour produire des estimations à
une échelle inférieure à la province, poursuivez avec le flux de travail
{doc}`small-area` révisé et des contrôles de 2021 appropriés.

## What to retain / Éléments à conserver

Keep the commands, `synthpopcan --version`, both package checksums, the DOI,
`manifest.json`, the two generated CSV files, and the JSON validation output
together with the research note. Also record any later calibration, filtering,
recoding, or enrichment.

Conservez les commandes, la sortie de `synthpopcan --version`, les deux sommes
de contrôle du paquet, le DOI, `manifest.json`, les deux fichiers CSV produits
et le résultat JSON de la validation avec la note de recherche. Consignez aussi
tout étalonnage, filtrage, recodage ou enrichissement ultérieur.

The release test suite checks this exact public command sequence for drift, but
does not download the Quebec package. From an installed wheel without network
access, it checks the real Quebec catalogue metadata and runs the analogous
fetch, inspect, generate, and validate path with the bundled fictional model
under its own demo identifier. This verifies packaging and CLI wiring without
misrepresenting synthetic bytes as Statistics Canada-derived. It does not test
the scientific content or checksum of the released Quebec model; the public
fetch still verifies the released checksums above.

La suite de tests de publication vérifie que cette séquence publique de
commandes ne dérive pas, mais elle ne télécharge pas le paquet québécois. À
partir d'un paquet wheel installé et sans accès réseau, elle vérifie les
métadonnées du catalogue québécois réel, puis exécute les étapes analogues de
téléchargement, d'inspection, de génération et de validation avec le modèle
fictif intégré, sous son propre identifiant de démonstration. Elle vérifie ainsi
l'empaquetage et l'interface sans présenter des octets synthétiques comme étant
dérivés de Statistique Canada. Elle ne vérifie ni le contenu scientifique ni la
somme de contrôle du modèle québécois publié; le téléchargement public vérifie
toujours les sommes de contrôle indiquées ci-dessus.
