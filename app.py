import streamlit as st
import pandas as pd

# --- CONFIGURATION ---
SCRAP_THRESHOLD = 4.0 

st.set_page_config(page_title="Pool Shop Optimizer", layout="wide")
st.title("🏗️ Hybrid Pool Shop: Auto-Batch & SC Dashboard")

# --- 1. INVENTORY SYNC ---
if 'inventory' not in st.session_state:
    st.session_state.inventory = pd.DataFrame(columns=["ID", "Type", "Width", "Color", "DateCode", "Length"])

with st.sidebar:
    st.header("Admin: Inventory Upload")
    uploaded_file = st.file_uploader("Upload Shop CSV", type=["csv"])
    if uploaded_file:
        st.session_state.inventory = pd.read_csv(uploaded_file)
        st.success("Inventory Loaded Successfully!")

# --- 2. PROJECT INPUTS ---
if not st.session_state.inventory.empty:
    st.header("Step 1: Project Specs")
    col_a, col_b = st.columns(2)
    with col_a:
        p_color = st.selectbox("Pool Color", st.session_state.inventory['Color'].unique())
    with col_b:
        p_width = st.selectbox("Wall Width (in)", st.session_state.inventory['Width'].unique())

    wall_input = st.text_input("Enter Required Wall Lengths (e.g. 15, 12, 10)", "12, 12, 10")
    
    if st.button("🚀 Run Optimizer"):
        cuts = sorted([float(x.strip()) for x in wall_input.split(",")], reverse=True)
        total_req = sum(cuts)
        
        # --- 3. AUTO-BATCH SELECTION ---
        # Find which batches have enough total stock to complete the job
        batch_lookup = st.session_state.inventory[
            (st.session_state.inventory['Color'] == p_color) & 
            (st.session_state.inventory['Width'] == p_width)
        ].groupby('DateCode')['Length'].sum()

        valid_batches = batch_lookup[batch_lookup >= total_req].index.tolist()

        if not valid_batches:
            st.error(f"❌ Material Shortage: No single Batch has {total_req}ft available in {p_color}.")
        else:
            # Select the batch that is the "Tightest Fit" (prioritize clearing small batches)
            selected_batch = batch_lookup[valid_batches].idxmin()
            
            st.divider()
            
            # --- 4. LAYOUT: ROLL OPTIMIZER (LEFT) & SC BIN (RIGHT) ---
            main_col, sc_col = st.columns([2, 1])

            with main_col:
                st.subheader(f"📊 Best Roll for Batch: {selected_batch}")
                
                # Find the shortest single roll in that batch that fits the whole job
                best_rolls = st.session_state.inventory[
                    (st.session_state.inventory['Type'].str.upper() == 'ROLL') & 
                    (st.session_state.inventory['DateCode'] == selected_batch) &
                    (st.session_state.inventory['Length'] >= total_req)
                ].sort_values(by='Length')

                if not best_rolls.empty:
                    pick = best_rolls.iloc[0]
                    st.info(f"👉 **Pull Roll ID: {pick['ID']}** ({pick['Length']} ft total)")
                    
                    # Visualization
                    remnant = pick['Length'] - total_req
                    v_cols = st.columns([c for c in cuts] + [max(remnant, 0.5)])
                    for i, c in enumerate(cuts):
                        v_cols[i].info(f"{c}'")
                    
                    if remnant < SCRAP_THRESHOLD:
                        v_cols[-1].error(f"SCRAP\n{remnant}'")
                    else:
                        v_cols[-1].success(f"REMNANT\n{remnant}'")
                else:
                    st.warning("Batch has enough total material, but it's split across multiple rolls.")

            with sc_col:
                st.subheader("📦 Matching SC Bin")
                # Show only Square Corners that match the selected batch
                sc_match = st.session_state.inventory[
                    (st.session_state.inventory['Type'].str.upper() == 'SC') & 
                    (st.session_state.inventory['Color'] == p_color) &
                    (st.session_state.inventory['DateCode'] == selected_batch)
                ]
                
                if not sc_match.empty:
                    st.write(f"Pre-cut corners available in **{selected_batch}**:")
                    st.dataframe(sc_match[['ID', 'Length']], hide_index=True, use_container_width=True)
                else:
                    st.write("No matching Square Corners in stock for this batch.")

else:
    st.info("Please upload your inventory CSV in the sidebar to begin.")
