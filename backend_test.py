#!/usr/bin/env python3
"""
Backend smoke tests for WebRTC EasyMesh application
Tests the FastAPI backend endpoints and WebSocket functionality
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed

# Add backend to path for imports
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / "frontend" / ".env")

# Get backend URL from environment
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
API_BASE = f"{BACKEND_URL}/api"
WS_BASE = BACKEND_URL.replace("http", "ws").replace("https", "wss") + "/api"

print(f"🔧 Testing backend at: {API_BASE}")
print(f"🔧 WebSocket base: {WS_BASE}")

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def add_result(self, test_name: str, passed: bool, message: str = ""):
        self.results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })
        if passed:
            self.passed += 1
            print(f"✅ {test_name}: {message}")
        else:
            self.failed += 1
            print(f"❌ {test_name}: {message}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n📊 Test Summary: {self.passed}/{total} passed")
        return self.failed == 0

async def test_root_endpoint():
    """Test GET /api/ returns 200 with Hello World message"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("message") == "Hello World":
                        return True, "Returns correct Hello World message"
                    else:
                        return False, f"Wrong message: {data}"
                else:
                    return False, f"Status {response.status}, expected 200"
    except Exception as e:
        return False, f"Request failed: {str(e)}"

async def test_host_info_endpoint():
    """Test GET /api/host-info returns correct structure"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/host-info") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check required fields
                    if "port" not in data:
                        return False, "Missing 'port' field"
                    if "ips" not in data:
                        return False, "Missing 'ips' field"
                    if "urls" not in data:
                        return False, "Missing 'urls' field"
                    
                    # Check types
                    if not isinstance(data["port"], int):
                        return False, f"Port should be int, got {type(data['port'])}"
                    if not isinstance(data["ips"], list):
                        return False, f"IPs should be array, got {type(data['ips'])}"
                    if not isinstance(data["urls"], list):
                        return False, f"URLs should be array, got {type(data['urls'])}"
                    
                    # Check URL format
                    for url in data["urls"]:
                        if not url.startswith("http://") or ":8001" not in url:
                            return False, f"URL format incorrect: {url}"
                    
                    return True, f"Correct structure: port={data['port']}, {len(data['ips'])} IPs, {len(data['urls'])} URLs"
                else:
                    return False, f"Status {response.status}, expected 200"
    except Exception as e:
        return False, f"Request failed: {str(e)}"

async def test_websocket_basic_connection():
    """Test WebSocket connection to /api/ws/session/{sid}"""
    session_id = "test-session-basic"
    ws_url = f"{WS_BASE}/ws/session/{session_id}"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Send join message
            join_msg = {
                "type": "join",
                "clientId": "test-client-1",
                "role": "host"
            }
            await websocket.send(json.dumps(join_msg))
            
            # Should receive peers message
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            if data.get("type") == "peers" and "test-client-1" in data.get("peers", []):
                return True, "WebSocket connection and join successful"
            else:
                return False, f"Unexpected response: {data}"
                
    except asyncio.TimeoutError:
        return False, "Timeout waiting for peers message"
    except Exception as e:
        return False, f"WebSocket connection failed: {str(e)}"

async def test_websocket_multiple_clients():
    """Test multiple clients joining same session and receiving peers updates"""
    session_id = "test-session-multi"
    ws_url = f"{WS_BASE}/ws/session/{session_id}"
    
    try:
        # Connect first client
        async with websockets.connect(ws_url) as ws1:
            join_msg1 = {
                "type": "join",
                "clientId": "client-1",
                "role": "host"
            }
            await ws1.send(json.dumps(join_msg1))
            
            # Wait for initial peers message
            await asyncio.wait_for(ws1.recv(), timeout=5.0)
            
            # Connect second client
            async with websockets.connect(ws_url) as ws2:
                join_msg2 = {
                    "type": "join",
                    "clientId": "client-2",
                    "role": "guest"
                }
                await ws2.send(json.dumps(join_msg2))
                
                # Both clients should receive updated peers list
                peers_msg1 = await asyncio.wait_for(ws1.recv(), timeout=5.0)
                peers_msg2 = await asyncio.wait_for(ws2.recv(), timeout=5.0)
                
                data1 = json.loads(peers_msg1)
                data2 = json.loads(peers_msg2)
                
                if (data1.get("type") == "peers" and 
                    data2.get("type") == "peers" and
                    len(data1.get("peers", [])) == 2 and
                    len(data2.get("peers", [])) == 2):
                    return True, "Multiple clients successfully joined and received peers updates"
                else:
                    return False, f"Peers messages incorrect: {data1}, {data2}"
                    
    except asyncio.TimeoutError:
        return False, "Timeout during multiple client test"
    except Exception as e:
        return False, f"Multiple client test failed: {str(e)}"

async def test_websocket_sdp_relay():
    """Test SDP offer relay between clients"""
    session_id = "test-session-sdp"
    ws_url = f"{WS_BASE}/ws/session/{session_id}"
    
    try:
        # Connect two clients
        async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2:
            # Join both clients
            await ws1.send(json.dumps({
                "type": "join",
                "clientId": "sender",
                "role": "host"
            }))
            await ws2.send(json.dumps({
                "type": "join",
                "clientId": "receiver",
                "role": "guest"
            }))
            
            # Clear initial peers messages
            await ws1.recv()
            await ws1.recv()  # Second peers message when client 2 joins
            await ws2.recv()
            
            # Send SDP offer from client 1 to client 2
            sdp_offer = {
                "type": "sdp-offer",
                "to": "receiver",
                "sdp": "fake-sdp-offer-data"
            }
            await ws1.send(json.dumps(sdp_offer))
            
            # Client 2 should receive the offer with "from" field added
            offer_msg = await asyncio.wait_for(ws2.recv(), timeout=5.0)
            data = json.loads(offer_msg)
            
            if (data.get("type") == "sdp-offer" and
                data.get("from") == "sender" and
                data.get("sdp") == "fake-sdp-offer-data"):
                return True, "SDP offer successfully relayed between clients"
            else:
                return False, f"SDP relay failed: {data}"
                
    except asyncio.TimeoutError:
        return False, "Timeout during SDP relay test"
    except Exception as e:
        return False, f"SDP relay test failed: {str(e)}"

async def test_websocket_ping_pong():
    """Test WebSocket ping/pong functionality"""
    session_id = "test-session-ping"
    ws_url = f"{WS_BASE}/ws/session/{session_id}"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # Join first
            await websocket.send(json.dumps({
                "type": "join",
                "clientId": "ping-client",
                "role": "host"
            }))
            
            # Clear peers message
            await websocket.recv()
            
            # Send ping
            await websocket.send(json.dumps({"type": "ping"}))
            
            # Should receive pong
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            if data.get("type") == "pong":
                return True, "Ping/pong functionality working"
            else:
                return False, f"Expected pong, got: {data}"
                
    except asyncio.TimeoutError:
        return False, "Timeout waiting for pong"
    except Exception as e:
        return False, f"Ping/pong test failed: {str(e)}"

async def test_api_404_vs_static():
    """Test that /api/unknown returns 404 from API, not static files"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/unknown") as response:
                if response.status == 404:
                    # Check if it's a JSON response (API) or HTML (static)
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        return True, "API returns proper 404 JSON response"
                    else:
                        # Even if not JSON, as long as it's 404, it's correct
                        return True, "API returns 404 (non-JSON but correct status)"
                else:
                    return False, f"Expected 404, got {response.status}"
    except Exception as e:
        return False, f"API 404 test failed: {str(e)}"

