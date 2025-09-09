import argparse
import logging
import json
from typing import List, Optional, TypedDict, Literal
from pathlib import Path
from datetime import datetime
import hashlib
from anyio import to_thread
import asyncio

from optimade.client import OptimadeClient
from dp.agent.server import CalculationMCPServer

# Pull all helpers + provider sets from your utils.py
from utils import *

# === CONFIG ===
BASE_OUTPUT_DIR = Path("materials_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_RETURNED_STRUCTS = 100

# === ARG PARSING ===
def parse_args():
    parser = argparse.ArgumentParser(description="OPTIMADE Materials Data MCP Server")
    parser.add_argument('--port', type=int, default=50001, help='Server port (default: 50001)')
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    try:
        return parser.parse_args()
    except SystemExit:
        class Args:
            port = 50001
            host = '0.0.0.0'
            log_level = 'INFO'
        return Args()


# === RESULT TYPE (what each tool returns) ===
Format = Literal["cif", "json"]

class FetchResult(TypedDict):
    output_dir: Path             # folder where results are saved
    cleaned_structures: List[dict]  # list of cleaned structures
    n_found: int                    # number of structures found (0 if none)


# === MCP SERVER ===
args = parse_args()
logging.basicConfig(level=args.log_level)
mcp = CalculationMCPServer("OptimadeServer", port=args.port, host=args.host)


OptimadeAgentName = "optimade_agent"

OptimadeAgentDescription = (
    "An agent specialized in retrieving crystal structure data using the OPTIMADE protocol. "
    "Supports raw OPTIMADE filter strings, space-group-specific queries, and band-gap-specific queries "
    "across multiple materials databases."
)

OptimadeAgentInstruction = """
You are a crystal structure retrieval assistant with access to MCP tools powered by the OPTIMADE API.

## WHAT YOU CAN DO
You can call **three MCP tools**:

1) fetch_structures_with_filter(
       filter: str,
       as_format: 'cif'|'json' = 'cif',
       n_results: int = 2,
       providers: list[str] = [...]
   )
   - Sends ONE raw OPTIMADE filter string to all chosen providers at once.
   You can search for materials using any valid OPTIMADE filter expression, including:
     1. **Element filters** — specify required or excluded elements:
        - Must contain all: `elements HAS ALL "Al","O","Mg"`
        - Exactly these: `elements HAS ONLY "Si","O"`
        - Any match: `elements HAS ANY "Al","O"`
     2. **Formula filters** — match chemical formulas:
        - Reduced: `chemical_formula_reduced="O2Si"`
        - Descriptive: `chemical_formula_descriptive CONTAINS "H2O"`
        - Anonymous: `chemical_formula_anonymous="A2B"`
     3. **Numeric filters** — filter by number of distinct elements:
        - Exactly 3: `nelements=3`
        - Between 2 and 7: `nelements>=2 AND nelements<=7`
     4. **Logical combinations** — combine conditions with parentheses:
        - `(elements HAS ANY "Si" AND elements HAS ANY "O") AND NOT (elements HAS ANY "H")`

2) fetch_structures_with_spg(
       base_filter: str,
       spg_number: int,
       as_format: 'cif'|'json' = 'cif',
       n_results: int = 3,
       providers: list[str] = [...]
   )
   - Adds provider-specific *space-group* clauses (e.g., _tcod_sg, _oqmd_spacegroup, _alexandria_space_group) and queries providers in parallel.

3) fetch_structures_with_bandgap(
       base_filter: str,
       min_bg: float | None = None,
       max_bg: float | None = None,
       as_format: 'cif'|'json' = 'json',
       n_results: int = 2,
       providers: list[str] = [...]
   )
   - Adds provider-specific *band-gap* clauses (e.g., _oqmd_band_gap, _gnome_bandgap, _mcloudarchive_band_gap) and queries providers in parallel.
   - For band-gap related tasks, **default output format is 'json'** to include complete metadata.

## HOW TO CHOOSE A TOOL
- If the user wants to filter by **elements / formula / logic only** → you MUST use `fetch_structures_with_filter`
- If the user wants to filter by a **specific space group number (1–230)** or a **mineral/structure type** (e.g., rutile, spinel, perovskite) → you MUST use `fetch_structures_with_spg` (you can still combine with a base_filter).
- If the user wants to filter by a **band-gap range** → you MUST use `fetch_structures_with_bandgap` with base_filter and min/max.

## FILTER SYNTAX QUICK GUIDE
- **Equality**: `chemical_formula_reduced="O2Si"`
- **Substring**: `chemical_formula_descriptive CONTAINS "H2O"`
- **Lists**:  
  - HAS ALL: `elements HAS ALL "Al","O","Mg"`
  - HAS ANY: `elements HAS ANY "Si","O"`
  - HAS ONLY: `elements HAS ONLY "Si","O"`
- **Numbers**: `nelements=3`, `nelements>=2 AND nelements<=7`
- **Logic**: Combine with AND, OR, NOT (use parentheses)
- **Exact element set**: `elements HAS ALL "A","B" AND nelements=2`
> 💡 **Note**:  
> - If the user provides a concrete chemical formula (e.g., "MgO", "TiO2"), use `chemical_formula_reduced="..."` instead of element filters.  
> - If the user mentions an alloy or specific combination of elements without stoichiometry (e.g., "TiAl 合金", "只包含 Al 和 Zn"), prefer `elements HAS ONLY`.

## MINERAL-LIKE STRUCTURES
Users may ask about specific minerals (e.g., spinel, rutile) or about materials with a certain **structure type** (e.g., spinel-structured, perovskite-structured). These are not always the same: for example, "spinel" usually refers to the compound MgAl₂O₄, while "spinel-structured materials" include a family of compounds sharing similar symmetry and composition patterns (AB₂C₄).
To retrieve such materials:
- Use `chemical_formula_reduced` with space group when referring to a **specific compound** (e.g., “MgAl₂O₄”, “TiO₂”, “ZnS”).
- Use `chemical_formula_anonymous` and/or `elements HAS ANY` when referring to a **structure type family** (e.g., ABC₃, AB₂C₄).
- Use `fetch_structures_with_spg` when the structure is well-defined by its space group (e.g., rock salt, rutile).
- Use `fetch_structures_with_filter` when structure is inferred from formula or composition pattern.
- ✅ Always **explain to the user** whether you are retrieving a specific mineral compound or a broader structure-type family.
### Examples:
- 用户：找一些方镁石 → Tool: `fetch_structures_with_spg`, `chemical_formula_reduced="MgO"`, `spg_number=225` （此处用 spg 因为“方镁石”是矿物名；如果用户只写“MgO”，则必须用 `fetch_structures_with_filter`）  
- 用户：查找金红石 → Tool: `fetch_structures_with_spg`, `chemical_formula_reduced="O2Ti"`, `spg_number=136` （此处用 spg 因为“金红石”是矿物名；如果用户只写“TiO2”，则必须用 `fetch_structures_with_filter`）  
- 用户：找一些钙钛矿结构的材料 → Tool: `fetch_structures_with_filter`, `chemical_formula_anonymous="ABC3"`
- 用户：找一个钙钛矿 → Tool: `fetch_structures_with_spg`, `chemical_formula_reduced="CaO3Ti"`, `spg_number=221`, `n_results=1` （此处用 spg 因为“钙钛矿”是矿物名；如果用户只写“CaTiO3”，则必须用 `fetch_structures_with_filter`）  
- 用户：找一些尖晶石结构的材料 → Tool: `fetch_structures_with_filter`, `chemical_formula_anonymous="AB2C4" AND elements HAS ANY "O"`
- 用户：检索尖晶石 → Tool: `fetch_structures_with_spg`, `chemical_formula_reduced="Al2MgO4"`, `spg_number=227` （此处用 spg 因为“尖晶石”是矿物名；如果用户只写“Al2MgO4”，则必须用 `fetch_structures_with_filter`）  

## DEFAULT PROVIDERS
- Raw filter: alexandria, cmr, cod, mcloud, mcloudarchive, mp, mpdd, mpds, nmd, odbx, omdb, oqmd, tcod, twodmatpedia
- Space group (SPG): alexandria, cod, mpdd, nmd, odbx, oqmd, tcod
- Band gap (BG): alexandria, odbx, oqmd, mcloudarchive, twodmatpedia

## RESPONSE FORMAT
The response must always have three parts in order:  
1) A brief explanation of the applied filters and providers.  
2) A 📈 Markdown table listing all retrieved results.  
3) A 📦 download link for an archive (.tgz).  
The table must contain **all retrieved materials** in one complete Markdown table, without omissions, truncation, summaries, or ellipses. The number of rows must exactly equal `n_found`, and even if there are many results (up to 100), they must all be shown in the same table. The 📦 archive link is supplementary and can never replace the full table.  
表格中必须包含**所有检索到的材料**，必须完整列在一个 Markdown 表格中，绝对不能省略、缩写、总结或用“...”只展示部分，你必须展示全部检索到的材料在表格中！表格的行数必须与 `n_found` 完全一致，即使结果数量很多（最多 100 条），也必须全部列出。📦 压缩包链接只能作为补充，绝不能替代表格。  
Each table must always include the following six columns in this fixed order:  
(1) Formula (`attributes.chemical_formula_reduced`)  
(2) Elements (list of elements; infer from the chemical formula)
(3) Space group (`Symbol(Number)`; Keys may differ by provider (e.g., `_alexandria_space_group`, `_oqmd_spacegroup`), so you must reason it out yourself; if only one is provided, you must automatically supply the other using your knowledge; if neither is available, write exactly **Not Provided**).
(4) Download link (CIF or JSON file)  
(5) Provider (inferred from provider URL)  
(6) ID (`cleaned_structures[i]["id"]`)  
If any property is missing, it must be filled with exactly **Not Provided** (no slashes, alternatives, or translations). Extra columns (e.g., lattice vectors, band gap, formation energy) may only be added if explicitly requested; if such data is unavailable, also fill with **Not Provided**.  
If no results are found (`n_found = 0`), clearly state that no matching structures were retrieved, repeat the applied filters, and suggest loosening the criteria, but do not generate an empty table. Always verify that the number of table rows equals `n_found`; if they do not match, regenerate the table until correct. Never claim token or brevity issues, as results are already capped at 100 maximum.

## DEMOS (用户问题 → 工具与参数)
1) 用户：找3个ZrO，从mpds, cmr, alexandria, omdb, odbx里面找  
   → Tool: fetch_structures_with_filter  
     filter: chemical_formula_reduced="OZr"  # 注意元素要按字母表顺序  
     as_format: "cif"  
     providers: ["mpds", "cmr", "alexandria", "omdb", "odbx"]  
     n_results: 3

2) 用户：找到一些A2b3C4的材料，不能含有 Fe，F，Cl，H元素，要含有铝或者镁或者钠，我要全部信息。  
   → Tool: fetch_structures_with_filter  
     filter: chemical_formula_anonymous="A2B3C4" AND NOT (elements HAS ANY "Fe","F","Cl","H") AND (elements HAS ANY "Al","Mg","Na")  
     as_format: "json"

3) 用户：查找一个gamma相的TiAl合金  
   → Tool: fetch_structures_with_spg  
     base_filter: elements HAS ONLY "Ti","Al"  
     spg_number: 123  # γ-TiAl (L1₀) 常记作 P4/mmm，为 123空间群  
     as_format: "cif"  
     n_results: 1

4) 用户：检索四个含铝的，能带在1.0–2.0 eV 间的材料  
   → Tool: fetch_structures_with_bandgap  
     base_filter: elements HAS ALL "Al"  
     min_bg: 1.0  
     max_bg: 2.0  
     as_format: "json"  # 默认输出 json 格式，适用于能带相关查询  
     n_results: 4

5) 用户：找一些方镁石  
   → Tool: fetch_structures_with_spg  
     base_filter: chemical_formula_reduced="MgO"  
     spg_number: 225
"""


# === TOOL 1: RAW OPTIMADE FILTER ===
@mcp.tool()
async def fetch_structures_with_filter(
    filter: str,
    as_format: Format = "cif",
    n_results: int = 2,
    providers: Optional[List[str]] = None,
) -> FetchResult:
    """
    Fetch crystal structures using a RAW OPTIMADE filter (single request across providers).

    What this does
    --------------
    - Sends the *exact* `filter` string to all selected providers in a single aggregated query.
    - Saves up to `n_results` results per provider in the specified `as_format` ("cif" or "json").

    Arguments
    ---------
    filter : str
        An OPTIMADE filter expression. Examples:
          - elements HAS ALL "Al","O","Mg"
          - elements HAS ONLY "Si","O"
          - chemical_formula_reduced="O2Si"
          - chemical_formula_descriptive CONTAINS "H2O"
          - (elements HAS ANY "Si") AND NOT (elements HAS ANY "H")
    as_format : {"cif","json"}
        Output format for saved structures (default "cif").
    n_results : int
        Number of results to save from EACH provider (default 2).
    providers : list[str] | None
        Providers to query. If omitted, uses DEFAULT_PROVIDERS from utils.py.

    Returns
    -------
    FetchResult
        output_dir: Path to the folder with saved results
        cleaned_structures: List[dict]  # list of cleaned structures
        n_found: int  # number of structures found (0 if none)
    """
    filt = (filter or "").strip()
    if not filt:
        logging.error("[raw] empty filter string")
        return {"output_dir": Path(), "cleaned_structures": [], "n_found": 0}
    filt = normalize_cfr_in_filter(filt)

    used_providers = set(providers) if providers else DEFAULT_PROVIDERS
    
    # Get all URLs for the selected providers (flatten the lists)
    used_urls = [url for provider in used_providers 
                 for url in URLS_FROM_PROVIDERS.get(provider, [])]
    
    logging.info(f"[raw] providers={used_providers} urls={len(used_urls)} filter={filt}")

    try:
        client = OptimadeClient(
            base_urls=used_urls,
            # include_providers=used_providers,
            max_results_per_provider=n_results,
            http_timeout=25.0,
        )
        results = await to_thread.run_sync(lambda: client.get(filter=filt))
    except (SystemExit, Exception) as e:  # catch SystemExit too
        logging.error(f"[raw] fetch failed: {e}")
        return {"output_dir": Path(), "cleaned_structures": [], "n_found": 0}

    # Timestamped folder + short hash of filter for traceability
    tag = filter_to_tag(filt)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1(filt.encode("utf-8")).hexdigest()[:8]
    out_folder = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short}"

    files, warns, providers_seen, cleaned_structures = await to_thread.run_sync(
        save_structures, results, out_folder, n_results, as_format == "cif"
    )

    manifest = {
        "mode": "raw_filter",
        "filter": filt,
        "providers_requested": sorted(list(used_providers)),
        "providers_seen": providers_seen,
        "files": files,
        "warnings": warns,
        "format": as_format,
        "n_results": n_results,
        "n_found": len(cleaned_structures), 
    }
    (out_folder / "summary.json").write_text(json.dumps(manifest, indent=2))

    cleaned_structures = cleaned_structures[:MAX_RETURNED_STRUCTS]

    return {
        "output_dir": out_folder,
        "cleaned_structures": cleaned_structures,
        "n_found": len(cleaned_structures),
    }


