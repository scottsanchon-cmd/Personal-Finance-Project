"""
Personal Finance Parser — Phase 1
Normalizes bank statements from multiple institutions into a standard schema.

Supported formats:
  - TD / CIBC style CSV  (date, description, debit, credit, balance)
  - Generic CSV          (auto-detected columns)
  - Excel (.xlsx / .xls) (Krung Thai and similar)
  - PDF                  (text-based, not scanned)

Output schema (all rows):
  date          datetime64  transaction date
  description   str         cleaned merchant / narrative
  amount        float       positive = money IN, negative = money OUT
  debit         float       raw debit amount  (NaN if credit)
  credit        float       raw credit amount (NaN if debit)
  balance       float       running balance after transaction
  currency      str         detected or passed-in currency code
  bank          str         source bank label
  source_file   str         original filename
"""

import re
import warnings
from pathlib import Path
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Canonical column names each bank uses
# ---------------------------------------------------------------------------
BANK_PROFILES = {
    "td_cibc": {
        "date":        ["date"],
        "description": ["transaction description", "description", "memo"],
        "debit":       ["debit"],
        "credit":      ["credit"],
        "balance":     ["balance"],
        "currency":    "CAD",
        "date_format": "%m/%d/%Y",
    },
    "krung_thai": {
        "date":        ["วันที่", "date", "transaction date"],
        "description": ["รายการ", "description", "details"],
        "debit":       ["ถอน", "debit", "withdrawal"],
        "credit":      ["ฝาก", "credit", "deposit"],
        "balance":     ["คงเหลือ", "balance"],
        "currency":    "THB",
        "date_format": "%d/%m/%Y",
    },
    "generic": {
        "date":        ["date", "txn date", "transaction date", "posted date", "value date"],
        "description": ["description", "transaction description", "details", "memo", "narrative"],
        "debit":       ["debit", "withdrawal", "amount out", "charge"],
        "credit":      ["credit", "deposit", "amount in"],
        "balance":     ["balance", "running balance"],
        "currency":    "USD",
        "date_format": None,   # pandas will infer
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_col(df_cols: list[str], candidates: list[str]) -> str | None:
    """Case-insensitive column name match."""
    lower = {c.strip().lower(): c for c in df_cols}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _clean_amount(series: pd.Series) -> pd.Series:
    """Strip commas, currency symbols, parentheses, whitespace → float."""
    s = series.astype(str).str.strip()
    s = s.str.replace(r"[฿$€£,\s]", "", regex=True)
    s = s.str.replace(r"\((.+)\)", r"-\1", regex=True)   # (1,234) → -1234
    s = s.replace({"": float("nan"), "nan": float("nan"), "-": float("nan")})
    return pd.to_numeric(s, errors="coerce")


def _clean_description(series: pd.Series) -> pd.Series:
    """Title-case, collapse whitespace, strip trailing punctuation."""
    s = series.astype(str).str.strip()
    s = s.str.replace(r"\s+", " ", regex=True)
    return s


def _detect_bank(df: pd.DataFrame, filename: str) -> str:
    """Heuristic: pick the best matching profile."""
    cols_lower = {c.strip().lower() for c in df.columns}
    name_lower = filename.lower()

    # Explicit filename hints
    if any(k in name_lower for k in ["krung", "ktb", "thai"]):
        return "krung_thai"
    if any(k in name_lower for k in ["td", "cibc", "rbc", "bmo", "scotiabank"]):
        return "td_cibc"

    # Thai column names → Krung Thai
    thai_cols = {"วันที่", "รายการ", "ถอน", "ฝาก", "คงเหลือ"}
    if thai_cols & cols_lower:
        return "krung_thai"

    # TD/CIBC have a column literally called "transaction description"
    if "transaction description" in cols_lower:
        return "td_cibc"

    return "generic"


def _build_normalized(df: pd.DataFrame, profile: dict, bank: str, source: str, currency: str) -> pd.DataFrame:
    """Map raw DataFrame columns → standard schema."""
    p = profile

    date_col   = _find_col(df.columns, p["date"])
    desc_col   = _find_col(df.columns, p["description"])
    debit_col  = _find_col(df.columns, p["debit"])
    credit_col = _find_col(df.columns, p["credit"])
    bal_col    = _find_col(df.columns, p["balance"])

    if not date_col or not desc_col:
        raise ValueError(f"Cannot find required columns (date/description) in {source}. "
                         f"Found: {list(df.columns)}")

    out = pd.DataFrame()

    # Date
    fmt = p.get("date_format")
    if fmt:
        out["date"] = pd.to_datetime(df[date_col].astype(str).str.strip(), format=fmt, errors="coerce")
    else:
        out["date"] = pd.to_datetime(df[date_col].astype(str).str.strip(), infer_datetime_format=True, errors="coerce")

    out["description"] = _clean_description(df[desc_col])

    out["debit"]  = _clean_amount(df[debit_col])  if debit_col  else float("nan")
    out["credit"] = _clean_amount(df[credit_col]) if credit_col else float("nan")
    out["balance"] = _clean_amount(df[bal_col])   if bal_col    else float("nan")

    # Unified signed amount: credit = positive inflow, debit = negative outflow
    out["amount"] = out["credit"].fillna(0) - out["debit"].fillna(0)
    out.loc[out["amount"] == 0, "amount"] = float("nan")

    out["currency"]    = currency or p.get("currency", "XXX")
    out["bank"]        = bank
    out["source_file"] = source

    # Drop rows where both date and description are missing
    out = out.dropna(subset=["date", "description"])
    out = out[out["description"].str.strip() != ""]

    out = out.sort_values("date").reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Format-specific loaders
# ---------------------------------------------------------------------------

def _load_csv(path: Path) -> pd.DataFrame:
    """Try several encodings and separators."""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "tis620"):
        for sep in (",", "\t", ";"):
            try:
                df = pd.read_csv(path, encoding=enc, sep=sep, thousands=",")
                if df.shape[1] >= 3:
                    return df
            except Exception:
                continue
    raise ValueError(f"Could not read CSV: {path}")


def _load_excel(path: Path) -> pd.DataFrame:
    """Load first non-empty sheet; try to find header row."""
    xf = pd.ExcelFile(path)
    for sheet in xf.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        # Find the row that looks like a header (contains "date" or "วันที่")
        for i, row in df.iterrows():
            vals = [str(v).strip().lower() for v in row]
            if any(k in vals for k in ["date", "วันที่", "transaction date"]):
                df.columns = df.iloc[i]
                df = df.iloc[i + 1:].reset_index(drop=True)
                return df
        # Fall back: assume first row is header
        df = pd.read_excel(path, sheet_name=sheet)
        if df.shape[1] >= 3:
            return df
    raise ValueError(f"No usable sheet found in {path}")


def _load_pdf(path: Path) -> pd.DataFrame:
    """Extract tables from a PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required for PDF parsing. Run: pip install pdfplumber")

    all_rows = []
    header = None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                if header is None:
                    header = table[0]
                    all_rows.extend(table[1:])
                else:
                    # Skip rows that look like repeated headers
                    for row in table:
                        if row != header:
                            all_rows.append(row)

    if not header or not all_rows:
        raise ValueError(f"No tables found in PDF: {path}")

    df = pd.DataFrame(all_rows, columns=header)
    df.columns = [str(c).strip() if c else f"col_{i}" for i, c in enumerate(df.columns)]
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_statement(
    filepath: str | Path,
    bank: str = "auto",
    currency: str = None,
) -> pd.DataFrame:
    """
    Parse a bank statement file into the standard schema.

    Parameters
    ----------
    filepath : path to CSV, XLSX, XLS, or PDF file
    bank     : 'auto' (detect), 'td_cibc', 'krung_thai', or 'generic'
    currency : override currency code (e.g. 'THB', 'CAD'). Auto-detected if None.

    Returns
    -------
    pd.DataFrame with columns:
        date, description, amount, debit, credit, balance, currency, bank, source_file
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw = _load_csv(path)
    elif suffix in (".xlsx", ".xls"):
        raw = _load_excel(path)
    elif suffix == ".pdf":
        raw = _load_pdf(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use CSV, XLSX, or PDF.")

    # Strip whitespace from column names
    raw.columns = [str(c).strip() for c in raw.columns]

    detected_bank = bank if bank != "auto" else _detect_bank(raw, path.name)
    profile = BANK_PROFILES.get(detected_bank, BANK_PROFILES["generic"])

    return _build_normalized(raw, profile, detected_bank, path.name, currency)


def parse_multiple(
    filepaths: list[str | Path],
    **kwargs,
) -> pd.DataFrame:
    """Parse and merge multiple statement files."""
    frames = [parse_statement(f, **kwargs) for f in filepaths]
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)
    # Remove exact duplicates (same date + description + amount)
    combined = combined.drop_duplicates(subset=["date", "description", "amount"])
    return combined


def summary(df: pd.DataFrame) -> dict:
    """Quick summary stats for a parsed statement."""
    debits  = df[df["amount"] < 0]["amount"]
    credits = df[df["amount"] > 0]["amount"]
    return {
        "transactions":    len(df),
        "date_range":      f"{df['date'].min().date()} → {df['date'].max().date()}",
        "total_spent":     round(abs(debits.sum()), 2),
        "total_received":  round(credits.sum(), 2),
        "net":             round(df["amount"].sum(), 2),
        "avg_transaction": round(abs(debits.mean()), 2),
        "currency":        df["currency"].iloc[0],
        "bank":            df["bank"].iloc[0],
    }
