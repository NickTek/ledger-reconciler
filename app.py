import streamlit as st
import pandas as pd
import io
from thefuzz import fuzz

st.set_page_config(page_title="Two-Way Reconciler", layout="wide")

st.title("📑Ledger Reconciler")
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
        m_a1 = st.selectbox("Match Field 1 (Primary)", df_a.columns, key="ma1")
        m_a2 = st.selectbox("Match Field 2 (Secondary)", df_a.columns, key="ma2")
        recon_a = st.selectbox("Reconcile Amount (A)", df_a.columns, key="ra")
    with c2:
        st.info("Ledger B Settings")
        m_b1 = st.selectbox("Match Field 1 (Primary)", df_b.columns, key="mb1")
        m_b2 = st.selectbox("Match Field 2 (Secondary)", df_b.columns, key="mb2")
        recon_b = st.selectbox("Reconcile Amount (B)", df_b.columns, key="rb")

    if st.button("🚀 Run Two-Way Reconciliation"):
        # 1. Initialize Columns for both files with 'Line Missing' as the default
        df_a['Recon_Status'] = 'Line Missing'
        df_a['Counterpart_Amount'] = 0.0
        df_a['Variance'] = df_a[recon_a]
        
        df_b['Recon_Status'] = 'Line Missing'
        df_b['Counterpart_Amount'] = 0.0
        df_b['Variance'] = df_b[recon_b]
        
        used_b_indices = set()

        # 2. Matching Engine (A -> B)
        for idx_a, row_a in df_a.iterrows():
            key_a = f"{row_a[m_a1]} {row_a[m_a2]}".lower().strip()
            val_a = round(float(row_a[recon_a]), 2)

            best_score = -1
            best_idx_b = None

            # Scan unmatched rows in B
            candidates = df_b[~df_b.index.isin(used_b_indices)]
            for idx_b, row_b in candidates.iterrows():
                key_b = f"{row_b[m_b1]} {row_b[m_b2]}".lower().strip()
                score = fuzz.token_sort_ratio(key_a, key_b)
                
                if score > best_score:
                    best_score = score
                    best_idx_b = idx_b
                if score == 100: break

            # 3. Apply Matching Logic
            if best_score >= 90:
                val_b = round(float(df_b.at[best_idx_b, recon_b]), 2)
                diff = round(val_a - val_b, 2)
                
                # Update Ledger A
                df_a.at[idx_a, 'Counterpart_Amount'] = val_b
                df_a.at[idx_a, 'Variance'] = diff
                
                # Update Ledger B
                df_b.at[best_idx_b, 'Counterpart_Amount'] = val_a
                df_b.at[best_idx_b, 'Variance'] = round(val_b - val_a, 2)
                
                status = 'Matched' if diff == 0 else 'Unmatched (Value Mismatch)'
                df_a.at[idx_a, 'Recon_Status'] = status
                df_b.at[best_idx_b, 'Recon_Status'] = status
                
                used_b_indices.add(best_idx_b)

        # 4. Final Cleanup: Ensure 'Line Missing' rows show 0.0 correctly
        # (Handled by initial setup, but confirms logic for the pivot)

        # 5. Create Summary Pivot
        pivot_df = df_a.groupby('Recon_Status').agg({
            recon_a: 'sum',
            'Counterpart_Amount': 'sum',
            'Variance': 'sum',
            'Recon_Status': 'count'
        }).rename(columns={'Recon_Status': 'Line Count'}).reset_index()

        # 6. Multi-Sheet Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pivot_df.to_excel(writer, sheet_name='Executive Summary', index=False)
            df_a.to_excel(writer, sheet_name='Ledger_A_Check', index=False)
            df_b.to_excel(writer, sheet_name='Ledger_B_Check', index=False)

        st.success("Analysis Complete!")
        st.download_button("📥 Download Combined Report", output.getvalue(), "Two_Way_Reconciliation.xlsx")
        
        st.subheader("📊 Summary Statistics")
        st.dataframe(pivot_df, use_container_width=True)