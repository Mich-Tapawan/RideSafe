from scripts.bar_graph import generate_bar_graph
from scripts.barangay_list import generate_barangay_list
from scripts.chart import generate_chart
from scripts.heat_map import generate_heat_map

_dashboard_cache = None
_barangay_list_cache = None
_insights_cache = None


def warm_dashboard_cache():
    global _dashboard_cache, _barangay_list_cache
    _dashboard_cache = {
        "bar_graph": generate_bar_graph(),
        "heat_map": generate_heat_map(),
        "chart_2022": generate_chart(2022),
        "chart_2023": generate_chart(2023),
        "chart_2024": generate_chart(2024),
    }
    _barangay_list_cache = generate_barangay_list()


def warm_insights_cache(model):
    """Precompute city rankings + hour-risk (expensive peak-risk scan)."""
    global _insights_cache
    from scripts.dashboard_insights import build_city_insights

    _insights_cache = build_city_insights(model)


def get_dashboard_html():
    if _dashboard_cache is None:
        warm_dashboard_cache()
    return _dashboard_cache


def get_barangay_list_cached():
    if _barangay_list_cache is None:
        warm_dashboard_cache()
    return _barangay_list_cache


def get_city_insights_cached(model=None):
    global _insights_cache
    if _insights_cache is None and model is not None:
        warm_insights_cache(model)
    return _insights_cache
