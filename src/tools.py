"""LangChain tools available to the fishing chatbot."""

from __future__ import annotations

from typing import Literal

from ddgs import DDGS
from langchain.mcp import MCPAdapter
from langchain_core.tools import tool

from .catch_repository import get_catch_summary, get_catches


# Readable tool names for the UI (status box and "Context used" view).
TOOL_LABELS = {
    "search_personal_catches": "Personal Catches",
    "search_fishing_knowledge": "Web Search",
    "openmeteo_search_locations": "Weather Location Search",
    "openmeteo_get_forecast": "Weather Forecast",
}

# Keeps individual catch lists short in the model context.
MAX_LISTED_CATCHES = 20


# ---------------------------------------------------------------------------
# Personal catch tool
# ---------------------------------------------------------------------------

@tool
def search_personal_catches(
    species: str | None = None,
    location: str | None = None,
    bundesland: str | None = None,
    min_length_cm: float | None = None,
    max_length_cm: float | None = None,
    min_weight_kg: float | None = None,
    max_weight_kg: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    result_type: Literal["summary", "list", "record"] = "summary",
    sort_by: Literal[
        "date_desc",
        "date_asc",
        "length_desc",
        "weight_desc",
        "name_asc",
    ] = "date_desc",
    limit: int = 10,
) -> dict:
    """Search the user's personal fishing catches.

    Use this only for questions about fish the user personally caught.

    Args:
        species: Fish species, for example Pike, Perch or Zander.
        location: Specific catch location, for example a lake or river.
        bundesland: German federal state such as Brandenburg or Berlin.
        min_length_cm: Minimum fish length in centimeters.
        max_length_cm: Maximum fish length in centimeters.
        min_weight_kg: Minimum fish weight in kilograms.
        max_weight_kg: Maximum fish weight in kilograms.
        start_date: Earliest catch date in YYYY-MM-DD format.
        end_date: Latest catch date in YYYY-MM-DD format.
        result_type: Use summary for counts/averages, list for individual
            catches, and record for one relevant catch.
        sort_by: Ordering of list/record results. Use length_desc for longest
            fish and weight_desc for heaviest fish.
        limit: Maximum number of individual catches. Values are capped at 20.
    """

    filters = {
        "species": species,
        "location": location,
        "bundesland": bundesland,
        "date_from": start_date,
        "date_to": end_date,
        "min_length": min_length_cm,
        "max_length": max_length_cm,
        "min_weight": min_weight_kg,
        "max_weight": max_weight_kg,
    }

    if result_type == "summary":
        return {
            "result_type": "summary",
            "summary": get_catch_summary(**filters),
        }

    if result_type == "record":
        limit = 1
    else:
        limit = max(1, min(int(limit), MAX_LISTED_CATCHES))

    catches = get_catches(**filters, sort_by=sort_by, limit=limit)

    # Never send image BLOBs into the LLM context.
    for catch in catches:
        del catch["image"]

    return {
        "result_type": result_type,
        "count_returned": len(catches),
        "catches": catches,
    }


# ---------------------------------------------------------------------------
# Web search tool
# ---------------------------------------------------------------------------

@tool
def search_fishing_knowledge(query: str) -> dict:
    """Search the internet for general fishing and fish knowledge.

    Use this tool for questions about fish species and fishing knowledge,
    for example:
    - fish habitat and behavior
    - seasonal behavior
    - water temperature and depth
    - diet and prey
    - spawning
    - typical size and weight
    - fishing techniques and strategies

    Do NOT use this tool for:
    - fishing regulations or legal questions
    - questions about the user's personal catches

    Args:
        query: A complete search query describing the information needed.
    """

    results = DDGS().text(query, max_results=5)

    return {
        "query": query,
        "results": [
            {
                "title": result.get("title"),
                "url": result.get("href"),
                "content": result.get("body"),
            }
            for result in results
        ],
    }


LOCAL_TOOLS = [
    search_personal_catches,
    search_fishing_knowledge,
]


# ---------------------------------------------------------------------------
# Weather MCP tools
# ---------------------------------------------------------------------------

WEATHER_MCP_URL = "https://open-meteo.caseyjhand.com/mcp"

WEATHER_TOOL_NAMES = {
    "openmeteo_search_locations",
    "openmeteo_get_forecast",
}


async def get_weather_tools():
    """Load the weather tools we need from the Open-Meteo MCP server."""

    async with MCPAdapter(WEATHER_MCP_URL) as adapter:
        all_tools = await adapter.list_tools()

    return [
        mcp_tool
        for mcp_tool in all_tools
        if mcp_tool.name in WEATHER_TOOL_NAMES
    ]


async def get_chat_tools():
    """Return all tools available to the fishing chatbot."""

    try:
        weather_tools = await get_weather_tools()
    except Exception as exc:
        print(f"Weather MCP server unavailable: {exc}")
        weather_tools = []

    return [*LOCAL_TOOLS, *weather_tools]
