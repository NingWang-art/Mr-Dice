import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Literal, TypedDict
from anyio import to_thread
import asyncio

# Add the parent directory to Python path to import mofdb_client
sys.path.append(str(Path(__file__).parent.parent))
from mofdb_client import fetch

from utils import *

# === Output format type ===
Format = Literal["cif", "json"]

# === Result return type ===
class FetchResult(TypedDict):
    output_dir: Path
    cleaned_structures: List[dict]
    n_found: int
    code: int
    message: str

BASE_OUTPUT_DIR = Path("materials_data_mofdb")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_mofs(
    mofid: str = None,
    mofkey: str = None,
    vf_min: float = None,
    vf_max: float = None,
    lcd_min: float = None,
    lcd_max: float = None,
    pld_min: float = None,
    pld_max: float = None,
    sa_m2g_min: float = None,
    sa_m2g_max: float = None,
    sa_m2cm3_min: float = None,
    sa_m2cm3_max: float = None,
    name: str = None,
    database: str = None,
    n_results: int = 10,
    output_formats: List[Format] = ["json", "cif"]
) -> FetchResult:
    """
    Fetch MOFs from mofdb and save them in chosen formats.
    Valid names are: ['CoREMOF 2014', 'CoREMOF 2019', 'CSD', 'hMOF', 'IZA', 'PCOD-syn', 'Tobacco']
    """

    # === Step 1: Query ===
    # try:
    results = list(fetch(
        mofid=mofid,
        mofkey=mofkey,
        vf_min=vf_min, vf_max=vf_max,
        lcd_min=lcd_min, lcd_max=lcd_max,
        pld_min=pld_min, pld_max=pld_max,
        sa_m2g_min=sa_m2g_min, sa_m2g_max=sa_m2g_max,
        sa_m2cm3_min=sa_m2cm3_min, sa_m2cm3_max=sa_m2cm3_max,
        name=name, database=database,
        limit=n_results,
    ))
    # except RuntimeError as e:
    #     # Handle "generator raised StopIteration" -> no results
    #     if "StopIteration" in str(e):
    #         results = []
    #     else:
    #         raise
    # except Exception as e:
    #     # This catches the Sentry "FrameLocalsProxy" bug or anything else unexpected
    #     print(f"encounter some error or find nothing")
    #     results = []

    n_found = len(results)

    # === Step 2: Build output folder ===
    filter_str = json.dumps({
        "mofid": mofid, "mofkey": mofkey, "name": name, "database": database,
        "vf_min": vf_min, "vf_max": vf_max,
        "lcd_min": lcd_min, "lcd_max": lcd_max,
        "pld_min": pld_min, "pld_max": pld_max,
        "sa_m2g_min": sa_m2g_min, "sa_m2g_max": sa_m2g_max,
        "sa_m2cm3_min": sa_m2cm3_min, "sa_m2cm3_max": sa_m2cm3_max,
        "n_results": n_results
    }, sort_keys=True, default=str)
    tag = tag_from_filters(
        mofid=mofid,
        mofkey=mofkey,
        name=name,
        database=database,
        vf_min=vf_min, vf_max=vf_max,
        lcd_min=lcd_min, lcd_max=lcd_max,
        pld_min=pld_min, pld_max=pld_max,
        sa_m2g_min=sa_m2g_min, sa_m2g_max=sa_m2g_max,
        sa_m2cm3_min=sa_m2cm3_min, sa_m2cm3_max=sa_m2cm3_max,
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha1(filter_str.encode("utf-8")).hexdigest()[:8]
    output_dir = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short_hash}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # === Step 3: Save ===
    cleaned = save_mofs(
        results, output_dir, output_formats
    )

    # === Step 4: Manifest ===
    manifest = {
        "filters": {
            "mofid": mofid, "mofkey": mofkey, "name": name, "database": database,
            "vf_min": vf_min, "vf_max": vf_max,
            "lcd_min": lcd_min, "lcd_max": lcd_max,
            "pld_min": pld_min, "pld_max": pld_max,
            "sa_m2g_min": sa_m2g_min, "sa_m2g_max": sa_m2g_max,
            "sa_m2cm3_min": sa_m2cm3_min, "sa_m2cm3_max": sa_m2cm3_max,
            "n_results": n_results,
        },
        "n_found": n_found,
        "formats": list(output_formats),
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(json.dumps(manifest, indent=2))

    return {
        "output_dir": output_dir,
        "n_found": n_found,
        "cleaned_structures": cleaned,
        "code": 0,
        "message": "Success",
    }


if __name__ == "__main__":
    result = fetch_mofs(
        # name="tobmof-27",
        mofid="Cl[Mn].N1=NC(=N[N]1)C1=N[N]C(=N[N]1)C#Cc1nnc(nn1)C1=NN=N[N]1.N1=NN=C([N]1)C1=N[N]C(=N[N]1)C#Cc1nnc(nn1)C1=NN=N[N]1.[Mn] MOFid-v1.bcu.cat0",
        # mofkey="Co.VZNLJUXIEJLYJK.MOFkey-v1.sql",
        # vf_min=0, vf_max=0.1,
        # lcd_min=6.0, lcd_max=7.0,
        # sa_m2g_min=0, sa_m2g_max=100,
        n_results=50,
        output_formats=["json", "cif"],
        # database="Tobacco",
    )
    print(result)

