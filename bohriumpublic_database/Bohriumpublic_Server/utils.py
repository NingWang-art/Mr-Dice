import json
from pathlib import Path
from typing import List, Optional, Literal, TypedDict
from datetime import datetime, timezone

import requests
import logging
import json
import os
from dotenv import load_dotenv
import requests


load_dotenv()

global DB_CORE_HOST
global BOHRIUM_CORE_HOST
# DB_CORE_HOST="https://db-core.test.dp.tech"
# BOHRIUM_CORE_HOST="https://bohrium-core.test.dp.tech"
DB_CORE_HOST="https://db-core.dp.tech"
BOHRIUM_CORE_HOST="https://bohrium-core.dp.tech"


# def get_user_info_by_ak() -> dict:
#     """
#     根据ak获取用户信息
#     """
#     ak = os.getenv("BOHRIUM_ACCESS_KEY", "a43c365d70964ff6b22710da97b46254")
#     if not ak:
#         raise ValueError("BOHRIUM_ACCESS_KEY environment variable is not set")
    
#     url = f"{BOHRIUM_CORE_HOST}/api/v1/ak/get_user?accessKey={ak}"
    
#     try:
#         response = requests.get(url)
#         response.raise_for_status()
#         data = response.json()
        
#         if data.get("code") == 0 and "data" in data:
#             return {
#                 "user_id": str(data["data"]["userId"]),
#                 "org_id": str(data["data"]["orgId"])
#             }
#         else:
#             raise Exception(f"API returned error: {data}")
            
#     except Exception as e:
#         raise Exception(f"Failed to get user info: {str(e)}")
x_user_id = '117756'

CRYSTAL_DROP_ATTRS = {
    "cif_file",
    "come_from",
    "material_id",
}

def parse_iso8601_utc(dt_str: str) -> datetime:
    """
    Parse an ISO 8601 UTC datetime string like '2024-01-01T00:00:00Z'.
    """
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1]
    return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)


def tag_from_filters(
    formula: Optional[str] = None,
    elements: Optional[List[str]] = None,
    space_symbol: Optional[str] = None,
    atom_count_range: Optional[List[str]] = None,
    predicted_formation_energy_range: Optional[List[str]] = None,
    band_gap_range: Optional[List[str]] = None,
    max_len: int = 60
) -> str:
    """
    Build a short tag string from Bohrium query filters.

    This tag is used to create unique output directories.

    Parameters
    ----------
    formula : str, optional
        Chemical formula keyword.
    elements : list of str, optional
        Required elements.
    space_symbol : str, optional
        Space group symbol.
    atom_count_range : [min,max], optional
        Atom count range.
    predicted_formation_energy_range : [min,max], optional
        Formation energy range (eV).
    band_gap_range : [min,max], optional
        Band gap range (eV).
    max_len : int
        Maximum length of the tag string.

    Returns
    -------
    str
        Shortened tag string (safe for filenames).
    """
    parts = []

    if formula:
        parts.append(formula.replace(" ", ""))
    if elements:
        parts.append("el" + "".join(sorted(elements)))
    if space_symbol:
        parts.append("sg" + space_symbol)
    if atom_count_range:
        parts.append("nat" + "-".join(atom_count_range))
    if predicted_formation_energy_range:
        parts.append("E" + "-".join(predicted_formation_energy_range))
    if band_gap_range:
        parts.append("Eg" + "-".join(band_gap_range))

    tag = "_".join(parts)
    return tag[:max_len] or "bohriumcrystal"


def save_structures_bohriumcrystal(
    items: List[dict],
    output_dir: Path,
    output_formats: List[Literal["json", "cif"]] = ["json"]
) -> List[dict]:
    """
    Save Bohrium crystal structures as JSON and/or CIF files.

    Parameters
    ----------
    items : list of dict
        Structures returned from Bohrium API (already JSON dicts).
    output_dir : Path
        Directory to save files into.
    output_formats : list of {"json", "cif"}
        Which formats to save. Default is ["json"].

    Returns
    -------
    cleaned : list of dict
        Metadata-only version of the structures (same as items).
    """

    cleaned = []

    for i, struct in enumerate(items):
        struct_id = struct.get("id", f"idx{i}")
        name = f"bohriumcrystal_{struct_id}_{i}"

        # Save JSON
        if "json" in output_formats:
            with open(output_dir / f"{name}.json", "w", encoding="utf-8") as f:
                json.dump(struct, f, indent=2, ensure_ascii=False)

        # Save CIF (download from URL)
        if "cif" in output_formats:
            cif_url = struct.get("cif_file")
            if not cif_url:
                logging.warning(f"No CIF URL for {struct_id}")
            else:
                try:
                    r = requests.get(cif_url, timeout=30)
                    r.raise_for_status()
                    with open(output_dir / f"{name}.cif", "wb") as f:
                        f.write(r.content)
                    logging.info(f"Saved CIF for {struct_id} -> {name}.cif")
                except Exception as e:
                    logging.error(f"Failed to download CIF for {struct_id}: {e}")

        # Make a cleaned copy (remove bulky parts like CIF URL or details)
        cleaned_struct = dict(struct)
        for key in CRYSTAL_DROP_ATTRS:
            cleaned_struct.pop(key, None)
        cleaned.append(cleaned_struct)

    return cleaned