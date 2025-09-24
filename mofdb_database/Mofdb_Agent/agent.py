import os
import nest_asyncio
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams
from dp.agent.adapter.adk import CalculationMCPToolset

# === 1. Environment & asyncio setup ===
load_dotenv()
nest_asyncio.apply()

# === Executors & Storage (same as OpenLAM for consistency) ===
LOCAL_EXECUTOR = {
    "type": "local"
}

HTTPS_STORAGE = {
    "type": "https",
    "plugin": {
        "type": "bohrium",
        "access_key": os.getenv("BOHRIUM_ACCESS_KEY"),
        "project_id": int(os.getenv("BOHRIUM_PROJECT_ID")),
        "app_key": "agent"
    }
}

server_url = os.getenv("SERVER_URL")

# === 2. Initialize MCP tools for MOFdb ===
mcp_tools = CalculationMCPToolset(
    connection_params=SseServerParams(url=server_url),
    storage=HTTPS_STORAGE,
    executor=LOCAL_EXECUTOR,
)

# === 3. Define Agent ===
root_agent = LlmAgent(
    model=LiteLlm(model="deepseek/deepseek-chat"),
    name="MOFdb_Agent",
    description="Retrieves MOF structures from the MOFdb database with filters for pore size, surface area, and database source.",
    instruction=(
        "You can call one MCP tool exposed by the MOFdb server:\n\n"

        "=== TOOL: fetch_mofs ===\n"
        "Use this tool to query the MOFdb database.\n"
        "It supports filtering by:\n"
        "• mofid (unique MOF identifier)\n"
        "• mofkey (hashed key for MOF structure)\n"
        "• name (MOF name)\n"
        "• database (one of: 'CoREMOF 2014', 'CoREMOF 2019', 'CSD', 'hMOF', 'IZA', 'PCOD-syn', 'Tobacco')\n"
        "• vf_min / vf_max (void fraction)\n"
        "• lcd_min / lcd_max (largest cavity diameter)\n"
        "• pld_min / pld_max (pore limiting diameter)\n"
        "• sa_m2g_min / sa_m2g_max (surface area per gram)\n"
        "• sa_m2cm3_min / sa_m2cm3_max (surface area per cm³)\n"
        "• n_results (max number of MOFs to return)\n"
        "• output_formats (list of 'json' or 'cif')\n\n"

        "=== EXAMPLES ===\n"
        "1) 查找 Tobacco 数据库中的某个 MOF：\n"
        "   → Tool: fetch_mofs\n"
        "     name: 'tobmof-27'\n"
        "     database: 'Tobacco'\n"
        "     n_results: 3\n"
        "     output_formats: ['cif']\n\n"

        "2) 查找比表面积 500–1000 m²/g 且 LCD 在 6–8 Å 之间的 MOF：\n"
        "   → Tool: fetch_mofs\n"
        "     sa_m2g_min: 500\n"
        "     sa_m2g_max: 1000\n"
        "     lcd_min: 6.0\n"
        "     lcd_max: 8.0\n"
        "     n_results: 10\n"
        "     output_formats: ['json']\n\n"

        "=== OUTPUT ===\n"
        "- The tool returns:\n"
        "   • output_dir: path to saved structures\n"
        "   • n_found: number of matching MOFs\n"
        "   • cleaned_structures: list of MOF dicts\n\n"

        "=== NOTES ===\n"
        "- Use 'json' if the user asks for metadata (pore sizes, surface area, database info).\n"
        "- Use 'cif' for structural visualization.\n"
        "- All filters are optional, but combining multiple filters improves precision.\n\n"

        "=== ANSWER FORMAT ===\n"
        "1. Summarize the filters used\n"
        "2. Report the number of MOFs found\n"
        "3. Return the output directory path\n"
    ),
    tools=[mcp_tools],
)