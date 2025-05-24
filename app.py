
import streamlit as st
import pandas as pd
from collections import Counter

st.set_page_config(page_title="Task Allocator", layout="wide")
st.title("Task Allocator with Zone Locking and Balanced Distribution")

st.markdown("Upload your task and team files below.")

task_file = st.file_uploader("Upload tasks.csv", type="csv")
team_file = st.file_uploader("Upload team.csv", type="csv")

if task_file and team_file:
    tasks_df = pd.read_csv(task_file)
    team_df = pd.read_csv(team_file)

    def priority_key(row):
        if row['priority'].lower() == 'fz':
            return (0, row['zone'], -row['difficulty'])
        elif row['priority'].lower() == 'dy':
            return (1, row['zone'], -row['difficulty'])
        else:
            priority_rank = {"High": 2, "Medium": 3, "Low": 4}
            return (priority_rank.get(row['priority'], 5), row['zone'], -row['difficulty'])

    tasks_sorted = tasks_df.copy()
    tasks_sorted["sort_key"] = tasks_sorted.apply(priority_key, axis=1)
    tasks_sorted = tasks_sorted.sort_values("sort_key").drop(columns="sort_key").to_dict("records")

    team = team_df.to_dict("records")
    for member in team:
        member["assigned"] = []
        member["used_time"] = 0
        member["locked_zone"] = None

    zone_assignments = Counter()

    for task in tasks_sorted:
        best_fit = None
        min_used_time = float("inf")

        for member in team:
            adjusted_time = task["time"] / member["speed"]
            if member["used_time"] + adjusted_time <= 300:
                priority_type = task["priority"].lower()

                if priority_type not in ["fz", "dy"]:
                    if not member["locked_zone"]:
                        # Assign to the least populated zone
                        least_assigned_zone = min(zone_assignments, key=zone_assignments.get, default=task["zone"])
                        member["locked_zone"] = least_assigned_zone
                        zone_assignments[least_assigned_zone] += 1
                    if member["locked_zone"] != task["zone"]:
                        continue

                if member["used_time"] < min_used_time:
                    best_fit = member
                    min_used_time = member["used_time"]

        if best_fit:
            adjusted_time = task["time"] / best_fit["speed"]
            best_fit["assigned"].append({
                "task_id": task["id"],
                "base_time": task["time"],
                "adjusted_time": round(adjusted_time, 1),
                "priority": task["priority"],
                "difficulty": task["difficulty"],
                "zone": task["zone"]
            })
            best_fit["used_time"] += adjusted_time
            if task["priority"].lower() not in ["fz", "dy"] and not best_fit["locked_zone"]:
                best_fit["locked_zone"] = task["zone"]
                zone_assignments[task["zone"]] += 1

    allocation_preview = []
    for member in team:
        for task in member["assigned"]:
            allocation_preview.append({
                "Team Member": member["name"],
                "Task ID": task["task_id"],
                "Base Time (mins)": task["base_time"],
                "Adjusted Time (mins)": task["adjusted_time"],
                "Priority": task["priority"],
                "Difficulty": task["difficulty"],
                "Zone": task["zone"],
                "Total Time Used (mins)": round(member["used_time"], 1)
            })

    result_df = pd.DataFrame(allocation_preview)
    st.markdown("### Allocated Tasks")
    st.dataframe(result_df)

    csv = result_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Allocation CSV", csv, "allocation_result.csv", "text/csv")