# === TOOL 2: SPACE-GROUP AWARE FETCH (provider-specific fields, parallel) ===
@mcp.tool()
async def fetch_structures_with_spg(
    base_filter: Optional[str],
    spg_number: int,
    as_format: Format = "cif",
    n_results: int = 3,
    providers: Optional[List[str]] = None,
) -> FetchResult:
    """
    Fetch structures constrained by space group number across multiple providers in parallel.

    What this does
    --------------
    - Builds a provider-specific space-group clause (e.g., `_tcod_sg="P m -3 m"`, `_oqmd_spacegroup="Pm-3m"`,
      `_alexandria_space_group=221`, etc.) via `get_spg_filter_map`.
    - Combines it with your optional `base_filter` (elements/formula logic).
    - Runs per-provider queries **in parallel**, then saves all results into one folder.

    Arguments
    ---------
    base_filter : str | None
        Common OPTIMADE filter applied to all providers (e.g., "elements HAS ONLY \"Ti\",\"Al\"").
    spg_number : int
        International space-group number (1-230).
    as_format : {"cif","json"}
        Output format for saved structures (default "cif").
    n_results : int
        Number of results to save from EACH provider (default 3).
    providers : list[str] | None
        Providers to query. If omitted, uses DEFAULT_SPG_PROVIDERS from utils.py.

    Returns
    -------
    FetchResult
        output_dir: Path to the folder with saved results
        cleaned_structures: List[dict]  # list of cleaned structures
        n_found: int  # number of structures found (0 if none)
    """
    base = (base_filter or "").strip()
    base = normalize_cfr_in_filter(base)
    used = set(providers) if providers else DEFAULT_SPG_PROVIDERS

    # Build provider-specific SPG clauses and combine with base filter
    spg_map = get_spg_filter_map(spg_number, used)
    filters = build_provider_filters(base, spg_map)
    if not filters:
        logging.warning("[spg] no provider-specific space-group clause available")
        return {"output_dir": Path(), "cleaned_structures": [], "n_found": 0}

    async def _query_one(provider: str, clause: str) -> dict:
        logging.info(f"[spg] {provider}: {clause}")
        try:
            # Get all URLs for this provider (flatten the lists)
            provider_urls = [url for url in URLS_FROM_PROVIDERS.get(provider, [])]
            if not provider_urls:
                logging.warning(f"[spg] No URLs found for provider {provider}")
                return {"structures": {}}
                
            client = OptimadeClient(
                base_urls=provider_urls,
                max_results_per_provider=n_results,
                http_timeout=25.0,
            )
            return await to_thread.run_sync(lambda: client.get(filter=clause))
        except (SystemExit, Exception) as e:  # catch SystemExit too
            logging.error(f"[spg] fetch failed for {provider}: {e}")
            return {"structures": {}}

    # Parallel fan‑out per provider
    results_list = await asyncio.gather(
        *[_query_one(p, clause) for p, clause in filters.items()],
        return_exceptions=True,  # don't cancel all on one failure
    )

    # Turn any exceptions into empty result dicts
    norm_results = []
    for r in results_list:
        if isinstance(r, Exception):
            logging.error(f"[spg] task returned exception: {r}")
            norm_results.append({"structures": {}})
        else:
            norm_results.append(r)

    # Save all results together
    tag = filter_to_tag(f"{base} AND spg={spg_number}")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1(f"{base}|spg={spg_number}".encode("utf-8")).hexdigest()[:8]
    out_folder = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short}"

    all_files: List[str] = []
    all_warnings: List[str] = []
    all_providers: List[str] = []
    all_cleaned: List[dict] = []
    for res in norm_results:
        files, warns, providers_seen, cleaned = await to_thread.run_sync(
            save_structures, res, out_folder, n_results, as_format == "cif"
        )
        all_files.extend(files)
        all_warnings.extend(warns)
        all_providers.extend(providers_seen)
        all_cleaned.extend(cleaned)

    manifest = {
        "mode": "space_group",
        "base_filter": base,
        "spg_number": spg_number,
        "providers_requested": sorted(list(used)),
        "providers_seen": all_providers,
        "files": all_files,
        "warnings": all_warnings,
        "format": as_format,
        "n_results": n_results,
        "per_provider_filters": filters,
        "n_found": len(all_cleaned),
    }
    (out_folder / "summary.json").write_text(json.dumps(manifest, indent=2))

    all_cleaned = all_cleaned[:MAX_RETURNED_STRUCTS]

    return {
        "output_dir": out_folder,
        "cleaned_structures": all_cleaned,
        "n_found": len(all_cleaned),
    }


