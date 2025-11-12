#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════════════════════════════╗"
echo "║                   POLISH IAMD C2 SYSTEM - VALIDATION TEST                            ║"
echo "╚══════════════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Test 1: Check if ARBITER API is accessible
echo "🔍 Test 1: Checking ARBITER API connectivity..."
curl -s -o /dev/null -w "%{http_code}" https://api.arbiter.traut.ai/v1/compare > /tmp/arbiter_status.txt 2>&1
ARBITER_STATUS=$(cat /tmp/arbiter_status.txt)

if [ "$ARBITER_STATUS" = "405" ] || [ "$ARBITER_STATUS" = "200" ]; then
    echo "   ✅ ARBITER API is accessible at https://api.arbiter.traut.ai/v1/compare"
else
    echo "   ⚠️  ARBITER API returned status: $ARBITER_STATUS"
    echo "   (405 is OK - means endpoint exists but needs POST)"
fi
echo ""

# Test 2: Check if Polish C2 service is running
echo "🔍 Test 2: Checking if Polish C2 service is running on port 8003..."
if curl -s http://localhost:8003/health > /dev/null 2>&1; then
    echo "   ✅ Polish C2 service is running"
    curl -s http://localhost:8003/health | python3 -m json.tool 2>/dev/null || echo "   (Service running but JSON parsing failed)"
else
    echo "   ❌ Polish C2 service is NOT running"
    echo "   Start it with: ./run.sh"
    exit 1
fi
echo ""

# Test 3: Run Kaliningrad validation scenario
echo "🔍 Test 3: Running Kaliningrad corridor validation scenario..."
echo "   (This will take a few seconds as it calls ARBITER)"
echo ""

RESPONSE=$(curl -s -X POST http://localhost:8003/api/validate-kaliningrad)

if echo "$RESPONSE" | grep -q "success"; then
    echo "   ✅ Validation scenario completed successfully"
    echo ""
    echo "   Results:"
    echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('success'):
    print(f\"   - Total time: {data.get('total_time_ms', 0):.0f}ms\")
    print(f\"   - ARBITER latency: {data.get('arbiter_latency_ms', 0):.0f}ms\")
    print(f\"   - Options generated: {data.get('options_generated', 0)}\")
    print(f\"   - Recommendations: {len(data.get('ranked_recommendations', []))}\")
    if data.get('ranked_recommendations'):
        print(f\"\\n   Top Recommendation:\")
        top = data['ranked_recommendations'][0]
        print(f\"   - #{top['rank']}: {top['title']}\")
        print(f\"   - Coherence: {top['coherence']*100:.1f}%\")
        print(f\"   - Cost: {top['estimated_cost_pln']:,} PLN\")
        print(f\"   - Success rate: {top['estimated_success_rate']:.0f}%\")
        print(f\"   - Degraded comms OK: {'TAK' if top.get('degraded_comms_ok') else 'NIE'}\")
" 2>/dev/null || echo "   (Response parsing failed)"
else
    echo "   ❌ Validation failed"
    echo "   Response: $RESPONSE"
fi
echo ""

echo "╔══════════════════════════════════════════════════════════════════════════════════════╗"
echo "║                              VALIDATION COMPLETE                                      ║"
echo "║                                                                                       ║"
echo "║  If all tests passed:                                                                ║"
echo "║    ✅ ARBITER API is accessible                                                      ║"
echo "║    ✅ Polish C2 service is running                                                   ║"
echo "║    ✅ Kaliningrad scenario validation works                                          ║"
echo "║                                                                                       ║"
echo "║  Open web interface: http://localhost:8003                                           ║"
echo "╚══════════════════════════════════════════════════════════════════════════════════════╝"
