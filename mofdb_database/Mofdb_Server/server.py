import argparse
import logging
import json
import hashlib
from typing import List, Optional, TypedDict, Literal
from pathlib import Path
from datetime import datetime
import os
import sys
from anyio import to_thread

from dp.agent.server import CalculationMCPServer
from utils import *

# Add mofdb path
sys.path.append(str(Path(__file__).parent.parent))
from mofdb_client import fetch


# === ARG PARSING ===
def parse_args():
    parser = argparse.ArgumentParser(description="MOFdb MCP Server")
    parser.add_argument('--port', type=int, default=50004, help='Server port (default: 50004)')
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    try:
        return parser.parse_args()
    except SystemExit:
        class Args:
            port = 50004
            host = '0.0.0.0'
            log_level = 'INFO'
        return Args()

# === OUTPUT TYPE ===
Format = Literal["cif", "json"]

class FetchResult(TypedDict):
    output_dir: Path
    cleaned_structures: List[dict]
    n_found: int
    code: int
    message: str

BASE_OUTPUT_DIR = Path("materials_data_mofdb")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_RETURNED_STRUCTS = 30

# === MCP SERVER ===
args = parse_args()
logging.basicConfig(level=args.log_level)
mcp = CalculationMCPServer("MOFDBServer", port=args.port, host=args.host)

# === MCP TOOL ===
@mcp.tool()
async def fetch_mofs(
    mofid: Optional[str] = None,
    mofkey: Optional[str] = None,
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
    name: Optional[str] = None,
    database: Optional[str] = None,
    n_results: int = 10,
    output_formats: List[Format] = ["cif"]
) -> FetchResult:
    """
    🧱 Fetch MOFs from MOFdb and save them to disk.

    🔍 What this tool does:
    -----------------------------------
    - Queries the MOFdb database using optional filters (geometry, surface area, etc.).
    - Supports filtering by MOFid, MOFkey, name, database, void fraction, pore sizes, SA, etc.
    - Saves results in `.cif` and/or `.json` formats.
    - Automatically creates a tagged output folder and writes a manifest.

    📤 Returns:
    -----------------------------------
    FetchResult (dict) with:
        - output_dir: Path to the output folder.
        - cleaned_structures: List of cleaned MOF dicts.
        - n_found: Number of MOFs returned.
    """

    # === Step 1: Query MOFdb ===
    try:
        results = await to_thread.run_sync(lambda: list(fetch(
            mofid=mofid,
            mofkey=mofkey,
            vf_min=vf_min, vf_max=vf_max,
            lcd_min=lcd_min, lcd_max=lcd_max,
            pld_min=pld_min, pld_max=pld_max,
            sa_m2g_min=sa_m2g_min, sa_m2g_max=sa_m2g_max,
            sa_m2cm3_min=sa_m2cm3_min, sa_m2cm3_max=sa_m2cm3_max,
            name=name,
            database=database,
            limit=n_results,
        )))
    except Exception as e:
        print(f"Encounter some error or Find nothing!")
        results = []    

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
    cleaned = await to_thread.run_sync(lambda: save_mofs(
        results,
        output_dir,
        output_formats
    ))

    cleaned = cleaned[:MAX_RETURNED_STRUCTS]
    n_found = len(cleaned)

    # === Step 4: Manifest ===
    manifest = {
        "filters": {
            "mofid": mofid, "mofkey": mofkey, "name": name, "database": database,
            "vf_min": vf_min, "vf_max": vf_max,
            "lcd_min": lcd_min, "lcd_max": lcd_max,
            "pld_min": pld_min, "pld_max": pld_max,
            "sa_m2g_min": sa_m2g_min, "sa_m2g_max": sa_m2g_max,
            "sa_m2cm3_min": sa_m2cm3_min, "sa_m2cm3_max": sa_m2cm3_max,
            "n_results": n_results
        },
        "n_found": n_found,
        "formats": output_formats,
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

# === START SERVER ===
if __name__ == "__main__":
    logging.info("Starting MOFdb MCP Server...")
    mcp.run(transport="sse")