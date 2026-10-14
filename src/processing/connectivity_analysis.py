
from pathlib import Path
import json
import math

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, MultiLineString, Point, mapping


# --------------------------------------------------
# FLOODRA: Scenario-Based Road Connectivity Analysis
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

ROADS_FILE = BASE_DIR / "data" / "processed" / "real_flooded_roads.geojson"
SETTLEMENTS_FILE = BASE_DIR / "data" / "raw" / "real_settlements.geojson"
OUTPUT_FILE = (
    BASE_DIR / "data" / "processed" / "connectivity_analysis.geojson"
)

# Do not classify settlements as disconnected if they cannot
# be reliably snapped to the road network.
MAX_SNAP_DISTANCE_M = 500
NODE_PRECISION_M = 1.0

HIGH_RISK = "HIGH RISK"


def load_geojson(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}\n"
            "Run the relevant FLOODRA processing script first."
        )

    return gpd.read_file(path)


def make_valid_geodataframe(gdf, name):
    if gdf.empty:
        raise ValueError(f"{name} contains no features.")

    if gdf.crs is None:
        raise ValueError(f"{name} has no CRS. Cannot calculate distances.")

    gdf = gdf[gdf.geometry.notna()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    if gdf.empty:
        raise ValueError(f"{name} has no usable geometries.")

    return gdf


def get_projected_layers(roads, settlements):
    """
    Use a local projected CRS so nearest-road distances are measured
    in metres rather than degrees.
    """
    if roads.crs != settlements.crs:
        settlements = settlements.to_crs(roads.crs)

    projected_crs = roads.estimate_utm_crs()

    if projected_crs is None:
        raise ValueError("Could not determine a suitable projected CRS.")

    return (
        roads.to_crs(projected_crs),
        settlements.to_crs(projected_crs),
        projected_crs,
    )


def node_key(x, y):
    """Snap coordinates to a consistent metric grid."""
    return (
        round(float(x) / NODE_PRECISION_M),
        round(float(y) / NODE_PRECISION_M),
    )


def add_line_to_graph(graph, line, properties):
    """
    Convert a LineString into graph edges using its consecutive
    coordinate pairs. MultiLineStrings are handled by the caller.
    """
    coordinates = list(line.coords)

    if len(coordinates) < 2:
        return

    for start, end in zip(coordinates[:-1], coordinates[1:]):
        x1, y1 = start[:2]
        x2, y2 = end[:2]

        first_node = node_key(x1, y1)
        second_node = node_key(x2, y2)

        if first_node == second_node:
            continue

        length_m = math.hypot(x2 - x1, y2 - y1)

        if length_m <= 0:
            continue

        graph.add_edge(
            first_node,
            second_node,
            weight=length_m,
            risk_level=str(properties.get("risk_level", "UNKNOWN")),
        )


def build_road_graph(roads, exclude_high_risk=False):
    graph = nx.Graph()

    for _, row in roads.iterrows():
        geometry = row.geometry
        properties = row.to_dict()

        risk_level = str(properties.get("risk_level", "UNKNOWN")).upper()

        if exclude_high_risk and risk_level == HIGH_RISK:
            continue

        if isinstance(geometry, LineString):
            add_line_to_graph(graph, geometry, properties)

        elif isinstance(geometry, MultiLineString):
            for line in geometry.geoms:
                add_line_to_graph(graph, line, properties)

    return graph


def nearest_node(graph, point):
    """Return the nearest graph node and its distance in metres."""
    if graph.number_of_nodes() == 0:
        return None, None

    best_node = None
    best_distance = float("inf")

    for node in graph.nodes:
        x = node[0] * NODE_PRECISION_M
        y = node[1] * NODE_PRECISION_M
        distance = math.hypot(point.x - x, point.y - y)

        if distance < best_distance:
            best_distance = distance
            best_node = node

    return best_node, best_distance


def largest_component(graph):
    if graph.number_of_nodes() == 0:
        return set()

    return set(max(nx.connected_components(graph), key=len))


def analyze_connectivity(roads, settlements):
    roads_m, settlements_m, projected_crs = get_projected_layers(
        roads, settlements
    )

    baseline_graph = build_road_graph(
        roads_m,
        exclude_high_risk=False,
    )

    scenario_graph = build_road_graph(
        roads_m,
        exclude_high_risk=True,
    )

    baseline_largest = largest_component(baseline_graph)
    scenario_largest = largest_component(scenario_graph)

    print(f"Projected CRS: {projected_crs}")
    print(f"Baseline graph nodes: {baseline_graph.number_of_nodes()}")
    print(f"Scenario graph nodes: {scenario_graph.number_of_nodes()}")
    print(f"Scenario largest component: {len(scenario_largest)} nodes")

    results = []

    for _, settlement in settlements_m.iterrows():
        geometry = settlement.geometry

        if geometry.geom_type == "Point":
            point = geometry
        else:
            point = geometry.representative_point()

        baseline_node, baseline_distance = nearest_node(
            baseline_graph, point
        )

        scenario_node, scenario_distance = nearest_node(
            scenario_graph, point
        )

        baseline_snapped = (
            baseline_node is not None
            and baseline_distance <= MAX_SNAP_DISTANCE_M
        )

        scenario_snapped = (
            scenario_node is not None
            and scenario_distance <= MAX_SNAP_DISTANCE_M
        )

        if not scenario_snapped:
            connected = None
            component_size = None
            status = "UNKNOWN"
        else:
            connected = scenario_node in scenario_largest
            component_size = len(
                nx.node_connected_component(scenario_graph, scenario_node)
            )
            status = "CONNECTED" if connected else "POTENTIALLY DISCONNECTED"

        properties = {
            key: value
            for key, value in settlement.items()
            if key != "geometry"
        }

        # Convert NumPy scalar values into JSON-compatible Python values.
        clean_properties = {}
        for key, value in properties.items():
            if hasattr(value, "item"):
                value = value.item()

            if value is None:
                clean_properties[key] = None
            elif isinstance(value, float) and not math.isfinite(value):
                clean_properties[key] = None
            else:
                clean_properties[key] = value

        clean_properties.update({
            "baseline_connected": bool(baseline_snapped),
            "baseline_snap_distance_m": (
                round(float(baseline_distance), 2)
                if baseline_distance is not None else None
            ),
            "snapped_to_network": bool(scenario_snapped),
            "snap_distance_m": (
                round(float(scenario_distance), 2)
                if scenario_distance is not None else None
            ),
            "scenario_connected_to_largest_component": connected,
            "scenario_component_size": component_size,
            "connectivity_status": status,
            "scenario": "HIGH_RISK_ROADS_EXCLUDED",
            "max_snap_distance_m": MAX_SNAP_DISTANCE_M,
        })

        results.append({
            "type": "Feature",
            "geometry": mapping(point),
            "properties": clean_properties,
        })

    output = {
        "type": "FeatureCollection",
        "features": results,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, allow_nan=False)

    connected_count = sum(
        feature["properties"]["connectivity_status"] == "CONNECTED"
        for feature in results
    )
    disconnected_count = sum(
        feature["properties"]["connectivity_status"]
        == "POTENTIALLY DISCONNECTED"
        for feature in results
    )
    unknown_count = sum(
        feature["properties"]["connectivity_status"] == "UNKNOWN"
        for feature in results
    )

    print("\nFLOODRA Connectivity Analysis Complete")
    print("--------------------------------------")
    print(f"Settlements analyzed: {len(results)}")
    print(f"Connected to largest component: {connected_count}")
    print(f"Potentially disconnected: {disconnected_count}")
    print(f"Unknown / too far from network: {unknown_count}")
    print(f"Output: {OUTPUT_FILE}")
    print(
        "\nImportant: this is a graph-based scenario estimate. "
        "It does not prove real-world isolation or account for "
        "every road closure, bridge failure, or access restriction."
    )


def main():
    roads = make_valid_geodataframe(
        load_geojson(ROADS_FILE), "Road risk data"
    )
    settlements = make_valid_geodataframe(
        load_geojson(SETTLEMENTS_FILE), "Settlement data"
    )

    if "risk_level" not in roads.columns:
        raise ValueError(
            "Road data is missing 'risk_level'. "
            "Run real_road_risk.py first."
        )

    analyze_connectivity(roads, settlements)


if __name__ == "__main__":
    main()
