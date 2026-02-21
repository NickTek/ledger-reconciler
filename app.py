import streamlit as st
import pandas as pd
import io
from thefuzz import fuzz

st.set_page_config(page_title="Professional Reconciler", layout="wide")

st.title("📑 Precision Ledger Reconciler")
st.markdown("---")

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

    if st.button("🚀 Run Reconciliation"):
        # Initialize Ledger A columns
        df_a['Recon_Status'] = 'Unmatched'
        df_a['B_Amount_Matched'] = 0.0  # Explicitly zero if no match
        df_a['Difference'] = df_a[recon_a]
        
        # Initialize Ledger B columns for the return file
        df_b['Recon_Status'] = 'Unmatched'
        
        used_b = set()

        for idx_a, row_a in df_a.iterrows():
            key_a = f"{row_a[m_a1]} {row_a[m_a2]}".lower().strip()
            val_a = round(float(row_a[recon_a]), 2)

            best_score = -1
            best_idx_b = None

            # Look for best identity match in B
            for idx_b, row_b in df_b[~df_b.index.isin(used_b)].iterrows():
                key_b = f"{row_b[m_b1]} {row_b[m_b2]}".lower().strip()
                score = fuzz.token_sort_ratio(key_a, key_b)
                if score > best_score:
                    best_score = score
                    best_idx_b = idx_b
                if score == 100: break

            # Process the match
            if best_score >= 90:
                val_b = round(float(df_b.at[best_idx_b, recon_b]), 2)
                diff = round(val_a - val_b, 2)
                
                df_a.at[idx_a, 'B_Amount_Matched'] = val_b
                df_a.at[idx_a, 'Difference'] = diff
                
                if diff == 0:
                    df_a.at[idx_a, 'Recon_Status'] = 'Matched'
                    df_b.at[best_idx_b, 'Recon_Status'] = 'Matched'
                else:
                    df_a.at[idx_a, 'Recon_Status'] = 'Unmatched (Value Mismatch)'
                    df_b.at[best_idx_b, 'Recon_Status'] = 'Unmatched (Value Mismatch)'
                
                used_b.add(best_idx_b)
            else:
                # Force zero if no match found
                df_a.at[idx_a, 'B_Amount_Matched'] = 0.0
                df_a.at[idx_a, 'Difference'] = val_a

        # Pivot Summary
        pivot_df = df_a.groupby('Recon_Status').agg({
            recon_a: 'sum',
            'B_Amount_Matched': 'sum',
            'Difference': 'sum',
            'Recon_Status': 'count'
        }).rename(columns={'Recon_Status': 'Count'}).reset_index()

        # Excel Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pivot_df.to_excel(writer, sheet_name='Summary', index=False)
            df_a.to_excel(writer, sheet_name='Ledger_A_Reconciled', index=False)
            df_b.to_excel(writer, sheet_name='Ledger_B_Reconciled', index=False)

        st.success("Reconciliation Complete!")
        st.download_button("📥 Download Combined Report", output.getvalue(), "Recon_Results.xlsx")
        st.subheader("Summary Table")
        st.dataframe(pivot_df, use_container_width=True)