
import streamlit as st
import pandas as pd
import io, re
from sampler import run_sampling
from utils_app import detect_columns, to_excel_bytes, read_any, build_printable_workbook_per_kebele

st.set_page_config(page_title="PPS Village Sampling (WFP Somali Region AO)", layout="wide")

st.title("PPS Village Sampling App")
st.caption("WFP Ethiopia – Somali Region AO | Jijiga Area Office")

with st.expander("ℹ️ What this app does", expanded=False):
    st.markdown("""
- **PPS per kebele** (MOS = total HHs) to pick **up to 2 villages**.
- **Main sample:** per selected village draw **15 Eligible + 15 Non‑eligible**; if only one village exists, it gets **30 per group**.
- **Reserves:** **4** per group per selected village (two-village case) or **8** if one village.
- **Rebalancing (main only)** within kebele and group.
- **No overlap** between main and reserves.
- **Reproducible** with a **random seed** (default `20251031`).
- Exports: `Sampled_HHs_Primary_FullColumns`, `Sampled_HHs_Reserves_FullColumns`, `Village_PPS_Selection`, `Kebele_Group_Summary`, `Kebele_Summary_Rollup`.
- Optional **field-team printable workbook** (one sheet per kebele).
    """)

st.subheader("1) Upload your household frame")
up = st.file_uploader("Upload XLSX or CSV", type=["xlsx","xls","csv"])

col1, col2, col3 = st.columns(3)
seed = col1.number_input("Random seed", value=20251031, step=1)
two_vill_target = col2.number_input("Target per group (two villages)", value=15, step=1)
one_vill_target = col3.number_input("Target per group (one village)", value=30, step=1)
rcol1, rcol2 = st.columns(2)
res_two = rcol1.number_input("Reserves per village per group (two villages)", value=4, step=1)
res_one = rcol2.number_input("Reserves per village per group (one village)", value=8, step=1)

gen_printable = st.checkbox("Also generate a field-team printable workbook (one sheet per kebele)", value=True)

