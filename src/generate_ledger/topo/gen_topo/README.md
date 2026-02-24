# 1) Generate JSON
python3 gen_star_topology.py -c star_config.json -o star.json

# 2) Convert JSON -> DOT
python3 json2dot.py star.json > star.dot

# 3) Render with neato honoring pinned positions (very important: -n2)
neato -n2 -Tpng star.dot > star.png
