#!/usr/bin/env python3
import argparse
import json
import math
import random
from typing import Any


def circ_mean_radians(angles: list[float]) -> float:
    sx = sum(math.cos(a) for a in angles)
    sy = sum(math.sin(a) for a in angles)
    return math.atan2(sy, sx)

# --------- helpers ---------
def pt(x: float) -> str:
    # format a coordinate value for neato pos (points), force-placed with '!'
    return f"{x:.1f}"

def pos(x: float, y: float) -> str:
    return f"{pt(x)},{pt(y)}!"

def clique_edges(ids: list[str]) -> list[list[str]]:
    E = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            E.append([ids[i], ids[j]])
    return E

def ensure_undirected_edge(u: str, v: str, Eset: set, Elist: list[list[str]]):
    if u == v:
        return
    a, b = (u, v) if u < v else (v, u)
    key = (a, b)
    if key not in Eset:
        Eset.add(key)
        Elist.append([a, b])

# def ring_positions(n: int, radius: float, start_angle_deg: float = -90.0) -> list[tuple]:
#     # equally spaced points on a circle, default placing the first at top (−90 deg)
#     out = []
#     for i in range(n):
#         ang = math.radians(start_angle_deg + 360.0 * i / max(1, n))
#         out.append((radius * math.cos(ang), radius * math.sin(ang)))
#     return out

def ring_positions(n: int, radius: float, start_angle_deg: float = -90.0) -> list[tuple[float,float]]:
    out = []
    for i in range(max(1, n)):
        ang = math.radians(start_angle_deg + 360.0 * i / n)
        out.append((radius * math.cos(ang), radius * math.sin(ang)))
    return out

