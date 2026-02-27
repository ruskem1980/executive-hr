#!/usr/bin/env bash
# agent-status-checker.sh - Periodic status checker for background agents
# Part of Variant A: Safe agent monitoring solution
#
# Usage:
#   bash agent-status-checker.sh check        - Check all agents, report status
#   bash agent-status-checker.sh hung          - Detect hung agents (no heartbeat >10min)
#   bash agent-status-checker.sh report        - Brief status report
#   bash agent-status-checker.sh completed     - List completed agents with summaries
#   bash agent-status-checker.sh output <id>   - Show output file content for agent

set -euo pipefail

TRACKING_DIR="${CLAUDE_FLOW_TRACKING_DIR:-.claude-flow/agent-tracking}"
HUNG_THRESHOLD_MIN=10

# Parse JSON field with python3 (available on macOS)
json_field() {
    local file="$1"
    local field="$2"
    python3 -c "import json; d=json.load(open('${file}')); print(d.get('${field}',''))" 2>/dev/null || echo ""
}

# Get current epoch seconds
epoch_now() {
    date +%s
}

# Convert ISO timestamp to epoch (macOS compatible)
iso_to_epoch() {
    local ts="$1"
    python3 -c "
from datetime import datetime
ts = '${ts}'.replace('Z', '+00:00')
try:
    dt = datetime.fromisoformat(ts)
    print(int(dt.timestamp()))
except:
    print(0)
" 2>/dev/null || echo "0"
}

# Minutes since a given ISO timestamp
minutes_since() {
    local ts="$1"
    local ts_epoch
    ts_epoch=$(iso_to_epoch "$ts")
    local now_epoch
    now_epoch=$(epoch_now)

    if [ "$ts_epoch" -eq 0 ]; then
        echo "unknown"
        return
    fi

    local diff=$(( (now_epoch - ts_epoch) / 60 ))
    echo "$diff"
}

