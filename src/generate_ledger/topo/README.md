# json2dot.py usage
1. Save your JSON as network.json (see schema above)
2. Generate DOT to stdout:

    python3 json2dot.py network.json

Or write to a file:

    python3 json2dot.py network.json -o graph.dot

or Pipe straight into dot (Graphviz) to make a PNG:
    
    python3 json2dot.py network.json | dot -Tpng > graph.png

# gen_star_topology usage

## Generate your topology JSON first (with your generator)
python3 gen_star.py -c star_config.json -o star.json

## Make cfgs: one file per node (validators, local hubs, central hubs)
python3 topology_to_ripple_cfg.py star.json -o cfg/

## Optional: only emit validator configs
python3 topology_to_ripple_cfg.py star.json -o cfg_validators/ --only-prefix val
