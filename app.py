import streamlit as st
import pandas as pd
import difflib
import re

# --- CONFIGURATION ---
SCRAP_THRESHOLD = 4.00 

st.set_page_config(page_title="Pool Shop Optimizer", layout="wide")
st.title("🏗️ Hybrid Pool: Total Footage & Fallback Optimizer")

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

    if st.button("🚀 Run Optimizer"):
        production_table['Length'] = production_table['Length'].astype(float).round(2)
        sc_reqs = production_table[production_table['Use_SC'] == True]['Length'].tolist()
        roll_reqs = sorted(production_table[production_table['Use_SC'] == False]['Length'].tolist(), reverse=True)
        
        # Calculate totals
        standard_roll_total = round(sum(roll_reqs), 2)
        fallback_total = round(sum(roll_reqs) + sum(sc_reqs), 2)

        master_filtered = st.session_state.inventory[
            (st.session_state.inventory['Color'] == p_color) & 
            (st.session_state.inventory['Width'] == p_width)
        ].copy()

        # --- PRIORITY 1: LOT ID EXTRACTION (4 NUMERALS) ---
        def get_base_lot(row):
            match = re.search(r'(\d{4})', str(row['DateCode']))
            if match: return match.group(1)
            match = re.search(r'(\d{4})', str(row['ID']))
            if match: return match.group(1)
            return str(row['DateCode'])

        master_filtered['BaseLot'] = master_filtered.apply(get_base_lot, axis=1)

        lot_scores = []
        for lot, group in master_filtered.groupby('BaseLot'):
            sc_group = group[group['Type'].str.upper() == 'SC'].copy()
            scs_found = 0
            for req_len in sc_reqs:
                match = sc_group[sc_group['Length'] == req_len]
                if not match.empty:
                    scs_found += 1
                    sc_group = sc_group.drop(match.index[0])

            rolls = group[group['Type'].str.upper() == 'ROLL']
            can_fit_std = not rolls[rolls['Length'] >= standard_roll_total].empty
            can_fit_fallback = not rolls[rolls['Length'] >= fallback_total].empty

            if can_fit_std or can_fit_fallback:
                lot_scores.append({
                    'BaseLot': lot,
                    'SC_Matches': scs_found,
                    'Can_Fallback': can_fit_fallback,
                    'Max_Single_Roll': rolls['Length'].max()
                })

        lot_df = pd.DataFrame(lot_scores)

        if lot_df.empty:
            st.error("❌ No suitable material found in inventory for these specs.")
        else:
            best_lot_row = lot_df.sort_values(by=['SC_Matches', 'Can_Fallback', 'Max_Single_Roll'], ascending=[False, False, True]).iloc[0]
            selected_base_lot = best_lot_row['BaseLot']
            
            winning_lot_inventory = master_filtered[master_filtered['BaseLot'] == selected_base_lot].copy()
            available_rolls = winning_lot_inventory[winning_lot_inventory['Type'].str.upper() == 'ROLL']
            
            actual_sc_matches = []
            temp_sc_bin = winning_lot_inventory[winning_lot_inventory['Type'].str.upper() == 'SC'].copy()
            for req_len in sc_reqs:
                match = temp_sc_bin[temp_sc_bin['Length'] == req_len]
                if not match.empty:
                    actual_sc_matches.append(match.iloc[0])
                    temp_sc_bin = temp_sc_bin.drop(match.index[0])

            all_scs_present = len(actual_sc_matches) == len(sc_reqs)
            
            if all_scs_present:
                final_cuts = roll_reqs
                mode_label = "Standard Match"
            else:
                missing_sc_lengths = sc_reqs[len(actual_sc_matches):]
                final_cuts = sorted(roll_reqs + missing_sc_lengths, reverse=True)
                mode_label = f"Fallback Match (Cutting {len(missing_sc_lengths)} SCs from Roll)"

            st.success(f"✅ **Lot {selected_base_lot} Selected** ({mode_label})")

            roll_col, sc_col = st.columns([2, 1])

            with roll_col:
                st.subheader("✂️ Roll Cut Map")
                total_needed = sum(final_cuts)
                eligible_single_rolls = available_rolls[available_rolls['Length'] >= total_needed].sort_values(by='Length')
                
                if not eligible_single_rolls.empty:
                    pick = eligible_single_rolls.iloc[0]
                    st.info(f"**Roll: {pick['ID']}** ({pick['Length']:.2f} ft) [Lot: {pick['DateCode']}]")
                    remnant = round(pick['Length'] - total_needed, 2)
                    v_cols = st.columns([float(c) for c in final_cuts] + [max(remnant, 0.5)])
                    for i, c in enumerate(final_cuts):
                        v_cols[i].info(f"{c:.2f}'")
                        
                    if len(eligible_single_rolls) > 1:
                        with st.expander(f"🔄 Other {p_width}in {p_color} rolls in Lot {selected_base_lot}"):
                            st.dataframe(eligible_single_rolls[['ID', 'Length', 'DateCode']].style.format({"Length": "{:.2f}"}), hide_index=True)
                else:
                    st.warning("⚠️ No single roll long enough. Multi-roll split required.")
                    st.dataframe(available_rolls[['ID', 'Length', 'DateCode']].sort_values(by='ID'), hide_index=True)

            with sc_col:
                st.subheader("📦 SC Bin")
                for sc in actual_sc_matches:
                    st.write(f"✅ **{sc['Length']:.2f}' SC** (ID: {sc['ID']})")
                
                if not all_scs_present:
                    for i in range(len(sc_reqs) - len(actual_sc_matches)):
                        st.warning("⚠️ Manual cut from roll")

                # --- RESTORED SC GLOBAL OPTIONS ---
                with st.expander(f"🔍 Global {p_width}in {p_color} SC Inventory"):
                    all_scs = master_filtered[master_filtered['Type'].str.upper() == 'SC'].sort_values(by=['BaseLot', 'Length'])
                    st.dataframe(all_scs[['ID', 'Length', 'DateCode']].style.format({"Length": "{:.2f}"}), hide_index=True, use_container_width=True)

            st.divider()
            s1, s2, s3 = st.columns(3)
            s1.metric("Total Used", f"{total_needed:.2f} ft")
            if 'remnant' in locals():
                s2.metric("Remnant", f"{remnant:.2f} ft", delta="REUSABLE" if remnant >= SCRAP_THRESHOLD else "SCRAP")
                s3.write(f"**Batch:** {pick['DateCode']}")

else:
    st.info("Upload inventory to begin.")