# --------- generator ---------
def generate(config: dict[str, Any]) -> dict[str, Any]:
    rnd = random.Random(config.get("seed", 0))

    num_central = int(config.get("num_central_hubs", 5))
    num_subnets = int(config.get("num_subnets", 4))
    vps = config.get("validators_per_subnet", 6)
    placement = config.get("placement", "barycentric")  # "barycentric" | "even"
    relax = bool(config.get("relax", False))            # if True, let neato refine (no pinning)

    if isinstance(vps, int):
        validators_per_subnet = [vps] * num_subnets
    else:
        validators_per_subnet = list(vps)
        assert len(validators_per_subnet) == num_subnets, "validators_per_subnet length must equal num_subnets"

    # Layout radii (points; 72 pt = 1 inch)
    hub_ring_r           = float(config.get("hub_ring_radius", 200))    # central hubs ring
    subnet_hub_ring_r    = float(config.get("subnet_hub_ring_radius", 700))  # local hubs ring
    validator_ring_r     = float(config.get("validator_ring_radius", 250))   # radius of validators around local hub
    subnet_twist_deg     = float(config.get("subnet_twist_degrees", 0))      # rotate validators within each subnet

    # Intra-subnet wiring
    min_deg = int(config.get("intra_min_degree", 1))   # per-validator (validator↔validator) min degree
    max_deg = int(config.get("intra_max_degree", 3))   # per-validator max degree
    assert 0 <= min_deg <= max_deg, "degree bounds invalid"

    # Local hub to validator connections
    hub_connect_fraction = float(config.get("hub_connect_fraction", 1.0))  # 0..1 fraction of validators to connect to local hub
    hub_connect_fraction = max(0.0, min(1.0, hub_connect_fraction))

    # Colors (soft pastels) for subnets
    pastel = ["#e8f5e9", "#e3f2fd", "#fff8e1", "#f3e5f5", "#e0f7fa", "#fce4ec", "#f1f8e9", "#e8eaf6"]

    G: dict[str, Any] = {
        "directed": False,
        "strict": True,
        "name": config.get("name", "StarClustersGenerated"),
        "graph": {
            "layout": "neato",
            "splines": "line",
            "overlap": "false",
            "pack": "true",
            "packmode": "cluster",
            "concentrate": True
        },
        "node": {"shape": "circle"},
        "edge": {"color": "gray60"},
        "subgraphs": [],
        "edges": []
    }

    # ----- central Hubs cluster -----
    hubs_nodes = []
    for i, (x, y) in enumerate(ring_positions(num_central, hub_ring_r), start=1):
        hubs_nodes.append({
            "id": f"Hub{i}_c",
            "label": f"Hub{i}",
            "pos": pos(x, y),
            "pin": True
        })

    hubs_cluster = {
        "name": "hubs",
        "cluster": True,
        "label": "Hubs",
        "node": {"shape": "octagon", "style": "filled", "fillcolor": "#eeeeee"},
        "nodes": hubs_nodes,
        "edges": clique_edges([n["id"] for n in hubs_nodes])  # fully interconnect central hubs
    }
    G["subgraphs"].append(hubs_cluster)

    # ----- subnet clusters -----
    # positions for local (per-subnet) hubs
    subnet_hub_positions = ring_positions(num_subnets, subnet_hub_ring_r, start_angle_deg=-45.0)
    global_val_counter = 1

    angles_by_central: dict[int, list[float]] = {i: [] for i in range(1, num_central+1)}
    local_hub_ids: list[str] = []   # to wire later
    central_choices: list[int] = []
    local_hub_positions: list[tuple[float,float]] = []

    for s in range(num_subnets):
        subnet_label = f"Subnet {s+1} ({validators_per_subnet[s]})"
        fill = pastel[s % len(pastel)]
        (hx, hy) = subnet_hub_positions[s]
        local_hub_id = f"s{s+1}_hub"
        local_hub_node = {"id": local_hub_id, "label": f"Hub{subnet_hub_ring_r and s+1}", "pos": pos(hx, hy), "pin": True}

        # positions for validators around the local hub
        nvals = validators_per_subnet[s]
        vals = []
        val_ids = []
        base_angle = subnet_twist_deg + (360.0 * s / max(1, num_subnets))
        for j, (dx, dy) in enumerate(ring_positions(nvals, validator_ring_r, start_angle_deg=base_angle), start=1):
            # add a touch of jitter so it doesn't look too perfect
            jitter_r = validator_ring_r * 0.12
            jx = dx + rnd.uniform(-jitter_r, jitter_r)
            jy = dy + rnd.uniform(-jitter_r, jitter_r)
            x, y = hx + jx, hy + jy
            vid = f"val{global_val_counter:02d}"
            vals.append({"id": vid, "pos": pos(x, y), "pin": True, "style": "filled", "fillcolor": fill})
            val_ids.append(vid)
            global_val_counter += 1

        # intra-subnet edges among validators (sparse/random, undirected)
        Eset = set()
        intra_edges: list[list[str]] = []
        target_deg = {vid: rnd.randint(min_deg, max_deg) for vid in val_ids}

        # simple degree-satisfying loop
        tries = 0
        max_tries = nvals * nvals * 5
        while tries < max_tries:
            need = [vid for vid in val_ids if target_deg[vid] > 0]
            if not need:
                break
            u = rnd.choice(need)
            v = rnd.choice([w for w in val_ids if w != u])
            ensure_undirected_edge(u, v, Eset, intra_edges)
            # update desired degrees (cap at 0)
            target_deg[u] = max(0, target_deg[u] - 1)
            target_deg[v] = max(0, target_deg[v] - 1)
            tries += 1

        # optional: ensure at least one node ends up with degree 1
        # (if all ended higher, trim one of u's edges)
        deg = {vid: 0 for vid in val_ids}
        for a, b in Eset:
            deg[a] += 1
            deg[b] += 1
        if all(d != 1 for d in deg.values()) and intra_edges:
            a, b = intra_edges[-1]
            Eset.remove(tuple(sorted((a, b))))
            intra_edges.pop()

        # local hub -> validators edges (subset by fraction)
        hub_edges = []
        for vid in val_ids:
            if rnd.random() <= hub_connect_fraction:
                hub_edges.append([local_hub_id, vid])

        # assemble subnet cluster object
        subnet_obj = {
            "name": f"s{s+1}",
            "cluster": True,
            "label": subnet_label,
            "node": {"style": "filled", "fillcolor": fill},
            "nodes": [local_hub_node] + vals,
            "edges": hub_edges + intra_edges
        }
        G["subgraphs"].append(subnet_obj)

        # connect THIS subnet hub to ONE random central hub
        central_choice = rnd.randint(1, num_central)
        G["edges"].append([local_hub_id, f"Hub{central_choice}_c"])

    return G

# --------- CLI ---------
def main():
    ap = argparse.ArgumentParser(description="Generate star/cluster network JSON for json2dot.py (neato -n2).")
    ap.add_argument("-c", "--config", help="Path to JSON config (optional).", default=None)
    ap.add_argument("-o", "--output", help="Write JSON to file (default: stdout).", default=None)
    args = ap.parse_args()

    # defaults
    cfg = {
        "seed": 42,
        "name": "StarClustersGenerated",
        "num_central_hubs": 5,
        "num_subnets": 4,
        "validators_per_subnet": [7, 6, 6, 6],
        "hub_ring_radius": 200,          # points
        "subnet_hub_ring_radius": 700,   # points
        "validator_ring_radius": 250,    # points
        "subnet_twist_degrees": 0,
        "intra_min_degree": 1,
        "intra_max_degree": 3,
        "hub_connect_fraction": 1.0
    }
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            user_cfg = json.load(f)
        cfg.update(user_cfg)

    graph = generate(cfg)
    out = json.dumps(graph, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)

if __name__ == "__main__":
    main()
