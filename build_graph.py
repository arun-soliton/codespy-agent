"""Build a knowledge graph from the static analysis JSON output."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Tuple

import matplotlib.pyplot as plt
import networkx as nx
from networkx.readwrite import json_graph


# =============================================================================
# Configuration - adjust these constants instead of using CLI arguments.
# =============================================================================

# Path to the analysis JSON. Use None to fall back to output/analysis.json next to this script.
ANALYSIS_PATH: Path | str | None = None

# Graph export configuration.
GRAPH_OUTPUT_FORMAT: str = "json"  # Options: graphml, gexf, json
GRAPH_OUTPUT_PATH: Path | str | None = (
    None  # None keeps the default alongside the analysis file.
)

# Neo4j export configuration.
NEO4J_EXPORT_ENABLED: bool = True  # Set True to export graph to Neo4j
NEO4J_URI: str = "bolt://localhost:7687"
NEO4J_USERNAME: str = "neo4j"
NEO4J_PASSWORD: str = "secret_code"
NEO4J_DATABASE: str = "neo4j"  # Use "neo4j" for default database
NEO4J_CLEAR_EXISTING: bool = True  # Clear existing graph data before import

# Visualization configuration.
RENDER_SHOW: bool = True  # Set True to display the matplotlib window.
RENDER_SAVE_PATH: Path | str | None = (
    Path(__file__).resolve().parent / "output" / "analysis_graph.png"
)  # Set to None to skip PNG rendering.


def load_analysis(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def default_analysis_path() -> Path:
    return Path(__file__).resolve().parent / "output" / "analysis.json"


def ensure_function_node(
    graph: nx.DiGraph,
    registry: Dict[str, str],
    entry: Dict[str, Any],
    *,
    kind: str,
    owner: str | None = None,
    external: bool = False,
) -> str:
    qualified = entry.get("qualified") or entry.get("name") or "<anonymous>"
    node_id = f"function::{qualified}"

    if node_id not in graph:
        location = entry.get("location") or {}
        attrs: Dict[str, Any] = {
            "type": kind,
            "label": qualified,
            "name": entry.get("name", qualified),
            "external": str(external).lower(),
        }
        if owner:
            attrs["owner"] = owner
        if location.get("file"):
            attrs["file"] = location["file"]
        if location.get("line") is not None:
            attrs["line"] = str(location["line"])
        description = entry.get("description")
        if description:
            attrs["description"] = description
        graph.add_node(node_id, **attrs)
    else:
        node_attrs = graph.nodes[node_id]
        if owner:
            node_attrs.setdefault("owner", owner)
        description = entry.get("description")
        if description and not node_attrs.get("description"):
            node_attrs["description"] = description

    registry[qualified] = node_id
    return node_id


def build_graph(data: Dict[str, Any]) -> Tuple[nx.DiGraph, Dict[str, str]]:
    graph = nx.DiGraph()
    functions: Dict[str, str] = {}

    for class_entry in data.get("classes", []):
        class_name = class_entry.get("name", "<anonymous>")
        class_id = f"class::{class_name}"
        graph.add_node(class_id, type="class", label=class_name, name=class_name)

        for method in class_entry.get("methods", []):
            method_id = ensure_function_node(
                graph,
                functions,
                method,
                kind="method",
                owner=class_name,
                external=False,
            )
            graph.add_edge(class_id, method_id, type="member")

    for free_function in data.get("free_functions", []):
        ensure_function_node(
            graph,
            functions,
            free_function,
            kind="function",
            owner=None,
            external=False,
        )

    for class_entry in data.get("classes", []):
        for method in class_entry.get("methods", []):
            caller_id = functions.get(method.get("qualified"))
            if not caller_id:
                continue
            for call in method.get("calls", []):
                callee_id = functions.get(call.get("qualified"))
                if not callee_id:
                    callee_id = ensure_function_node(
                        graph,
                        functions,
                        {
                            "name": call.get("name"),
                            "qualified": call.get("qualified") or call.get("name"),
                            "location": call.get("location", {}),
                        },
                        kind=(
                            "external_function"
                            if call.get("external", True)
                            else "function"
                        ),
                        owner=None,
                        external=call.get("external", True),
                    )
                if not graph.has_edge(caller_id, callee_id):
                    graph.add_edge(caller_id, callee_id, type="calls")

    for free_function in data.get("free_functions", []):
        caller_id = functions.get(free_function.get("qualified"))
        if not caller_id:
            continue
        for call in free_function.get("calls", []):
            callee_id = functions.get(call.get("qualified"))
            if not callee_id:
                callee_id = ensure_function_node(
                    graph,
                    functions,
                    {
                        "name": call.get("name"),
                        "qualified": call.get("qualified") or call.get("name"),
                        "location": call.get("location", {}),
                    },
                    kind=(
                        "external_function"
                        if call.get("external", True)
                        else "function"
                    ),
                    owner=None,
                    external=call.get("external", True),
                )
            if not graph.has_edge(caller_id, callee_id):
                graph.add_edge(caller_id, callee_id, type="calls")

    return graph, functions


def write_graph(graph: nx.DiGraph, output_path: Path, fmt: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "graphml":
        nx.write_graphml(graph, output_path)
    elif fmt == "gexf":
        nx.write_gexf(graph, output_path)
    elif fmt == "json":
        payload = json_graph.node_link_data(graph)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def export_to_neo4j(
    graph: nx.DiGraph,
    uri: str,
    username: str,
    password: str,
    database: str,
    clear_existing: bool = True,
) -> None:
    """Export the knowledge graph to Neo4j database."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("Warning: neo4j package not installed. Run: pip install neo4j")
        print("Skipping Neo4j export.")
        return

    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))

        with driver.session(database=database) as session:
            # Clear existing data if requested
            if clear_existing:
                print("Clearing existing Neo4j graph data...")
                session.run("MATCH (n) DETACH DELETE n")

            # Create nodes
            print(f"Creating {graph.number_of_nodes()} nodes in Neo4j...")
            for node_id, attrs in graph.nodes(data=True):
                node_type = attrs.get("type", "Node")
                properties = {k: v for k, v in attrs.items() if k != "type"}
                properties["id"] = node_id

                # Build property string for Cypher query
                prop_items = ", ".join(f"{k}: ${k}" for k in properties.keys())
                query = f"CREATE (n:{node_type} {{{prop_items}}})"
                session.run(query, **properties)

            # Create relationships
            print(f"Creating {graph.number_of_edges()} relationships in Neo4j...")
            for source, target, attrs in graph.edges(data=True):
                rel_type = attrs.get("type", "RELATES_TO").upper().replace(" ", "_")
                query = f"""
                MATCH (a {{id: $source}})
                MATCH (b {{id: $target}})
                CREATE (a)-[r:{rel_type}]->(b)
                """
                session.run(query, source=source, target=target)

            print(f"✓ Successfully exported graph to Neo4j at {uri}")
            print(f"  Database: {database}")
            print(f"  Nodes: {graph.number_of_nodes()}")
            print(f"  Relationships: {graph.number_of_edges()}")

    except Exception as e:
        print(f"Error exporting to Neo4j: {e}")
        print("Make sure Neo4j server is running and credentials are correct.")
    finally:
        if driver:
            driver.close()


