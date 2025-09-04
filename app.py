
import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="MLP Lookup", page_icon="🔎", layout="centered")

# ------------------------
# Data loading
# ------------------------
@st.cache_data
def load_catalog(path: str = "products.csv"):
    df = pd.read_csv(path, dtype=str).fillna("")
    # Normalize a matching key (case-insensitive, trim spaces)
    if "Model" not in df.columns:
        raise ValueError("products.csv must have a 'Model' column")
    df["_key"] = df["Model"].astype(str).str.strip().str.upper()
    return df

cat = load_catalog()

st.title("🔎 MLP Lookup (Paste from Excel)")
st.caption("Excel se **Model** column copy karke yahan paste karein. 1 se 200+ models supported.")

with st.expander("How to use (quick)", expanded=True):
    st.markdown(
        '''
        1. Apni **Excel** file kholein → **Model** wale **column** ko select kijiye → **Ctrl+C**.
        2. Niche **Paste box** me **Ctrl+V** kijiye (new lines auto-handle ho jati hain).
        3. **Find MLPs** dabaiye → results table me MLP & Description dikh jayega.
        4. **Download CSV** se result download kar sakte hain.
        
        **Tips**
        - Matching **exact model code** par hota hai (case-insensitive, extra spaces ignored).
        - Duplicate models ko input order preserve karte hue unique treat kiya jata hai.
        - Not found models ko **Status** column me highlight kiya jata hai.
        '''
    )

# ------------------------
# Input Area
# ------------------------
user_text = st.text_area("Paste your Model(s) here:", height=180, placeholder="PRD-1001
PRD-1003
PRD-2005")

colA, colB, colC = st.columns([1,1,1])
with colA:
    keep_order = st.checkbox("Keep input order", value=True)
with colB:
    show_only_not_found = st.checkbox("Show only Not found", value=False)
with colC:
    allow_contains = st.checkbox("Use 'contains' if exact not found", value=False)

# ------------------------
# Helpers
# ------------------------
def parse_models(raw: str):
    if not raw.strip():
        return []
    # Split by newlines, commas, tabs, semicolons
    tokens = re.split(r"[
,	;]", raw)
    cleaned = []
    seen = set()
    for t in tokens:
        t2 = t.strip()
        if not t2:
            continue
        key = t2.upper()
        if key not in seen:
            seen.add(key)
            cleaned.append(t2)
    return cleaned

# ------------------------
# Search
# ------------------------
if st.button("Find MLPs", type="primary"):
    models = parse_models(user_text)
    if not models:
        st.warning("Please paste at least one model.")
        st.stop()

    # Build query frame preserving order
    q = pd.DataFrame({"Model_in": models})
    q["_key"] = q["Model_in"].str.strip().str.upper()

    # Exact match join
    res = q.merge(cat, on="_key", how="left")

    # If allow_contains and some not found, try contains match for them
    if allow_contains:
        missing_mask = res["MLP"].isna() | (res["MLP"].astype(str).str.strip() == "")
        if missing_mask.any():
            missing_keys = res.loc[missing_mask, "_key"].unique().tolist()
            # Prepare a contains map: for each missing key, try to find first catalog row containing it
            cat_lc = cat.copy()
            cat_lc["_model_uc"] = cat_lc["Model"].str.upper()
            contains_rows = []
            for key in missing_keys:
                hit = cat_lc[cat_lc["_model_uc"].str.contains(re.escape(key), na=False)]
                if not hit.empty:
                    # Take first hit
                    row = hit.iloc[0]
                    contains_rows.append({"_key": key, "Model": row["Model"], "MLP": row.get("MLP", ""), "Description": row.get("Description", "")})
            if contains_rows:
                contains_df = pd.DataFrame(contains_rows)
                res = res.drop(columns=[c for c in ["Model","MLP","Description"] if c in res.columns])                         .merge(contains_df, on="_key", how="left")

    res_display = res.copy()
    # Prefer original input model text for display
    res_display["Model"] = res_display.get("Model", "").where(res_display.get("Model").notna(), res_display["Model_in"]) if "Model" in res_display else res_display["Model_in"]

    # Status
    res_display["Status"] = res_display.get("MLP", "").apply(lambda x: "Not found" if (pd.isna(x) or str(x).strip()=="") else "OK")

    # Keep order (already preserved by q construction). Optionally filter only not found
    if show_only_not_found:
        res_display = res_display[res_display["Status"]=="Not found"]

    # Final columns order
    cols = ["Model", "MLP", "Description", "Status"]
    res_display = res_display[[c for c in cols if c in res_display.columns]]

    matched = int((res_display["Status"]=="OK").sum()) if "Status" in res_display else 0
    st.success(f"Matched {matched} of {len(res_display)}")

    # Style: highlight Not found
    def highlight_row(row):
        return ["background-color: #fde2e1" if row.get("Status") == "Not found" else "" for _ in row]

    try:
        st.dataframe(res_display.style.apply(highlight_row, axis=1), use_container_width=True)
    except Exception:
        st.dataframe(res_display, use_container_width=True)

    # Download
    csv_bytes = res_display.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Results (CSV)", data=csv_bytes, file_name="lookup_results.csv", mime="text/csv")
else:
    st.info("Excel se Model column copy karke yahan paste karein, phir **Find MLPs** dabaiye.")
