# Measured Trust — presenter walkthrough

Audience: external policy, media, and industry readers. Target length: 12–15 minutes. The school-feeding data is always described as a synthetic proof case; the market category is disconnected relational data.

## 1. Measured Trust

Open with the category, not the implementation: many organizations need to connect records that were never designed to connect. The question is not whether rows can be joined; it is whether the resulting identity claims deserve trust.

## 2. One person can become three records

Pause on the fictional person. Let the audience notice that each system looks reasonable by itself. The error appears only when systems must work together.

## 3. When records fail to connect

Translate the technical risk into human and institutional consequences: people disappear, are counted twice, and change the denominator. That can alter service allocation, eligibility, or whether an outcome is visible. A clean interface does not repair a weak identity layer.

## 4. A hidden answer key measures trust

Explain the synthetic generator briefly. It deliberately perturbs spelling, name order, dates, sex codes, and identifiers. The linkage pipeline cannot read the answer key; evaluation alone can.

## 5. Evidence gates

Walk left to right. Every stage leaves something inspectable: raw provenance, standardized fields, issue records, linkage decisions, and serving products. This is the reusable architecture.

## 6. Quality assurance performance

Lead with 90.75%, then name both sides of the ledger: 1,433 defects found, 146 missed, and 445 extra flags requiring review. Avoid calling the last number an error rate; it is a workload and precision signal.

## 7. Chain of custody

The differentiator is not merely “we validate data.” Every issue is traceable to a source, rule, field, run, severity, and resolution path. Mention that public outputs are aggregated.

## 8. The unresolved relationships

Exact rules made no false links in this run, but left 324 known relationships unresolved. Define recall plainly as the share of known relationships recovered; the missing third is why precision cannot be the only performance claim.

## 9. What Splink contributes

Call Splink probabilistic entity resolution using the Fellegi–Sunter model. Do not call it deep learning. Its value is learning the weight of exact and fuzzy evidence together when no single field is reliable.

## 10. Inspectable configuration

Keep this short. One global model trains on the full baseline/endline population, is persisted to JSON, and is loaded by a fresh linker before prediction. This separation proves that inference uses learned parameters rather than an in-memory shortcut. The repository includes the runnable example.

## 11. Links restored

Return explicitly to Samira and the person-level consequence. Trained Splink accepted 256 more true relationships overall than exact rules while preserving 100% measured precision in the fixed synthetic run. Recall rose from 63.2% to 92.3%.

## 12. Skeptic’s slide

Spend time here. Synthetic performance does not estimate production prevalence. Global candidate generation raised cross-group transfer recall from 26.9% to 73.1%, but seven of 26 known moves remain unresolved. Production requires monitoring, review, and threshold governance.

## 13. Reusable market category

Show that the nouns change—customer, patient, beneficiary, worker, respondent, learner—but the failure pattern remains: related records, incompatible identifiers, and decisions that depend on joining them.

## 14. Evidence ledger

This is the ethos slide. The repository backs the story with automated tests, warehouse tests, quality rules, an orchestrated asset graph, decision views, and a privacy boundary.

## 15. Close

Return to the thesis and to the fictional person: whether someone remains visible and counted once. The product is not movement of data; it is a measured account of what was preserved, what was repaired, what remains uncertain, and what deserves review.