def visualize_graph(
    graph: nx.DiGraph,
    *,
    output_path: Path | None,
    show: bool,
) -> None:
    if graph.number_of_nodes() == 0:
        print("Graph is empty; skipping visualization.")
        return

    node_colors: Dict[str, str] = {}
    palette = {
        "class": "#2c7bb6",
        "method": "#1a9641",
        "function": "#fdae61",
        "external_function": "#d7191c",
    }

    for node_id, attrs in graph.nodes(data=True):
        node_type = attrs.get("type", "function")
        node_colors[node_id] = palette.get(node_type, "#aaaaaa")

    positions = nx.spring_layout(graph, seed=42)

    fig, ax = plt.subplots(figsize=(max(6, math.sqrt(graph.number_of_nodes())), 6))
    nx.draw_networkx_nodes(
        graph,
        positions,
        node_color=[node_colors[node] for node in graph.nodes],
        node_size=450,
        ax=ax,
    )
    nx.draw_networkx_labels(
        graph,
        positions,
        labels={
            node: attrs.get("name", node) for node, attrs in graph.nodes(data=True)
        },
        font_size=8,
        ax=ax,
    )
    edge_colors = [
        "#7f7f7f" if data.get("type") != "member" else "#313695"
        for _, _, data in graph.edges(data=True)
    ]
    nx.draw_networkx_edges(
        graph, positions, edge_color=edge_colors, arrows=True, arrowsize=12, ax=ax
    )
    ax.set_axis_off()
    plt.tight_layout()
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, format="png", dpi=300, bbox_inches="tight")
        print(f"Visualization saved to {output_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)


def _resolve_path(value: Path | str | None) -> Path | None:
    if value is None:
        return None
    return Path(value).expanduser().resolve()


def main() -> None:
    analysis_path = _resolve_path(ANALYSIS_PATH) or default_analysis_path()
    analysis_path = analysis_path.expanduser().resolve()

    if not analysis_path.exists():
        raise FileNotFoundError(f"Analysis file not found: {analysis_path}")

    data = load_analysis(analysis_path)
    graph, _ = build_graph(data)

    fmt = GRAPH_OUTPUT_FORMAT.lower()
    if fmt not in {"graphml", "gexf", "json"}:
        raise ValueError(f"Unsupported format configured: {GRAPH_OUTPUT_FORMAT}")

    output_path = _resolve_path(GRAPH_OUTPUT_PATH)
    if not output_path:
        default_name = f"{analysis_path.stem}_graph.{fmt}"
        output_path = analysis_path.with_name(default_name)
    output_path = output_path.expanduser().resolve()

    write_graph(graph, output_path, fmt)

    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    print(f"Graph written to {output_path} ({node_count} nodes, {edge_count} edges)")

    # Export to Neo4j if enabled
    if NEO4J_EXPORT_ENABLED:
        print("\nExporting to Neo4j...")
        export_to_neo4j(
            graph,
            uri=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
            clear_existing=NEO4J_CLEAR_EXISTING,
        )

    save_path = _resolve_path(RENDER_SAVE_PATH)
    if (RENDER_SHOW or save_path) and graph.number_of_nodes() > 0:
        visualize_graph(
            graph,
            output_path=save_path,
            show=RENDER_SHOW,
        )


if __name__ == "__main__":
    main()
