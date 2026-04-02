import streamlit as st
import pandas as pd

# --- CONFIGURATION ---
SCRAP_THRESHOLD = 4.00 

st.set_page_config(page_title="Pool Shop Optimizer", layout="wide")
st.title("🏗️ Hybrid Pool: Full Production & Inventory Dashboard")

# --- 1. INVENTORY SYNC ---
if 'inventory' not in st.session_state:
    st.session_state.inventory = pd.DataFrame(columns=["ID", "Type", "Width", "Color", "DateCode", "Length"])

with st.sidebar:
    st.header("Admin: Inventory Upload")
    uploaded_file = st.file_uploader("Upload Shop CSV", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        df['Length'] = df['Length'].astype(float).round(2)
        st.session_state.inventory = df
        st.success("Inventory Loaded!")

# --- 2. POOL CONFIGURATION ---
if not st.session_state.inventory.empty:
    st.header("Step 1: Project Specs")
    c1, c2, c3 = st.columns(3)
    with c1:
        p_color = st.selectbox("Pool Color", st.session_state.inventory['Color'].unique())
    with c2:
        p_width = st.selectbox("Wall Width (in)", st.session_state.inventory['Width'].unique())
    with c3:
        pool_type = st.selectbox("Pool Shape/Type", ["Rectangle with SC", "Rectangle w/out SC", "Freeform"])

    st.divider()
    st.subheader(f"Step 2: Enter {pool_type} Dimensions")
    
    wall_data = []
    if pool_type == "Rectangle with SC":
        col_len, col_wid = st.columns(2)
        with col_len:
            rect_l = st.number_input("Straight Wall Length (ft)", min_value=1.0, value=20.0, step=0.5)
        with col_wid:
            rect_w = st.number_input("Corner Wall Width (ft) - Will use SC", min_value=1.0, value=12.0, step=0.5)
        wall_data = [
            {"Length": rect_l, "Use_SC": False},
            {"Length": rect_l, "Use_SC": False},
            {"Length": rect_w, "Use_SC": True},
            {"Length": rect_w, "Use_SC": True}
        ]
    elif pool_type == "Rectangle w/out SC":
        total_p = st.number_input("Total Continuous Perimeter (ft)", min_value=1.0, value=64.0, step=0.5)
        wall_data = [{"Length": total_p, "Use_SC": False}]
    elif pool_type == "Freeform":
        total_f = st.number_input("Total Perimeter Length (ft)", min_value=1.0, value=80.0, step=0.5)
        wall_data = [{"Length": total_f, "Use_SC": False}]

    production_table = st.data_editor(
        pd.DataFrame(wall_data), 
        num_rows="dynamic", 
        column_config={
            "Length": st.column_config.NumberColumn("Length (ft)", format="%.2f"),
            "Use_SC": st.column_config.CheckboxColumn("Use SC?")
        },
        use_container_width=True
    )

    if st.button("🚀 Run Production Matcher"):
        production_table['Length'] = production_table['Length'].astype(float).round(2)
        sc_needed = production_table[production_table['Use_SC'] == True]
        roll_cuts_needed = sorted(production_table[production_table['Use_SC'] == False]['Length'].tolist(), reverse=True)
        total_roll_ft = round(sum(roll_cuts_needed), 2)

        # --- 3. AUTO-BATCH SELECTION ---
        batch_lookup = st.session_state.inventory[
            (st.session_state.inventory['Color'] == p_color) & 
            (st.session_state.inventory['Width'] == p_width)
        ].groupby('DateCode')['Length'].sum()

        valid_batches = batch_lookup[batch_lookup >= total_roll_ft].index.tolist()

        if not valid_batches:
            st.error(f"❌ Material Shortage: No single Date Code has {total_roll_ft:.2f}ft available.")
        else:
            selected_batch = batch_lookup[valid_batches].idxmin()
            st.success(f"✅ **Batch Match Found:** Using Date Code **{selected_batch}**")

            roll_col, sc_col = st.columns([2, 1])

            with roll_col:
                st.subheader("✂️ Roll Cut Map")
                # Single roll search
                all_eligible_rolls = st.session_state.inventory[
                    (st.session_state.inventory['Type'].str.upper() == 'ROLL') & 
                    (st.session_state.inventory['DateCode'] == selected_batch) &
                    (st.session_state.inventory['Length'] >= total_roll_ft)
                ].sort_values(by='Length')

                if not all_eligible_rolls.empty:
                    pick = all_eligible_rolls.iloc[0]
                    st.info(f"**Recommended Roll: {pick['ID']}** ({pick['Length']:.2f} ft)")
                    remnant = round(pick['Length'] - total_roll_ft, 2)
                    v_cols = st.columns([c for c in roll_cuts_needed] + [0.5])
                    for i, c in enumerate(roll_cuts_needed):
                        v_cols[i].info(f"{c:.2f}'")
                else:
                    # NEW: SHOW MULTI-ROLL OPTIONS IF SINGLE MATCH FAILS
                    st.warning(f"⚠️ Single Roll Match Failed for Batch {selected_batch}.")
                    st.write("You must split the job across multiple rolls. Here are the available rolls in this batch:")
                    batch_rolls = st.session_state.inventory[
                        (st.session_state.inventory['Type'].str.upper() == 'ROLL') & 
                        (st.session_state.inventory['DateCode'] == selected_batch)
                    ].sort_values(by='Length', ascending=False)
                    st.dataframe(batch_rolls[['ID', 'Length', 'Width']], hide_index=True, use_container_width=True)

            with sc_col:
                st.subheader("📦 SC Bin Visibility")
                st.markdown("**Batch Matches:**")
                for _, row in sc_needed.iterrows():
                    match = st.session_state.inventory[
                        (st.session_state.inventory['Type'].str.upper() == 'SC') & 
                        (st.session_state.inventory['Length'] == row['Length']) &
                        (st.session_state.inventory['DateCode'] == selected_batch)
                    ]
                    if not match.empty:
                        st.write(f"✅ **{row['Length']:.2f}ft SC** (ID: {match.iloc[0]['ID']})")
                    else:
                        st.error(f"❌ **{row['Length']:.2f}ft SC** NOT IN BATCH")

                with st.expander("🔍 Full SC Inventory"):
                    all_scs = st.session_state.inventory[
                        (st.session_state.inventory['Type'].str.upper() == 'SC') & 
                        (st.session_state.inventory['Color'] == p_color)
                    ].sort_values(by=['DateCode', 'Length'])
                    st.dataframe(all_scs[['ID', 'Length', 'DateCode']].style.format({"Length": "{:.2f}"}), hide_index=True, use_container_width=True)

            # --- 5. CLEAN SUMMARY ---
            st.divider()
            st.subheader("📋 Roll Usage Summary")
            
            if 'pick' in locals():
                s1, s2, s3 = st.columns(3)
                s1.metric("Total Used", f"{total_roll_ft:.2f} ft")
                if remnant >= SCRAP_THRESHOLD:
                    s2.metric("New Remnant", f"{remnant:.2f} ft", delta="REUSABLE", delta_color="normal")
                    s3.write("**Action:** Re-label & Restock")
                else:
                    s2.metric("Waste (Scrap)", f"{remnant:.2f} ft", delta="SCRAP", delta_color="inverse")
                    s3.write("**Action:** Dispose of Waste")
            else:
                st.write("Summary unavailable: Job requires splitting across multiple rolls.")

else:
    st.info("Upload your inventory CSV in the sidebar.")
