#!/bin/bash
# M3 Max 128GB Optimization Script (OS-level tuning, requires sudo)
# For claude-flow settings use: bash scripts/hw-detect.sh --apply
# Run: sudo bash ~/Desktop/Проекты/PT_Standart/scripts/optimize-m3max.sh

set -e

echo "============================================"
echo "  MacBook Pro M3 Max 128GB — Optimization"
echo "============================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Run with sudo"
    echo "sudo bash $0"
    exit 1
fi

# 1. Network Stack
echo "[1/5] Network stack..."
sysctl -w kern.ipc.somaxconn=2048
sysctl -w kern.ipc.maxsockbuf=16777216
sysctl -w net.inet.tcp.sendspace=262144
sysctl -w net.inet.tcp.recvspace=262144
echo "  -> Done"
echo ""

# 2. Persist sysctl settings
echo "[2/5] Persisting sysctl settings..."
if [ ! -f /etc/sysctl.conf ] || ! grep -q "somaxconn" /etc/sysctl.conf 2>/dev/null; then
    cat >> /etc/sysctl.conf << 'SYSCTL'
# M3 Max Optimization
kern.ipc.somaxconn=2048
kern.ipc.maxsockbuf=16777216
net.inet.tcp.sendspace=262144
net.inet.tcp.recvspace=262144
SYSCTL
    echo "  -> /etc/sysctl.conf updated"
else
    echo "  -> /etc/sysctl.conf already configured, skipping"
fi
echo ""

# 3. Power Management
echo "[3/5] Power management..."
pmset -c powermode 2           # High performance on AC
pmset -c disksleep 0           # No disk sleep on AC
echo "  -> Performance mode ON, disk sleep OFF"
echo ""

# 4. Disable Hibernation
echo "[4/5] Disabling hibernation (saves ~128GB disk)..."
pmset -a hibernatemode 0
if [ -f /var/vm/sleepimage ]; then
    rm -f /var/vm/sleepimage
    echo "  -> Removed /var/vm/sleepimage"
fi
echo "  -> Hibernation disabled"
echo ""

# 5. File Descriptors (persistent)
echo "[5/5] Persistent file descriptor limit..."
PLIST_PATH="/Library/LaunchDaemons/limit.maxfiles.plist"
if [ ! -f "$PLIST_PATH" ]; then
    cat > "$PLIST_PATH" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>limit.maxfiles</string>
    <key>ProgramArguments</key>
    <array>
        <string>launchctl</string>
        <string>limit</string>
        <string>maxfiles</string>
        <string>524288</string>
        <string>524288</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLIST
    chmod 644 "$PLIST_PATH"
    launchctl load "$PLIST_PATH" 2>/dev/null || true
    echo "  -> LaunchDaemon created and loaded"
else
    echo "  -> LaunchDaemon already exists, skipping"
fi
echo ""

# 6. Spotlight exclusion
echo "[BONUS] Spotlight indexing..."
mdutil -i off "/Users/at/Desktop/Проекты" 2>/dev/null && \
    echo "  -> Disabled for ~/Desktop/Проекты" || \
    echo "  -> Could not disable (may need Full Disk Access)"
echo ""

# Verification
echo "============================================"
echo "  Verification"
echo "============================================"
echo ""
echo "somaxconn:    $(sysctl -n kern.ipc.somaxconn)"
echo "maxsockbuf:   $(sysctl -n kern.ipc.maxsockbuf)"
echo "tcp.send:     $(sysctl -n net.inet.tcp.sendspace)"
echo "tcp.recv:     $(sysctl -n net.inet.tcp.recvspace)"
echo "powermode:    $(pmset -g | grep powermode | awk '{print $2}')"
echo "hibernate:    $(pmset -g | grep hibernatemode | awk '{print $2}')"
echo "disksleep:    $(pmset -g | grep disksleep | awk '{print $2}')"
echo ""
echo "============================================"
echo "  All done! Reboot recommended."
echo "============================================"
