#!/bin/bash

c=$1

docker exec \
    $c rippled --silent feature  | jq -r '.result.features[] | select(.enabled == true) | .name' | sort

# docker exec \
#     val0 rippled --silent feature \
#         | jq -r '.result.features[] | {name, enabled}'

#docker exec val0 rippled --silent feature | jq -r '.result.features | to_entries[] | select(.value.enabled == false) | "\(.key) \(.value.name)"'
