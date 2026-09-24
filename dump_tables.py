"""Dump full contents of key small tables to understand exact joins."""
import pandas as pd
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 40)

PATH = r"C:\Users\703313047\OneDrive - Genpact\Desktop\Projects\Compass\Database\Market_Risk_Case2_2Week_History_Database.xlsx"

for sheet in ["risk_metric", "risk_metric_mr", "risk_metric_mr_obs", "risk_metric_obs",
              "risk_threshold", "risk_measure", "risk", "risk_factor", "scenario_mr",
              "risk_factor_shock", "sensitivity", "asset_class", "instrument",
              "risk_pnl_record", "risk_threshold_breach"]:
    df = pd.read_excel(PATH, sheet_name=sheet, engine="openpyxl")
    print("\n" + "=" * 100)
    print(f"### {sheet}")
    print("=" * 100)
    print(df.to_string(index=False))
