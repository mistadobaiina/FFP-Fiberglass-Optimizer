import streamlit as st
import pandas as pd

# --- CONFIGURATION ---
SCRAP_THRESHOLD = 4.0 

st.set_page_config(page_title="Pool Shop Optimizer", layout="wide")
st.title("🏗️ Hybrid Pool: Wall & SC Production Planner")

# --- 1. INVENTORY SYNC ---
if 'inventory' not in st.session_state:
    st.session_state.inventory = pd.DataFrame(columns=["ID", "Type", "Width", "Color", "DateCode", "Length"])

with st.sidebar:
    st.header("Admin: Inventory Upload")
    uploaded_file = st.file_uploader("Upload Shop CSV", type=["csv"])
    if uploaded_file:
        st.session_state.inventory = pd.read_csv(uploaded_file)
        st.success("Inventory Loaded!")

# --- 2. PROJECT REQUIREMENTS ---
if not st.session_state.inventory.empty:
    st.header("Step 1: Project Specs")
    c1, c2 = st.columns(2)
    with c1:
        p_color = st.selectbox("Pool Color", st.session_state.inventory['Color'].unique())
    with c2:
        p_width = st.selectbox("Wall Width (in)", st.session_state.inventory['Width'].unique())

    st.subheader("Step 2: Enter Wall List")
    st.caption("Enter lengths and check 'Use SC' for corner pieces.")
    
    # Create an editable table for wall inputs
    input_df = pd.DataFrame([
        {"Length": 12.0, "Use_SC": False},
        {"Length": 12.0, "Use_SC": False},
        {"Length": 4.0, "Use_SC": True},
        {"Length": 4.0, "Use_SC": True}
    ])
    
    production_table = st.data_editor(
        input_df, 
        num_rows="dynamic", 
        column_config={
            "Length": st.column_config.NumberColumn("Length (ft)", min_value=0.5, step=0.5),
            "Use_SC": st.column_config.CheckboxColumn("Use SC?", default=False)
        },
        use_container_width=True
    )

    if st.button("🚀 Run Production Matcher"):
        # Separate the items
        sc_needed = production_table[production_table['Use_SC'] == True]
        roll_cuts_needed = production_table[production_table['Use_SC'] == False]['Length'].tolist()
        total_roll_ft = sum(roll_cuts_needed)

        # --- 3. AUTO-BATCH SELECTION ---
        # Find which batches have enough TOTAL roll stock + the required SCs
        batch_lookup = st.session_state.inventory[
            (st.session_state.inventory['Color'] == p_color) & 
            (st.session_state.inventory['Width'] == p_width)
        ].groupby('DateCode')['Length'].sum()

        valid_batches = batch_lookup[batch_lookup >= total_roll_ft].index.tolist()

        if not valid_batches:
            st.error(f"❌ Material Shortage: No single Batch has {total_roll_ft}ft available.")
        else:
            selected_batch = batch_lookup[valid_batches].idxmin()
            st.success(f"✅ **Batch Match Found:** Using Date Code **{selected_batch}**")

            # --- 4. LAYOUT: PULL LISTS ---
            roll_col, sc_col = st.columns([2, 1])

            with roll_col:
                st.subheader("✂️ Roll Cut Map")
                # Find best roll for the non-SC walls
                best_rolls = st.session_state.inventory[
                    (st.session_state.inventory['Type'].str.upper() == 'ROLL') & 
                    (st.session_state.inventory['DateCode'] == selected_batch) &
                    (st.session_state.inventory['Length'] >= total_roll_ft)
                ].sort_values(by='Length')

                if not best_rolls.empty:
                    pick = best_rolls.iloc[0]
                    st.info(f"**Pull Roll: {pick['ID']}**")
                    
                    # Visualization
                    remnant = pick['Length'] - total_roll_ft
                    v_cols = st.columns([c for c in sorted(roll_cuts_needed, reverse=True)] + [max(remnant, 0.5)])
                    for i, c in enumerate(sorted(roll_cuts_needed, reverse=True)):
                        v_cols[i].info(f"{c}'")
                    
                    if remnant < SCRAP_THRESHOLD:
                        v_cols[-1].error(f"SCRAP: {remnant}'")
                    else:
                        v_cols[-1].success(f"REMNANT: {remnant}'")
                else:
                    st.warning("Batch has enough total footage, but it's split across multiple rolls.")

            with sc_col:
                st.subheader("📦 SC Pull List")
                # Check if the requested SCs actually exist in this batch
                for _, row in sc_needed.iterrows():
                    match = st.session_state.inventory[
                        (st.session_state.inventory['Type'].str.upper() == 'SC') & 
                        (st.session_state.inventory['Length'] == row['Length']) &
                        (st.session_state.inventory['DateCode'] == selected_batch)
                    ]
                    if not match.empty:
                        st.write(f"✅ **{row['Length']}ft SC** (Item: {match.iloc[0]['ID']})")
                    else:
                        st.error(f"❌ **{row['Length']}ft SC** NOT IN STOCK for this batch.")

else:
    st.info("Please upload your inventory CSV in the sidebar.")
