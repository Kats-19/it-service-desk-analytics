import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="IT Service Desk Analytics", page_icon="🛠️", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv("data/tickets.csv", parse_dates=["created_at", "resolved_at"])
    # nullable boolean so True/False/<NA> behave correctly
    df["sla_met"] = df["sla_met"].astype("boolean")
    return df

df = load_data()

# ---------------- Sidebar filters ----------------
st.sidebar.title("Filters")

date_min = df["created_at"].min().date()
date_max = df["created_at"].max().date()

date_range = st.sidebar.date_input(
    "Created date range",
    value=(date_min, date_max),
    min_value=date_min,
    max_value=date_max
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = date_min, date_max

priority_filter = st.sidebar.multiselect(
    "Priority",
    sorted(df["priority"].unique()),
    default=sorted(df["priority"].unique())
)
category_filter = st.sidebar.multiselect(
    "Category",
    sorted(df["category"].unique()),
    default=sorted(df["category"].unique())
)
dept_filter = st.sidebar.multiselect(
    "Department",
    sorted(df["department"].unique()),
    default=sorted(df["department"].unique())
)

mask = (
    (df["created_at"].dt.date >= start_date) &
    (df["created_at"].dt.date <= end_date) &
    (df["priority"].isin(priority_filter)) &
    (df["category"].isin(category_filter)) &
    (df["department"].isin(dept_filter))
)
f = df.loc[mask].copy()

resolved_df = f[f["status"] == "Resolved"].copy()
open_df = f[f["status"] == "Open"].copy()

# ---------------- KPIs ----------------
total = len(f)
resolved = len(resolved_df)
open_tickets = len(open_df)

sla_rate = resolved_df["sla_met"].mean() if resolved > 0 else pd.NA
med_res = resolved_df["resolution_hours"].median() if resolved > 0 else pd.NA

# “Wow metric” 1: backlog age
now = pd.Timestamp.now()
if open_tickets > 0:
    open_df["hours_open"] = (now - open_df["created_at"]).dt.total_seconds() / 3600
    median_backlog_hours = open_df["hours_open"].median()
else:
    median_backlog_hours = pd.NA

# “Wow metric” 2: breach count
if resolved > 0:
    # breach means SLA not met (False); <NA> ignored naturally
    resolved_df["breach"] = resolved_df["sla_met"].astype("boolean").eq(False)
    breach_count = int(resolved_df["breach"].sum())
else:
    breach_count = 0

# ---------------- Header ----------------
st.title("🛠️ IT Service Desk Analytics & Optimization")
st.caption("Synthetic IT ticket dataset → KPIs, bottlenecks, SLA performance, and actionable recommendations.")

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total tickets", f"{total:,}")
k2.metric("Resolved", f"{resolved:,}")
k3.metric("Open", f"{open_tickets:,}")
k4.metric("SLA met rate", "—" if pd.isna(sla_rate) else f"{sla_rate*100:.1f}%")
k5.metric("Median resolution (hrs)", "—" if pd.isna(med_res) else f"{med_res:.1f}")
k6.metric("Median backlog age (hrs)", "—" if pd.isna(median_backlog_hours) else f"{median_backlog_hours:.1f}")

st.divider()

# ---------------- Tabs ----------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview",
    "SLA & Priority",
    "Categories & Departments",
    "Assignees",
    "Recommendations",
    "Data"
])

# ===================== Overview =====================
with tab1:
    c1, c2 = st.columns([1.3, 1.0])

    with c1:
        vol = f.groupby(pd.Grouper(key="created_at", freq="W")).size().reset_index(name="tickets")
        fig = px.line(vol, x="created_at", y="tickets", markers=True, title="Ticket Volume (Weekly)")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Quick summary")
        if resolved == 0:
            st.info("No resolved tickets in the selected filters yet. Try expanding the date range or filters.")
        else:
            st.write(f"• **SLA breaches:** {breach_count} tickets")
            st.write(f"• **Most common category:** {f['category'].value_counts().idxmax()}")
            st.write(f"• **Most common priority:** {f['priority'].value_counts().idxmax()}")
            if open_tickets > 0:
                st.write(f"• **Backlog median age:** {median_backlog_hours:.1f} hours")

    if open_tickets > 0:
        st.subheader("Backlog age (Open tickets)")
        backlog = open_df.copy()
        backlog["age_bucket"] = pd.cut(
            backlog["hours_open"],
            bins=[0, 4, 12, 24, 48, 120, float("inf")],
            labels=["0–4h", "4–12h", "12–24h", "1–2d", "2–5d", "5d+"]
        )
        bucket_counts = backlog["age_bucket"].value_counts().sort_index().reset_index()
        bucket_counts.columns = ["age_bucket", "tickets"]
        fig = px.bar(bucket_counts, x="age_bucket", y="tickets", title="Open Tickets by Age Bucket")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No open tickets in the selected filters (great!).")

