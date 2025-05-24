import streamlit as st
import pandas as pd
import time
from collections import Counter, defaultdict

st.set_page_config(page_title="Task Allocator + Tracker", layout="wide")
st.title("Task Allocator and Team Tracker")

# Page selector
view_mode = st.radio("Select View", ["Lead View", "Team Member View"])

if "allocation_data" not in st.session_state:
    st.session_state.allocation_data = None
if "task_state" not in st.session_state:
    st.session_state.task_state = {}

if view_mode == "Lead View":
    st.header("Lead View: Allocate Tasks")

    task_file = st.file_uploader("Upload tasks.csv", type="csv")
    team_file = st.file_uploader("Upload team.csv", type="csv")

    if task_file and team_file:
        tasks_df = pd.read_csv(task_file)
        team_df = pd.read_csv(team_file)

        tasks_df.columns = tasks_df.columns.str.strip().str.lower()
        team_df.columns = team_df.columns.str.strip().str.lower()

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
        zone_remaining_tasks = defaultdict(int)
        for task in tasks_sorted:
            pr = str(task["priority"]).lower()
            if pr not in ["fz", "dy"]:
                zone_remaining_tasks[task["zone"]] += 1

        non_fz_dy_zones = sorted(zone_remaining_tasks)
        zone_cycle = iter(non_fz_dy_zones)
        unassigned_tasks = []

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
                            try:
                                next_zone = next(zone_cycle)
                            except StopIteration:
                                zone_cycle = iter(non_fz_dy_zones)
                                next_zone = next(zone_cycle)
                            member["locked_zone"] = next_zone
                        if member["locked_zone"] != task_zone:
                            if zone_remaining_tasks[member["locked_zone"]] > 0:
                                continue
                            else:
                                member["locked_zone"] = task_zone
                        if len(member["assigned"]) == 0 and speed < 1.0 and task_difficulty >= 4:
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
                if task_priority not in ["fz", "dy"]:
                    zone_remaining_tasks[task_zone] -= 1
            else:
                unassigned_tasks.append(task)

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
        st.session_state.allocation_data = result_df

        st.success("Tasks allocated and saved for team view.")
        st.dataframe(result_df)

        if unassigned_tasks:
            st.markdown("### Unassigned Tasks")
            st.dataframe(pd.DataFrame(unassigned_tasks)[["id", "time", "priority", "difficulty", "zone"]])

elif view_mode == "Team Member View":
    st.header("Team Member View")

    if st.session_state.allocation_data is None:
        st.warning("No allocation data available. Please run the Lead View first.")
    else:
        df = st.session_state.allocation_data
        df.columns = df.columns.str.strip().str.lower()
        team_members = df["Team Member"].unique().tolist()
        selected_member = st.selectbox("Select your name", team_members)

        member_tasks = df[df["Team Member"] == selected_member].reset_index(drop=True)
        total_tasks = len(member_tasks)
        completed = 0

        st.markdown(f"### Layouts Assigned to {selected_member}")

        for idx, row in member_tasks.iterrows():
            task_id = row["task id"]
            adjusted_time = row["adjusted time (mins)"]
            zone = row["zone"]

            if task_id not in st.session_state.task_state:
                st.session_state.task_state[task_id] = {
                    "started": False,
                    "start_time": None,
                    "completed": False,
                    "complete_time": None,
                    "adjusted_time": adjusted_time
                }

            task = st.session_state.task_state[task_id]

            with st.expander(f"{idx+1}. {task_id} ({zone})"):
                st.write(f"Estimated Time: {adjusted_time} mins")

                if idx == 0 or all(st.session_state.task_state[member_tasks.loc[i, 'task id']]['completed'] for i in range(idx)):
                    if not task["started"]:
                        if st.button(f"Start {task_id}", key=f"start_{task_id}"):
                            task["started"] = True
                            task["start_time"] = time.time()

                    if task["started"] and not task["completed"]:
                        elapsed = (time.time() - task["start_time"]) / 60
                        delta = round(elapsed - adjusted_time, 1)
                        status = "Ahead" if delta < 0 else "Behind"
                        st.write(f"Elapsed: {round(elapsed,1)} mins")
                        st.write(f"Status: {status} ({abs(delta)} mins {'early' if delta < 0 else 'late'})")
                        if st.button(f"Complete {task_id}", key=f"complete_{task_id}"):
                            task["completed"] = True
                            task["complete_time"] = time.time()

                    if task["completed"]:
                        st.success("Completed")
                        completed += 1
                else:
                    st.warning("This layout is locked until the previous one is complete.")

        progress = int((completed / total_tasks) * 100)
        st.progress(progress / 100)
        st.markdown(f"**Progress: {completed} of {total_tasks} tasks complete ({progress}%)**")

