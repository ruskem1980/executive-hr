#!/bin/bash
# ============================================================================
# Claude Flow V3 — Hardware Detection & Auto-Configuration
# ============================================================================
# Detects hardware, classifies into tier, generates optimal claude-flow config.
# Replaces hardcoded per-machine scripts with universal auto-detection.
#
# Usage:
#   bash scripts/hw-detect.sh              # detect + show config
#   bash scripts/hw-detect.sh --apply      # detect + apply to settings
#   bash scripts/hw-detect.sh --json       # output raw JSON
#   bash scripts/hw-detect.sh --tier       # show tier only
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SETTINGS_FILE="$PROJECT_ROOT/.claude/settings.json"
DAEMON_STATE="$PROJECT_ROOT/.claude-flow/daemon-state.json"
HW_CACHE="$PROJECT_ROOT/.claude-flow/hw-profile.json"

# ── Platform detection ───────────────────────────────────────────────────────

detect_platform() {
  local os=$(uname -s)
  case "$os" in
    Darwin) echo "macos" ;;
    Linux)  echo "linux" ;;
    *)      echo "unknown" ;;
  esac
}

# ── CPU detection ────────────────────────────────────────────────────────────

detect_cpu() {
  local platform=$(detect_platform)
  local cpu_brand="" cpu_cores=0 perf_cores=0 eff_cores=0 cpu_arch=""

  if [ "$platform" = "macos" ]; then
    cpu_brand=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")
    cpu_cores=$(sysctl -n hw.ncpu 2>/dev/null || echo "4")
    cpu_arch=$(uname -m)

    # Apple Silicon: detect P/E cores
    perf_cores=$(sysctl -n hw.perflevel0.logicalcpu 2>/dev/null || echo "0")
    eff_cores=$(sysctl -n hw.perflevel1.logicalcpu 2>/dev/null || echo "0")

    # Fallback: if no P/E split, all cores are performance
    if [ "$perf_cores" -eq 0 ]; then
      perf_cores=$cpu_cores
    fi

  elif [ "$platform" = "linux" ]; then
    cpu_brand=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo "Unknown")
    cpu_cores=$(nproc 2>/dev/null || grep -c "^processor" /proc/cpuinfo 2>/dev/null || echo "4")
    cpu_arch=$(uname -m)
    perf_cores=$cpu_cores
    eff_cores=0
  fi

  echo "$cpu_brand|$cpu_cores|$perf_cores|$eff_cores|$cpu_arch"
}

# ── RAM detection ────────────────────────────────────────────────────────────

detect_ram_gb() {
  local platform=$(detect_platform)

  if [ "$platform" = "macos" ]; then
    local bytes=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
    echo $((bytes / 1073741824))
  elif [ "$platform" = "linux" ]; then
    local kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "0")
    echo $((kb / 1048576))
  else
    echo "0"
  fi
}

# ── GPU detection ────────────────────────────────────────────────────────────

detect_gpu() {
  local platform=$(detect_platform)
  local gpu_name="" gpu_cores=0 gpu_mem=""

  if [ "$platform" = "macos" ]; then
    gpu_name=$(system_profiler SPDisplaysDataType 2>/dev/null | grep "Chipset Model" | head -1 | cut -d: -f2 | xargs || echo "Unknown")
    gpu_cores=$(system_profiler SPDisplaysDataType 2>/dev/null | grep "Total Number of Cores" | head -1 | cut -d: -f2 | xargs || echo "0")
    gpu_mem=$(system_profiler SPDisplaysDataType 2>/dev/null | grep "VRAM" | head -1 | cut -d: -f2 | xargs || echo "shared")

    # Apple Silicon uses unified memory — GPU mem = system RAM
    if echo "$gpu_name" | grep -qi "Apple M"; then
      gpu_mem="unified"
    fi

  elif [ "$platform" = "linux" ]; then
    if command -v nvidia-smi &>/dev/null; then
      gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "Unknown")
      gpu_mem=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1 || echo "0")
    elif command -v lspci &>/dev/null; then
      gpu_name=$(lspci 2>/dev/null | grep -i "vga\|3d\|display" | head -1 | cut -d: -f3 | xargs || echo "Integrated")
    else
      gpu_name="Unknown"
    fi
  fi

  echo "$gpu_name|$gpu_cores|$gpu_mem"
}

