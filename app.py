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
        if pd.api.types.is_numeric_dtype(df[col]) and not mapping['amount']:
            if 'bal' not in col_clean:
                mapping['amount'] = col
        if any(key in col_clean for key in ['ref', 'desc', 'memo', 'doc', 'particulars']):
            mapping['ref'] = col
        if not mapping['date']:
            try:
                pd.to_datetime(df[col].head(3))
                mapping['date'] = col
            except: pass
    return mapping

st.title("📑 Professional Ledger Reconciler")

file_a = st.sidebar.file_uploader("Upload Ledger A (ERP)", type=['xlsx', 'csv'])
file_b = st.sidebar.file_uploader("Upload Ledger B (Bank)", type=['xlsx', 'csv'])

if file_a and file_b:
    df_a = pd.read_excel(file_a) if file_a.name.endswith('xlsx') else pd.read_csv(file_a)
    df_b = pd.read_excel(file_b) if file_b.name.endswith('xlsx') else pd.read_csv(file_b)
    
    map_a = find_columns(df_a)
    map_b = find_columns(df_b)
    
    st.subheader("Mapping Discovery")
    c1, c2 = st.columns(2)
    c1.write(f"**Ledger A:** Amount: `{map_a['amount']}` | Ref: `{map_a['ref']}`")
    c2.write(f"**Ledger B:** Amount: `{map_b['amount']}` | Ref: `{map_b['ref']}`")

    if st.button("🚀 Run Reconciliation Report"):
        # Setup columns
        df_a['Recon_Status'] = 'Unmatched'
        df_a['B_Amount'] = 0.0
        df_a['Difference'] = df_a[map_a['amount']]
        
        used_indices_b = set()

        # Matching Loop
        for idx_a, row_a in df_a.iterrows():
            amt_a = round(float(row_a[map_a['amount']]), 2)
            ref_a = str(row_a[map_a['ref']]) if map_a['ref'] else ""

            # Find candidates in B with identical amount (exact match for safety)
            candidates = df_b[
                (df_b[map_b['amount']].round(2) == amt_a) & 
                (~df_b.index.isin(used_indices_b))
            ]

            if not candidates.empty:
                best_score = -1
                best_idx_b = None
                
                for idx_b, row_b in candidates.iterrows():
                    ref_b = str(row_b[map_b['ref']]) if map_b['ref'] else ""
                    score = fuzz.token_sort_ratio(ref_a, ref_b)
                    if score > best_score:
                        best_score = score
                        best_idx_b = idx_b
                
                if best_score >= 70 or len(candidates) == 1:
                    # Update Ledger A with B's data
                    val_b = df_b.at[best_idx_b, map_b['amount']]
                    df_a.at[idx_a, 'Recon_Status'] = 'Matched'
                    df_a.at[idx_a, 'B_Amount'] = val_b
                    df_a.at[idx_a, 'Difference'] = amt_a - val_b
                    used_indices_b.add(best_idx_b)

        # Create Pivot Summary
        pivot_df = df_a.groupby('Recon_Status').agg({
            map_a['amount']: 'sum',
            'B_Amount': 'sum',
            'Difference': 'sum',
            'Recon_Status': 'count'
        }).rename(columns={'Recon_Status': 'Transaction_Count'}).reset_index()

        # Excel Export with multiple sheets
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Sheet 1: Pivot Summary
            pivot_df.to_excel(writer, sheet_name='Summary_Pivot', index=False)
            
            # Sheet 2: Detailed Recon
            df_a.to_excel(writer, sheet_name='Reconciled_Data', index=False)
            
            # Formatting
            workbook = writer.book
            summary_sheet = writer.sheets['Summary_Pivot']
            header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
            for col_num, value in enumerate(pivot_df.columns.values):
                summary_sheet.write(0, col_num, value, header_format)

        st.success("Reconciliation Report Generated!")
        st.download_button(
            label="📥 Download Multi-Sheet Report",
            data=output.getvalue(),
            file_name="Reconciliation_Final_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.subheader("Quick Preview: Pivot Summary")
        st.table(pivot_df)