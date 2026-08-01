-- Independent set-based replication of the operating linkage scorecard.
-- Run from the repository root after `make pipeline PROFILE=tiny`.

WITH truth AS (
    SELECT baseline_record_id, endline_record_id, transferred
    FROM read_parquet('data/ground_truth/truth_links.parquet')
),
candidate_pairs AS (
    SELECT * EXCLUDE (pair_rank)
    FROM (
        SELECT
            baseline_record_id,
            endline_record_id,
            COALESCE(match_probability, 1.0) AS match_probability,
            ROW_NUMBER() OVER (
                PARTITION BY baseline_record_id, endline_record_id
                ORDER BY
                    COALESCE(match_probability, 1.0) DESC,
                    match_weight DESC NULLS LAST,
                    candidate_id
            ) AS pair_rank
        FROM read_parquet(
            'data/lakehouse/linkage/silver_linkage_candidates.parquet'
        )
        WHERE method = 'deterministic'
    )
    WHERE pair_rank = 1
),
eligible_exact AS (
    SELECT
        *,
        COUNT(*) OVER (PARTITION BY baseline_record_id) AS baseline_choices,
        COUNT(*) OVER (PARTITION BY endline_record_id) AS endline_choices
    FROM candidate_pairs
    WHERE match_probability >= 0.10
),
exact_accepted AS (
    SELECT baseline_record_id, endline_record_id
    FROM eligible_exact
    WHERE baseline_choices = 1 AND endline_choices = 1
),
splink_accepted AS (
    SELECT baseline_record_id, endline_record_id
    FROM read_parquet(
        'data/lakehouse/linkage/silver_linkage_results.parquet'
    )
    WHERE decision = 'accepted' AND source_method = 'splink'
),
predictions AS (
    SELECT 'deterministic' AS method, * FROM exact_accepted
    UNION ALL
    SELECT 'splink' AS method, * FROM splink_accepted
),
counts AS (
    SELECT
        predictions.method,
        COUNT(*) AS predicted_pairs,
        COUNT(truth.baseline_record_id) AS true_positives,
        COUNT(*) - COUNT(truth.baseline_record_id) AS false_positives,
        (SELECT COUNT(*) FROM truth) - COUNT(truth.baseline_record_id)
            AS false_negatives,
        COUNT(truth.baseline_record_id) FILTER (WHERE truth.transferred)
            AS transfer_true_positives
    FROM predictions
    LEFT JOIN truth USING (baseline_record_id, endline_record_id)
    GROUP BY predictions.method
),
rates AS (
    SELECT
        method,
        predicted_pairs,
        true_positives,
        false_positives,
        false_negatives,
        true_positives::DOUBLE / NULLIF(predicted_pairs, 0) AS precision,
        true_positives::DOUBLE / (SELECT COUNT(*) FROM truth) AS recall,
        transfer_true_positives::DOUBLE
            / (SELECT COUNT(*) FROM truth WHERE transferred) AS transfer_recall
    FROM counts
)
SELECT
    method,
    predicted_pairs,
    true_positives,
    false_positives,
    false_negatives,
    precision,
    recall,
    2.0 * precision * recall / NULLIF(precision + recall, 0) AS f1,
    transfer_recall
FROM rates
ORDER BY method;