# ── Disk detection ───────────────────────────────────────────────────────────

detect_disk() {
  local platform=$(detect_platform)
  local disk_type="unknown" disk_free=""

  if [ "$platform" = "macos" ]; then
    local is_ssd=$(diskutil info / 2>/dev/null | grep "Solid State" | awk '{print $NF}')
    disk_type=$( [ "$is_ssd" = "Yes" ] && echo "ssd" || echo "hdd" )
    disk_free=$(df -h / 2>/dev/null | awk 'NR==2 {print $4}')

  elif [ "$platform" = "linux" ]; then
    local root_dev=$(df / 2>/dev/null | awk 'NR==2 {print $1}' | sed 's/[0-9]*$//')
    local dev_name=$(basename "$root_dev" 2>/dev/null || echo "sda")
    if [ -f "/sys/block/$dev_name/queue/rotational" ]; then
      local rot=$(cat "/sys/block/$dev_name/queue/rotational" 2>/dev/null || echo "1")
      disk_type=$( [ "$rot" = "0" ] && echo "ssd" || echo "hdd" )
    fi
    disk_free=$(df -h / 2>/dev/null | awk 'NR==2 {print $4}')
  fi

  echo "$disk_type|$disk_free"
}

# ── Tier classification ──────────────────────────────────────────────────────

classify_tier() {
  local cores=$1
  local ram_gb=$2
  local gpu_cores=$3

  # Score: weighted sum of resources
  local score=0
  score=$((score + cores * 3))        # CPU weight
  score=$((score + ram_gb))            # RAM weight (1 per GB)
  score=$((score + gpu_cores / 5))     # GPU weight

  if [ $score -ge 150 ]; then
    echo "ultra"        # M3 Max 128GB, i9/Ryzen9 64GB+, etc.
  elif [ $score -ge 80 ]; then
    echo "performance"  # M2 Pro 32GB, i7 32GB, etc.
  elif [ $score -ge 40 ]; then
    echo "standard"     # M1 16GB, i5 16GB, etc.
  else
    echo "light"        # 8GB or less, low-core CPUs
  fi
}

# ── Generate optimal config ─────────────────────────────────────────────────

generate_config() {
  local tier=$1
  local cores=$2
  local ram_gb=$3

  local max_agents max_concurrent topology strategy
  local worker_audit_interval worker_optimize_interval worker_consolidate_interval
  local max_cpu_load min_free_mem_pct
  local enabled_workers

  case "$tier" in
    ultra)
      max_agents=15
      max_concurrent=6
      topology="hierarchical-mesh"
      strategy="specialized"
      max_cpu_load=$((cores - 2))
      min_free_mem_pct=15
      worker_audit_interval=600000        # 10 min
      worker_optimize_interval=900000     # 15 min
      worker_consolidate_interval=1800000 # 30 min
      enabled_workers='["map","audit","optimize","consolidate","testgaps","ultralearn","deepdive","document","refactor","benchmark","predict"]'
      ;;
    performance)
      max_agents=10
      max_concurrent=4
      topology="hierarchical"
      strategy="specialized"
      max_cpu_load=$((cores - 2))
      min_free_mem_pct=20
      worker_audit_interval=900000        # 15 min
      worker_optimize_interval=1200000    # 20 min
      worker_consolidate_interval=3600000 # 60 min
      enabled_workers='["map","audit","optimize","consolidate","testgaps","deepdive","document"]'
      ;;
    standard)
      max_agents=6
      max_concurrent=2
      topology="hierarchical"
      strategy="balanced"
      max_cpu_load=$((cores - 1))
      min_free_mem_pct=25
      worker_audit_interval=1800000       # 30 min
      worker_optimize_interval=1800000    # 30 min
      worker_consolidate_interval=7200000 # 2 hours
      enabled_workers='["map","audit","optimize","consolidate","testgaps"]'
      ;;
    light)
      max_agents=3
      max_concurrent=1
      topology="hierarchical"
      strategy="minimal"
      max_cpu_load=$((cores > 1 ? cores - 1 : 1))
      min_free_mem_pct=30
      worker_audit_interval=3600000       # 60 min
      worker_optimize_interval=3600000    # 60 min
      worker_consolidate_interval=14400000 # 4 hours
      enabled_workers='["map","audit","optimize"]'
      ;;
  esac

  cat << EOJSON
{
  "tier": "$tier",
  "swarm": {
    "maxAgents": $max_agents,
    "topology": "$topology",
    "strategy": "$strategy"
  },
  "daemon": {
    "maxConcurrent": $max_concurrent,
    "resourceThresholds": {
      "maxCpuLoad": $max_cpu_load,
      "minFreeMemoryPercent": $min_free_mem_pct
    },
    "enabledWorkers": $enabled_workers,
    "intervals": {
      "audit": $worker_audit_interval,
      "optimize": $worker_optimize_interval,
      "consolidate": $worker_consolidate_interval
    }
  },
  "memory": {
    "backend": "$( [ "$tier" = "light" ] && echo "sqlite" || echo "hybrid" )",
    "enableHNSW": $( [ "$tier" = "light" ] && echo "false" || echo "true" )
  },
  "neural": {
    "enabled": $( [ "$tier" = "light" ] && echo "false" || echo "true" )
  }
}
EOJSON
}

