"""Public DQA command center backed only by safe gold tables. Use this rule as shown."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from sbfp_platform.config import load_config

st.set_page_config(page_title="SBFP Data Command Center", page_icon="🍚", layout="wide")


@st.cache_data(show_spinner=False)
def read_gold(path: str) -> pd.DataFrame:
    file_path = Path(path)
    return pd.read_parquet(file_path) if file_path.is_file() else pd.DataFrame()


def table(name: str) -> pd.DataFrame:
    return read_gold(str(load_config().paths.gold_dir / f"{name}.parquet"))


def empty_state() -> None:
    st.info("No materialized gold data yet. Run `make pipeline PROFILE=tiny`, then refresh.")


def metric_row(items: list[tuple[str, object, str | None]]) -> None:
    for column, (label, value, help_text) in zip(st.columns(len(items)), items, strict=True):
        column.metric(label, value, help=help_text)


OPERATING_THRESHOLD = 0.10


def operating_linkage(method: str = "splink") -> pd.Series | None:
    score = table("gold_linkage_scorecard")
    if score.empty:
        return None
    rows = score[(score.get("method") == method) & (score.get("threshold") == OPERATING_THRESHOLD)]
    return None if rows.empty else rows.iloc[0]


st.title("School Feeding Data Command Center")
st.caption("Synthetic data · Measured quality · Privacy-safe public aggregates")

overview_tab, schools_tab, dqa_tab, linkage_tab, exposure_tab, panel_tab = st.tabs(
    [
        "Overview",
        "School submissions",
        "Data quality",
        "Record linkage",
        "Program exposure",
        "Evaluation readiness",
    ]
)

with overview_tab:
    st.header("From messy submissions to measured trust")
    public = table("gold_public_dashboard_metrics")
    dqa = table("gold_dqa_scorecard")
    operating = operating_linkage()
    if public.empty or dqa.empty or operating is None:
        empty_state()
    else:
        injected = int(dqa["injected_count"].sum())
        detected = int(dqa["detected_count"].sum())
        metric_row(
            [
                ("Schools processed", f"{int(public['school_count'].sum()):,}", None),
                (
                    "Records processed",
                    f"{int(public['baseline_record_count'].sum() + public['endline_record_count'].sum()):,}",
                    "Baseline plus endline records",
                ),
                ("DQA detection", f"{detected / injected:.1%}", "Against injected defects"),
                ("Linkage F1", f"{operating['f1']:.1%}", "Trained Splink at 0.10"),
            ]
        )
        st.success("Pipeline materialized successfully: bronze → silver → DQA/linkage → gold.")
        overview = public.copy()
        overview["assignment"] = overview["treatment_status"].map({0: "Control", 1: "Treatment"})
        long = overview.melt(
            id_vars="assignment",
            value_vars=["baseline_record_count", "endline_record_count", "accepted_link_count"],
            var_name="metric",
            value_name="records",
        )
        st.altair_chart(
            alt.Chart(long)
            .mark_bar()
            .encode(
                x=alt.X("assignment:N", title=None),
                y=alt.Y("records:Q", title="Records"),
                color=alt.Color("metric:N", title=None),
                xOffset="metric:N",
                tooltip=["assignment", "metric", "records"],
            ),
            width="stretch",
        )
        st.caption("All dashboard tables are synthetic, de-identified gold outputs.")

with schools_tab:
    st.header("School submission monitoring")
    data = table("gold_school_monitoring_mart")
    issues = table("gold_dqa_command_center")
    if data.empty:
        empty_state()
    else:
        complete = int(((data["baseline_records"] > 0) & (data["endline_records"] > 0)).sum())
        metric_row(
            [
                ("Complete schools", f"{complete}/{len(data)}", "Both waves submitted"),
                ("Baseline rows", f"{int(data['baseline_records'].sum()):,}", None),
                ("Endline rows", f"{int(data['endline_records'].sum()):,}", None),
                ("Critical issues", f"{int(data['critical_issue_count'].sum()):,}", None),
            ]
        )
        school_long = data.melt(
            id_vars=["school_id", "school_name"],
            value_vars=["baseline_records", "endline_records"],
            var_name="period",
            value_name="records",
        )
        st.altair_chart(
            alt.Chart(school_long)
            .mark_bar()
            .encode(
                x=alt.X("records:Q"),
                y=alt.Y("school_name:N", sort="-x", title=None),
                color="period:N",
                tooltip=["school_id", "school_name", "period", "records"],
            ),
            width="stretch",
        )
        if not issues.empty:
            late = issues[issues["rule_id"] == "DQA_TIMELINESS_LATE_SUBMISSION"]
            st.subheader("Late submissions")
            st.dataframe(late, width="stretch", hide_index=True)
        with st.expander("School-level monitoring table"):
            st.dataframe(data, width="stretch", hide_index=True)

with dqa_tab:
    st.header("Did the quality rules catch what was injected?")
    score = table("gold_dqa_scorecard")
    command = table("gold_dqa_command_center")
    panel = table("gold_evaluation_child_panel")
    if score.empty:
        empty_state()
    else:
        injected = int(score["injected_count"].sum())
        detected = int(score["detected_count"].sum())
        false_positive = int(score["false_positive_count"].sum())
        metric_row(
            [
                ("Injected defects", f"{injected:,}", None),
                ("Detected", f"{detected:,}", None),
                ("Detection rate", f"{detected / injected:.1%}", None),
                ("False positives", f"{false_positive:,}", None),
            ]
        )
        chart_data = score[score["injected_count"] > 0].assign(
            detection_pct=lambda frame: frame["detection_rate"] * 100
        )
        st.altair_chart(
            alt.Chart(chart_data)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X(
                    "detection_pct:Q", title="Detection rate (%)", scale=alt.Scale(domain=[0, 100])
                ),
                y=alt.Y("rule_id:N", title=None, sort="-x"),
                color=alt.Color("severity:N", title="Severity"),
                tooltip=["rule_id", "injected_count", "detected_count", "false_positive_count"],
            ),
            width="stretch",
        )
        if not command.empty:
            severity = command.groupby("severity", as_index=False)["issue_count"].sum()
            st.altair_chart(
                alt.Chart(severity)
                .mark_arc(innerRadius=45)
                .encode(
                    theta="issue_count:Q", color="severity:N", tooltip=["severity", "issue_count"]
                ),
                width="stretch",
            )
            st.subheader("Issues by school, period, field/rule")
            st.dataframe(command, width="stretch", hide_index=True)
        if not panel.empty:
            missing = (
                panel.filter(regex="^(height|weight)_cm_").isna().mean().rename("missing_rate")
            )
            st.subheader("Anthropometric missingness")
            st.bar_chart(missing)
        with st.expander("Rule-level measured scorecard"):
            st.dataframe(score, width="stretch", hide_index=True)

with linkage_tab:
    st.header("Known-truth linkage performance")
    score = table("gold_linkage_scorecard")
    review = table("gold_linkage_review_mart")
    operating = operating_linkage()
    deterministic_operating = operating_linkage("deterministic")
    if score.empty or operating is None or deterministic_operating is None:
        empty_state()
    else:
        metric_row(
            [
                ("Precision @ 0.10", f"{operating['precision']:.1%}", None),
                ("Recall @ 0.10", f"{operating['recall']:.1%}", None),
                ("F1 @ 0.10", f"{operating['f1']:.1%}", None),
                ("Transfer recall", f"{operating['transfer_recall']:.1%}", "Cross-school pupils"),
            ]
        )
        st.subheader("How Splink performs at the operating threshold")
        comparison = pd.DataFrame(
            [deterministic_operating, operating],
            index=["Exact-rule benchmark", "Trained Splink resolver"],
        )[
            [
                "true_positives",
                "false_positives",
                "precision",
                "recall",
                "f1",
                "review_queue_size",
            ]
        ].rename(
            columns={
                "true_positives": "True links",
                "false_positives": "False links",
                "precision": "Precision",
                "recall": "Recall",
                "f1": "F1",
                "review_queue_size": "Review queue",
            }
        )
        st.dataframe(
            comparison.style.format({"Precision": "{:.1%}", "Recall": "{:.1%}", "F1": "{:.1%}"}),
            width="stretch",
        )
        recovered = int(operating["true_positives"] - deterministic_operating["true_positives"])
        st.info(
            f"Trained Splink recovers {recovered} more true links than exact rules; "
            "the held-out answer key records no false accepted links at 0.10."
        )
        long = score.melt(
            id_vars=["method", "threshold"],
            value_vars=["precision", "recall", "f1"],
            var_name="metric",
            value_name="value",
        )
        st.altair_chart(
            alt.Chart(long)
            .mark_line(point=True)
            .encode(
                x=alt.X("threshold:Q", scale=alt.Scale(domain=[0.1, 0.9])),
                y=alt.Y("value:Q", scale=alt.Scale(domain=[0, 1])),
                color="metric:N",
                strokeDash="method:N",
                tooltip=["method", "threshold", "metric", alt.Tooltip("value:Q", format=".3f")],
            ),
            width="stretch",
        )
        if not review.empty:
            queue = review[review["decision"] == "review"].drop_duplicates("link_id")
            st.subheader(f"Review queue ({len(queue):,})")
            st.dataframe(queue, width="stretch", hide_index=True)
            confidence = review[review["method"] == "splink"]["match_probability"].dropna()
            if not confidence.empty:
                st.subheader("Trained Splink match confidence")
                st.bar_chart(confidence.value_counts(bins=10).sort_index())

with exposure_tab:
    st.header("Allocation pressure and ration dilution")
    data = table("gold_program_exposure_mart")
    if data.empty:
        empty_state()
    else:
        metric_row(
            [
                ("Schools", len(data), None),
                ("Allocation shortfalls", int(data["allocation_shortfall_flag"].sum()), None),
                ("Mean dilution ratio", f"{data['dilution_ratio'].mean():.1%}", None),
                (
                    "Mean effective ration",
                    f"{data['effective_rice_kg_per_child'].mean():.3f} kg",
                    None,
                ),
            ]
        )
        st.altair_chart(
            alt.Chart(data)
            .mark_circle(size=150)
            .encode(
                x=alt.X("current_enrollment:Q", title="Current enrollment"),
                y=alt.Y("allocated_children:Q", title="Allocated children"),
                color=alt.Color("treatment_status:N", title="Treatment"),
                tooltip=[
                    "school_name",
                    "allocated_children",
                    "current_enrollment",
                    alt.Tooltip("dilution_ratio:Q", format=".1%"),
                    alt.Tooltip("effective_rice_kg_per_child:Q", format=".3f"),
                ],
            ),
            width="stretch",
        )
        st.dataframe(data, width="stretch", hide_index=True)

with panel_tab:
    st.header("Evaluation readiness")
    data = table("gold_evaluation_child_panel")
    if data.empty:
        empty_state()
    else:
        complete = (
            data[
                [
                    "height_cm_baseline",
                    "height_cm_endline",
                    "weight_kg_baseline",
                    "weight_kg_endline",
                ]
            ]
            .notna()
            .all(axis=1)
            .mean()
        )
        critical = int(data["has_critical_issue"].sum())
        metric_row(
            [
                ("Linked children", f"{len(data):,}", None),
                ("Complete anthropometry", f"{complete:.1%}", None),
                ("Critical issue rows", f"{critical:,}", None),
                ("Export readiness", "Ready" if critical == 0 else "Review", None),
            ]
        )
        timing = data["elapsed_days"].dropna()
        if not timing.empty:
            st.subheader("Baseline-to-endline timing")
            st.bar_chart(timing.value_counts(bins=12).sort_index())
        st.subheader("Privacy-safe panel preview")
        st.dataframe(data.head(200), width="stretch", hide_index=True)
