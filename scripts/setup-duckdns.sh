#!/bin/bash
# DuckDNS Setup Script for Avira
# This script configures DuckDNS to point to your home server

# Configuration
DUCKDNS_DOMAIN="aviraa"
DUCKDNS_TOKEN="4ad84ece-5c93-43e2-99d3-7ae8cdff07c8"  # Get from https://www.duckdns.org
CURRENT_IP="65.188.101.168"

echo "=== Avira DuckDNS Setup ==="
echo ""

# Update DuckDNS
update_duckdns() {
    echo "Updating DuckDNS..."
    RESPONSE=$(curl -s "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=${CURRENT_IP}")
    
    if [ "$RESPONSE" = "OK" ]; then
        echo "✅ DuckDNS updated successfully!"
        echo "   Domain: ${DUCKDNS_DOMAIN}.duckdns.org"
        echo "   IP: ${CURRENT_IP}"
    else
        echo "❌ DuckDNS update failed: $RESPONSE"
        echo "   Make sure your token is correct"
    fi
}

# Create cron job for auto-update
setup_cron() {
    echo ""
    echo "Setting up auto-update cron job..."
    
    CRON_CMD="*/5 * * * * curl -s 'https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=' > /dev/null 2>&1"
    
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "duckdns.org"; then
        echo "⚠️  DuckDNS cron job already exists"
    else
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
        echo "✅ Cron job added (updates every 5 minutes)"
    fi
}

# Setup port forwarding instructions
show_port_forwarding() {
    echo ""
    echo "=== Port Forwarding Setup ==="
    echo ""
    echo "You need to configure port forwarding on your router:"
    echo ""
    echo "1. Log into your router (usually http://192.168.1.1)"
    echo "2. Find 'Port Forwarding' or 'NAT' settings"
    echo "3. Add these rules:"
    echo ""
    echo "   ┌─────────────┬──────────────┬───────────────┬──────────┐"
    echo "   │ Service     │ External Port│ Internal Port │ Protocol │"
    echo "   ├─────────────┼──────────────┼───────────────┼──────────┤"
    echo "   │ Avira API   │ 30000        │ 30000         │ TCP      │"
    echo "   │ Avira Web   │ 30080        │ 30080         │ TCP      │"
    echo "   └─────────────┴──────────────┴───────────────┴──────────┘"
    echo ""
    echo "   Internal IP: $(hostname -I 2>/dev/null | awk '{print $1}' || echo 'YOUR_LOCAL_IP')"
    echo ""
}

# Test connection
test_connection() {
    echo ""
    echo "=== Testing Connection ==="
    echo ""
    echo "Testing ${DUCKDNS_DOMAIN}.duckdns.org:30000..."
    
    if curl -s --connect-timeout 5 "http://${DUCKDNS_DOMAIN}.duckdns.org:30000/health" | grep -q "healthy"; then
        echo "✅ Connection successful! API is accessible."
    else
        echo "❌ Connection failed. Check:"
        echo "   - Port forwarding is configured"
        echo "   - Firewall allows port 30000"
        echo "   - Backend service is running"
    fi
}

# Main
echo "1. Updating DuckDNS record..."
update_duckdns

echo ""
echo "2. Would you like to setup auto-update cron? (y/n)"
read -r answer
if [ "$answer" = "y" ]; then
    setup_cron
fi

show_port_forwarding

echo ""
echo "3. Would you like to test the connection? (y/n)"
read -r answer
if [ "$answer" = "y" ]; then
    test_connection
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Your Avira services will be accessible at:"
echo "  API:  http://aviraa.duckdns.org:30000"
echo "  Web:  http://aviraa.duckdns.org:30080"
echo ""
echo "Mobile apps should connect to: http://aviraa.duckdns.org:30000"
