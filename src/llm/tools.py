"""
LLM Tool Calling 工具 — web_search 实现。

支持 Tavily / SerpAPI 两种搜索后端，通过环境变量 SEARCH_PROVIDER 切换。
用于 Phase 3.5 商业知识检索 Agent 的实时搜索能力。
"""

from __future__ import annotations

import json
import os
from typing import Any

from loguru import logger

# ══════════════════════════════════════════════════════════════
# Tool Schema 定义 (OpenAI/DeepSeek 兼容格式)
# ══════════════════════════════════════════════════════════════

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "搜索互联网获取公司最新商业信息、新闻报道、行业动态、监管公告。"
            "用于获取管理层变动、行业排名、风险事件、分红政策等实时信息。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，建议使用公司名称+具体问题，如「贵州茅台 2025年管理层变动」",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["news", "general", "financial"],
                    "description": (
                        "搜索类型: news=近2年新闻, general=综合搜索, "
                        "financial=财务/监管公告"
                    ),
                },
            },
            "required": ["query"],
        },
    },
}

# 商业检索 Agent 可用的全部工具
BUSINESS_RETRIEVAL_TOOLS = [WEB_SEARCH_TOOL]


# ══════════════════════════════════════════════════════════════
# 搜索后端实现
# ══════════════════════════════════════════════════════════════


def _search_provider() -> str:
    """返回当前搜索后端: tavily | serpapi | none。"""
    return os.environ.get("SEARCH_PROVIDER", "none").lower()


def _search_tavily(query: str, search_type: str = "general") -> str:
    """通过 Tavily API 搜索。"""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        logger.warning("TAVILY_API_KEY 未配置")
        return ""

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        include_domains = []
        if search_type == "financial":
            include_domains = ["cninfo.com.cn", "sse.com.cn", "szse.cn"]

        response = client.search(
            query=query,
            search_depth="advanced" if search_type != "general" else "basic",
            include_domains=include_domains if include_domains else None,
            max_results=5,
        )

        results: list[str] = []
        for r in response.get("results", [])[:5]:
            title = r.get("title", "")
            url = r.get("url", "")
            content = r.get("content", "")[:300]
            results.append(f"**{title}**\n{content}\nURL: {url}")

        return "\n\n".join(results) if results else "(无搜索结果)"

    except ImportError:
        logger.warning("tavily-python 未安装，请运行: pip install tavily-python")
        return ""
    except Exception as e:
        logger.warning(f"Tavily 搜索失败: {e}")
        return ""


def _search_serpapi(query: str, search_type: str = "general") -> str:
    """通过 SerpAPI 搜索。"""
    api_key = os.environ.get("SERPAPI_API_KEY", "")
    if not api_key:
        logger.warning("SERPAPI_API_KEY 未配置")
        return ""

    try:
        import requests

        params: dict[str, Any] = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": 5,
            "hl": "zh-CN",
            "gl": "cn",
        }
        if search_type == "news":
            params["tbm"] = "nws"

        resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results: list[str] = []
        items = data.get("organic_results", data.get("news_results", []))[:5]
        for r in items:
            title = r.get("title", "")
            url = r.get("link", "")
            snippet = r.get("snippet", "")[:300]
            results.append(f"**{title}**\n{snippet}\nURL: {url}")

        return "\n\n".join(results) if results else "(无搜索结果)"

    except Exception as e:
        logger.warning(f"SerpAPI 搜索失败: {e}")
        return ""


def execute_web_search(query: str, search_type: str = "general") -> str:
    """执行 web 搜索，自动选择后端。

    Args:
        query: 搜索关键词
        search_type: news | general | financial

    Returns:
        格式化的搜索结果 Markdown 文本，无结果时返回空字符串
    """
    provider = _search_provider()

    if provider == "none":
        logger.info(f"SEARCH_PROVIDER=none，跳过 web_search: {query[:60]}")
        return ""

    if provider == "tavily":
        return _search_tavily(query, search_type)
    elif provider == "serpapi":
        return _search_serpapi(query, search_type)
    else:
        logger.warning(f"未知搜索后端: {provider}，尝试 Tavily...")
        result = _search_tavily(query, search_type)
        if not result:
            result = _search_serpapi(query, search_type)
        return result


# ══════════════════════════════════════════════════════════════
# Tool 执行分发器
# ══════════════════════════════════════════════════════════════


def execute_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """执行单个 tool call 并返回结果字符串。

    Args:
        tool_name: 函数名 (如 "web_search")
        arguments: 函数参数 dict

    Returns:
        工具执行结果文本
    """
    if tool_name == "web_search":
        query = arguments.get("query", "")
        search_type = arguments.get("search_type", "general")
        if not query:
            return json.dumps({"error": "query 参数不能为空"}, ensure_ascii=False)
        result = execute_web_search(query, search_type)
        return result if result else json.dumps(
            {"status": "no_results", "message": "未找到搜索结果或搜索不可用"},
            ensure_ascii=False,
        )

    logger.warning(f"未知 tool: {tool_name}")
    return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
