#!/usr/bin/env bash
# Run pytest across the same Python/OS matrix as CI.
# Requires Docker. Mirrors .github/workflows/tests.yml exactly.
#
# Source is copied into each container via docker cp — no mounts,
# no risk of tainting the local venv or file permissions.
# Failed containers are left running for debugging:
#   docker exec -it gl-test-<distro>-py<version> bash
set -uo pipefail

VERSIONS=(12 13 14)
DISTROS=(bookworm trixie)
LOGDIR=$(mktemp -d)
PIDS=()
KEYS=()

for v in "${VERSIONS[@]}"; do
    for os in "${DISTROS[@]}"; do
        key="${os}-py${v}"
        tag="python3.${v}-${os}"
        logfile="${LOGDIR}/${key}.log"
        (
            name="gl-test-${key}"
            docker rm -f "$name" > /dev/null 2>&1 || true

            # Start a container that stays alive, copy source in, then exec tests
            docker run -d --name "$name" -w /work "ghcr.io/astral-sh/uv:${tag}" \
                sleep infinity > /dev/null 2>&1
            for f in src tests pyproject.toml uv.lock README.md; do
                docker cp "$(pwd)/$f" "${name}:/work/$f" 2>/dev/null
            done

            docker exec "$name" sh -c '
                if ! uv sync --group dev --group fast; then
                    rm -rf .venv && uv sync --group dev
                fi &&
                uv run pytest -q
            ' > "$logfile" 2>&1
            exit_code=$?

            if [ $exit_code -eq 0 ]; then
                echo "PASS" > "${logfile}.result"
                docker rm -f "$name" > /dev/null 2>&1
            else
                echo "FAIL" > "${logfile}.result"
            fi
        ) &
        PIDS+=($!)
        KEYS+=("$key")
        echo "Started ${key} (PID $!)"
    done
done

echo ""
echo "Waiting for ${#PIDS[@]} jobs..."
echo ""

# Save cursor position, then poll with redraw
tput sc 2>/dev/null || true
while true; do
    alive=0
    for pid in "${PIDS[@]}"; do
        kill -0 "$pid" 2>/dev/null && alive=$((alive + 1))
    done
    [ "$alive" -eq 0 ] && break

    # Restore cursor and clear to end of screen, then print
    tput rc 2>/dev/null && tput ed 2>/dev/null || true
    echo "  ${alive}/${#PIDS[@]} running:"
    docker ps --filter "name=gl-test-" --format "    {{.Names}}" 2>/dev/null | sed 's/gl-test-//g'
    sleep 2
done
tput rc 2>/dev/null && tput ed 2>/dev/null || true

for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null || true
done

GREEN='\033[32m'
RED='\033[31m'
RESET='\033[0m'
PASS_LIST=()
FAIL_LIST=()

echo "=========================================="
echo "  RESULTS"
echo "=========================================="

for key in "${KEYS[@]}"; do
    result=$(cat "${LOGDIR}/${key}.log.result" 2>/dev/null || echo "FAIL")
    if [ "$result" = "PASS" ]; then
        echo -e "  ${GREEN}✓${RESET} ${key}"
        PASS_LIST+=("$key")
    else
        echo -e "  ${RED}✗${RESET} ${key}"
        FAIL_LIST+=("$key")
    fi
done

echo ""
echo "  ${#PASS_LIST[@]} passed, ${#FAIL_LIST[@]} failed"

if [ ${#FAIL_LIST[@]} -gt 0 ]; then
    echo ""
    echo "Failed job logs:"
    for key in "${FAIL_LIST[@]}"; do
        echo ""
        echo -e "  ${RED}--- ${key} ---${RESET}"
        tail -20 "${LOGDIR}/${key}.log"
        echo -e "  Debug: ${GREEN}docker exec -it gl-test-${key} bash${RESET}"
    done
    echo ""
    echo "Full logs: ${LOGDIR}/"
    exit 1
else
    rm -rf "$LOGDIR"
fi
