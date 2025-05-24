import streamlit as st
import pandas as pd
from collections import defaultdict, Counter

st.set_page_config(page_title="Task Allocator", layout="wide")
st.title("Task Allocator (Even Zone Distribution After FZ/DY)")

st.markdown("Upload your task and team files below.")

task_file = st.file_uploader("Upload tasks.csv", type="csv")
team_file = st.file_uploader("Upload team.csv", type="csv")

if task_file and team_file:
    tasks_df = pd.read_csv(task_file)
    team_df = pd.read_csv(team_file)

    tasks_df.columns = tasks_df.columns.str.strip().str.lower()
    team_df.columns = team_df.columns.str.strip().str.lower()

    required_task_cols = {"id", "time", "priority", "difficulty", "zone"}
    required_team_cols = {"name", "speed"}
    if not required_task_cols.issubset(tasks_df.columns) or not required_team_cols.issubset(team_df.columns):
        st.error("Missing required columns in one of the files. Please check headers.")
    else:
        def priority_key(row):
            priority = str(row.get('priority', '')).strip().lower()
            if priority == 'fz':
                return (0, row.get('zone', ''), -row.get('difficulty', 0))
            elif priority == 'dy':
                return (1, row.get('zone', ''), -row.get('difficulty', 0))
            else:
                priority_rank = {"high": 2, "medium": 3, "low": 4}
                return (priority_rank.get(priority, 5), row.get('zone', ''), -row.get('difficulty', 0))

        tasks_df["sort_key"] = tasks_df.apply(priority_key, axis=1)
        tasks_sorted = tasks_df.sort_values("sort_key").drop(columns="sort_key").to_dict("records")

        team = team_df.to_dict("records")
        for member in team:
            member["assigned"] = []
            member["used_time"] = 0
            member["locked_zone"] = None

        zone_assignments = Counter()
        zone_load = Counter()

        # Determine unique zones from non-FZ/DY tasks
        non_fz_dy_zones = set()
        for task in tasks_sorted:
            pr = str(task.get("priority", "")).strip().lower()
            if pr not in ["fz", "dy"]:
                non_fz_dy_zones.add(task.get("zone", ""))

        non_fz_dy_zones = sorted(non_fz_dy_zones)
        zone_cycle = iter(non_fz_dy_zones)

        for task in tasks_sorted:
            best_fit = None
            min_used_time = float("inf")
            task_id = task.get("id")
            task_time = task.get("time", 0)
            task_zone = task.get("zone", "")
            task_difficulty = task.get("difficulty", 0)
            task_priority = str(task.get("priority", "")).strip().lower()

            for member in team:
                speed = member.get("speed", 1.0)
                adjusted_time = task_time / speed if speed else 0
                if member["used_time"] + adjusted_time <= 300:
                    if task_priority not in ["fz", "dy"]:
                        if not member["locked_zone"]:
                            # Evenly assign members to zones using cycling
                            try:
                                next_zone = next(zone_cycle)
                            except StopIteration:
                                zone_cycle = iter(non_fz_dy_zones)
                                next_zone = next(zone_cycle)
                            member["locked_zone"] = next_zone

                        if member["locked_zone"] != task_zone:
                            continue

                    if member["used_time"] < min_used_time:
                        best_fit = member
                        min_used_time = member["used_time"]

            if best_fit:
                adjusted_time = task_time / best_fit["speed"] if best_fit["speed"] else 0
                best_fit["assigned"].append({
                    "task_id": task_id,
                    "base_time": task_time,
                    "adjusted_time": round(adjusted_time, 1),
                    "priority": task.get("priority", ""),
                    "difficulty": task_difficulty,
                    "zone": task_zone
                })
                best_fit["used_time"] += adjusted_time
                if task_priority not in ["fz", "dy"] and not best_fit["locked_zone"]:
                    best_fit["locked_zone"] = task_zone

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
