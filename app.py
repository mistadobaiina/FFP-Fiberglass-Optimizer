import streamlit as st
import pandas as pd
from datetime import datetime

# --- DATABASE INITIALIZATION ---
# In a real scenario, this would load from a CSV file on your drive
if 'job_history' not in st.session_state:
    st.session_state.job_history = []

SCRAP_THRESHOLD = 4.0

st.title("🏊 Hybrid Pool Project Ledger")

# --- SIDEBAR: HISTORY VIEWER ---
with st.sidebar:
    st.header("📜 Job History")
    if st.session_state.job_history:
        history_df = pd.DataFrame(st.session_state.job_history)
        st.dataframe(history_df[['Job Name', 'Date', 'Color', 'Total Ft']])
    else:
        st.write("No jobs recorded yet.")

# --- STEP 1: JOB DETAILS ---
st.header("Step 1: Project Info")
col_a, col_b = st.columns(2)
with col_a:
    job_name = st.text_input("Client Name / Job ID", placeholder="e.g. Miller - Dayton")
with col_b:
    install_date = st.date_input("Installation Date", datetime.now())

# --- STEP 2: MATERIAL & CUTS ---
st.header("Step 2: Material Specs")
c1, c2, c3 = st.columns(3)
with c1:
    color = st.selectbox("Fiberglass Color", ["Blue", "Grey", "White"])
with c2:
    width = st.selectbox("Width (inches)", [43, 48])
with c3:
    batch = st.text_input("Date Code / Batch #", "2026-04-A")

wall_input = st.text_input("Enter Wall Cuts (comma separated)", "12, 12, 10")

# --- STEP 3: OPTIMIZE & SAVE ---
if st.button("Finalize Job & Save to History"):
    cuts = [float(x.strip()) for x in wall_input.split(",")]
    total_ft = sum(cuts)
    
    # Visualization (Simplified for the Ledger)
    st.success(f"Project '{job_name}' Processed.")
    
    # Create the record
    new_record = {
        "Job Name": job_name,
        "Date": install_date.strftime("%Y-%m-%d"),
        "Color": color,
        "Width": width,
        "Batch": batch,
        "Total Ft": total_ft,
        "Cuts": str(cuts)
    }
    
    # Save to Session (and potentially a CSV)
    st.session_state.job_history.append(new_record)
    st.balloons() # Visual confirmation for the crew