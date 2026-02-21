import streamlit as st
import pandas as pd
import io
from thefuzz import fuzz

st.set_page_config(page_title="Two-Way Reconciler", layout="wide")

st.title("📑 Two-Way Ledger Reconciler")
st.markdown("---")

file_a = st.sidebar.file_uploader("Upload Ledger A (ERP)", type=['xlsx', 'csv'])
file_b = st.sidebar.file_uploader("Upload Ledger B (Bank)", type=['xlsx', 'csv'])

if file_a and file_b:
    df_a = pd.read_excel(file_a) if file_a.name.endswith('xlsx') else pd.read_csv(file_a)
    df_b = pd.read_excel(file_b) if file_b.name.endswith('xlsx') else pd.read_csv(file_b)
    
    st.subheader("🔍 Column Configuration")
    c1, c2 = st.columns(2)
    with c1:
        st.info("Ledger A (ERP) Settings")
        m_a1 = st.selectbox("Match Field 1", df_a.columns, key="ma1")
        m_a2 = st.selectbox("Match Field 2", df_a.columns, key="ma2")
        recon_a = st.selectbox("Amount Column (A)", df_a.columns, key="ra")
    with c2:
        st.info("Ledger B (Bank) Settings")
        m_b1 = st.selectbox("Match Field 1", df_b.columns, key="mb1")
        m_b2 = st.selectbox("Match Field 2", df_b.columns, key="mb2")
        recon_b = st.selectbox("Amount Column (B)", df_b.columns, key="rb")

    if st.button("🚀 Run Two-Way Reconciliation"):
        # 1. Initialize Columns for both DataFrames
        df_a['Recon_Status'] = 'Unmatched'
        df_a['Matched_Amount_from_B'] = 0.0
        df_a['Difference'] = df_a[recon_a]
        
        df_b['Recon_Status'] = 'Unmatched'
        df_b['Matched_Amount_from_A'] = 0.0
        df_b['Difference'] = df_b[recon_b]
        
        used_b_indices = set()

        # 2. Forward Match: Ledger A -> Ledger B
        for idx_a, row_a in df_a.iterrows():
            key_a = f"{row_a[m_a1]} {row_a[m_a2]}".lower().strip()
            val_a = round(float(row_a[recon_a]), 2)

            best_score = -1
            best_idx_b = None

            # Look for best match in B among unused rows
            for idx_b, row_b in df_b[~df_b.index.isin(used_b_indices)].iterrows():
                key_b = f"{row_b[m_b1]} {row_b[m_b2]}".lower().strip()
                score = fuzz.token_sort_ratio(key_a, key_b)
                if score > best_score:
                    best_score = score
                    best_idx_b = idx_b
                if score == 100: break

            # If a structural match is found (Identity Match)
            if best_score >= 90:
                val_b = round(float(df_b.at[best_idx_b, recon_b]), 2)
                diff = round(val_a - val_b, 2)
                
                # Update Ledger A
                df_a.at[idx_a, 'Matched_Amount_from_B'] = val_b
                df_a.at[idx_a, 'Difference'] = diff
                
                # Update Ledger B
                df_b.at[best_idx_b, 'Matched_Amount_from_A'] = val_a
                df_b.at[best_idx_b, 'Difference'] = -diff # Inverse difference for B
                
                if diff == 0:
                    status = 'Matched'
                else:
                    status = 'Unmatched (Value Mismatch)'
                
                df_a.at[idx_a, 'Recon_Status'] = status
                df_b.at[best_idx_b, 'Recon_Status'] = status
                used_b_indices.add(best_idx_b)

        # 3. Post-Process Ledger B (Items never found in A)
        # These are already set to 'Unmatched' and 0.0 by default from step 1

        # 4. Generate Pivot Summary based on Ledger A
        pivot_df = df_a.groupby('Recon_Status').agg({
            recon_a: 'sum',
            'Matched_Amount_from_B': 'sum',
            'Difference': 'sum',
            'Recon_Status': 'count'
        }).rename(columns={'Recon_Status': 'Row Count'}).reset_index()

        # 5. Export to Multi-Sheet Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pivot_df.to_excel(writer, sheet_name='Summary', index=False)
            df_a.to_excel(writer, sheet_name='Ledger_A_Report', index=False)
            df_b.to_excel(writer, sheet_name='Ledger_B_Report', index=False)

        st.success("Two-Way Reconciliation Complete!")
        st.download_button("📥 Download Full Reconciliation Report", output.getvalue(), "Two_Way_Recon.xlsx")
        
        st.subheader("High-Level Summary (Ledger A Perspective)")
        st.dataframe(pivot_df, use_container_width=True)