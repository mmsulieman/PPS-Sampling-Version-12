
import numpy as np
import pandas as pd
import re

def _norm(s: str) -> str:
    s = str(s)
    s = re.sub(r"[^0-9A-Za-z_]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_").lower()

def _clean_code(x):
    x = str(x)
    x = re.sub(r"[^0-9A-Za-z]+", "-", x)
    x = re.sub(r"-+", "-", x).strip("-")
    return x[:18]

def _make_ids(indices, kebele, village, group, kind):
    keb = _clean_code(kebele)
    vil = _clean_code(village)
    grp = "EL" if str(group).lower().startswith("el") else "NE"
    prefix = f"PPS-{'PR' if kind=='Primary' else 'RP'}-{keb}-{vil}-{grp}-"
    return {idx: f"{prefix}{i+1:02d}" for i, idx in enumerate(indices)}

def _pps_select(rng, villages, sizes, k=2):
    villages = list(villages)
    sizes = np.asarray(sizes, dtype=float)
    k = min(k, len(villages))
    if k <= 0:
        return []
    chosen = []
    available = list(range(len(villages)))
    while len(chosen) < k and available:
        w = sizes[available]
        probs = (w / w.sum()) if w.sum() > 0 else np.ones_like(w)/len(w)
        idx_in_avail = rng.choice(len(available), p=probs)
        gidx = available.pop(idx_in_avail)
        chosen.append(villages[gidx])
    return chosen

