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
        # Ensure Length is float and formatted
        df['Length'] = df['Length'].astype(float).round(2)
        st.session_state.inventory = df
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
    
    # Standard Rectangle Template
    input_df = pd.DataFrame([
        {"Length": 12.00, "Use_SC": False},
        {"Length": 12.00, "Use_SC": False},
        {"Length": 4.00, "Use_SC": True},
        {"Length": 4.00, "Use_SC": True}
    ])
    
    production_table = st.data_editor(
        input_df, 
        num_rows="dynamic", 
        column_config={
            "Length": st.column_config.NumberColumn("Length (ft)", min_value=0.50, step=0.01, format="%.2f"),
            "Use_SC": st.column_config.CheckboxColumn("Use SC?", default=False)
        },
        use_container_width=True
    )

    if st.button("🚀 Run Production Matcher"):
        # Format input lengths to 2 decimal points
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
            st.error(f"❌ Material Shortage: No single Batch has {total_roll_ft:.2f}ft available.")
        else:
            selected_batch = batch_lookup[valid_batches].idxmin()
            st.success(f"✅ **Batch Match Found:** Using Date Code **{selected_batch}**")

            # --- 4. THE PULL LISTS ---
            roll_col, sc_col = st.columns([2, 1])

            with roll_col:
                st.subheader("✂️ Roll Cut Map")
                all_eligible_rolls = st.session_state.inventory[
                    (st.session_state.inventory['Type'].str.upper() == 'ROLL') & 
                    (st.session_state.inventory['DateCode'] == selected_batch) &
                    (st.session_state.inventory['Length'] >= total_roll_ft)
                ].sort_values(by='Length')

                if not all_eligible_rolls.empty:
                    pick = all_eligible_rolls.iloc[0]
                    st.info(f"**Recommended Roll: {pick['ID']}** ({pick['Length']:.2f} ft)")
                    
                    # Cut Map Visualization
                    v_cols = st.columns([c for c in roll_cuts_needed] + [0.5])
                    for i, c in enumerate(roll_cuts_needed):
                        v_cols[i].info(f"{c:.2f}'")
                    
                    if len(all_eligible_rolls) > 1:
                        with st.expander("🔄 Show other roll options for this batch"):
                            other_display = all_eligible_rolls.iloc[1:][['ID', 'Length', 'Width']].copy()
                            st.dataframe(other_display.style.format({"Length": "{:.2f}"}), hide_index=True)
                else:
                    st.warning("Batch footage is split across multiple rolls.")

            with sc_col:
                st.subheader("📦 SC Bin Visibility")
                st.markdown("**Batch Matches (Best Choice):**")
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

                st.write("---")
                with st.expander("🔍 View All Other SCs in Stock"):
                    all_scs = st.session_state.inventory[
                        (st.session_state.inventory['Type'].str.upper() == 'SC') & 
                        (st.session_state.inventory['Color'] == p_color)
                    ].sort_values(by=['DateCode', 'Length'])
                    st.dataframe(all_scs[['ID', 'Length', 'DateCode']].style.format({"Length": "{:.2f}"}), hide_index=True, use_container_width=True)

            # --- 5. CLEAN SUMMARY ---
            st.divider()
            st.subheader("📋 Roll Usage Summary")
            
            if 'pick' in locals():
                remnant = round(pick['Length'] - total_roll_ft, 2)
                s1, s2, s3 = st.columns(3)
                s1.metric("Total Used", f"{total_roll_ft:.2f} ft")
                
                if remnant >= SCRAP_THRESHOLD:
                    s2.metric("New Remnant", f"{remnant:.2f} ft", delta="REUSABLE", delta_color="normal")
                    s3.write("**Action:** Re-label & Restock")
                else:
                    s2.metric("Waste (Scrap)", f"{remnant:.2f} ft", delta="SCRAP", delta_color="inverse")
                    s3.write("**Action:** Dispose of Waste")

else:
    st.info("Upload your inventory CSV in the sidebar.")
