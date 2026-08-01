# Measured Trust — Deck Outline

## Audience and rhetoric

| Choice | Commitment |
|---|---|
| Source | Verified pipeline outputs, scorecards, tests, architecture notes, dashboard, reports, and privacy checks in this repository |
| Audience | External non-academic: policy teams, media, data leaders, technical hiring teams, and industry practitioners |
| Rhetoric | 30% logos, 25% ethos, 45% pathos |
| Language | Minimal jargon; define Splink as probabilistic entity resolution, not deep learning |
| Figure language | Python |
| Format | Beamer PDF, approximately 14 slides |
| Closing sentence | “A trustworthy pipeline does not merely move data—it measures what survives the journey.” |

The spoken story leads. Technical detail arrives only after the audience sees
the administrative problem, the consequences, and the evidence. The movement
is narrative → application → picture → code → technical proof.

## Theme — Evidence Ledger

The deck resembles a calm public-service operations ledger: warm paper fields,
dark ink, and precise evidence marks. Signal Teal traces the live data path.
Evidence Amber marks the held-out answer key. Resolver Violet marks
probabilistic linkage. Audit Red appears only for failures or limitations.

Frame titles use one teal left rule. Section dividers use a full-bleed Midnight
Ink field. Cards resemble ledger entries rather than app widgets. Every slide
has one assertion, large type, and generous white space.

| Role | Color | Hex |
|---|---|---|
| Live pipeline | Signal Teal | `#0F766E` |
| Held-out truth | Evidence Amber | `#D97706` |
| Probabilistic linkage | Resolver Violet | `#6D28D9` |
| Main text / dark field | Midnight Ink | `#0F172A` |
| Secondary text | Slate | `#475569` |
| Main background | Warm Paper | `#FCFAF5` |
| Secondary background | Mist | `#E7EEF0` |
| Failure / warning | Audit Red | `#B42318` |
| Verified result | Verified Green | `#15803D` |
| Supporting chart accent | Civic Blue | `#1D4ED8` |

## The arc

### Act I — Tension: bad records become bad decisions

1. **Measured Trust: a data pipeline that grades itself**
   Cover. Present school-feeding records as the case study, then state the
   general problem: independently designed tables that describe the same
   entities without stable shared keys. All records are synthetic and inspired
   by the shape—not the contents—of an SBFP evaluation workflow.

2. **One person can become three records before anyone sees a dashboard**
   Open on one fictional person represented by reordered names, a shifted
   birth date, and conflicting sex entries across disconnected systems. No
   architecture yet.

3. **A polished dashboard can make broken joins look authoritative**
   Show the consequence chain: form disagreement → missed or false match →
   distorted operational totals → weak decisions.

4. **The platform creates a hidden answer key so trust can be measured**
   Reveal the central idea: synthetic truth records every planted defect and
   true child pair, while the live pipeline is barred from reading it.

### Act II — Investigation: trust is built as a sequence of gates

5. **A proper pipeline turns disconnected tables into one auditable path**
   Picture the full bronze → silver → DQA/linkage → gold flow. Each gate has a
   plain-language job: preserve, standardize, challenge, reconcile, serve. The
   thirteen-file demonstration remains visible as evidence, not as the limit of
   the architecture.

6. **Quality assurance catches 1,433 of 1,579 planted defects**
   Show DQA sensitivity by rule and retain the 146 missed defects in view.
   Explain that quality assurance produces evidence and review work—not magic.

7. **Every issue can be traced back to one file and one source row**
   Follow a synthetic issue through its stable record ID. Pair lineage with the
   privacy boundary: names and LRNs stop before gold products and exports.

8. **Exact rules recover only 63.2% when identity fields disagree**
   Show why deterministic matching fails: 45% of endline names change, 15% of
   birth dates disagree, 8% of sexes disagree, and 35% of rows carry missing or
   malformed LRNs.

9. **Probabilistic linkage combines weak clues that exact rules discard**
   Use a picture of three imperfect signals—similar name, nearby birth date,
   supporting sex value—converging on one match probability. Introduce Splink
   as a Fellegi–Sunter probabilistic model, not a deep-learning model.

10. **One model is trained, saved, and reloaded for inference**
    Show the real execution boundary: full population → global training → saved
    model JSON → fresh linker → predictions across groups. The complete runnable
    example lives in a standalone Python script.

11. **Trained Splink raises true links from 556 to 812**
    Compare the exact-rule benchmark with the trained Splink resolver at the
    benchmark-selected threshold.
    Highlight the production result: 812 true links, no false accepted links,
    92.3% recall, and 96.0% F1.

12. **Even global Splink misses 7 of 26 cross-group moves**
    State the strongest objections: synthetic data, local infrastructure, a
    benchmark-tuned threshold, seven unresolved cross-group moves, and no claim
    of program impact.
    Pair every limitation with the engineering decision it exposes.

### Act III — Resolution: evidence becomes operational value

13. **The same trust pattern applies wherever relational systems were never designed to meet**
    Connect the engineering to customer records, patient registries, beneficiary
    lists, workforce systems, survey waves, and the school-feeding case study.
    The reusable pattern is ingestion + QA + entity resolution + lineage + safe
    serving. End the evidence ledger with 407 tests, 27 dbt tests, 21 DQA rules,
    eight Dagster assets, six app views, and a privacy scan.

14. **A trustworthy pipeline does not merely move data—it measures what survives the journey**
    Full-bleed closing slide. No “Questions?” and no competing message.

## Figures and tables — code first

Every chart will be generated before the deck references it. Scripts will load
only synthetic truth and privacy-safe outputs from the fixed-seed tiny profile.

| Evidence asset | Message | Standalone Python source | Output |
|---|---|---|---|
| Identity disagreement portrait | One person can look different across systems | `scripts/generate_identity_variation.py` | `figures/identity_variation.pdf` |
| Trust-gate pipeline | Quality is accumulated, not appended at the end | `scripts/generate_trust_pipeline.py` | `figures/trust_pipeline.pdf` |
| DQA detection | Most planted defects are caught; misses remain visible | `scripts/generate_quality_detection.py` | `figures/quality_detection.pdf` |
| Linkage comparison | Probabilistic linkage creates measurable lift | `scripts/generate_linkage_comparison.py` | `figures/linkage_comparison.pdf` |
| Evidence ledger | The marketing claims map to executable proof | `scripts/generate_evidence_ledger.py` | `tables/evidence_ledger.tex` |
| Runnable matching skeleton | Splink comparisons and threshold are inspectable | `scripts/run_linkage_example.py` | Slide 10 code block |

## README alignment

After the deck is approved and compiled, the README will adopt the same arc:
general disconnected-data problem first, trust gates second, probabilistic lift
third, verified evidence fourth, and the school-feeding case study as proof
rather than scope. The README will link the deck PDF and use only metrics
generated by the fixed-seed scorecards.
