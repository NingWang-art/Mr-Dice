import json
import logging
import re
from pathlib import Path
from typing import List, Literal, TypedDict, Any

Format = Literal["cif", "json"]

MOFDB_DROP_ATTRS = {
    "cif", 
    "json_repr", 
    "isotherms", 
    "heats",
    "isotherms_filtered",
    "heats_filtered",
}

from typing import Optional

def tag_from_filters(
    mofid: Optional[str] = None,
    mofkey: Optional[str] = None,
    name: Optional[str] = None,
    database: Optional[str] = None,
    vf_min: Optional[float] = None,
    vf_max: Optional[float] = None,
    lcd_min: Optional[float] = None,
    lcd_max: Optional[float] = None,
    pld_min: Optional[float] = None,
    pld_max: Optional[float] = None,
    sa_m2g_min: Optional[float] = None,
    sa_m2g_max: Optional[float] = None,
    sa_m2cm3_min: Optional[float] = None,
    sa_m2cm3_max: Optional[float] = None,
    max_len: int = 40
) -> str:
    """
    Build a short tag string from MOFdb filter parameters for naming output folders.
    """
    parts = []

    if mofid:
        parts.append(f"id{mofid[:8]}")   # 避免太长，截取前8位
    if mofkey:
        parts.append(f"key{mofkey[:8]}")
    if name:
        parts.append(name.replace(" ", "_"))
    if database:
        parts.append(database.replace(" ", ""))

    if vf_min is not None or vf_max is not None:
        parts.append(f"vf{vf_min or ''}-{vf_max or ''}")
    if lcd_min is not None or lcd_max is not None:
        parts.append(f"lcd{lcd_min or ''}-{lcd_max or ''}")
    if pld_min is not None or pld_max is not None:
        parts.append(f"pld{pld_min or ''}-{pld_max or ''}")
    if sa_m2g_min is not None or sa_m2g_max is not None:
        parts.append(f"sa_g{sa_m2g_min or ''}-{sa_m2g_max or ''}")
    if sa_m2cm3_min is not None or sa_m2cm3_max is not None:
        parts.append(f"sa_cm3{sa_m2cm3_min or ''}-{sa_m2cm3_max or ''}")

    tag = "_".join(str(p) for p in parts if p)
    return tag[:max_len] or "mofdb"


def _safe_basename(text: str, max_len: int = 80) -> str:
    """
    Make a safe, reasonably short filename stem.
    """
    text = str(text) if text is not None else "mof"
    # Replace slashes and spaces
    text = text.replace("/", "_").replace("\\", "_").replace(" ", "_")
    # Keep only safe characters
    text = re.sub(r"[^A-Za-z0-9._-]", "_", text)
    # Collapse multiple underscores
    text = re.sub(r"_+", "_", text).strip("_")
    # Limit length
    return text[:max_len] or "mof"


def _pick_identifier(mof: Any, idx: int) -> str:
    """
    Prefer name -> mofkey -> mofid -> id -> idx for file naming.
    """
    ident = (
        getattr(mof, "name", None)
        or getattr(mof, "mofkey", None)
        or getattr(mof, "mofid", None)
        or getattr(mof, "id", None)
        or f"idx{idx}"
    )
    return _safe_basename(ident, max_len=20)


def _provider(mof: Any) -> str:
    """
    Use database as provider tag; fallback to 'mofdb'.
    """
    prov = getattr(mof, "database", None) or "mofdb"
    return _safe_basename(prov)


def save_mofs(
    items: List[Any],
    output_dir: Path,
    output_formats: List[Format] = ["cif", "json"]
) -> List[dict]:
    """
    Save MOFdb entries as JSON and/or CIF files, and return cleaned metadata.

    - JSON: use `mof.json_repr` if available (no field removal).
    - CIF:  write `mof.cif` text if present.
    - cleaned: copy of `mof.__dict__` minus {cif, json_repr, isotherms, heats}.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned: List[dict] = []

    for i, mof in enumerate(items):
        prov = _provider(mof)
        ident = _pick_identifier(mof, i)
        stem = _safe_basename(f"{prov}_{ident}_{i}")

        # ---- Save JSON (use json_repr verbatim if possible)
        if "json" in output_formats:
            data = getattr(mof, "json_repr", None)
            try:
                if data is None:
                    # Fallback to serializing __dict__
                    data = json.loads(json.dumps(mof.__dict__, default=str))
                elif isinstance(data, str):
                    # If json_repr is a JSON string, parse it; otherwise wrap it.
                    try:
                        data = json.loads(data)
                    except Exception:
                        data = {"raw": data}
                # Write JSON
                with open(output_dir / f"{stem}.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logging.error(f"Failed to save JSON for {ident}: {e}")

        # ---- Save CIF (plain text)
        if "cif" in output_formats:
            cif_txt = getattr(mof, "cif", None)
            if cif_txt:
                try:
                    with open(output_dir / f"{stem}.cif", "w", encoding="utf-8") as f:
                        f.write(cif_txt)
                except Exception as e:
                    logging.error(f"Failed to save CIF for {ident}: {e}")
            else:
                logging.warning(f"No CIF content for {ident} ({prov})")


        # ---- Build cleaned (drop heavy fields + simplify adsorbates)
        md = dict(getattr(mof, "__dict__", {}))
        for k in MOFDB_DROP_ATTRS:
            md.pop(k, None)

        cleaned.append(md)

    return cleaned