def run_sampling(
    df_raw: pd.DataFrame,
    col_map: dict,
    seed: int = 20251031,
    targets=(15, 30),         # (two-village per group, one-village per group)
    reserves=(4, 8)           # (two-village per group, one-village per group)
):
    col_woreda  = col_map.get("woreda")
    col_kebele  = col_map["kebele"]
    col_village = col_map["village"]
    col_elig    = col_map.get("eligibility")

    dfn = df_raw.copy()
    ren = {c: _norm(c) for c in dfn.columns}
    dfn.columns = [ren[c] for c in dfn.columns]

    w = _norm(col_woreda) if col_woreda else None
    k = _norm(col_kebele)
    v = _norm(col_village)
    e = _norm(col_elig) if col_elig else None

    if e and e in dfn.columns:
        elig_lower = dfn[e].astype(str).str.strip().str.lower()
        dfn["group"] = np.where(elig_lower == "eligible", "Eligible", "Non-eligible")
    else:
        dfn["group"] = "Eligible"

    rng = np.random.default_rng(int(seed))
    TWO_VILL, ONE_VILL = targets
    RES_TWO, RES_ONE = reserves

    primary_idx = []
    reserve_idx = []

    pps_rows = []
    kgrp_rows = []
    kroll_rows = []

    for keb, g_k in dfn.groupby(k, dropna=False):
        woreda_val = (g_k[w].iloc[0] if w and w in g_k.columns else None)
        v_sizes = g_k.groupby(v, dropna=False).size()
        selected = _pps_select(rng, v_sizes.index.tolist(), v_sizes.values, k=2)

        rank_map = {sel_v: i+1 for i, sel_v in enumerate(selected)}
        for vv, mos in v_sizes.sort_values(ascending=False).items():
            pps_rows.append({
                "Woreda": woreda_val,
                "Kebele": keb,
                "Village": vv,
                "MOS_Total_HHs": int(mos),
                "Selected": "Yes" if vv in selected else "No",
                "Selection_Rank": rank_map.get(vv, None)
            })

        if not selected:
            kroll_rows.append({
                "Woreda": woreda_val,
                "Kebele": keb,
                "Selected_Villages_Count": 0,
                "Selected_Villages": "",
                "MOS_Total_HHs": int(v_sizes.sum()),
                "Primary_Drawn_Total": 0,
                "Reserve_Target_Total": 0,
                "Reserve_Drawn_Total": 0
            })
            continue

        if len(selected) == 1:
            per_target = ONE_VILL
            per_reserve = RES_ONE
        else:
            per_target = TWO_VILL
            per_reserve = RES_TWO

        keb_primary_total = 0
        keb_res_target_total = 0
        keb_res_drawn_total = 0

        for grp_val, g_grp in g_k.groupby("group", dropna=False):
            avail = {sel_v: len(g_grp[g_grp[v] == sel_v]) for sel_v in selected}

            if len(selected) == 1:
                sel_v = selected[0]
                a = avail.get(sel_v, 0)
                b = min(per_target, a)

                gv = g_grp[g_grp[v] == sel_v]
                idx_p = gv.sample(n=b, random_state=int(rng.integers(0,1_000_000)), replace=False).index if b > 0 else gv.iloc[:0].index
                primary_idx.extend(idx_p.tolist())

                rem = gv.drop(index=idx_p)
                r_take = min(per_reserve, len(rem))
                idx_r = rem.sample(n=r_take, random_state=int(rng.integers(0,1_000_000)), replace=False).index if r_take > 0 else rem.iloc[:0].index
                reserve_idx.extend(idx_r.tolist())

                keb_primary_total += len(idx_p)
                keb_res_target_total += per_reserve
                keb_res_drawn_total += len(idx_r)

                kgrp_rows.append({
                    "Woreda": woreda_val,
                    "Kebele": keb,
                    "Group": grp_val,
                    "Selected_Villages": sel_v,
                    "Available_Total": int(a),
                    "Primary_Target_Total": int(per_target),
                    "Primary_Drawn_Total": int(len(idx_p)),
                    "Reserve_Target_Total": int(per_reserve),
                    "Reserve_Drawn_Total": int(len(idx_r)),
                })
            else:
                v1, v2 = selected[0], selected[1]
                a1, a2 = avail.get(v1, 0), avail.get(v2, 0)
                b1, b2 = min(per_target, a1), min(per_target, a2)

                if a1 < per_target and a2 > per_target:
                    shift = min(per_target - a1, a2 - per_target)
                    b2 += shift
                elif a2 < per_target and a1 > per_target:
                    shift = min(per_target - a2, a1 - per_target)
                    b1 += shift

                gv1 = g_grp[g_grp[v] == v1]
                gv2 = g_grp[g_grp[v] == v2]
                idx_p1 = gv1.sample(n=min(b1, len(gv1)), random_state=int(rng.integers(0,1_000_000)), replace=False).index if b1 > 0 else gv1.iloc[:0].index
                idx_p2 = gv2.sample(n=min(b2, len(gv2)), random_state=int(rng.integers(0,1_000_000)), replace=False).index if b2 > 0 else gv2.iloc[:0].index
                primary_idx.extend(idx_p1.tolist())
                primary_idx.extend(idx_p2.tolist())

                rem1 = gv1.drop(index=idx_p1)
                rem2 = gv2.drop(index=idx_p2)
                r1_take = min(per_reserve, len(rem1))
                r2_take = min(per_reserve, len(rem2))
                idx_r1 = rem1.sample(n=r1_take, random_state=int(rng.integers(0,1_000_000)), replace=False).index if r1_take > 0 else rem1.iloc[:0].index
                idx_r2 = rem2.sample(n=r2_take, random_state=int(rng.integers(0,1_000_000)), replace=False).index if r2_take > 0 else rem2.iloc[:0].index
                reserve_idx.extend(idx_r1.tolist())
                reserve_idx.extend(idx_r2.tolist())

                keb_primary_total += len(idx_p1) + len(idx_p2)
                keb_res_target_total += (per_reserve + per_reserve)
                keb_res_drawn_total += (len(idx_r1) + len(idx_r2))

                kgrp_rows.append({
                    "Woreda": woreda_val,
                    "Kebele": keb,
                    "Group": grp_val,
                    "Selected_Villages": f"{v1}, {v2}",
                    "Available_Total": int(a1 + a2),
                    "Primary_Target_Total": int(per_target * 2),
                    "Primary_Drawn_Total": int(len(idx_p1) + len(idx_p2)),
                    "Reserve_Target_Total": int(per_reserve * 2),
                    "Reserve_Drawn_Total": int(len(idx_r1) + len(idx_r2)),
                })

        kroll_rows.append({
            "Woreda": woreda_val,
            "Kebele": keb,
            "Selected_Villages_Count": len(selected),
            "Selected_Villages": ", ".join(map(str, selected)),
            "MOS_Total_HHs": int(v_sizes.sum()),
            "Primary_Drawn_Total": int(keb_primary_total),
            "Reserve_Target_Total": int(keb_res_target_total),
            "Reserve_Drawn_Total": int(keb_res_drawn_total)
        })

    primary_df = df_raw.loc[primary_idx].copy()
    reserve_df = df_raw.loc[reserve_idx].copy()

    id_map = {}
    if not primary_df.empty:
        sel_norm = dfn.loc[primary_df.index, [k, v, "group"]]
        for (keb, vil, grp), gsub in sel_norm.groupby([k, v, "group"]):
            id_map.update(_make_ids(gsub.index.tolist(), keb, vil, grp, "Primary"))
    if not reserve_df.empty:
        sel_norm = dfn.loc[reserve_df.index, [k, v, "group"]]
        for (keb, vil, grp), gsub in sel_norm.groupby([k, v, "group"]):
            id_map.update(_make_ids(gsub.index.tolist(), keb, vil, grp, "Replacement"))

    def _attach_flags(df_sel, kind):
        if df_sel.empty:
            return df_sel
        df_sel.insert(0, "Group", dfn.loc[df_sel.index, "group"].values)
        df_sel.insert(0, "Selection", kind)
        df_sel.insert(0, "Sample ID", pd.Series(id_map).reindex(df_sel.index).values)
        return df_sel

    primary_df = _attach_flags(primary_df, "Primary")
    reserve_df = _attach_flags(reserve_df, "Replacement")

    pps_df   = pd.DataFrame(pps_rows).sort_values(["Woreda","Kebele","Selected","Selection_Rank","Village"], ascending=[True,True,False,True,True])
    kgrp_df  = pd.DataFrame(kgrp_rows).sort_values(["Woreda","Kebele","Group"]) if len(kgrp_rows)>0 else pd.DataFrame(columns=["Woreda","Kebele","Group","Selected_Villages","Available_Total","Primary_Target_Total","Primary_Drawn_Total","Reserve_Target_Total","Reserve_Drawn_Total"]) 
    kroll_df = pd.DataFrame(kroll_rows).sort_values(["Woreda","Kebele"]) if len(kroll_rows)>0 else pd.DataFrame(columns=["Woreda","Kebele","Selected_Villages_Count","Selected_Villages","MOS_Total_HHs","Primary_Drawn_Total","Reserve_Target_Total","Reserve_Drawn_Total"]) 

    printable_df = pd.concat([primary_df, reserve_df], ignore_index=True)
    if not printable_df.empty:
        sort_cols = [c for c in ["Kebele","Village","Group","Selection","Sample ID"] if c in printable_df.columns]
        printable_df = printable_df.sort_values(sort_cols)
        if "Village" in printable_df.columns and "Kebele" in printable_df.columns:
            printable_df.insert(0, "Line No", printable_df.groupby(["Kebele","Village"]).cumcount()+1)
        else:
            printable_df.insert(0, "Line No", range(1, len(printable_df)+1))

    return {
        "primary_df": primary_df,
        "reserve_df": reserve_df,
        "pps_df": pps_df,
        "kgrp_df": kgrp_df,
        "kroll_df": kroll_df,
        "printable_df": printable_df
    }
