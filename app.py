import streamlit as st
import pandas as pd
import io
from thefuzz import fuzz

# Page Config
st.set_page_config(page_title="Private AI Reconciler", layout="wide")

def find_columns(df):
    """Smart detection of Date, Amount, and Reference columns"""
    mapping = {'amount': None, 'ref': None, 'date': None}
    for col in df.columns:
        col_clean = str(col).lower().strip()
        # Detect Amount
        if pd.api.types.is_numeric_dtype(df[col]) and not mapping['amount']:
            if 'bal' not in col_clean:
                mapping['amount'] = col
        # Detect Reference/Description
        if any(key in col_clean for key in ['ref', 'desc', 'memo', 'doc', 'particulars']):
            mapping['ref'] = col
        # Detect Date
        if not mapping['date']:
            try:
                pd.to_datetime(df[col].head(3))
                mapping['date'] = col
            except: pass
    return mapping

st.title("📑 Professional Ledger Reconciler")
st.info("Privacy Mode: Active. Data is processed in-memory and never sent to third-party AI APIs.")

# File Uploaders
col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Upload Ledger A (e.g. ERP)", type=['xlsx', 'csv'])
with col2:
    file_b = st.file_uploader("Upload Ledger B (e.g. Bank)", type=['xlsx', 'csv'])

if file_a and file_b:
    # Load Data
    df_a = pd.read_excel(file_a) if file_a.name.endswith('xlsx') else pd.read_csv(file_a)
    df_b = pd.read_excel(file_b) if file_b.name.endswith('xlsx') else pd.read_csv(file_b)
    
    # Auto-Map Columns
    map_a = find_columns(df_a)
    map_b = find_columns(df_b)
    
    st.subheader("Automated Mapping Verification")
    st.write(f"**Ledger A:** Amount: `{map_a['amount']}` | Ref: `{map_a['ref']}`")
    st.write(f"**Ledger B:** Amount: `{map_b['amount']}` | Ref: `{map_b['ref']}`")

    if st.button("🚀 Start Smart Reconciliation"):
        # 1. Preparation
        df_a['Recon_Status'] = 'Unmatched'
        df_a['Similarity_Score'] = 0
        df_b['Recon_Status'] = 'Unmatched'
        
        used_indices_b = set()

        # 2. Matching Logic (Primary: Amount, Secondary: Fuzzy Ref)
        for idx_a, row_a in df_a.iterrows():
            amt_a = round(float(row_a[map_a['amount']]), 2)
            ref_a = str(row_a[map_a['ref']]) if map_a['ref'] else ""

            # Find candidates in B with identical amount
            candidates = df_b[
                (df_b[map_b['amount']].round(2) == amt_a) & 
                (~df_b.index.isin(used_indices_b))
            ]

            if not candidates.empty:
                best_score = -1
                best_idx_b = None
                
                for idx_b, row_b in candidates.iterrows():
                    ref_b = str(row_b[map_b['ref']]) if map_b['ref'] else ""
                    # Calculate Fuzzy Similarity (0-100)
                    score = fuzz.token_sort_ratio(ref_a, ref_b)
                    
                    if score > best_score:
                        best_score = score
                        best_idx_b = idx_b
                
                # Validation: Match if score > 70 or if it's the only amount match
                if best_score >= 70 or len(candidates) == 1:
                    df_a.at[idx_a, 'Recon_Status'] = 'Matched'
                    df_a.at[idx_a, 'Similarity_Score'] = best_score
                    df_b.at[best_idx_b, 'Recon_Status'] = 'Matched'
                    used_indices_b.add(best_idx_b)

        # 3. Summary & Downloads
        st.success("Reconciliation Complete!")
        total_matched = df_a[df_a['Recon_Status'] == 'Matched'][map_a['amount']].sum()
        st.metric("Total Matched Volume", f"${total_matched:,.2f}")

        def convert_df(df):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()

        st.download_button("📥 Download Reconciled Ledger A", convert_df(df_a), "Ledger_A_Results.xlsx")
        st.download_button("📥 Download Reconciled Ledger B", convert_df(df_b), "Ledger_B_Results.xlsx")