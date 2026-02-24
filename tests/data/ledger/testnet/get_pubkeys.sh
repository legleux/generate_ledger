#!/bin/bash

for i in 0 1; do
    docker exec val${i} rippled --silent server_info \
    | jq -r '.result.info | {hostid, pubkey_node, pubkey_validator} | to_entries[] | "\(.key): \(.value)"'
done