# Check all agents and report comprehensive status
cmd_check() {
    if [ ! -d "$TRACKING_DIR" ]; then
        echo "NO_AGENTS: No tracking directory found"
        return 0
    fi

    local active_count=0
    local completed_count=0
    local hung_count=0
    local has_agents=false

    echo "=== Agent Status Check ($(date -u +"%H:%M:%S UTC")) ==="
    echo ""

    for started_file in "$TRACKING_DIR"/*.started.json; do
        [ -f "$started_file" ] || continue
        has_agents=true

        local agent_id
        agent_id=$(basename "$started_file" .started.json)
        local agent_type
        agent_type=$(json_field "$started_file" "type")
        local task
        task=$(json_field "$started_file" "task")
        local started_at
        started_at=$(json_field "$started_file" "startedAt")

        # Check if completed
        if [ -f "$TRACKING_DIR/${agent_id}.completed.json" ]; then
            completed_count=$((completed_count + 1))
            local status
            status=$(json_field "$TRACKING_DIR/${agent_id}.completed.json" "status")
            local summary
            summary=$(json_field "$TRACKING_DIR/${agent_id}.completed.json" "summary")
            local completed_at
            completed_at=$(json_field "$TRACKING_DIR/${agent_id}.completed.json" "completedAt")

            if [ "$status" = "success" ]; then
                echo "  DONE  ${agent_id} (${agent_type})"
            else
                echo "  FAIL  ${agent_id} (${agent_type})"
            fi
            echo "        Task: ${task}"
            echo "        Status: ${status} | Completed: ${completed_at}"
            [ -n "$summary" ] && echo "        Summary: ${summary}"
            echo ""
            continue
        fi

        # Active agent - check heartbeat
        active_count=$((active_count + 1))
        local last_hb="never"
        local hb_minutes="unknown"
        local tools_used="0"
        local tokens_used="0"

        if [ -f "$TRACKING_DIR/${agent_id}.heartbeat.json" ]; then
            last_hb=$(json_field "$TRACKING_DIR/${agent_id}.heartbeat.json" "lastHeartbeat")
            tools_used=$(json_field "$TRACKING_DIR/${agent_id}.heartbeat.json" "toolsUsed")
            tokens_used=$(json_field "$TRACKING_DIR/${agent_id}.heartbeat.json" "tokensUsed")
            hb_minutes=$(minutes_since "$last_hb")
        fi

        # Detect hung
        local is_hung=false
        if [ "$hb_minutes" != "unknown" ] && [ "$hb_minutes" -ge "$HUNG_THRESHOLD_MIN" ]; then
            is_hung=true
            hung_count=$((hung_count + 1))
        fi

        if [ "$is_hung" = true ]; then
            echo "  HUNG  ${agent_id} (${agent_type}) - no heartbeat for ${hb_minutes}min"
        else
            echo "  RUN   ${agent_id} (${agent_type}) - heartbeat ${hb_minutes}min ago"
        fi
        echo "        Task: ${task}"
        echo "        Running since: ${started_at} | Tools: ${tools_used} | Tokens: ${tokens_used}"
        echo ""
    done

    if [ "$has_agents" = false ]; then
        echo "  No tracked agents found."
        echo ""
    fi

    echo "--- Summary ---"
    echo "Active: ${active_count} | Completed: ${completed_count} | Hung: ${hung_count}"

    # Return actionable recommendations
    if [ "$hung_count" -gt 0 ]; then
        echo ""
        echo "ACTION NEEDED: ${hung_count} agent(s) appear hung (no heartbeat >${HUNG_THRESHOLD_MIN}min)."
        echo "Consider checking their output files with: bash .claude/helpers/agent-status-checker.sh output <agent_id>"
    fi

    if [ "$completed_count" -gt 0 ]; then
        echo ""
        echo "RESULTS READY: ${completed_count} agent(s) completed. Review with: bash .claude/helpers/agent-status-checker.sh completed"
    fi
}

# Detect and report only hung agents
cmd_hung() {
    if [ ! -d "$TRACKING_DIR" ]; then
        echo "NO_AGENTS"
        return 0
    fi

    local hung_count=0

    for started_file in "$TRACKING_DIR"/*.started.json; do
        [ -f "$started_file" ] || continue

        local agent_id
        agent_id=$(basename "$started_file" .started.json)

        # Skip completed
        [ -f "$TRACKING_DIR/${agent_id}.completed.json" ] && continue

        local hb_minutes="unknown"
        if [ -f "$TRACKING_DIR/${agent_id}.heartbeat.json" ]; then
            local last_hb
            last_hb=$(json_field "$TRACKING_DIR/${agent_id}.heartbeat.json" "lastHeartbeat")
            hb_minutes=$(minutes_since "$last_hb")
        fi

        if [ "$hb_minutes" != "unknown" ] && [ "$hb_minutes" -ge "$HUNG_THRESHOLD_MIN" ]; then
            hung_count=$((hung_count + 1))
            local agent_type
            agent_type=$(json_field "$started_file" "type")
            local task
            task=$(json_field "$started_file" "task")
            echo "HUNG: ${agent_id} (${agent_type}) - no heartbeat for ${hb_minutes}min"
            echo "  Task: ${task}"
        fi
    done

    if [ "$hung_count" -eq 0 ]; then
        echo "OK: No hung agents detected"
    fi
}

# Brief status report (one line per agent)
cmd_report() {
    if [ ! -d "$TRACKING_DIR" ]; then
        echo "No agents tracked"
        return 0
    fi

    local active=0
    local done=0

    for started_file in "$TRACKING_DIR"/*.started.json; do
        [ -f "$started_file" ] || continue

        local agent_id
        agent_id=$(basename "$started_file" .started.json)
        local agent_type
        agent_type=$(json_field "$started_file" "type")

        if [ -f "$TRACKING_DIR/${agent_id}.completed.json" ]; then
            done=$((done + 1))
            local status
            status=$(json_field "$TRACKING_DIR/${agent_id}.completed.json" "status")
            printf "  %-12s %-20s %s\n" "[${status}]" "$agent_id" "$agent_type"
        else
            active=$((active + 1))
            printf "  %-12s %-20s %s\n" "[running]" "$agent_id" "$agent_type"
        fi
    done

    if [ $((active + done)) -eq 0 ]; then
        echo "No agents tracked"
    fi
    echo "Active: ${active} | Done: ${done}"
}

# List completed agents with full summaries
cmd_completed() {
    if [ ! -d "$TRACKING_DIR" ]; then
        echo "No completed agents"
        return 0
    fi

    local count=0

    for comp_file in "$TRACKING_DIR"/*.completed.json; do
        [ -f "$comp_file" ] || continue
        count=$((count + 1))

        local agent_id
        agent_id=$(basename "$comp_file" .completed.json)
        local status
        status=$(json_field "$comp_file" "status")
        local summary
        summary=$(json_field "$comp_file" "summary")
        local completed_at
        completed_at=$(json_field "$comp_file" "completedAt")

        local agent_type="unknown"
        if [ -f "$TRACKING_DIR/${agent_id}.started.json" ]; then
            agent_type=$(json_field "$TRACKING_DIR/${agent_id}.started.json" "type")
        fi

        local output_file=""
        if [ -f "$TRACKING_DIR/${agent_id}.started.json" ]; then
            output_file=$(json_field "$TRACKING_DIR/${agent_id}.started.json" "outputFile")
        fi

        echo "Agent: ${agent_id} (${agent_type})"
        echo "  Status: ${status}"
        echo "  Completed: ${completed_at}"
        echo "  Summary: ${summary}"
        [ -n "$output_file" ] && echo "  Output: ${output_file}"
        echo ""
    done

    if [ "$count" -eq 0 ]; then
        echo "No completed agents found"
    fi
}

# Show output file content for a specific agent
cmd_output() {
    local agent_id="${1:?Error: agent_id required}"

    if [ ! -f "$TRACKING_DIR/${agent_id}.started.json" ]; then
        echo "ERROR: No tracking found for agent ${agent_id}"
        return 1
    fi

    local output_file
    output_file=$(json_field "$TRACKING_DIR/${agent_id}.started.json" "outputFile")

    if [ -z "$output_file" ]; then
        echo "No output file recorded for agent ${agent_id}"
        return 1
    fi

    if [ ! -f "$output_file" ]; then
        echo "Output file not found: ${output_file}"
        return 1
    fi

    echo "=== Output for agent ${agent_id} ==="
    echo "File: ${output_file}"
    echo "---"
    tail -50 "$output_file"
}

# Main dispatcher
case "${1:-help}" in
    check)     shift; cmd_check ;;
    hung)      shift; cmd_hung ;;
    report)    shift; cmd_report ;;
    completed) shift; cmd_completed ;;
    output)    shift; cmd_output "$@" ;;
    help|*)
        echo "Usage: $(basename "$0") {check|hung|report|completed|output}"
        echo ""
        echo "Commands:"
        echo "  check              - Full status check of all agents"
        echo "  hung               - Detect hung agents (no heartbeat >${HUNG_THRESHOLD_MIN}min)"
        echo "  report             - Brief one-line-per-agent report"
        echo "  completed          - List completed agents with summaries"
        echo "  output <agent_id>  - Show output file for specific agent"
        ;;
esac
