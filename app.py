import streamlit as st
import pandas as pd

# --- CONFIGURATION ---
SCRAP_THRESHOLD = 4.0 

st.set_page_config(page_title="Pool Shop Optimizer", layout="wide")
st.title("🏗️ Hybrid Pool Shop: Roll & SC Dashboard")

# --- 1. INVENTORY SYNC ---
if 'inventory' not in st.session_state:
    st.session_state.inventory = pd.DataFrame(columns=["ID", "Type", "Width", "Color", "DateCode", "Length"])

with st.sidebar:
    st.header("Admin: Inventory Upload")
    uploaded_file = st.file_uploader("Upload Shop CSV", type=["csv"])
    if uploaded_file:
        st.session_state.inventory = pd.read_csv(uploaded_file)
        st.success("Inventory Updated!")

# --- 2. GLOBAL PROJECT FILTERS ---
if not st.session_state.inventory.empty:
    st.header("Step 1: Set Project Specs")
    f1, f2, f3 = st.columns(3)
    with f1:
        p_color = st.selectbox("Color", st.session_state.inventory['Color'].unique())
    with f2:
        p_width = st.selectbox("Width", st.session_state.inventory['Width'].unique())
    with f3:
        # Filter batches based on color
        batches = st.session_state.inventory[st.session_state.inventory['Color'] == p_color]['DateCode'].unique()
        selected_batch = st.selectbox("Batch / Date Code", batches)

    # --- 3. THE OPTIMIZER ---
    st.divider()
    st.header("Step 2: Calculate Best Roll")
    
    col_input, col_sc = st.columns([2, 1])

    with col_input:
        wall_input = st.text_input("Enter Wall Lengths (e.g. 15, 12, 12)", "12, 12")
        
        if st.button("🚀 Find Best Roll Match"):
            cuts = sorted([float(x.strip()) for x in wall_input.split(",")], reverse=True)
            total_req = sum(cuts)

            # Filter for "Rolls" that match specs and are long enough
            available_rolls = st.session_state.inventory[
                (st.session_state.inventory['Type'].str.upper() == 'ROLL') & 
                (st.session_state.inventory['Color'] == p_color) &
                (st.session_state.inventory['Width'] == p_width) &
                (st.session_state.inventory['DateCode'] == selected_batch) &
                (st.session_state.inventory['Length'] >= total_req)
            ].sort_values(by='Length')

            if not available_rolls.empty:
                best_roll = available_rolls.iloc[0]
                st.subheader(f"🌟 Use Roll: {best_roll['ID']}")
                st.info(f"This is the **shortest** available roll ({best_roll['Length']}ft) that satisfies the {total_req}ft requirement.")
                
                # Visual Map
                remnant = best_roll['Length'] - total_req
                viz_cols = st.columns([c for c in cuts] + [max(remnant, 0.5)])
                for i, c in enumerate(cuts):
                    viz_cols[i].info(f"{c}'")
                
                if remnant < SCRAP_THRESHOLD:
                    viz_cols[-1].error(f"SCRAP\n{remnant}'")
                else:
                    viz_cols[-1].success(f"REMNANT\n{remnant}'")
                
                # Other Rolls table
                with st.expander("View other available rolls in this batch"):
                    st.table(available_rolls[1:])
            else:
                st.error("No single roll is long enough. Check your inventory or split the job.")

    # --- 4. SQUARE CORNER VISIBILITY ---
    with col_sc:
        st.subheader("📦 Available SCs")
        st.caption(f"Matching {p_color} / {selected_batch}")
        
        sc_inventory = st.session_state.inventory[
            (st.session_state.inventory['Type'].str.upper() == 'SC') & 
            (st.session_state.inventory['Color'] == p_color) &
            (st.session_state.inventory['DateCode'] == selected_batch)
        ]
        
        if not sc_inventory.empty:
            # Display SCs as a clean list with "Pull" buttons or just data
            st.dataframe(sc_inventory[['ID', 'Length']], hide_index=True, use_container_width=True)
            st.write(f"Total SCs in Stock: {len(sc_inventory)}")
        else:
            st.warning("No matching Square Corners in bin.")

else:
    st.info("👋 Welcome! Please upload your 'current_inventory.csv' in the sidebar to get started.")
