from pygraphviz import AGraph
import itertools

# A = AGraph()

validators = 5
node_list = [f"val{i}" for i in range(validators)]
nodes = list(itertools.permutations(node_list, 2))
# # gen_node(connections: list)
# A.node_attr["style"] = "filled"
# A.node_attr["shape"] = "circle"
# A.node_attr["fixedsize"] = "true"
# A.node_attr["fontcolor"] = "#220808"
# # d = {
# #     "val0": {"": None},
# #     "val1": {"1": None, "3": None},
# #     "val2": {"2": None}
# #     "val3": {"2": None}
# #     "val4": {"2": None}
# #     }
# e1 = ("val0", "val1")
# e2 = ("val1", "val2")
# e3 = ("val0", "val2")
# for n in nodes:
#     A.add_edge(n)

# # A = AGraph(d)
# f = "my_network"
# A.write(f"{f}.dot")  # write to simple.dot
# A.draw(f"{f}.png", prog="circo")  # draw to png using circo layout

import graphviz
from pathlib import Path
import sys
file_ = sys.argv[1]
gv_src = Path(file_)
outfile = gv_src.stem
out_format="png"
src = graphviz.Source(
    gv_src.read_text(),
    # engine="dot",
    engine="fdp",
    # engine="neato",
    # engine="circo",
    filename=outfile,
    format=out_format
)
print(f"Writing {outfile}.{out_format}")
src.render()
# p = graphviz.Graph(
#     name='testnet',
#     format='png',
#     engine='circo',
#     # engine='neato',
#     )
# p.edge('val0', 'val1')
# p.edge('val0', 'val2')
# p.edge('val0', 'val3')
# p.edge('val1', 'val2')
# p.edge('val1', 'val3')
# c = graphviz.Graph(name='subnet_2')#, node_attr={'shape': 'box'})
# with p.subgraph(name="cluster_0") as c:
#     c.edge('val0', 'val1')
#     c.edge('val0', 'val2')
#     c.edge('val0', 'val3')
#     c.edge('val1', 'val2')
#     c.edge('val1', 'val3')
# with p.subgraph(name="cluster_1") as c:
#     c.edge('val4', 'val5')
#     c.edge('val5', 'val6')
#     c.edge('val6', 'val7')
#     c.edge('val4', 'val6')
# p.render()

## Attempt 2
#p = graphviz.Graph('parent')
#p.edge('spam', 'eggs')
#with p.subgraph(name='child', node_attr={'shape': 'box'}) as c:
#   c.edge('foo', 'bar')
