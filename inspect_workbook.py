"""Inspect the Market Risk workbook — sheets, columns, dtypes, sample rows, row counts."""
import pandas as pd
import json
import sys

PATH = r"C:\Users\703313047\OneDrive - Genpact\Desktop\Projects\Compass\Database\Market_Risk_Case2_2Week_History_Database.xlsx"

xls = pd.ExcelFile(PATH, engine="openpyxl")
print("=" * 80)
print(f"SHEETS ({len(xls.sheet_names)}):")
for s in xls.sheet_names:
    print(f"  - {s}")
print("=" * 80)

for sheet in xls.sheet_names:
    df = pd.read_excel(PATH, sheet_name=sheet, engine="openpyxl")
    print(f"\n### SHEET: {sheet}  | rows={len(df)}  cols={len(df.columns)}")
    print("-" * 70)
    for col in df.columns:
        non_null = df[col].notna().sum()
        dtype = str(df[col].dtype)
        # sample distinct
        vals = df[col].dropna().unique()
        sample = list(vals[:4])
        sample_str = ", ".join(str(v)[:30] for v in sample)
        print(f"  {col:38s} | {dtype:12s} | nn={non_null:4d} | uniq={df[col].nunique():4d} | e.g. {sample_str}")
