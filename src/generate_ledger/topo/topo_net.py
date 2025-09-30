import gravis as gv

rectangle = {"shape": "rectangle"}
circle = {"shape": "circle"}
hexagon = {"shape": "hexagon"}
green = {"color": "#1FD41F"}
blue = {"color": "#0193bf"}
red = {"color": "#ff0000"}
load_color = red
hub_color = green
val_color = blue
hub_shape = circle
val_shape = hexagon
graph_height = 1000

val_meta = {"metadata": {**val_shape, **val_color}}
hub_meta = {"metadata": {**hub_shape, **hub_color}}
metadata = {
    "node_color": "white",
    "node_size": 30,
    "node_border_size": 2,
    "node_label_size": 20,
}
graph = {
    "label": "antithesis_net",
    "directed": False,
}
graph.update(metadata=metadata)
load = {"load": {"metadata": {**load_color}}}
num_hub = 4
num_val = 25
hub_nodes = {f"hub{i}": val_meta for i in range(num_hub)}
val_nodes = {f"val{i}": hub_meta for i in range(num_val)}
nodes = {**load, **hub_nodes, **val_nodes}
edges = [
    ["hub0", "hub1"],
    ["hub0", "hub2"],
    ["hub0", "hub3"],
    ["hub0", "load"],
    ["hub0", "val0"],
    ["hub0", "val24"],
    ["hub1", "hub0"],
    ["hub1", "hub2"],
    ["hub1", "hub3"],
    ["hub1", "hub4"],
    ["hub1", "load"],
    ["hub1", "val4"],
    ["hub1", "val6"],
    ["hub2", "hub0"],
    ["hub2", "hub1"],
    ["hub2", "hub3"],
    ["hub2", "load"],
    ["hub2", "val10"],
    ["hub2", "val8"],
    ["hub3", "load"],
    ["hub3", "val15"],
    ["hub3", "val20"],
    ["val0", "val1"],
    ["val0", "val2"],
    ["val10", "val12"],
    ["val10", "val8"],
    ["val13", "val14"],
    ["val13", "val16"],
    ["val13", "val18"],
    ["val13", "val19"],
    ["val15", "val13"],
    ["val15", "val19"],
    ["val17", "val13"],
    ["val17", "val20"],
    ["val22", "val3"],
    ["val23", "val22"],
    ["val24", "val23"],
    ["val24", "val23"],
    ["val3", "val0"],
    ["val3", "val21"],
    ["val4", "val5"],
    ["val4", "val7"],
    ["val5", "val7"],
    ["val6", "val5"],
    ["val6", "val7"],
    ["val8", "val11"],
    ["val8", "val9"],
    ["val9", "val11"],
    ["val9", "val12"],
]
edge_list = []
for a, b in edges:
    edge_list.append({"source": a, "target": b})

graph.update(nodes=nodes)
graph.update(edges=edge_list)
graph1 = {"graph": graph}

fig = gv.vis(
    graph1,
    graph_height=graph_height,
    # show_node_label=False,
    # show_edge_label=False,
    # edge_label_data_source="en"
)
fig.display()
