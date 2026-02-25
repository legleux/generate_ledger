#!/usr/bin/env python3
"""
json2dot.py — Convert a JSON network description into Graphviz DOT.

JSON schema (flexible):

{
  "directed": true,                 # optional (default true)
  "strict": false,                  # optional (default false)
  "name": "MyGraph",                # optional graph name
  "graph": { "rankdir": "LR" },     # optional graph attrs (e.g., ranksep, nodesep, compound)
  "node":  { "shape": "box" },      # optional default node attrs
  "edge":  { "color": "gray50" },   # optional default edge attrs

  "nodes": [ "A", {"id":"B","label":"Bee"} ],
  "edges": [ ["A","B"], {"source":"B","target":"A","label":"back"} ],

  "subgraphs": [
    {
      "name": "subnet_A",
      "cluster": true,              # if true, renders as a boxed cluster (prefixes name with 'cluster_')
      "label": "Subnet A",
      "node": {"shape":"circle"},   # local defaults (graph/node/edge) are supported
      "nodes": [ "A1", "A2", {"id":"A_gw","shape":"doublecircle"} ],
      "edges": [ ["A1","A2"], ["A2","A_gw"] ]
      // "subgraphs": [ ... ]       # nested subgraphs are supported
    }
  ]
}

Usage:
  python3 json2dot.py spec.json > graph.dot
  python3 json2dot.py spec.json -o graph.dot
  python3 json2dot.py spec.json --validate-single-exit | dot -Tpng > graph.png
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from typing import Any

# ---------- Utilities ----------

def q(value: Any) -> str:
    """Quote a Graphviz attribute value safely."""
    if isinstance(value, (int, float)) or value in (True, False):
        return str(value).lower() if isinstance(value, bool) else str(value)
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'

def attrs_to_str(attrs: Mapping[str, Any]) -> str:
    if not attrs:
        return ""
    parts = [f'{k}={q(v)}' for k, v in attrs.items()]
    return " [" + ", ".join(parts) + "]"


def normalize_edge(e: Any) -> dict[str, Any]:
    """
    Accepts any of:
      - ["A","B"]                          # no attrs
      - ["A","B", {"label":"x", ...}]     # with attrs
      - {"source":"A","target":"B", ...}
      - {"u":"A","v":"B", ...}            # alias keys
    Returns dict with "source","target", plus any attributes.
    """
    if isinstance(e, list):
        EDGE_PAIR = 2
        EDGE_WITH_ATTRS = 3
        if len(e) == EDGE_PAIR:
            return {"source": e[0], "target": e[1]}
        if len(e) == EDGE_WITH_ATTRS and isinstance(e[2], dict):
            d = {"source": e[0], "target": e[1]}
            d.update(e[2])
            return d
    if isinstance(e, dict):
        if "source" in e and "target" in e:
            return dict(e)
        if "u" in e and "v" in e:
            d = dict(e)
            d["source"], d["target"] = d.pop("u"), d.pop("v")
            return d
    raise ValueError(f"Unrecognized edge format: {e!r}")


def emit_stmt(line: str, out) -> None:
    out.write(line + "\n")

# ---------- Cluster helpers ----------

def _canonical_cluster_name(name: str) -> str:
    return name if name.startswith("cluster_") else f"cluster_{name}"

def collect_cluster_name_map(spec: Mapping[str, Any]) -> dict[str, str]:
    """
    Build a map of user-provided subgraph names -> canonical 'cluster_*' names
    for those marked with "cluster": true. Non-cluster subgraphs are ignored.
    """
    name_map: dict[str, str] = {}
    def walk(s: Mapping[str, Any]):
        for sg in (s.get("subgraphs") or []) or []:
            if not isinstance(sg, Mapping):
                continue
            nm = str(sg.get("name", "cluster"))
            if sg.get("cluster", False):
                name_map[nm] = _canonical_cluster_name(nm)
                # also allow canonical key to map to itself (idempotent)
                name_map[name_map[nm]] = name_map[nm]
            # Recurse
            walk(sg)
    walk(spec)
    return name_map

def map_ltail_lhead(attrs: dict[str, Any], cluster_name_map: Mapping[str, str]) -> dict[str, Any]:
    """
    Normalize ltail/lhead values to canonical 'cluster_*' names when they refer
    to clusters declared with cluster:true.
    """
    if not attrs:
        return attrs
    out = dict(attrs)
    for k in ("ltail", "lhead"):
        if k in out:
            val = str(out[k])
            if val in cluster_name_map:
                out[k] = cluster_name_map[val]
    return out

# ---------- Emission ----------

def emit_nodes_and_edges(
    spec: Mapping[str, Any],
    edge_op: str,
    out,
    indent: str,
    cluster_name_map: Mapping[str, str]
) -> None:
    # Nodes
    for n in (spec.get("nodes") or []) or []:
        if isinstance(n, str):
            node_id, node_attrs = n, {}
        elif isinstance(n, Mapping) and "id" in n:
            node_id = n["id"]
            node_attrs = {k: v for k, v in n.items() if k != "id"}
        else:
            raise ValueError(f"Unrecognized node format: {n!r}")
        emit_stmt(f"{indent}{q(node_id)}{attrs_to_str(node_attrs)};", out)

    # Edges
    raw_edges = (spec.get("edges") or []) or []
    for e in (normalize_edge(x) for x in raw_edges):
        src, dst = e.get("source"), e.get("target")
        if src is None or dst is None:
            raise ValueError(f"Edge missing source/target: {e!r}")
        edge_attrs = {k: v for k, v in e.items() if k not in ("source", "target")}
        edge_attrs = map_ltail_lhead(edge_attrs, cluster_name_map)
        emit_stmt(f"{indent}{q(src)} {edge_op} {q(dst)}{attrs_to_str(edge_attrs)};", out)

def emit_subgraphs(
    spec: Mapping[str, Any],
    edge_op: str,
    out,
    indent: str,
    cluster_name_map: Mapping[str, str]
) -> None:
    for sg in (spec.get("subgraphs") or []) or []:
        if not isinstance(sg, Mapping):
            raise ValueError(f"Subgraph must be an object: {sg!r}")
        name = str(sg.get("name", "cluster"))
        is_cluster = bool(sg.get("cluster", False))
        sg_name = _canonical_cluster_name(name) if is_cluster else name

        emit_stmt(f"{indent}subgraph {sg_name} {{", out)

        # Local defaults/attrs
        if "label" in sg:
            emit_stmt(f"{indent}  label={q(sg['label'])};", out)
        if sg.get("graph"):
            emit_stmt(f"{indent}  graph{attrs_to_str(sg['graph'])};", out)
        if sg.get("node"):
            emit_stmt(f"{indent}  node{attrs_to_str(sg['node'])};", out)
        if sg.get("edge"):
            emit_stmt(f"{indent}  edge{attrs_to_str(sg['edge'])};", out)

        # Body + nested
        emit_nodes_and_edges(sg, edge_op, out, indent + "  ", cluster_name_map)
        emit_subgraphs(sg, edge_op, out, indent + "  ", cluster_name_map)

        emit_stmt(f"{indent}}}", out)

# ---------- Validation (optional) ----------

def _gather_membership(spec: Mapping[str, Any]) -> dict[str, str]:
    """
    Return a map: node_id -> subgraph_name (closest enclosing subgraph name).
    """
    membership: dict[str, str] = {}
    def node_ids(container: Mapping[str, Any]) -> list[str]:
        out: list[str] = []
        for n in (container.get("nodes") or []) or []:
            if isinstance(n, str):
                out.append(n)
            elif isinstance(n, Mapping) and "id" in n:
                out.append(str(n["id"]))
        return out

    def walk(s: Mapping[str, Any], parent_name: str | None):
        # assign membership for nodes at this level (to current parent)
        if parent_name:
            for nid in node_ids(s):
                membership[nid] = parent_name
        # then recurse into children subgraphs (which will override for nested nodes)
        for sg in (s.get("subgraphs") or []) or []:
            if not isinstance(sg, Mapping):
                continue
            nm = str(sg.get("name", "cluster"))
            walk(sg, nm)
    walk(spec, None)
    return membership

def _collect_all_edges(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    Collect edges from the whole structure (top and nested subgraphs).
    """
    edges: list[dict[str, Any]] = []
    def walk(s: Mapping[str, Any]):
        for e in (s.get("edges") or []) or []:
            edges.append(normalize_edge(e))
        for sg in (s.get("subgraphs") or []) or []:
            walk(sg)
    walk(spec)
    return edges