# ===================== SLA & Priority =====================
with tab2:
    c1, c2 = st.columns(2)

    with c1:
        if resolved > 0:
            sla_by_p = resolved_df.groupby("priority")["sla_met"].mean().reset_index()
            fig = px.bar(sla_by_p, x="priority", y="sla_met", title="SLA Met Rate by Priority", text_auto=".1%")
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No resolved tickets available for SLA analysis.")

    with c2:
        if resolved > 0:
            breaches_by_cat = resolved_df.groupby("category")["breach"].mean().reset_index().sort_values("breach", ascending=False)
            fig = px.bar(breaches_by_cat, x="category", y="breach", title="SLA Breach Rate by Category", text_auto=".1%")
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No resolved tickets available for breach analysis.")

# ===================== Categories & Departments =====================
with tab3:
    c3, c4 = st.columns(2)

    with c3:
        cat = f["category"].value_counts().reset_index()
        cat.columns = ["category", "tickets"]
        fig = px.bar(cat, x="category", y="tickets", title="Tickets by Category")
        st.plotly_chart(fig, use_container_width=True)

    with c4:
        if resolved > 0:
            dep = resolved_df.groupby("department")["resolution_hours"].median().reset_index()
            fig = px.bar(dep, x="department", y="resolution_hours", title="Median Resolution Time by Department (hrs)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No resolved tickets available for department resolution chart.")

# ===================== Assignees =====================
with tab4:
    st.subheader("Assignee workload & performance (for process improvement, not blame)")

    if resolved > 0:
        ass = resolved_df.groupby("assignee").agg(
            tickets=("ticket_id", "count"),
            median_resolution=("resolution_hours", "median"),
            sla_met_rate=("sla_met", "mean")
        ).reset_index().sort_values(["tickets"], ascending=False)

        st.dataframe(ass, use_container_width=True)

        fig = px.scatter(
            ass,
            x="tickets",
            y="median_resolution",
            size="tickets",
            hover_name="assignee",
            title="Workload vs Median Resolution Time"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.caption("Tip: if one person has high tickets + high median time, that can indicate overload, hard ticket types, or missing documentation.")
    else:
        st.info("No resolved tickets available for assignee analysis.")

# ===================== Recommendations =====================
with tab5:
    st.subheader("🔍 Bottlenecks & Recommendations")

    if resolved > 0:
        breach = resolved_df.groupby("category")["breach"].mean().reset_index().sort_values("breach", ascending=False)
        worst_cat = breach.iloc[0]["category"]
        worst_breach = breach.iloc[0]["breach"]

        st.write("**Top issue category (highest SLA breach rate):**", f"{worst_cat} ({worst_breach*100:.1f}% breached)")

        st.write("**Suggested actions (practical + realistic):**")
        st.markdown(
            f"""
- Create a short **runbook** for **{worst_cat}** tickets (common causes + standard fixes).
- Add a **triage checklist** so P1/P2 tickets get the right category and assignee immediately.
- Review recurring **{worst_cat}** issues weekly; convert fixes into a knowledge-base article.
- Track improvements: target **+5–10%** SLA compliance over the next month after changes.
"""
        )

        st.write("**Where to focus first:**")
        top_prio = resolved_df.groupby("priority")["breach"].mean().reset_index().sort_values("breach", ascending=False).head(1)
        st.write(f"• Priority with the most breaches: **{top_prio.iloc[0]['priority']}**")

        st.write("**Breach rate table:**")
        st.dataframe(breach, use_container_width=True)

    else:
        st.info("No resolved tickets in the selected range — broaden the date range or filters.")

# ===================== Data =====================
with tab6:
    st.subheader("📄 Raw Data (Filtered)")
    st.dataframe(f.sort_values("created_at", ascending=False), use_container_width=True)
