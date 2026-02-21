import streamlit as st
import pandas as pd
import io
from thefuzz import fuzz

st.set_page_config(page_title="Precision Reconciler", layout="wide")

st.title("📑 Precision Ledger Reconciler")
st.markdown("---")

# Sidebar for File Uploads
file_a = st.sidebar.file_uploader("Upload Ledger A (ERP)", type=['xlsx', 'csv'])
file_b = st.sidebar.file_uploader("Upload Ledger B (Bank)", type=['xlsx', 'csv'])

if file_a and file_b:
    df_a = pd.read_excel(file_a) if file_a.name.endswith('xlsx') else pd.read_csv(file_a)
    df_b = pd.read_excel(file_b) if file_b.name.endswith('xlsx') else pd.read_csv(file_b)
    
    st.subheader("🔍 Column Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("Ledger A Settings")
        match_a_1 = st.selectbox("Primary Match Field (e.g. ID)", df_a.columns, key="ma1")
        match_a_2 = st.selectbox("Secondary Match Field (e.g. Date)", df_a.columns, key="ma2")
        recon_a = st.selectbox("Column to RECONCILE (Value)", df_a.columns, key="ra")
        
    with col2:
        st.info("Ledger B Settings")
        match_b_1 = st.selectbox("Primary Match Field (e.g. ID)", df_b.columns, key="mb1")
        match_b_2 = st.selectbox("Secondary Match Field (e.g. Date)", df_b.columns, key="mb2")
        recon_b = st.selectbox("Column to RECONCILE (Value)", df_b.columns, key="rb")

    if st.button("🚀 Run Precision Reconciliation"):
        # 1. Initialize Results Columns
        df_a['Recon_Status'] = 'Unmatched'
        df_a['B_Value'] = 0.0
        df_a['Difference'] = df_a[recon_a] # Default difference is the total A value
        
        used_indices_b = set()

        # 2. Matching Logic
        for idx_a, row_a in df_a.iterrows():
            # Construct comparison keys
            key_a = f"{str(row_a[match_a_1])} | {str(row_a[match_a_2])}"
            val_a = round(float(row_a[recon_a]), 2)

            # Look for candidates in B that haven't been used yet
            candidates = df_b[~df_b.index.isin(used_indices_b)]
            
            best_score = -1
            best_idx_b = None

            for idx_b, row_b in candidates.iterrows():
                key_b = f"{str(row_b[match_b_1])} | {str(row_b[match_b_2])}"
                
                # Using fuzzy matching for the identity keys
                score = fuzz.token_sort_ratio(key_a, key_b)
                if score > best_score:
                    best_score = score
                    best_idx_b = idx_b
                if score == 100: break

            # 3. Validation Logic
            if best_score >= 90: # High-confidence ID match
                val_b = round(float(df_b.at[best_idx_b, recon_b]), 2)
                diff = round(val_a - val_b, 2)
                
                df_a.at[idx_a, 'B_Value'] = val_b
                df_a.at[idx_a, 'Difference'] = diff
                
                # Strict Status Requirement: Only 'Matched' if difference is 0
                if diff == 0:
                    df_a.at[idx_a, 'Recon_Status'] = 'Matched'
                else:
                    df_a.at[idx_a, 'Recon_Status'] = 'Unmatched (Value Mismatch)'
                
                used_indices_b.add(best_idx_b)

        # 4. Create Pivot Summary
        pivot_df = df_a.groupby('Recon_Status').agg({
            recon_a: 'sum',
            'B_Value': 'sum',
            'Difference': 'sum',
            'Recon_Status': 'count'
        }).rename(columns={'Recon_Status': 'Transaction Count'}).reset_index()

        # 5. Visual Summary & Download
        st.divider()
        st.subheader("📊 Reconciliation Summary")
        st.table(pivot_df)

        # Excel Export Logic
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pivot_df.to_excel(writer, sheet_name='Summary Pivot', index=False)
            df_a.to_excel(writer, sheet_name='Detailed Comparison', index=False)
            
            # Formatting the Excel
            workbook = writer.book
            worksheet = writer.sheets['Detailed Comparison']
            money_fmt = workbook.add_format({'num_format': '#,##0.00'})
            worksheet.set_column('A:Z', 15, money_fmt)

        st.download_button(
            label="📥 Download Detailed Excel Report",
            data=output.getvalue(),
            file_name="Reconciliation_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )