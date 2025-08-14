#!/usr/bin/env python3
"""
Focused WebRTC Signaling Backend Test
Tests the core WebRTC signaling functionality as requested in the review.
"""

import asyncio
import websockets
import json
import requests
from datetime import datetime

class WebRTCSignalingTester:
    def __init__(self, base_url="https://remote-launcher.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        self.ws_base = base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        self.tests_passed = 0
        self.tests_total = 0

    def test_basic_api_health(self):
        """Test basic API health endpoints"""
        print("🔍 Testing Basic API Health...")
        
        try:
            # Test root endpoint
            response = requests.get(f"{self.api_base}/", timeout=10)
            if response.status_code == 200:
                print("✅ Root API endpoint working")
                self.tests_passed += 1
            else:
                print(f"❌ Root API failed: {response.status_code}")
            self.tests_total += 1
            
            # Test status endpoint
            test_data = {"client_name": f"health_check_{datetime.now().strftime('%H%M%S')}"}
            response = requests.post(f"{self.api_base}/status", json=test_data, timeout=10)
            if response.status_code == 200:
                print("✅ Status endpoint working")
                self.tests_passed += 1
            else:
                print(f"❌ Status endpoint failed: {response.status_code}")
            self.tests_total += 1
            
        except Exception as e:
            print(f"❌ API health test failed: {e}")
            self.tests_total += 2

    async def test_websocket_connection_establishment(self):
        """Test WebSocket connection establishment"""
        print("\n🔍 Testing WebSocket Connection Establishment...")
        
        session_id = f"conn_test_{datetime.now().strftime('%H%M%S')}"
        ws_url = f"{self.ws_base}/api/ws/session/{session_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print("✅ WebSocket connection established")
                
                # Test join message
                join_msg = {
                    "type": "join",
                    "clientId": f"test_client_{datetime.now().strftime('%H%M%S')}",
                    "role": "host"
                }
                await websocket.send(json.dumps(join_msg))
                
                # Wait for peers response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                msg = json.loads(response)
                
                if msg.get("type") == "peers":
                    print("✅ Join and peers discovery working")
                    self.tests_passed += 1
                else:
                    print(f"❌ Unexpected response: {msg}")
                    
        except Exception as e:
            print(f"❌ WebSocket connection test failed: {e}")
            
        self.tests_total += 1

    async def test_multiple_clients_session_management(self):
        """Test multiple clients joining the same session"""
        print("\n🔍 Testing Multiple Clients Session Management...")
        
        session_id = f"multi_test_{datetime.now().strftime('%H%M%S')}"
        ws_url = f"{self.ws_base}/api/ws/session/{session_id}"
        
        try:
            async with websockets.connect(ws_url) as host_ws, \
                       websockets.connect(ws_url) as guest_ws:
                
                # Host joins
                await host_ws.send(json.dumps({
                    "type": "join",
                    "clientId": "host_client",
                    "role": "host"
                }))
                
                # Guest joins
                await guest_ws.send(json.dumps({
                    "type": "join", 
                    "clientId": "guest_client",
                    "role": "guest"
                }))
                
                # Collect all peer messages
                host_peers1 = json.loads(await host_ws.recv())
                guest_peers = json.loads(await guest_ws.recv())
                host_peers2 = json.loads(await host_ws.recv())
                
                # Verify both clients are in final peers list
                final_peers = host_peers2.get("peers", [])
                if len(final_peers) == 2 and "host_client" in final_peers and "guest_client" in final_peers:
                    print("✅ Multiple clients session management working")
                    print(f"   Final peers: {final_peers}")
                    self.tests_passed += 1
                else:
                    print(f"❌ Session management failed. Final peers: {final_peers}")
                    
        except Exception as e:
            print(f"❌ Multiple clients test failed: {e}")
            
        self.tests_total += 1

    async def test_webrtc_signaling_message_routing(self):
        """Test WebRTC signaling message routing between peers"""
        print("\n🔍 Testing WebRTC Signaling Message Routing...")
        
        session_id = f"routing_test_{datetime.now().strftime('%H%M%S')}"
        ws_url = f"{self.ws_base}/api/ws/session/{session_id}"
        
        try:
            async with websockets.connect(ws_url) as host_ws, \
                       websockets.connect(ws_url) as guest_ws:
                
                # Both clients join
                await host_ws.send(json.dumps({
                    "type": "join",
                    "clientId": "host_router",
                    "role": "host"
                }))
                await guest_ws.send(json.dumps({
                    "type": "join",
                    "clientId": "guest_router", 
                    "role": "guest"
                }))
                
                # Clear peers messages
                await host_ws.recv()
                await guest_ws.recv()
                await host_ws.recv()
                
                # Test SDP offer routing
                sdp_offer = {
                    "type": "sdp-offer",
                    "to": "guest_router",
                    "sdp": "v=0\r\no=- 123456 654321 IN IP4 127.0.0.1\r\n"
                }
                await host_ws.send(json.dumps(sdp_offer))
                
                offer_response = await asyncio.wait_for(guest_ws.recv(), timeout=5)
                offer_msg = json.loads(offer_response)
                
                # Test SDP answer routing
                sdp_answer = {
                    "type": "sdp-answer",
                    "to": "host_router",
                    "sdp": "v=0\r\no=- 654321 123456 IN IP4 127.0.0.1\r\n"
                }
                await guest_ws.send(json.dumps(sdp_answer))
                
                answer_response = await asyncio.wait_for(host_ws.recv(), timeout=5)
                answer_msg = json.loads(answer_response)
                
                # Test ICE candidate routing
                ice_candidate = {
                    "type": "ice-candidate",
                    "to": "guest_router",
                    "candidate": "candidate:1 1 UDP 2130706431 192.168.1.100 54400 typ host"
                }
                await host_ws.send(json.dumps(ice_candidate))
                
                ice_response = await asyncio.wait_for(guest_ws.recv(), timeout=5)
                ice_msg = json.loads(ice_response)
                
                # Verify all message routing
                routing_success = (
                    offer_msg.get("type") == "sdp-offer" and offer_msg.get("from") == "host_router" and
                    answer_msg.get("type") == "sdp-answer" and answer_msg.get("from") == "guest_router" and
                    ice_msg.get("type") == "ice-candidate" and ice_msg.get("from") == "host_router"
                )
                
                if routing_success:
                    print("✅ WebRTC signaling message routing working")
                    print("   ✓ SDP offer routed correctly")
                    print("   ✓ SDP answer routed correctly") 
                    print("   ✓ ICE candidate routed correctly")
                    self.tests_passed += 1
                else:
                    print("❌ WebRTC message routing failed")
                    print(f"   Offer: {offer_msg}")
                    print(f"   Answer: {answer_msg}")
                    print(f"   ICE: {ice_msg}")
                    
        except Exception as e:
            print(f"❌ WebRTC message routing test failed: {e}")
            
        self.tests_total += 1

    async def test_client_disconnection_handling(self):
        """Test graceful client disconnection handling"""
        print("\n🔍 Testing Client Disconnection Handling...")
        
        session_id = f"disconnect_test_{datetime.now().strftime('%H%M%S')}"
        ws_url = f"{self.ws_base}/api/ws/session/{session_id}"
        
        try:
            host_ws = await websockets.connect(ws_url)
            guest_ws = await websockets.connect(ws_url)
            
            # Both clients join
            await host_ws.send(json.dumps({
                "type": "join",
                "clientId": "host_disconnect",
                "role": "host"
            }))
            await guest_ws.send(json.dumps({
                "type": "join",
                "clientId": "guest_disconnect",
                "role": "guest"
            }))
            
            # Clear initial messages
            await host_ws.recv()
            await guest_ws.recv()
            await host_ws.recv()
            
            # Guest disconnects abruptly
            await guest_ws.close()
            
            # Host should receive updated peers list
            disconnect_response = await asyncio.wait_for(host_ws.recv(), timeout=5)
            disconnect_msg = json.loads(disconnect_response)
            
            await host_ws.close()
            
            if (disconnect_msg.get("type") == "peers" and 
                len(disconnect_msg.get("peers", [])) == 1 and
                "host_disconnect" in disconnect_msg.get("peers", [])):
                print("✅ Client disconnection handling working")
                print(f"   Remaining peers: {disconnect_msg.get('peers')}")
                self.tests_passed += 1
            else:
                print(f"❌ Disconnection handling failed: {disconnect_msg}")
                
        except Exception as e:
            print(f"❌ Client disconnection test failed: {e}")
            
        self.tests_total += 1

    async def test_websocket_connection_stability(self):
        """Test WebSocket connection stability with ping/pong"""
        print("\n🔍 Testing WebSocket Connection Stability...")
        
        session_id = f"stability_test_{datetime.now().strftime('%H%M%S')}"
        ws_url = f"{self.ws_base}/api/ws/session/{session_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Join first
                await websocket.send(json.dumps({
                    "type": "join",
                    "clientId": "stability_client",
                    "role": "test"
                }))
                
                # Clear peers message
                await websocket.recv()
                
                # Test ping/pong multiple times
                ping_success = 0
                for i in range(3):
                    await websocket.send(json.dumps({"type": "ping"}))
                    pong_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    pong_msg = json.loads(pong_response)
                    
                    if pong_msg.get("type") == "pong":
                        ping_success += 1
                
                if ping_success == 3:
                    print("✅ WebSocket connection stability confirmed")
                    print("   ✓ Multiple ping/pong cycles successful")
                    self.tests_passed += 1
                else:
                    print(f"❌ Connection stability issues: {ping_success}/3 pings successful")
                    
        except Exception as e:
            print(f"❌ Connection stability test failed: {e}")
            
        self.tests_total += 1

    def test_ftp_bridge_endpoints(self):
        """Test FTP bridge endpoints (expecting controlled failures)"""
        print("\n🔍 Testing FTP Bridge Endpoints...")
        
        try:
            # Test FTP list with invalid config (should return proper error)
            dummy_config = {
                "config": {
                    "host": "nonexistent.ftp.server",
                    "port": 21,
                    "user": "testuser",
                    "password": "testpass",
                    "passive": True,
                    "cwd": "/"
                },
                "path": "."
            }
            
            response = requests.post(f"{self.api_base}/ftp/list", json=dummy_config, timeout=10)
            
            if response.status_code == 400:
                error_data = response.json()
                if "detail" in error_data and "FTP connect failed" in error_data["detail"]:
                    print("✅ FTP bridge error handling working")
                    print(f"   Proper error response: {error_data['detail']}")
                    self.tests_passed += 1
                else:
                    print(f"❌ FTP bridge error format incorrect: {error_data}")
            else:
                print(f"❌ FTP bridge unexpected status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ FTP bridge test failed: {e}")
            
        self.tests_total += 1

    async def run_all_tests(self):
        """Run all WebRTC signaling tests"""
        print("🚀 Starting Focused WebRTC Signaling Backend Tests")
        print("=" * 60)
        
        # Test 1: Basic API Health
        self.test_basic_api_health()
        
        # Test 2: WebSocket Connection Establishment
        await self.test_websocket_connection_establishment()
        
        # Test 3: Multiple Clients Session Management
        await self.test_multiple_clients_session_management()
        
        # Test 4: WebRTC Message Routing
        await self.test_webrtc_signaling_message_routing()
        
        # Test 5: Client Disconnection Handling
        await self.test_client_disconnection_handling()
        
        # Test 6: Connection Stability
        await self.test_websocket_connection_stability()
        
        # Test 7: FTP Bridge (if needed)
        self.test_ftp_bridge_endpoints()
        
        # Print results
        print("\n" + "=" * 60)
        print("📊 WebRTC Signaling Test Results:")
        print(f"   Tests Passed: {self.tests_passed}/{self.tests_total}")
        print(f"   Success Rate: {(self.tests_passed/self.tests_total*100):.1f}%" if self.tests_total > 0 else "No tests run")
        
        if self.tests_passed == self.tests_total:
            print("🎉 All WebRTC signaling tests passed!")
            print("✅ Backend signaling infrastructure is robust and ready for peer-to-peer connections")
            return True
        else:
            print("⚠️  Some WebRTC signaling tests failed")
            return False

async def main():
    tester = WebRTCSignalingTester()
    success = await tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))