# ── Apply config to settings.json ────────────────────────────────────────────

apply_config() {
  local tier=$1
  local config=$2

  if [ ! -f "$SETTINGS_FILE" ]; then
    echo "ERROR: Settings file not found: $SETTINGS_FILE"
    return 1
  fi

  # Extract values from config JSON
  local max_agents=$(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['swarm']['maxAgents'])")
  local topology=$(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['swarm']['topology'])")
  local max_concurrent=$(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['daemon']['maxConcurrent'])")
  local max_cpu=$(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['daemon']['resourceThresholds']['maxCpuLoad'])")
  local min_mem=$(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['daemon']['resourceThresholds']['minFreeMemoryPercent'])")
  local memory_backend=$(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['memory']['backend'])")
  local enable_hnsw=$(echo "$config" | python3 -c "import sys,json; print(str(json.load(sys.stdin)['memory']['enableHNSW']).lower())")
  local enable_neural=$(echo "$config" | python3 -c "import sys,json; print(str(json.load(sys.stdin)['neural']['enabled']).lower())")

  # Update settings.json using python3 (available on macOS and most Linux)
  python3 << PYEOF
import json, sys

with open("$SETTINGS_FILE", "r") as f:
    settings = json.load(f)

cf = settings.get("claudeFlow", {})

# Swarm settings
cf.setdefault("swarm", {})
cf["swarm"]["maxAgents"] = $max_agents
cf["swarm"]["topology"] = "$topology"

# Memory settings
cf.setdefault("memory", {})
cf["memory"]["backend"] = "$memory_backend"
cf["memory"]["enableHNSW"] = "$enable_hnsw" == "true"

# Neural settings
cf.setdefault("neural", {})
cf["neural"]["enabled"] = "$enable_neural" == "true"

# Hardware tier tag
cf["hardwareTier"] = "$tier"

settings["claudeFlow"] = cf

with open("$SETTINGS_FILE", "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)

print("  -> settings.json updated")
PYEOF

  # Update daemon-state.json
  if [ -f "$DAEMON_STATE" ]; then
    python3 << PYEOF2
import json

with open("$DAEMON_STATE", "r") as f:
    state = json.load(f)

state["config"]["maxConcurrent"] = $max_concurrent
state["config"]["resourceThresholds"]["maxCpuLoad"] = $max_cpu
state["config"]["resourceThresholds"]["minFreeMemoryPercent"] = $min_mem

with open("$DAEMON_STATE", "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

print("  -> daemon-state.json updated")
PYEOF2
  fi
}

# ── Main ─────────────────────────────────────────────────────────────────────

main() {
  local mode="${1:---show}"
  local platform=$(detect_platform)

  # Detect hardware
  IFS='|' read -r cpu_brand cpu_cores perf_cores eff_cores cpu_arch <<< "$(detect_cpu)"
  local ram_gb=$(detect_ram_gb)
  IFS='|' read -r gpu_name gpu_cores gpu_mem <<< "$(detect_gpu)"
  IFS='|' read -r disk_type disk_free <<< "$(detect_disk)"

  # Classify tier
  local tier=$(classify_tier "$cpu_cores" "$ram_gb" "${gpu_cores:-0}")

  # Generate optimal config
  local config=$(generate_config "$tier" "$cpu_cores" "$ram_gb")

  # Build full hardware profile
  local hw_profile
  hw_profile=$(cat << EOPROFILE
{
  "detectedAt": "$(date -Iseconds)",
  "platform": "$platform",
  "cpu": {
    "brand": "$cpu_brand",
    "totalCores": $cpu_cores,
    "performanceCores": $perf_cores,
    "efficiencyCores": $eff_cores,
    "architecture": "$cpu_arch"
  },
  "ram": {
    "totalGB": $ram_gb
  },
  "gpu": {
    "name": "$gpu_name",
    "cores": ${gpu_cores:-0},
    "memory": "$gpu_mem"
  },
  "disk": {
    "type": "$disk_type",
    "freeSpace": "$disk_free"
  },
  "tier": "$tier",
  "optimalConfig": $config
}
EOPROFILE
)

  # Cache the profile
  mkdir -p "$(dirname "$HW_CACHE")"
  echo "$hw_profile" > "$HW_CACHE"

  case "$mode" in
    --json)
      echo "$hw_profile"
      ;;
    --tier)
      echo "$tier"
      ;;
    --apply)
      echo "============================================"
      echo "  Hardware Auto-Configuration"
      echo "============================================"
      echo ""
      echo "  CPU:    $cpu_brand"
      echo "  Cores:  $cpu_cores ($perf_cores P + $eff_cores E)"
      echo "  RAM:    ${ram_gb} GB"
      echo "  GPU:    $gpu_name (${gpu_cores:-0} cores, $gpu_mem)"
      echo "  Disk:   $disk_type ($disk_free free)"
      echo "  Tier:   $tier"
      echo ""
      echo "  Applying optimal settings..."
      apply_config "$tier" "$config"
      echo ""
      echo "  Max Agents:     $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['swarm']['maxAgents'])")"
      echo "  Topology:       $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['swarm']['topology'])")"
      echo "  Max Concurrent: $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['daemon']['maxConcurrent'])")"
      echo "  Memory:         $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['memory']['backend'])")"
      echo "  HNSW:           $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['memory']['enableHNSW'])")"
      echo "  Neural:         $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['neural']['enabled'])")"
      echo ""
      echo "============================================"
      echo "  Done! Settings optimized for: $tier"
      echo "============================================"
      ;;
    --show|*)
      echo "============================================"
      echo "  Hardware Profile"
      echo "============================================"
      echo ""
      echo "  Platform: $platform"
      echo "  CPU:      $cpu_brand"
      echo "  Cores:    $cpu_cores total ($perf_cores P + $eff_cores E)"
      echo "  Arch:     $cpu_arch"
      echo "  RAM:      ${ram_gb} GB"
      echo "  GPU:      $gpu_name (${gpu_cores:-0} cores, $gpu_mem)"
      echo "  Disk:     $disk_type ($disk_free free)"
      echo ""
      echo "  >>> Tier: $tier <<<"
      echo ""
      echo "  Recommended settings:"
      echo "    Max Agents:     $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['swarm']['maxAgents'])")"
      echo "    Topology:       $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['swarm']['topology'])")"
      echo "    Max Concurrent: $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['daemon']['maxConcurrent'])")"
      echo "    Memory:         $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['memory']['backend'])")"
      echo "    HNSW:           $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['memory']['enableHNSW'])")"
      echo "    Neural:         $(echo "$config" | python3 -c "import sys,json; print(json.load(sys.stdin)['neural']['enabled'])")"
      echo ""
      echo "  Run with --apply to apply these settings."
      echo "============================================"
      ;;
  esac
}

main "$@"
