#!/bin/bash

container=$1
docker exec $1 rippled --silent server_info  | jq -r '.result.info | del (.state_accounting, .ports, .load, .initial_sync_duration_us, .io_latency_ms, .jq_trans_overflow, .node_size, .time, .server_state_duration_us, .load_factor, .last_close, .peer_disconnects_resources)'
