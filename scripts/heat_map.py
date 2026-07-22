import geopandas as gpd
import folium

from scripts.repository import get_barangay_stats_df


def generate_heat_map():
    geojson_path = "./static/assets/Imus.geojson"
    barangay_map = gpd.read_file(geojson_path)

    df = get_barangay_stats_df()
    if df.empty:
        m = folium.Map(location=[14.4296, 120.9367], zoom_start=13)
        return m._repr_html_()

    barangay_map["NAME_3"] = barangay_map["NAME_3"].str.strip().str.title()
    barangay_map = barangay_map.merge(df, left_on="NAME_3", right_on="Barangay Name")

    m = folium.Map(location=[14.4296, 120.9367], zoom_start=13)

    folium.Choropleth(
        geo_data=barangay_map,
        name="choropleth",
        data=barangay_map,
        columns=["Barangay Name", "Count of barangay"],
        key_on="feature.properties.NAME_3",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Traffic Incident Count",
    ).add_to(m)

    return m._repr_html_()
