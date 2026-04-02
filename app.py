import streamlit as st
import pandas as pd

# --- CONFIGURATION ---
SCRAP_THRESHOLD = 4.0 

st.set_page_config(page_title="Pool Batch Optimizer", layout="wide")
st.title("🏗️ Hybrid Pool: Automatic Batch Matcher")

# --- 1. INVENTORY SYNC ---
if 'inventory' not in st.session_state:
    st.session_state.inventory = pd.DataFrame(columns=["ID", "Type", "Width", "Color", "DateCode", "Length"])

with st.sidebar:
    st.header("Admin: Inventory Upload")
    uploaded_file = st.file_uploader("Upload Shop CSV", type=["csv"])
    if uploaded_file:
        st.session_state.inventory = pd.read_csv(uploaded_file)
        st.success("Inventory Updated!")

# --- 2. PROJECT SPECS ---
if not st.session_state.inventory.empty:
    st.header("Step 1: Project Requirements")
    c1, c2 = st.columns(2)
    with c1:
        p_color = st.selectbox("Pool Color", st.session_state.inventory['Color'].unique())
    with c2:
        p_width = st.selectbox("Roll Width (in)", st.session_state.inventory['Width'].unique())

    wall_input = st.text_input("Enter All Wall Lengths (e.g. 15, 12, 12, 10)", "12, 12, 10")
    
    if st.button("🔍 Optimize Batch & Find Best Roll"):
        cuts = sorted([float(x.strip()) for x in wall_input.split(",")], reverse=True)
        total_req = sum(cuts)
        st.write(f"**Total Material Needed:** {total_req} ft")

        # --- 3. THE AUTO-BATCH LOGIC ---
        # Find Date Codes that have enough TOTAL length in stock
        batch_summary = st.session_state.inventory[
            (st.session_state.inventory['Color'] == p_color) & 
            (st.session_state.inventory['Width'] == p_width)
        ].groupby('DateCode')['Length'].sum()

        valid_batches = batch_summary[batch_summary >= total_req].index.tolist()

        if not valid_batches:
            st.error(f"❌ Shortage Alert: No single Date Code in stock has {total_req}ft of {p_color} {p_width}\" fiberglass.")
        else:
            # Pick the "Tightest" Batch (The one with the least total stock that still fits)
            # This helps clear out older/smaller batches first.
            best_batch_code = batch_summary[valid_batches].idxmin()
            st.success(f"✅ **Batch Match Found:** Using Date Code **{best_batch_code}** for this project.")

            # --- 4. FIND THE BEST ROLL WITHIN THAT BATCH ---
            eligible_rolls = st.session_state.inventory[
                (st.session_state.inventory['Type'].str.upper() == 'ROLL') & 
                (st.session_state.inventory['DateCode'] == best_batch_code) &
                (st.session_state.inventory['Width'] == p_width) &
                (st.session_state.inventory['Length'] >= total_req)
            ].sort_values(by='Length')

            if not eligible_rolls.empty:
                best_roll = eligible_rolls.iloc[0]
                st.subheader(f"🌟 Pull Roll: {best_roll['ID']}")
                
                # Visual Map
                remnant = best_roll['Length'] - total_req
                viz_cols = st.columns([c for c in cuts] + [max(remnant, 0.5)])
                for i, c in enumerate(cuts):
                    viz_cols[i].info(f"{c}'")
                
                if remnant < SCRAP_THRESHOLD:
                    viz_cols[-1].error(f"SCRAP\n{remnant}'")
                else:
                    viz_cols[-1].success(f"REMNANT\n{remnant}'")
            else:
                st.warning(f"Batch {best_batch_code} has enough total material, but it is split across multiple rolls. You will need to use two rolls from the same batch.")

            # --- 5. AUTOMATIC SC VISIBILITY ---
            st.divider()
            st.subheader(f"📦 Square Corner Bin (Batch: {best_batch_code})")
            sc_inventory = st.session_state.inventory[
                (st.session_state.inventory['Type'].str.upper() == 'SC') & 
                (st.session_state.inventory['Color'] == p_color) &
                (st.session_state.inventory['DateCode'] == best_batch_code)
            ]
            if not sc_inventory.empty:
                st.dataframe(sc_inventory[['ID', 'Length']], hide_index=True)
            else:
                st.write("No pre-cut Square Corners available for this batch.")

else:
    st.info("Upload your inventory CSV in the sidebar to begin.")