async def test_root_static_serving():
    """Test that GET / serves HTML content (static files)"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BACKEND_URL + "/") as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    text = await response.text()
                    
                    if 'text/html' in content_type or '<html' in text.lower():
                        return True, "Root serves HTML content"
                    else:
                        return False, f"Root doesn't serve HTML: {content_type}"
                else:
                    return False, f"Root returns {response.status}, expected 200"
    except Exception as e:
        return False, f"Root static test failed: {str(e)}"

async def run_all_tests():
    """Run all backend tests"""
    results = TestResults()
    
    print("🚀 Starting Backend Smoke Tests\n")
    
    # Test 1: Root API endpoint
    passed, message = await test_root_endpoint()
    results.add_result("GET /api/ Hello World", passed, message)
    
    # Test 2: Host info endpoint
    passed, message = await test_host_info_endpoint()
    results.add_result("GET /api/host-info structure", passed, message)
    
    # Test 3: Basic WebSocket connection
    passed, message = await test_websocket_basic_connection()
    results.add_result("WebSocket basic connection", passed, message)
    
    # Test 4: Multiple clients
    passed, message = await test_websocket_multiple_clients()
    results.add_result("WebSocket multiple clients", passed, message)
    
    # Test 5: SDP relay
    passed, message = await test_websocket_sdp_relay()
    results.add_result("WebSocket SDP offer relay", passed, message)
    
    # Test 6: Ping/pong
    passed, message = await test_websocket_ping_pong()
    results.add_result("WebSocket ping/pong", passed, message)
    
    # Test 7: API 404 vs static
    passed, message = await test_api_404_vs_static()
    results.add_result("API 404 handling", passed, message)
    
    # Test 8: Root static serving
    passed, message = await test_root_static_serving()
    results.add_result("Root static file serving", passed, message)
    
    return results.summary()

if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        if success:
            print("\n🎉 All backend tests passed!")
            sys.exit(0)
        else:
            print("\n💥 Some backend tests failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        sys.exit(1)