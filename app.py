import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- CONFIGURATION ---
SCRAP_THRESHOLD = 4.0  # Feet

st.set_page_config(page_title="Pool Inventory Optimizer", layout="wide")
st.title("🏗️ Hybrid Pool Inventory & Cut Manager")

# --- SECTION 1: INVENTORY UPLOAD ---
st.header("Step 1: Sync Shop Inventory")
uploaded_file = st.file_uploader("Upload 'current_inventory.csv'", type=["csv"])

# Initialize session state for inventory
if 'inventory' not in st.session_state:
    st.session_state.inventory = pd.DataFrame(columns=["ID", "Width", "Color", "DateCode", "Length"])

if uploaded_file is not None:
    # Load the uploaded CSV into the app's memory
    st.session_state.inventory = pd.read_csv(uploaded_file)
    st.success(f"Loaded {len(st.session_state.inventory)} rolls from CSV.")

# --- SIDEBAR: TEMPLATE GENERATOR ---
with st.sidebar:
    st.header("Admin Tools")
    # Create a dummy template for the user to download
    template = pd.DataFrame({
        "ID": ["R-101", "R-102"],
        "Width": [43, 48],
        "Color": ["Blue", "Grey"],
        "DateCode": ["2026-04-A", "2026-04-B"],
        "Length": [150.0, 150.0]
    })
    csv_template = template.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV Template", data=csv_template, file_name="inventory_template.csv")
    
    st.write("---")
    st.write("### Active Inventory View")
    st.dataframe(st.session_state.inventory)

# --- SECTION 2: PROJECT CUTTING ---
st.header("Step 2: Project Optimization")

if st.session_state.inventory.empty:
    st.warning("Please upload an inventory CSV to begin.")
else:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        p_color = st.selectbox("Select Color", st.session_state.inventory['Color'].unique())
    with col2:
        p_width = st.selectbox("Select Width", st.session_state.inventory['Width'].unique())
    with col3:
        # Filter batches based on color/width
        batches = st.session_state.inventory[
            (st.session_state.inventory['Color'] == p_color) & 
            (st.session_state.inventory['Width'] == p_width)
        ]['DateCode'].unique()
        selected_batch = st.selectbox("Select Date Code", batches)

    wall_input = st.text_input("Enter Wall Lengths (e.g. 12, 12, 10)", "12, 10")

    if st.button("Calculate Cuts"):
        cuts = sorted([float(x.strip()) for x in wall_input.split(",")], reverse=True)
        
        # Get the specific rolls for this batch
        eligible_rolls = st.session_state.inventory[
            (st.session_state.inventory['DateCode'] == selected_batch) & 
            (st.session_state.inventory['Width'] == p_width)
        ].to_dict('records')

        for roll in eligible_rolls:
            st.subheader(f"Using Roll: {roll['ID']}")
            current_len = roll['Length']
            used = []
            
            for cut in cuts[:]:
                if cut <= current_len:
                    used.append(cut)
                    current_len -= cut
                    cuts.remove(cut)
            
            if used:
                # Visualization
                st.write(f"✅ Cut Map: {used}")
                remnant = current_len
                
                # Visual Bar
                cols = st.columns([c for c in used] + [remnant if remnant > 0 else 0.1])
                for i, c in enumerate(used):
                    cols[i].info(f"{c} ft")
                
                if remnant < SCRAP_THRESHOLD:
                    cols[-1].error(f"SCRAP: {remnant} ft")
                else:
                    cols[-1].success(f"REMNANT: {remnant} ft")
