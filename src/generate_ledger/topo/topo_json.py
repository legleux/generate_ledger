topo = {
  "directed": True,                       # optional (default True)
  "strict": False,                        # optional (default False)
  "name": "xrpl_net",                     # optional graph name
  "graph": { "rankdir": "LR" },           # optional graph attrs
  "node":  { "shape": "box" },            # optional default node attrs
  "edge":  { "color": "gray50" },         # optional default edge attrs

  "nodes": [
    { "id": "A", "label": "Service A" },
    { "id": "B", "label": "Service B", "shape": "ellipse" }
  ],

  "edges": [
    { "source": "A", "target": "B", "label": "calls", "style": "dashed" }
    # You can also use short forms, e.g. ["A","B"] or {"u":"A","v":"B"}
  ]
}
