import streamlit as st
import pandas as pd
import difflib
import re

# --- CONFIGURATION ---
SCRAP_THRESHOLD = 4.00 

st.set_page_config(page_title="Pool Shop Optimizer", layout="wide")
st.title("🏗️ Hybrid Pool: Restricted Production Dashboard")

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
        p_width = st.selectbox("Wall Width/Height (in)", st.session_state.inventory['Width'].unique())
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

    if st.button("🚀 Run Restricted Matcher"):
        production_table['Length'] = production_table['Length'].astype(float).round(2)
        sc_needed = production_table[production_table['Use_SC'] == True]
        roll_cuts_needed = sorted(production_table[production_table['Use_SC'] == False]['Length'].tolist(), reverse=True)
        total_roll_ft = round(sum(roll_cuts_needed), 2)

        # Apply Hard Constraints first
        master_filtered = st.session_state.inventory[
            (st.session_state.inventory['Color'] == p_color) & 
            (st.session_state.inventory['Width'] == p_width)
        ].copy()

        # --- PRIORITY 1: LOT ID EXTRACTION (4 NUMERALS) ---
        def get_base_lot(row):
            # Look for 4 consecutive numerals in DateCode
            match = re.search(r'(\d{4})', str(row['DateCode']))
            if match: return match.group(1)
            # Fallback: Look in ID just in case
            match = re.search(r'(\d{4})', str(row['ID']))
            if match: return match.group(1)
            return str(row['DateCode']) # Failsafe

        master_filtered['BaseLot'] = master_filtered.apply(get_base_lot, axis=1)

        # --- SCORE EVERY LOT ---
        lot_scores = []
        for lot, group in master_filtered.groupby('BaseLot'):
            # Check Roll requirement
            roll_ft = group[group['Type'].str.upper() == 'ROLL']['Length'].sum()
            if roll_ft < total_roll_ft:
                continue 
                
            # Check SC requirement (Count how many required SCs exist in this lot)
            sc_group = group[group['Type'].str.upper() == 'SC'].copy()
            scs_found = 0
            for _, row in sc_needed.iterrows():
                match = sc_group[sc_group['Length'] == row['Length']]
                if not match.empty:
                    scs_found += 1
                    sc_group = sc_group.drop(match.index[0]) # Consume to prevent double counting
                    
            # Calculate Waste
            single_rolls = group[(group['Type'].str.upper() == 'ROLL') & (group['Length'] >= total_roll_ft)]
            min_waste = (single_rolls['Length'].min() - total_roll_ft) if not single_rolls.empty else 99999
                
            lot_scores.append({
                'BaseLot': lot,
                'SC_Matches': scs_found,
                'Min_Waste': min_waste
            })

        lot_df = pd.DataFrame(lot_scores)

        if lot_df.empty:
            st.error(f"❌ Material Shortage: No Base Lot ID has {total_roll_ft:.2f}ft of {p_width}in {p_color} available.")
        else:
            # Sort Lots: 1. Max SC Matches, 2. Lowest Waste
            best_lot_row = lot_df.sort_values(by=['SC_Matches', 'Min_Waste'], ascending=[False, True]).iloc[0]
            selected_base_lot = best_lot_row['BaseLot']
            
            st.success(f"✅ **Base Lot Match Found:** Using Lot ID **{selected_base_lot}**")
            if best_lot_row['SC_Matches'] < len(sc_needed):
                st.warning(f"⚠️ This Lot has the roll footage, but is missing some required SCs. You will need to substitute SCs from another lot below.")

            winning_lot_inventory = master_filtered[master_filtered['BaseLot'] == selected_base_lot].copy()

            roll_col, sc_col = st.columns([2, 1])

            with roll_col:
                st.subheader("✂️ Roll Cut Map")
                batch_rolls = winning_lot_inventory[winning_lot_inventory['Type'].str.upper() == 'ROLL']
                eligible_single_rolls = batch_rolls[batch_rolls['Length'] >= total_roll_ft]

                if not eligible_single_rolls.empty:
                    # Priority 3: Minimize length applied here
                    pick = eligible_single_rolls.sort_values(by=['Length']).iloc[0]
                    target_roll_id = str(pick['ID'])
                    
                    st.info(f"**Recommended Roll: {pick['ID']}** ({pick['Length']:.2f} ft) [Lot: {pick['DateCode']}]")
                    
                    remnant = round(pick['Length'] - total_roll_ft, 2)
                    v_cols = st.columns([c for c in roll_cuts_needed] + [max(remnant, 0.5)])
                    for i, c in enumerate(roll_cuts_needed):
                        v_cols[i].info(f"{c:.2f}'")
                    
                    if len(eligible_single_rolls) > 1:
                        with st.expander(f"🔄 Other {p_width}in {p_color} rolls in Base Lot {selected_base_lot}"):
                            st.dataframe(eligible_single_rolls[['ID', 'Length', 'DateCode']].style.format({"Length": "{:.2f}"}), hide_index=True)
                else:
                    target_roll_id = ""
                    st.warning(f"⚠️ Multi-Roll Split Required.")
                    st.dataframe(batch_rolls[['ID', 'Length', 'DateCode']].sort_values(by='ID'), hide_index=True)

            with sc_col:
                st.subheader("📦 SC Bin Visibility")
                st.markdown(f"**Lot {selected_base_lot} Matches:**")
                
                available_scs = winning_lot_inventory[winning_lot_inventory['Type'].str.upper() == 'SC'].copy()
                
                for _, row in sc_needed.iterrows():
                    sc_matches = available_scs[available_scs['Length'] == row['Length']].copy()
                    
                    if not sc_matches.empty:
                        # Priority 2: Match SC string to Roll string
                        if target_roll_id:
                            sc_matches['sim'] = sc_matches['ID'].apply(
                                lambda x: difflib.SequenceMatcher(None, str(x), target_roll_id).ratio()
                            )
                            best_sc = sc_matches.sort_values(by='sim', ascending=False).iloc[0]
                        else:
                            best_sc = sc_matches.sort_values(by='ID').iloc[0]
                            
                        st.write(f"✅ **{row['Length']:.2f}ft SC** (ID: {best_sc['ID']} | Lot: {best_sc['DateCode']})")
                        # Consume the piece so it isn't listed twice
                        available_scs = available_scs.drop(best_sc.name)
                    else:
                        st.error(f"❌ **{row['Length']:.2f}ft SC** NOT IN BATCH")

                with st.expander(f"🔍 Global {p_width}in {p_color} SC Inventory"):
                    all_scs = master_filtered[master_filtered['Type'].str.upper() == 'SC'].sort_values(by=['BaseLot', 'Length'])
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
    st.info("Please upload your inventory CSV in the sidebar.")
