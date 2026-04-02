import streamlit as st
import pandas as pd

# --- CONFIGURATION ---
SCRAP_THRESHOLD = 4.0 

st.set_page_config(page_title="Pool Inventory & SC Manager", layout="wide")
st.title("🏗️ Hybrid Pool Inventory & Corner Optimizer")

# --- INVENTORY UPLOAD ---
st.header("Step 1: Sync Shop Inventory")
uploaded_file = st.file_uploader("Upload 'current_inventory.csv'", type=["csv"])

if 'inventory' not in st.session_state:
    st.session_state.inventory = pd.DataFrame(columns=["ID", "Type", "Width", "Color", "DateCode", "Length"])

if uploaded_file is not None:
    st.session_state.inventory = pd.read_csv(uploaded_file)
    st.success(f"Inventory Loaded: {len(st.session_state.inventory)} items.")

# --- PROJECT OPTIMIZATION ---
st.header("Step 2: Project Build-Out")

if st.session_state.inventory.empty:
    st.warning("Please upload an inventory CSV to begin.")
else:
    col1, col2, col3 = st.columns(3)
    with col1:
        p_color = st.selectbox("Color", st.session_state.inventory['Color'].unique())
    with col2:
        p_width = st.selectbox("Width", st.session_state.inventory['Width'].unique())
    with col3:
        batches = st.session_state.inventory[st.session_state.inventory['Color'] == p_color]['DateCode'].unique()
        selected_batch = st.selectbox("Date Code Match", batches)

    # --- NEW: SQUARE CORNER SECTION ---
    st.subheader("Wall & Corner Requirements")
    
    # We use a data editor to let the user mark which pieces are Square Corners
    input_df = pd.DataFrame([
        {"Length": 12.0, "Is_Square_Corner": False},
        {"Length": 4.0, "Is_Square_Corner": True}
    ])
    
    edited_df = st.data_editor(input_df, num_rows="dynamic", column_config={
        "Is_Square_Corner": st.column_config.CheckboxColumn("Square Corner? (SC)", default=False)
    })

    if st.button("Generate Pull List & Cut Map"):
        # Split the requirements into "Roll Cuts" and "SC Pulls"
        sc_reqs = edited_df[edited_df['Is_Square_Corner'] == True]
        roll_reqs = edited_df[edited_df['Is_Square_Corner'] == False]
        
        # 1. HANDLE SQUARE CORNERS (Exact Match)
        if not sc_reqs.empty:
            st.info("📦 **Square Corner Pull List**")
            for _, row in sc_reqs.iterrows():
                # Find matching SC in inventory
                match = st.session_state.inventory[
                    (st.session_state.inventory['Type'] == 'SC') & 
                    (st.session_state.inventory['Length'] == row['Length']) &
                    (st.session_state.inventory['Color'] == p_color) &
                    (st.session_state.inventory['DateCode'] == selected_batch)
                ]
                if not match.empty:
                    st.write(f"✅ Pull SC Item **{match.iloc[0]['ID']}** ({row['Length']} ft)")
                else:
                    st.error(f"❌ No {row['Length']}ft Square Corner found in {p_color} / {selected_batch}")

        # 2. HANDLE ROLLS (Optimization Logic)
        if not roll_reqs.empty:
            st.info("✂️ **Fiberglass Roll Cut Map**")
            cuts = sorted(roll_reqs['Length'].tolist(), reverse=True)
            eligible_rolls = st.session_state.inventory[
                (st.session_state.inventory['Type'] == 'Roll') & 
                (st.session_state.inventory['DateCode'] == selected_batch)
            ].to_dict('records')
            
            # (Insert previous optimization/visualization logic here)
            for roll in eligible_rolls:
                # ... [Optimization logic for roll cutting] ...
                st.write(f"Using Roll {roll['ID']}")