st.subheader("2) Map columns (auto-detected, adjust if needed)")
if up:
    df = read_any(up)
    guess = detect_columns(df)
    c1, c2, c3, c4 = st.columns(4)
    woreda_col = c1.selectbox("Woreda column (optional)", [None] + list(df.columns), index=(list(df.columns).index(guess["woreda"]) + 1) if guess["woreda"] in df.columns else 0)
    kebele_col = c2.selectbox("Kebele column (required)", list(df.columns), index=(list(df.columns).index(guess["kebele"]) if guess["kebele"] in df.columns else 0))
    village_col = c3.selectbox("Village column (required)", list(df.columns), index=(list(df.columns).index(guess["village"]) if guess["village"] in df.columns else 0))
    elig_col = c4.selectbox("Eligibility column (Eligible / Non‑eligible)", [None] + list(df.columns), index=(list(df.columns).index(guess["eligibility"]) + 1) if guess["eligibility"] in df.columns else 0)

    st.divider()
    run = st.button("▶️ Run PPS Sampling")
    demo = st.button("🧪 Demo mode (use bundled sample)")

    if run or demo:
        if demo:
            # load bundled sample
            demo_path = 'data/sample_input.xlsx'
            try:
                df = pd.read_excel(demo_path, engine='openpyxl')
                woreda_col = 'Woreda'; kebele_col = 'Kebele'; village_col = 'Village'; elig_col = 'Eligibility'
            except Exception as e:
                st.error(f"Demo sample not found or unreadable: {e}")
                st.stop()

        with st.spinner("Running PPS selection and drawing samples..."):
            col_map = {
                "woreda": woreda_col,
                "kebele": kebele_col,
                "village": village_col,
                "eligibility": elig_col
            }
            out = run_sampling(
                df_raw=df,
                col_map=col_map,
                seed=int(seed),
                targets=(int(two_vill_target), int(one_vill_target)),
                reserves=(int(res_two), int(res_one))
            )

        st.success("Done.")

        n_kebeles = out["kroll_df"]["Kebele"].nunique() if not out["kroll_df"].empty else 0
        n_primary = len(out["primary_df"])
        n_reserve = len(out["reserve_df"])
        m1, m2, m3 = st.columns(3)
        m1.metric("Kebeles", n_kebeles)
        m2.metric("Primary HHs", n_primary)
        m3.metric("Reserve HHs", n_reserve)

        st.subheader("3) Review (peek)")
        st.write("**Village PPS Selection (head)**")
        st.dataframe(out["pps_df"].head(20), use_container_width=True, hide_index=True)
        st.write("**Kebele Group Summary (head)**")
        st.dataframe(out["kgrp_df"].head(20), use_container_width=True, hide_index=True)

        main_excel = to_excel_bytes({
            "Sampled_HHs_Primary_FullColumns": out["primary_df"],
            "Sampled_HHs_Reserves_FullColumns": out["reserve_df"],
            "Village_PPS_Selection": out["pps_df"],
            "Kebele_Group_Summary": out["kgrp_df"],
            "Kebele_Summary_Rollup": out["kroll_df"],
        })
        st.download_button(
            "⬇️ Download main Excel (5 sheets)",
            data=main_excel,
            file_name="PPS_Sample_Plan_FullOutputs.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Optional printable workbook (guarded)
        if gen_printable:
            if out["printable_df"].empty:
                st.info("No sampled households to print yet. Run sampling or adjust parameters.")
            else:
                printable_excel = build_printable_workbook_per_kebele(out["printable_df"])
                st.download_button(
                    "⬇️ Download Field-Team Printable Workbook (one sheet per kebele)",
                    data=printable_excel,
                    file_name="FieldTeam_Printable_List.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        # Validation expander (compare against a reference workbook)
        with st.expander("✅ Validate against expected workbook (optional)", expanded=False):
            ref = st.file_uploader("Upload expected output Excel", type=["xlsx"], key="ref")
            if ref is not None:
                def read_xlsx_bytes(b):
                    xf = pd.ExcelFile(io.BytesIO(b), engine="openpyxl")
                    return {s: xf.parse(s) for s in xf.sheet_names}

                produced = read_xlsx_bytes(main_excel)
                expected = read_xlsx_bytes(ref.read())

                req = [
                    "Sampled_HHs_Primary_FullColumns",
                    "Sampled_HHs_Reserves_FullColumns",
                    "Village_PPS_Selection",
                    "Kebele_Group_Summary",
                    "Kebele_Summary_Rollup"
                ]
                msgs = []
                ok = True
                for s in req:
                    if s not in produced:
                        msgs.append(f"❌ Missing in produced: {s}"); ok=False
                    if s not in expected:
                        msgs.append(f"❌ Missing in expected: {s}"); ok=False
                for s in req:
                    if s in produced and s in expected:
                        if list(produced[s].columns) != list(expected[s].columns):
                            ok=False
                            msgs.append(f"❌ [{s}] columns differ.")
                rx = re.compile(r"^PPS-(PR|RP)-.+-.+-(EL|NE)-\d{2}$")
                if "Sampled_HHs_Primary_FullColumns" in produced and "Sampled_HHs_Reserves_FullColumns" in produced:
                    for name in ["Sampled_HHs_Primary_FullColumns","Sampled_HHs_Reserves_FullColumns"]:
                        if "Sample ID" not in produced[name].columns:
                            msgs.append(f"❌ [{name}] missing 'Sample ID'"); ok=False
                        else:
                            bad = produced[name]["Sample ID"].astype(str).map(lambda x: bool(rx.match(x))).eq(False).sum()
                            if bad>0: msgs.append(f"❌ [{name}] invalid Sample ID format ({bad})."); ok=False
                    a = set(produced["Sampled_HHs_Primary_FullColumns"]["Sample ID"].astype(str))
                    b = set(produced["Sampled_HHs_Reserves_FullColumns"]["Sample ID"].astype(str))
                    if a & b:
                        msgs.append("❌ Overlap between Primary and Replacement Sample IDs."); ok=False
                if ok:
                    st.success("✅ Validation passed.")
                else:
                    st.error("❌ Validation failed.")
                    for m in msgs:
                        st.write(m)
else:
    st.info("Upload an Excel/CSV household frame to begin.")

st.divider()
with st.expander("📄 Download a sample template (optional)"):
    tmpl = pd.DataFrame({
        "Woreda": ["Karsadula","Karsadula"],
        "Kebele": ["Baabul","Baabul"],
        "Village": ["Village-1","Village-1"],
        "Eligibility": ["Eligible","Non-eligible"],
        "HH_ID": ["HH-0001","HH-0002"],
        "HH_Name": ["Amina Ahmed","Hassan Ismail"],
        "Phone": ["",""]
    })
    from utils_app import to_excel_bytes
    st.download_button(
        "⬇️ sample_template.xlsx",
        data=to_excel_bytes({"Template": tmpl}),
        file_name="sample_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.caption("© WFP Somali Region AO — Built for reproducible, PPS-based village sampling.")