def validate_single_exit(spec: Mapping[str, Any]) -> None:
    """
    Enforce: each subgraph/subnet has at most one 'external' edge
    (edge that connects a node inside the subgraph to anything outside).
    """
    membership = _gather_membership(spec)
    edges = _collect_all_edges(spec)

    counts: dict[str, int] = {}

    for e in edges:
        a = membership.get(e["source"])
        b = membership.get(e["target"])
        if a == b:
            # both inside same subnet (or both None = global): not external
            continue
        # If edge crosses a boundary, bump each side that is inside a subnet
        if a:
            counts[a] = counts.get(a, 0) + 1
        if b:
            counts[b] = counts.get(b, 0) + 1

    bad = [name for name, c in counts.items() if c > 1]
    if bad:
        raise ValueError(f"Subnets with >1 external edge: {bad}")

# ---------- Main conversion ----------

def json_to_dot(spec: dict[str, Any], *, validate_exits: bool = False) -> str:
    directed = bool(spec.get("directed", True))
    strict = bool(spec.get("strict", False))
    name = spec.get("name") or ("G" if directed else "G_undirected")

    graph_kw = "digraph" if directed else "graph"
    edge_op = "->" if directed else "--"
    strict_kw = "strict " if strict else ""

    # Gather attrs
    graph_attrs = dict(spec.get("graph", {}) or {})
    node_defaults = spec.get("node", {}) or {}
    edge_defaults = spec.get("edge", {}) or {}

    # Auto-enable compound when using subgraphs (for clean ltail/lhead routing)
    has_subgraphs = bool((spec.get("subgraphs") or []) or [])
    if has_subgraphs and "compound" not in graph_attrs:
        graph_attrs["compound"] = True

    from io import StringIO  # noqa: PLC0415
    buf = StringIO()

    # Cluster name normalization map
    cluster_name_map = collect_cluster_name_map(spec)

    # Optional validation
    if validate_exits:
        validate_single_exit(spec)

    emit_stmt(f"{strict_kw}{graph_kw} {name} {{", buf)

    # Global defaults
    if graph_attrs:
        emit_stmt(f"  graph{attrs_to_str(graph_attrs)};", buf)
    if node_defaults:
        emit_stmt(f"  node{attrs_to_str(node_defaults)};", buf)
    if edge_defaults:
        emit_stmt(f"  edge{attrs_to_str(edge_defaults)};", buf)

    # Top-level body
    emit_nodes_and_edges(spec, edge_op, buf, "  ", cluster_name_map)
    # Subgraphs
    emit_subgraphs(spec, edge_op, buf, "  ", cluster_name_map)

    emit_stmt("}", buf)
    return buf.getvalue()

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(
        description="Convert a JSON network description (with optional subgraphs/clusters) to Graphviz DOT."
    )
    ap.add_argument("input", help="Path to JSON file (or '-' for stdin)")
    ap.add_argument("-o", "--output", help="Write DOT to this file (default: stdout)")
    ap.add_argument("--validate-single-exit", action="store_true",
                    help="Ensure each subnet/subgraph has at most one external edge.")
    args = ap.parse_args()

    # Read
    if args.input == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)

    try:
        dot = json_to_dot(data, validate_exits=args.validate_single_exit)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(dot)
    else:
        sys.stdout.write(dot)

if __name__ == "__main__":
    main()
