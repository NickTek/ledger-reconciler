import streamlit as st
import pandas as pd
import io
from thefuzz import fuzz

st.set_page_config(page_title="Professional Reconciler", layout="wide")

st.title("📑 Two-Way Precision Reconciler")
st.info("Logic: If a record exists in one file but not the other, status will show 'Line Missing' and the offset value will be 0.0.")

file_a = st.sidebar.file_uploader("Upload Ledger A (ERP)", type=['xlsx', 'csv'])
file_b = st.sidebar.file_uploader("Upload Ledger B (Bank)", type=['xlsx', 'csv'])

if file_a and file_b:
    df_a = pd.read_excel(file_a) if file_a.name.endswith('xlsx') else pd.read_csv(file_a)
    df_b = pd.read_excel(file_b) if file_b.name.endswith('xlsx') else pd.read_csv(file_b)
    
    st.subheader("🔍 Column Configuration")
    c1, c2 = st.columns(2)
    with c1:
        st.info("Ledger A Settings")
        m_a1 = st.selectbox("Match Field 1", df_a.columns, key="ma1")
        m_a2 = st.selectbox("Match Field 2", df_a.columns, key="ma2")
        recon_a = st.selectbox("Reconcile Amount (A)", df_a.columns, key="ra")
    with c2:
        st.info("Ledger B Settings")
        m_b1 = st.selectbox("Match Field 1", df_b.columns, key="mb1")
        m_b2 = st.selectbox("Match Field 2", df_b.columns, key="mb2")
        recon_b = st.selectbox("Reconcile Amount (B)", df_b.columns, key="rb")

    if st.button("🚀 Run Full Two-Way Match"):
        # 1. Initialize Columns for Ledger A
        df_a['Recon_Status'] = 'Line Missing'
        df_a['Value_from_B'] = 0.0
        df_a['Difference'] = df_a[recon_a]
        
        # 2. Initialize Columns for Ledger B
        df_b['Recon_Status'] = 'Line Missing'
        df_b['Value_from_A'] = 0.0
        df_b['Difference'] = df_b[recon_b]
        
        used_b_indices = set()

        # 3. Match Ledger A -> Ledger B
        for idx_a, row_a in df_a.iterrows():
            key_a = f"{row_a[m_a1]} {row_a[m_a2]}".lower().strip()
            val_a = round(float(row_a[recon_a]), 2)

            best_score = -1
            best_idx_b = None

            # Filter B for candidates not already matched
            candidates = df_b[~df_b.index.isin(used_b_indices)]
            
            for idx_b, row_b in candidates.iterrows():
                key_b = f"{row_b[m_b1]} {row_b[m_b2]}".lower().strip()
                score = fuzz.token_sort_ratio(key_a, key_b)
                if score > best_score:
                    best_score = score
                    best_idx_b = idx_b
                if score == 100: break

            # 4. Identity Found - Now Check Values
            if best_score >= 90:
                val_b = round(float(df_b.at[best_idx_b, recon_b]), 2)
                diff = round(val_a - val_b, 2)
                
                # Update Ledger A
                df_a.at[idx_a, 'Value_from_B'] = val_b
                df_a.at[idx_a, 'Difference'] = diff
                
                # Update Ledger B
                df_b.at[best_idx_b, 'Value_from_A'] = val_a
                df_b.at[best_idx_b, 'Difference'] = round(val_b - val_a, 2)
                
                if diff == 0:
                    status = 'Matched'
                else:
                    status = 'Unmatched (Value Mismatch)'
                
                df_a.at[idx_a, 'Recon_Status'] = status
                df_b.at[best_idx_b, 'Recon_Status'] = status
                used_b_indices.add(best_idx_b)

        # 5. Create Summary Pivot for Sheet 1
        pivot_df = df_a.groupby('Recon_Status').agg({
            recon_a: 'sum',
            'Value_from_B': 'sum',
            'Difference': 'sum',
            'Recon_Status': 'count'
        }).rename(columns={'Recon_Status': 'Transaction Count'}).reset_index()

        # 6. Excel Export with all sheets
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pivot_df.to_excel(writer, sheet_name='Summary_Pivot', index=False)
            df_a.to_excel(writer, sheet_name='Ledger_A_Results', index=False)
            df_b.to_excel(writer, sheet_name='Ledger_B_Results', index=False)

        st.success("Reconciliation Report Generated!")
        st.download_button("📥 Download Multi-Sheet Report", output.getvalue(), "Reconciliation_Final.xlsx")
        st.table(pivot_df)