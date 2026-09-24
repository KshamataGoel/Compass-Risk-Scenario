import pandas as pd
pd.set_option("display.max_columns", None); pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 45)
PATH = r"C:\Users\703313047\OneDrive - Genpact\Desktop\Projects\Compass\Database\Market_Risk_Case2_2Week_History_Database.xlsx"

for sheet in ["hsbc_global_Business_Unit", "desk", "book", "portfolio_hierarchy"]:
    df = pd.read_excel(PATH, sheet_name=sheet, engine="openpyxl")
    print("\n" + "="*90 + f"\n### {sheet}\n" + "="*90); print(df.to_string(index=False))

pos = pd.read_excel(PATH, sheet_name="position", engine="openpyxl")
pos.columns = [c.replace(" (FK)","").strip() for c in pos.columns]
print("\n\n### POSITION asOfDate distribution:")
print(pos.groupby("asOfDate").size())
latest = pos["asOfDate"].max()
print(f"\nLatest asOfDate = {latest}")
cur = pos[pos["asOfDate"]==latest]
print(f"Latest snapshot: {len(cur)} positions | trades={cur['tradeId'].nunique()} | instruments={cur['instrumentId'].nunique()} | books={cur['bookId'].nunique()} | desks={cur['deskId'].nunique()}")
print("MarketValueBcy total:", cur["marketValueBcy"].sum())
print(cur[["positionId","asOfDate","bookId","tradeId","instrumentId","deskId","marketValueBcy"]].to_string(index=False))

rfo = pd.read_excel(PATH, sheet_name="risk_factor_obs", engine="openpyxl")
print("\n### risk_factor_obs dates:", sorted(rfo["observationDate"].astype(str).unique()))
