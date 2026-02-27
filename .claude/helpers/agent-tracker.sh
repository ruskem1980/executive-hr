#!/usr/bin/env bash
# agent-tracker.sh - Sentinel file system for background agent monitoring
# Part of Variant A: Safe agent monitoring solution
#
# Usage:
#   bash agent-tracker.sh create <agent_id> <agent_type> <task_description> [output_file]
#   bash agent-tracker.sh heartbeat <agent_id> [tools_used] [tokens_used]
#   bash agent-tracker.sh complete <agent_id> <status> [summary]
#   bash agent-tracker.sh cleanup
#   bash agent-tracker.sh list

set -euo pipefail

TRACKING_DIR="${CLAUDE_FLOW_TRACKING_DIR:-.claude-flow/agent-tracking}"
MAX_AGE_HOURS=24

# Ensure tracking directory exists
ensure_dir() {
    mkdir -p "$TRACKING_DIR"
}

# ISO 8601 timestamp
now_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Create tracking files for a new agent
# Args: agent_id, agent_type, task_description, [output_file]
cmd_create() {
    local agent_id="${1:?Error: agent_id required}"
    local agent_type="${2:?Error: agent_type required}"
    local task_desc="${3:?Error: task_description required}"
    local output_file="${4:-}"

    ensure_dir

    # Create started sentinel
    cat > "$TRACKING_DIR/${agent_id}.started.json" <<EOF
{
  "agentId": "${agent_id}",
  "type": "${agent_type}",
  "task": $(printf '%s' "$task_desc" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo "\"${task_desc}\""),
  "startedAt": "$(now_iso)",
  "outputFile": "${output_file}"
}
EOF

    # Create initial heartbeat
    cat > "$TRACKING_DIR/${agent_id}.heartbeat.json" <<EOF
{
  "agentId": "${agent_id}",
  "lastHeartbeat": "$(now_iso)",
  "toolsUsed": 0,
  "tokensUsed": 0
}
EOF

    echo "OK: Tracking created for agent ${agent_id} (${agent_type})"
}

# Update heartbeat for an agent
# Args: agent_id, [tools_used], [tokens_used]
cmd_heartbeat() {
    local agent_id="${1:?Error: agent_id required}"
    local tools_used="${2:-0}"
    local tokens_used="${3:-0}"

    ensure_dir

    if [ ! -f "$TRACKING_DIR/${agent_id}.started.json" ]; then
        echo "WARN: No tracking found for agent ${agent_id}"
        return 1
    fi

    # Skip if already completed
    if [ -f "$TRACKING_DIR/${agent_id}.completed.json" ]; then
        echo "INFO: Agent ${agent_id} already completed, skipping heartbeat"
        return 0
    fi

    cat > "$TRACKING_DIR/${agent_id}.heartbeat.json" <<EOF
{
  "agentId": "${agent_id}",
  "lastHeartbeat": "$(now_iso)",
  "toolsUsed": ${tools_used},
  "tokensUsed": ${tokens_used}
}
EOF

    echo "OK: Heartbeat updated for agent ${agent_id}"
}

# Mark agent as completed
# Args: agent_id, status (success|failure|error), [summary]
cmd_complete() {
    local agent_id="${1:?Error: agent_id required}"
    local status="${2:?Error: status required (success|failure|error)}"
    local summary="${3:-No summary provided}"

    ensure_dir

    if [ ! -f "$TRACKING_DIR/${agent_id}.started.json" ]; then
        echo "WARN: No tracking found for agent ${agent_id}"
        return 1
    fi

    cat > "$TRACKING_DIR/${agent_id}.completed.json" <<EOF
{
  "agentId": "${agent_id}",
  "completedAt": "$(now_iso)",
  "status": "${status}",
  "summary": $(printf '%s' "$summary" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo "\"${summary}\"")
}
EOF

    echo "OK: Agent ${agent_id} marked as ${status}"
}

# Cleanup tracking files older than MAX_AGE_HOURS
cmd_cleanup() {
    ensure_dir

    local count=0
    # Find files older than MAX_AGE_HOURS and remove them
    while IFS= read -r -d '' file; do
        rm -f "$file"
        count=$((count + 1))
    done < <(find "$TRACKING_DIR" -name "*.json" -type f -mmin +$((MAX_AGE_HOURS * 60)) -print0 2>/dev/null)

    echo "OK: Cleaned up ${count} old tracking files"
}

# List all tracked agents with their current status
cmd_list() {
    ensure_dir

    local active=0
    local completed=0
    local total=0

    # Find unique agent IDs from started files
    for started_file in "$TRACKING_DIR"/*.started.json; do
        [ -f "$started_file" ] || continue

        local basename
        basename=$(basename "$started_file" .started.json)
        total=$((total + 1))

        if [ -f "$TRACKING_DIR/${basename}.completed.json" ]; then
            completed=$((completed + 1))
            local comp_status
            comp_status=$(python3 -c "import json; d=json.load(open('$TRACKING_DIR/${basename}.completed.json')); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")
            local agent_type
            agent_type=$(python3 -c "import json; d=json.load(open('$started_file')); print(d.get('type','unknown'))" 2>/dev/null || echo "unknown")
            echo "  [DONE:${comp_status}] ${basename} (${agent_type})"
        else
            active=$((active + 1))
            local agent_type
            agent_type=$(python3 -c "import json; d=json.load(open('$started_file')); print(d.get('type','unknown'))" 2>/dev/null || echo "unknown")
            local last_hb="no heartbeat"
            if [ -f "$TRACKING_DIR/${basename}.heartbeat.json" ]; then
                last_hb=$(python3 -c "import json; d=json.load(open('$TRACKING_DIR/${basename}.heartbeat.json')); print(d.get('lastHeartbeat','unknown'))" 2>/dev/null || echo "unknown")
            fi
            echo "  [ACTIVE] ${basename} (${agent_type}) - last heartbeat: ${last_hb}"
        fi
    done

    if [ "$total" -eq 0 ]; then
        echo "No tracked agents found."
    else
        echo "---"
        echo "Total: ${total} | Active: ${active} | Completed: ${completed}"
    fi
}

# Main dispatcher
case "${1:-help}" in
    create)    shift; cmd_create "$@" ;;
    heartbeat) shift; cmd_heartbeat "$@" ;;
    complete)  shift; cmd_complete "$@" ;;
    cleanup)   shift; cmd_cleanup ;;
    list)      shift; cmd_list ;;
    help|*)
        echo "Usage: $(basename "$0") {create|heartbeat|complete|cleanup|list}"
        echo ""
        echo "Commands:"
        echo "  create <id> <type> <task> [output_file]  - Start tracking an agent"
        echo "  heartbeat <id> [tools] [tokens]          - Update agent heartbeat"
        echo "  complete <id> <status> [summary]          - Mark agent as completed"
        echo "  cleanup                                    - Remove files older than ${MAX_AGE_HOURS}h"
        echo "  list                                       - Show all tracked agents"
        ;;
esac
