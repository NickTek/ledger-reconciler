import streamlit as st
import pandas as pd
import io
from thefuzz import fuzz

st.set_page_config(page_title="Custom AI Reconciler", layout="wide")

def get_options(df):
    return ["None"] + list(df.columns)

st.title("📑 Precision Ledger Reconciler")

# Sidebar for File Uploads
file_a = st.sidebar.file_uploader("Upload Ledger A (ERP)", type=['xlsx', 'csv'])
file_b = st.sidebar.file_uploader("Upload Ledger B (Bank/Other)", type=['xlsx', 'csv'])

if file_a and file_b:
    df_a = pd.read_excel(file_a) if file_a.name.endswith('xlsx') else pd.read_csv(file_a)
    df_b = pd.read_excel(file_b) if file_b.name.endswith('xlsx') else pd.read_csv(file_b)
    
    st.subheader("⚙️ Configure Matching Logic")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### Ledger A Settings")
        match_col_a = st.selectbox("Column to MATCH (e.g., ID, Ref, Invoice)", df_a.columns, key="ma")
        recon_col_a = st.selectbox("Column to RECONCILE (e.g., Total Amount)", df_a.columns, key="ra")
        
    with col2:
        st.write("### Ledger B Settings")
        match_col_b = st.selectbox("Column to MATCH (e.g., Description, ID)", df_b.columns, key="mb")
        recon_col_b = st.selectbox("Column to RECONCILE (e.g., Statement Amount)", df_b.columns, key="rb")

    if st.button("🚀 Run Custom Reconciliation"):
        # Initialize columns
        df_a['Recon_Status'] = 'Unmatched'
        df_a[f'B_{recon_col_b}'] = 0.0
        df_a['Difference'] = df_a[recon_col_a] # Default diff is the full amount
        
        used_indices_b = set()

        for idx_a, row_a in df_a.iterrows():
            # Get the ID/Line to match on
            id_a = str(row_a[match_col_a])
            val_a = float(row_a[recon_col_a])

            # Filter B for potential matches based on ID similarity or exact match
            # Here we use fuzzy matching on the IDs specifically
            best_score = -1
            best_idx_b = None
            
            # Optimization: only check unmatched rows in B
            candidates = df_b[~df_b.index.isin(used_indices_b)]
            
            for idx_b, row_b in candidates.iterrows():
                id_b = str(row_b[match_col_b])
                
                # Check for ID match
                score = fuzz.token_sort_ratio(id_a, id_b)
                
                if score > best_score:
                    best_score = score
                    best_idx_b = idx_b
                
                # Exit early if perfect ID match found
                if score == 100:
                    break
            
            # If ID match is strong (e.g. >80), reconcile the amounts
            if best_score >= 80:
                val_b = float(df_b.at[best_idx_b, recon_col_b])
                df_a.at[idx_a, 'Recon_Status'] = 'Matched'
                df_a.at[idx_a, f'B_{recon_col_b}'] = val_b
                df_a.at[idx_a, 'Difference'] = val_a - val_b
                used_indices_b.add(best_idx_b)

        # Create Pivot
        pivot_df = df_a.groupby('Recon_Status').agg({
            recon_col_a: 'sum',
            f'B_{recon_col_b}': 'sum',
            'Difference': 'sum',
            'Recon_Status': 'count'
        }).rename(columns={'Recon_Status': 'Count'}).reset_index()

        # Excel Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pivot_df.to_excel(writer, sheet_name='Summary', index=False)
            df_a.to_excel(writer, sheet_name='Details', index=False)
            
            # Auto-adjust column widths
            for sheet in writer.sheets.values():
                sheet.set_column('A:Z', 18)

        st.success("Analysis Complete!")
        st.download_button("📥 Download Report", output.getvalue(), "Recon_Analysis.xlsx")
        st.table(pivot_df)