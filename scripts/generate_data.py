import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import os

random.seed(7)
np.random.seed(7)

PRIORITIES = ["P1", "P2", "P3", "P4"]
PRIORITY_WEIGHTS = [0.08, 0.18, 0.44, 0.30]  # most are not urgent

CATEGORIES = ["Network", "Hardware", "Software", "Access", "Email", "Security", "Other"]
CATEGORY_WEIGHTS = [0.18, 0.16, 0.26, 0.14, 0.12, 0.08, 0.06]

DEPARTMENTS = ["Sales", "HR", "Finance", "Operations", "Engineering", "Students", "Admin"]
DEPT_WEIGHTS = [0.16, 0.10, 0.10, 0.18, 0.18, 0.20, 0.08]

ASSIGNEES = ["Alex", "Mina", "Jonas", "Sara", "Lea", "Omar", "Noah"]

SLA_HOURS_BY_PRIORITY = {"P1": 4, "P2": 12, "P3": 48, "P4": 120}

def sample_weighted(items, weights, n):
    return list(np.random.choice(items, size=n, p=np.array(weights)/np.sum(weights)))

def generate(n=1200, start_date="2025-09-01", months=5):
    start = pd.to_datetime(start_date)
    end = start + pd.DateOffset(months=months)

    created_at = pd.to_datetime(
        np.random.randint(start.value // 10**9, end.value // 10**9, size=n),
        unit="s"
    )

    created_at = pd.Series(created_at).sort_values().reset_index(drop=True)

    priority = sample_weighted(PRIORITIES, PRIORITY_WEIGHTS, n)
    category = sample_weighted(CATEGORIES, CATEGORY_WEIGHTS, n)
    department = sample_weighted(DEPARTMENTS, DEPT_WEIGHTS, n)

    # Assign assignees with slight imbalance (realistic)
    assignee_weights = np.array([0.18, 0.14, 0.16, 0.12, 0.14, 0.14, 0.12])
    assignee = list(np.random.choice(ASSIGNEES, size=n, p=assignee_weights/assignee_weights.sum()))

    sla_hours = [SLA_HOURS_BY_PRIORITY[p] for p in priority]

    # Resolution time: depends on priority + category; add noise + a few outliers
    base = []
    for p, c in zip(priority, category):
        if p == "P1":
            mu = 2
        elif p == "P2":
            mu = 8
        elif p == "P3":
            mu = 30
        else:
            mu = 72

        # category effects
        if c in ["Access", "Email"]:
            mu *= 0.7
        elif c in ["Network", "Security"]:
            mu *= 1.2
        elif c == "Hardware":
            mu *= 1.1

        base.append(mu)

    resolution_hours = np.maximum(0.2, np.random.lognormal(mean=np.log(np.array(base)), sigma=0.55))
    # Add a few extreme long tickets (waiting for parts, approvals, etc.)
    outlier_idx = np.random.choice(np.arange(n), size=max(8, n//150), replace=False)
    resolution_hours[outlier_idx] *= np.random.uniform(2.5, 6.0, size=len(outlier_idx))

    resolved_at = created_at + pd.to_timedelta(resolution_hours, unit="h")

    # Some tickets still open
    status = np.where(np.random.rand(n) < 0.92, "Resolved", "Open")
    now = pd.Timestamp(datetime.now())
    resolved_at = pd.Series(resolved_at)
    resolved_at[status == "Open"] = pd.NaT

    df = pd.DataFrame({
        "ticket_id": [f"TKT-{100000+i}" for i in range(n)],
        "created_at": created_at,
        "resolved_at": resolved_at,
        "status": status,
        "priority": priority,
        "category": category,
        "department": department,
        "assignee": assignee,
        "sla_hours": sla_hours
    })

    # For resolved tickets, compute metrics
    df["resolution_hours"] = np.where(
        df["status"] == "Resolved",
        (df["resolved_at"] - df["created_at"]).dt.total_seconds() / 3600.0,
        np.nan
    )
    df["sla_met"] = np.where(
        df["status"] == "Resolved",
        df["resolution_hours"] <= df["sla_hours"],
        np.nan
    )

    return df

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    df = generate()
    df.to_csv("data/tickets.csv", index=False)
    print("✅ Generated data/tickets.csv with", len(df), "rows")
