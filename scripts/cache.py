import logging
import os
import threading

from scripts.bar_graph import generate_bar_graph
from scripts.barangay_list import generate_barangay_list
from scripts.chart import generate_chart

_dashboard_cache = None
_barangay_list_cache = None
_heat_map_html = None
_insights_cache = None
_cache_lock = threading.Lock()
_heat_lock = threading.Lock()
logger = logging.getLogger(__name__)

HEATMAP_PLACEHOLDER = (
    '<div class="heat-map-placeholder" data-heatmap-pending="1">'
    "<p>Loading map…</p>"
    "</div>"
)


def _lean_host() -> bool:
    return os.environ.get("RENDER", "").lower() in ("true", "1") or os.environ.get(
        "LEAN_CACHE", ""
    ).lower() in ("1", "true", "yes")


def warm_dashboard_cache(include_heat_map: bool = False):
    """Warm Plotly charts + barangay list. Folium heatmap is optional (memory-heavy)."""
    global _dashboard_cache, _barangay_list_cache
    with _cache_lock:
        if _dashboard_cache is None or _barangay_list_cache is None:
            logger.info("Warming dashboard chart cache…")
            _dashboard_cache = {
                "bar_graph": generate_bar_graph(),
                "chart_2022": generate_chart(2022),
                "chart_2023": generate_chart(2023),
                "chart_2024": generate_chart(2024),
                "heat_map": HEATMAP_PLACEHOLDER,
            }
            _barangay_list_cache = generate_barangay_list()
            logger.info("Dashboard chart cache ready.")

    if include_heat_map:
        get_heat_map_html()


def ensure_heat_map():
    """Build Folium map once (deferred — main OOM risk on free Render)."""
    get_heat_map_html()


def get_heat_map_html() -> str:
    global _heat_map_html, _dashboard_cache
    with _heat_lock:
        if _heat_map_html is not None:
            return _heat_map_html
        logger.info("Generating Folium heatmap…")
        from scripts.heat_map import generate_heat_map

        _heat_map_html = generate_heat_map()
        if _dashboard_cache is not None:
            _dashboard_cache["heat_map"] = _heat_map_html
        logger.info("Folium heatmap ready.")
        return _heat_map_html


def warm_insights_cache(model):
    """Precompute city rankings + hour-risk (expensive peak-risk scan)."""
    global _insights_cache
    if model is None:
        return
    with _cache_lock:
        if _insights_cache is not None:
            return
        logger.info("Warming insights cache…")
        from scripts.dashboard_insights import build_city_insights

        _insights_cache = build_city_insights(model, lean=_lean_host())
        logger.info("Insights cache ready.")


def get_dashboard_html():
    if _dashboard_cache is None:
        warm_dashboard_cache(include_heat_map=False)
    return _dashboard_cache


def get_barangay_list_cached():
    if _barangay_list_cache is None:
        warm_dashboard_cache(include_heat_map=False)
    return _barangay_list_cache


def get_city_insights_cached(model=None):
    global _insights_cache
    if _insights_cache is None and model is not None:
        warm_insights_cache(model)
    return _insights_cache