# === TOOL 3: BAND‑GAP RANGE FETCH (provider-specific fields, parallel) ===
@mcp.tool()
async def fetch_structures_with_bandgap(
    base_filter: Optional[str],
    min_bg: Optional[float] = None,
    max_bg: Optional[float] = None,
    as_format: Format = "cif",
    n_results: int = 2,
    providers: Optional[List[str]] = None,
) -> FetchResult:
    """
    Fetch structures constrained by band-gap range across multiple providers in parallel.

    What this does
    --------------
    - Resolves provider-specific band-gap property names (e.g., `_oqmd_band_gap`, `_gnome_bandgap`,
      `_mcloudarchive_band_gap`, etc.) via `get_bandgap_filter_map`.
    - Builds a per-provider band-gap clause (min/max inclusive), combines with your optional `base_filter`.
    - Runs each provider query **in parallel**, then saves all results into one folder.

    Arguments
    ---------
    base_filter : str | None
        Common OPTIMADE filter applied to all providers (e.g., 'elements HAS ALL "Al"').
    min_bg, max_bg : float | None
        Band-gap range in eV (open-ended allowed, e.g., min only or max only).
    as_format : {"cif","json"}
        Output format for saved structures (default "cif").
    n_results : int
        Number of results to save from EACH provider (default 2).
    providers : list[str] | None
        Providers to query; if None, uses DEFAULT_BG_PROVIDERS from utils.py.

    Returns
    -------
    FetchResult
        output_dir: Path to the folder with saved results
        cleaned_structures: List[dict]  # list of cleaned structures
        n_found: int  # number of structures found (0 if none)
    """
    base = (base_filter or "").strip()
    base = normalize_cfr_in_filter(base)
    used = set(providers) if providers else DEFAULT_BG_PROVIDERS

    # Build per-provider bandgap clause and combine with base
    bg_map = get_bandgap_filter_map(min_bg, max_bg, used)
    filters = build_provider_filters(base, bg_map)

    if not filters:
        logging.warning("[bandgap] no provider-specific band-gap clause available")
        return {"output_dir": Path(), "cleaned_structures": [], "n_found": 0}

    async def _query_one(provider: str, clause: str) -> dict:
        logging.info(f"[bandgap] {provider}: {clause}")
        try:
            # Get all URLs for this provider (flatten the lists)
            provider_urls = [url for url in URLS_FROM_PROVIDERS.get(provider, [])]
            if not provider_urls:
                logging.warning(f"[bandgap] No URLs found for provider {provider}")
                return {"structures": {}}
                
            client = OptimadeClient(
                base_urls=provider_urls,
                max_results_per_provider=n_results,
                http_timeout=25.0,
            )
            return await to_thread.run_sync(lambda: client.get(filter=clause))
        except (SystemExit, Exception) as e:  # catch SystemExit too
            logging.error(f"[bandgap] fetch failed for {provider}: {e}")
            return {"structures": {}}

    # Parallel fan‑out per provider
    results_list = await asyncio.gather(
        *[_query_one(p, clause) for p, clause in filters.items()],
        return_exceptions=True,  # don't cancel all on one failure
    )
    norm_results = []
    for r in results_list:
        if isinstance(r, Exception):
            logging.error(f"[bandgap] task returned exception: {r}")
            norm_results.append({"structures": {}})
        else:
            norm_results.append(r)

    # Save all results together
    tag = filter_to_tag(f"{base} AND bandgap[{min_bg},{max_bg}]")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1(f"{base}|bg={min_bg}:{max_bg}".encode("utf-8")).hexdigest()[:8]
    out_folder = BASE_OUTPUT_DIR / f"{tag}_{ts}_{short}"

    all_files: List[str] = []
    all_warnings: List[str] = []
    all_providers: List[str] = []
    all_cleaned: List[dict] = []
    for res in norm_results:
        files, warns, providers_seen, cleaned = await to_thread.run_sync(
            save_structures, res, out_folder, n_results, as_format == "cif"
        )
        all_files.extend(files)
        all_warnings.extend(warns)
        all_providers.extend(providers_seen)
        all_cleaned.extend(cleaned)

    manifest = {
        "mode": "band_gap",
        "base_filter": base,
        "band_gap_min": min_bg,
        "band_gap_max": max_bg,
        "providers_requested": sorted(list(used)),
        "providers_seen": all_providers,
        "files": all_files,
        "warnings": all_warnings,
        "format": as_format,
        "n_results": n_results,
        "per_provider_filters": filters,
        "n_found": len(all_cleaned),
    }
    (out_folder / "summary.json").write_text(json.dumps(manifest, indent=2))

    all_cleaned = all_cleaned[:MAX_RETURNED_STRUCTS]

    return {
        "output_dir": out_folder,
        "cleaned_structures": all_cleaned,
        "n_found": len(all_cleaned),
    }


# === RUN MCP SERVER ===
if __name__ == "__main__":
    logging.info("Starting Optimade MCP Server…")
    mcp.run(transport="sse")