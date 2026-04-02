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
    
    # Pre-fill with a standard rectangle example
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
        sc_needed = production_table[production_table['Use_SC'] == True]
        roll_cuts_needed = sorted(production_table[production_table['Use_SC'] == False]['Length'].tolist(), reverse=True)
        total_roll_ft = sum(roll_cuts_needed)

        # --- 3. AUTO-BATCH SELECTION ---
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

            # --- 4. THE PULL LISTS ---
            roll_col, sc_col = st.columns([2, 1])

            with roll_col:
                st.subheader("✂️ Roll Cut Map")
                best_rolls = st.session_state.inventory[
                    (st.session_state.inventory['Type'].str.upper() == 'ROLL') & 
                    (st.session_state.inventory['DateCode'] == selected_batch) &
                    (st.session_state.inventory['Length'] >= total_roll_ft)
                ].sort_values(by='Length')

                if not best_rolls.empty:
                    pick = best_rolls.iloc[0]
                    st.info(f"**Pull Roll: {pick['ID']}**")
                    
                    # Visualization (Cuts only)
                    remnant = pick['Length'] - total_roll_ft
                    v_cols = st.columns([c for c in roll_cuts_needed] + [0.5]) # Tiny buffer for visual
                    for i, c in enumerate(roll_cuts_needed):
                        v_cols[i].info(f"{c}'")
                else:
                    st.warning("Batch footage is split across multiple rolls.")

            with sc_col:
                st.subheader("📦 SC Pull List")
                for _, row in sc_needed.iterrows():
                    match = st.session_state.inventory[
                        (st.session_state.inventory['Type'].str.upper() == 'SC') & 
                        (st.session_state.inventory['Length'] == row['Length']) &
                        (st.session_state.inventory['DateCode'] == selected_batch)
                    ]
                    if not match.empty:
                        st.write(f"✅ **{row['Length']}ft SC** (ID: {match.iloc[0]['ID']})")
                    else:
                        st.error(f"❌ **{row['Length']}ft SC** NOT IN STOCK")

            # --- 5. CLEAN SUMMARY (BELOW) ---
            st.divider()
            st.subheader("📋 Roll Usage Summary")
            
            summary_c1, summary_c2, summary_c3 = st.columns(3)
            
            with summary_c1:
                st.metric("Total Used", f"{total_roll_ft} ft")
            
            if 'pick' in locals():
                with summary_c2:
                    if remnant >= SCRAP_THRESHOLD:
                        st.metric("New Remnant Length", f"{remnant} ft", delta="REUSABLE", delta_color="normal")
                    else:
                        st.metric("Scrap Generated", f"{remnant} ft", delta="SCRAP", delta_color="inverse")
                
                with summary_c3:
                    status = "✅ Re-label & Restock" if remnant >= SCRAP_THRESHOLD else "🗑️ Dispose of Waste"
                    st.write(f"**Action Required:**")
                    st.write(status)

else:
    st.info("Upload your inventory CSV in the sidebar.")
