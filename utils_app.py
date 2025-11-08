
import io
import re
import pandas as pd

INVALID_SHEET_CHARS = r'[:\/?*\[\]]'

def detect_columns(df: pd.DataFrame):
    cols = list(df.columns)
    def pick(patterns):
        for p in patterns:
            for c in cols:
                if re.search(p, str(c), flags=re.I):
                    return c
        return None
    return {
        "woreda":      pick([r"^woreda$", r"woreda"]),
        "kebele":      pick([r"^kebele$", r"kebele"]),
        "village":     pick([r"^village$", r"village"]),
        "eligibility": pick([r"^eligib", r"eligib", r"^eligible$"])
    }

def to_excel_bytes(sheets: dict) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=name[:31])
    bio.seek(0)
    return bio.getvalue()

def read_any(file) -> pd.DataFrame:
    fname = (file.name if hasattr(file, "name") else "")
    if fname.lower().endswith((".csv", ".txt")):
        return pd.read_csv(file)
    else:
        return pd.read_excel(file, engine="openpyxl")

# ---- Safe sheet naming and robust printable builder ----

def _safe_sheet_name(name: str, used: set) -> str:
    s = re.sub(INVALID_SHEET_CHARS, "-", str(name))
    s = s[:31] if len(s) > 31 else s
    if not s:
        s = "Sheet"
    base = s
    n = 2
    while s in used:
        suffix = f" ({n})"
        s = (base[: (31 - len(suffix))] + suffix) if len(base) + len(suffix) > 31 else base + suffix
        n += 1
    used.add(s)
    return s

def build_printable_workbook_per_kebele(dfall: pd.DataFrame) -> bytes:
    bio = io.BytesIO()

    if dfall is None or not isinstance(dfall, pd.DataFrame) or dfall.empty:
        fallback = pd.DataFrame([{
            "Info": "No sampled households to print.",
            "Hint": "Run sampling first or check filters."
        }])
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            fallback.to_excel(writer, index=False, sheet_name="Printable")
        bio.seek(0)
        return bio.getvalue()

    df = dfall.copy()
    for col in ["Kebele", "Village", "Group", "Selection", "Sample ID"]:
        if col not in df.columns:
            df[col] = ""

    sort_cols = ["Kebele", "Village", "Group", "Selection", "Sample ID"]
    df = df.sort_values(sort_cols, kind="mergesort", ignore_index=True)

    used_names = set()
    wrote_any = False

    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        if "Kebele" not in df.columns or df["Kebele"].astype(str).str.strip().eq("").all():
            tmp = df.copy()
            if "Village" in tmp.columns:
                tmp.insert(0, "Line No", tmp.groupby("Village").cumcount() + 1)
            else:
                tmp.insert(0, "Line No", range(1, len(tmp) + 1))
            tmp.to_excel(writer, index=False, sheet_name="Printable")
            wrote_any = True
        else:
            for keb, gk in df.groupby("Kebele", dropna=False):
                gk = gk.copy()
                if "Village" in gk.columns:
                    gk.insert(0, "Line No", gk.groupby("Village").cumcount() + 1)
                else:
                    gk.insert(0, "Line No", range(1, len(gk) + 1))
                sheet = _safe_sheet_name(keb, used_names)
                gk.to_excel(writer, index=False, sheet_name=sheet)
                wrote_any = True

        if not wrote_any:
            pd.DataFrame([{"Info": "No data written"}]).to_excel(writer, index=False, sheet_name="Printable")

    bio.seek(0)
    return bio.getvalue()
