import requests
import sys
import json
import asyncio
import websockets
from datetime import datetime

class BackendAPITester:
    def __init__(self, base_url="https://twilio-alt-connect.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_base}/{endpoint}" if not endpoint.startswith('http') else endpoint
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    resp_json = response.json()
                    print(f"   Response: {json.dumps(resp_json, indent=2)[:200]}...")
                except:
                    print(f"   Response: {response.text[:200]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")

            return success, response

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, None

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_status_endpoints(self):
        """Test status check endpoints"""
        # Test creating a status check
        test_data = {"client_name": f"test_client_{datetime.now().strftime('%H%M%S')}"}
        success, response = self.run_test("Create Status Check", "POST", "status", 200, test_data)
        
        if success:
            # Test getting status checks
            self.run_test("Get Status Checks", "GET", "status", 200)
        
        return success

    def test_ftp_endpoints(self):
        """Test FTP endpoints with dummy data (expecting failures)"""
        # Test FTP list with invalid config (should fail with 400)
        dummy_ftp_config = {
            "config": {
                "host": "invalid.host.example.com",
                "port": 21,
                "user": "testuser",
                "password": "testpass",
                "passive": True,
                "cwd": "/"
            },
            "path": "."
        }
        
        success, response = self.run_test("FTP List (Expected Failure)", "POST", "ftp/list", 400, dummy_ftp_config)
        
        # Check if we get proper error JSON
        if response and response.status_code == 400:
            try:
                error_json = response.json()
                if "detail" in error_json:
                    print(f"✅ Proper error JSON returned: {error_json['detail']}")
                    return True
                else:
                    print(f"❌ Error JSON missing 'detail' field")
                    return False
            except:
                print(f"❌ Response is not valid JSON")
                return False
        
        return success

    async def test_websocket_signaling(self):
        """Test WebSocket signaling endpoint with comprehensive WebRTC scenarios"""
        session_id = f"test_session_{datetime.now().strftime('%H%M%S')}"
        
        # Convert HTTP URL to WebSocket URL
        ws_base = self.base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        ws_url = f"{ws_base}/api/ws/session/{session_id}"
        
        print(f"\n🔍 Testing WebSocket Signaling...")
        print(f"   WS URL: {ws_url}")
        
        # Test 1: Single client connection
        success1 = await self._test_single_client_connection(ws_url)
        
        # Test 2: Multiple clients in same session
        success2 = await self._test_multiple_clients_session(ws_url)
        
        # Test 3: WebRTC message routing
        success3 = await self._test_webrtc_message_routing(ws_url)
        
        # Test 4: Client disconnection handling
        success4 = await self._test_client_disconnection(ws_url)
        
        # Test 5: Ping/Pong functionality
        success5 = await self._test_ping_pong(ws_url)
        
        total_tests = 5
        passed_tests = sum([success1, success2, success3, success4, success5])
        self.tests_run += total_tests
        self.tests_passed += passed_tests
        
        print(f"\n📊 WebSocket Tests: {passed_tests}/{total_tests} passed")
        return passed_tests == total_tests

    async def _test_single_client_connection(self, ws_url):
        """Test single client connection and join"""
        client_id = f"host_{datetime.now().strftime('%H%M%S')}"
        
        print(f"\n🔍 Test 1: Single Client Connection")
        try:
            async with websockets.connect(ws_url) as websocket:
                # Send join message
                join_msg = {
                    "type": "join",
                    "clientId": client_id,
                    "role": "host"
                }
                await websocket.send(json.dumps(join_msg))
                
                # Wait for peers response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                msg = json.loads(response)
                
                if msg.get("type") == "peers" and client_id in msg.get("peers", []):
                    print(f"✅ Single client connection successful")
                    return True
                else:
                    print(f"❌ Unexpected peers response: {msg}")
                    return False
                    
        except Exception as e:
            print(f"❌ Single client test failed: {str(e)}")
            return False

    async def _test_multiple_clients_session(self, ws_url):
        """Test multiple clients joining the same session"""
        print(f"\n🔍 Test 2: Multiple Clients in Same Session")
        
        host_id = f"host_{datetime.now().strftime('%H%M%S')}"
        guest_id = f"guest_{datetime.now().strftime('%H%M%S')}"
        
        try:
            # Connect both clients
            async with websockets.connect(ws_url) as host_ws, \
                       websockets.connect(ws_url) as guest_ws:
                
                # Host joins first
                host_join = {
                    "type": "join",
                    "clientId": host_id,
                    "role": "host"
                }
                await host_ws.send(json.dumps(host_join))
                
                # Wait for host peers response
                host_response = await asyncio.wait_for(host_ws.recv(), timeout=5)
                host_msg = json.loads(host_response)
                
                # Guest joins
                guest_join = {
                    "type": "join",
                    "clientId": guest_id,
                    "role": "guest"
                }
                await guest_ws.send(json.dumps(guest_join))
                
                # Wait for guest peers response
                guest_response = await asyncio.wait_for(guest_ws.recv(), timeout=5)
                guest_msg = json.loads(guest_response)
                
                # Host should receive updated peers list
                host_update = await asyncio.wait_for(host_ws.recv(), timeout=5)
                host_update_msg = json.loads(host_update)
                
                # Verify both clients are in peers list
                if (host_msg.get("type") == "peers" and 
                    guest_msg.get("type") == "peers" and 
                    host_update_msg.get("type") == "peers" and
                    len(host_update_msg.get("peers", [])) == 2):
                    print(f"✅ Multiple clients session successful")
                    print(f"   Final peers: {host_update_msg.get('peers')}")
                    return True
                else:
                    print(f"❌ Multiple clients test failed")
                    print(f"   Host initial: {host_msg}")
                    print(f"   Guest: {guest_msg}")
                    print(f"   Host update: {host_update_msg}")
                    return False
                    
        except Exception as e:
            print(f"❌ Multiple clients test failed: {str(e)}")
            return False

    async def _test_webrtc_message_routing(self, ws_url):
        """Test WebRTC signaling message routing between peers"""
        print(f"\n🔍 Test 3: WebRTC Message Routing")
        
        host_id = f"host_{datetime.now().strftime('%H%M%S')}"
        guest_id = f"guest_{datetime.now().strftime('%H%M%S')}"
        
        try:
            async with websockets.connect(ws_url) as host_ws, \
                       websockets.connect(ws_url) as guest_ws:
                
                # Both clients join
                await host_ws.send(json.dumps({
                    "type": "join",
                    "clientId": host_id,
                    "role": "host"
                }))
                await guest_ws.send(json.dumps({
                    "type": "join",
                    "clientId": guest_id,
                    "role": "guest"
                }))
                
                # Clear initial peers messages
                await host_ws.recv()  # host peers
                await guest_ws.recv()  # guest peers
                await host_ws.recv()  # host updated peers
                
                # Test SDP offer routing
                sdp_offer = {
                    "type": "sdp-offer",
                    "to": guest_id,
                    "sdp": "fake-sdp-offer-data"
                }
                await host_ws.send(json.dumps(sdp_offer))
                
                # Guest should receive the offer with 'from' field
                offer_response = await asyncio.wait_for(guest_ws.recv(), timeout=5)
                offer_msg = json.loads(offer_response)
                
                # Test SDP answer routing
                sdp_answer = {
                    "type": "sdp-answer",
                    "to": host_id,
                    "sdp": "fake-sdp-answer-data"
                }
                await guest_ws.send(json.dumps(sdp_answer))
                
                # Host should receive the answer
                answer_response = await asyncio.wait_for(host_ws.recv(), timeout=5)
                answer_msg = json.loads(answer_response)
                
                # Test ICE candidate routing
                ice_candidate = {
                    "type": "ice-candidate",
                    "to": guest_id,
                    "candidate": "fake-ice-candidate"
                }
                await host_ws.send(json.dumps(ice_candidate))
                
                # Guest should receive the ICE candidate
                ice_response = await asyncio.wait_for(guest_ws.recv(), timeout=5)
                ice_msg = json.loads(ice_response)
                
                # Verify message routing
                if (offer_msg.get("type") == "sdp-offer" and offer_msg.get("from") == host_id and
                    answer_msg.get("type") == "sdp-answer" and answer_msg.get("from") == guest_id and
                    ice_msg.get("type") == "ice-candidate" and ice_msg.get("from") == host_id):
                    print(f"✅ WebRTC message routing successful")
                    return True
                else:
                    print(f"❌ WebRTC message routing failed")
                    print(f"   Offer: {offer_msg}")
                    print(f"   Answer: {answer_msg}")
                    print(f"   ICE: {ice_msg}")
                    return False
                    
        except Exception as e:
            print(f"❌ WebRTC message routing test failed: {str(e)}")
            return False

    async def _test_client_disconnection(self, ws_url):
        """Test graceful client disconnection handling"""
        print(f"\n🔍 Test 4: Client Disconnection Handling")
        
        host_id = f"host_{datetime.now().strftime('%H%M%S')}"
        guest_id = f"guest_{datetime.now().strftime('%H%M%S')}"
        
        try:
            host_ws = await websockets.connect(ws_url)
            guest_ws = await websockets.connect(ws_url)
            
            # Both clients join
            await host_ws.send(json.dumps({
                "type": "join",
                "clientId": host_id,
                "role": "host"
            }))
            await guest_ws.send(json.dumps({
                "type": "join",
                "clientId": guest_id,
                "role": "guest"
            }))
            
            # Clear initial messages
            await host_ws.recv()  # host peers
            await guest_ws.recv()  # guest peers
            await host_ws.recv()  # host updated peers
            
            # Guest disconnects
            await guest_ws.close()
            
            # Host should receive updated peers list
            disconnect_response = await asyncio.wait_for(host_ws.recv(), timeout=5)
            disconnect_msg = json.loads(disconnect_response)
            
            await host_ws.close()
            
            if (disconnect_msg.get("type") == "peers" and 
                len(disconnect_msg.get("peers", [])) == 1 and
                host_id in disconnect_msg.get("peers", [])):
                print(f"✅ Client disconnection handling successful")
                return True
            else:
                print(f"❌ Client disconnection handling failed")
                print(f"   Disconnect response: {disconnect_msg}")
                return False
                
        except Exception as e:
            print(f"❌ Client disconnection test failed: {str(e)}")
            return False

    async def _test_ping_pong(self, ws_url):
        """Test ping/pong functionality"""
        print(f"\n🔍 Test 5: Ping/Pong Functionality")
        
        client_id = f"ping_client_{datetime.now().strftime('%H%M%S')}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Join first
                await websocket.send(json.dumps({
                    "type": "join",
                    "clientId": client_id,
                    "role": "test"
                }))
                
                # Clear peers message
                await websocket.recv()
                
                # Send ping
                await websocket.send(json.dumps({"type": "ping"}))
                
                # Wait for pong
                pong_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                pong_msg = json.loads(pong_response)
                
                if pong_msg.get("type") == "pong":
                    print(f"✅ Ping/Pong functionality successful")
                    return True
                else:
                    print(f"❌ Ping/Pong failed - received: {pong_msg}")
                    return False
                    
        except Exception as e:
            print(f"❌ Ping/Pong test failed: {str(e)}")
            return False
    async def test_websocket_edge_cases(self):
        """Test WebSocket edge cases and error handling"""
        session_id = f"edge_test_{datetime.now().strftime('%H%M%S')}"
        
        # Convert HTTP URL to WebSocket URL
        ws_base = self.base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        ws_url = f"{ws_base}/api/ws/session/{session_id}"
        
        print(f"\n🔍 Testing WebSocket Edge Cases...")
        
        # Test 1: Invalid join message
        success1 = await self._test_invalid_join_message(ws_url)
        
        # Test 2: Message to non-existent peer
        success2 = await self._test_message_to_nonexistent_peer(ws_url)
        
        # Test 3: Malformed JSON messages
        success3 = await self._test_malformed_messages(ws_url)
        
        # Test 4: Leave message handling
        success4 = await self._test_leave_message(ws_url)
        
        total_tests = 4
        passed_tests = sum([success1, success2, success3, success4])
        self.tests_run += total_tests
        self.tests_passed += passed_tests
        
        print(f"\n📊 Edge Case Tests: {passed_tests}/{total_tests} passed")
        return passed_tests == total_tests

    async def _test_invalid_join_message(self, ws_url):
        """Test handling of invalid join messages"""
        print(f"\n🔍 Edge Test 1: Invalid Join Message")
        
        try:
            websocket = await websockets.connect(ws_url)
            
            # Send invalid join message (missing type)
            invalid_join = {"clientId": "test", "role": "host"}
            await websocket.send(json.dumps(invalid_join))
            
            # Connection should be closed by server
            try:
                await asyncio.wait_for(websocket.recv(), timeout=3)
                await websocket.close()
                print(f"❌ Server should have closed connection for invalid join")
                return False
            except websockets.exceptions.ConnectionClosed:
                print(f"✅ Server properly closed connection for invalid join")
                return True
                
        except Exception as e:
            print(f"❌ Invalid join test failed: {str(e)}")
            return False

    async def _test_message_to_nonexistent_peer(self, ws_url):
        """Test sending messages to non-existent peers"""
        print(f"\n🔍 Edge Test 2: Message to Non-existent Peer")
        
        client_id = f"sender_{datetime.now().strftime('%H%M%S')}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Join properly
                await websocket.send(json.dumps({
                    "type": "join",
                    "clientId": client_id,
                    "role": "host"
                }))
                
                # Clear peers message
                await websocket.recv()
                
                # Send message to non-existent peer
                message_to_ghost = {
                    "type": "sdp-offer",
                    "to": "non_existent_peer",
                    "sdp": "fake-sdp"
                }
                await websocket.send(json.dumps(message_to_ghost))
                
                # Should not receive any response (message should be ignored)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2)
                    print(f"❌ Received unexpected response: {response}")
                    return False
                except asyncio.TimeoutError:
                    print(f"✅ Message to non-existent peer properly ignored")
                    return True
                    
        except Exception as e:
            print(f"❌ Non-existent peer test failed: {str(e)}")
            return False

    async def _test_malformed_messages(self, ws_url):
        """Test handling of malformed JSON messages"""
        print(f"\n🔍 Edge Test 3: Malformed Messages")
        
        client_id = f"malform_{datetime.now().strftime('%H%M%S')}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Join properly
                await websocket.send(json.dumps({
                    "type": "join",
                    "clientId": client_id,
                    "role": "host"
                }))
                
                # Clear peers message
                await websocket.recv()
                
                # Send malformed JSON
                await websocket.send("invalid json {")
                
                # Connection should remain open (server should handle gracefully)
                # Send a valid ping to test connection is still alive
                await websocket.send(json.dumps({"type": "ping"}))
                
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                msg = json.loads(response)
                
                if msg.get("type") == "pong":
                    print(f"✅ Connection survived malformed JSON")
                    return True
                else:
                    print(f"❌ Unexpected response after malformed JSON: {msg}")
                    return False
                    
        except Exception as e:
            print(f"❌ Malformed message test failed: {str(e)}")
            return False

    async def _test_leave_message(self, ws_url):
        """Test explicit leave message handling"""
        print(f"\n🔍 Edge Test 4: Leave Message Handling")
        
        host_id = f"host_leave_{datetime.now().strftime('%H%M%S')}"
        guest_id = f"guest_leave_{datetime.now().strftime('%H%M%S')}"
        
        try:
            async with websockets.connect(ws_url) as host_ws, \
                       websockets.connect(ws_url) as guest_ws:
                
                # Both clients join
                await host_ws.send(json.dumps({
                    "type": "join",
                    "clientId": host_id,
                    "role": "host"
                }))
                await guest_ws.send(json.dumps({
                    "type": "join",
                    "clientId": guest_id,
                    "role": "guest"
                }))
                
                # Clear initial messages
                await host_ws.recv()  # host peers
                await guest_ws.recv()  # guest peers
                await host_ws.recv()  # host updated peers
                
                # Guest sends leave message
                await guest_ws.send(json.dumps({"type": "leave"}))
                
                # Host should receive updated peers list
                leave_response = await asyncio.wait_for(host_ws.recv(), timeout=5)
                leave_msg = json.loads(leave_response)
                
                if (leave_msg.get("type") == "peers" and 
                    len(leave_msg.get("peers", [])) == 1 and
                    host_id in leave_msg.get("peers", [])):
                    print(f"✅ Leave message handling successful")
                    return True
                else:
                    print(f"❌ Leave message handling failed")
                    print(f"   Leave response: {leave_msg}")
                    return False
                    
        except Exception as e:
            print(f"❌ Leave message test failed: {str(e)}")
            return False

def main():
    print("🚀 Starting Backend API Tests...")
    print("=" * 50)
    
    tester = BackendAPITester()
    
    # Test basic API endpoints
    print("\n📡 Testing Basic API Endpoints")
    print("-" * 30)
    tester.test_root_endpoint()
    tester.test_status_endpoints()
    
    # Test FTP endpoints
    print("\n📁 Testing FTP Endpoints")
    print("-" * 30)
    tester.test_ftp_endpoints()
    
    # Test WebSocket signaling
    print("\n🔌 Testing WebSocket Signaling")
    print("-" * 30)
    try:
        asyncio.run(tester.test_websocket_signaling())
    except Exception as e:
        print(f"❌ WebSocket test setup failed: {str(e)}")
        tester.tests_run += 1
    
    # Test WebSocket edge cases
    print("\n🔧 Testing WebSocket Edge Cases")
    print("-" * 30)
    try:
        asyncio.run(tester.test_websocket_edge_cases())
    except Exception as e:
        print(f"❌ WebSocket edge case test setup failed: {str(e)}")
        tester.tests_run += 1
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Backend Tests Summary:")
    print(f"   Tests Run: {tester.tests_run}")
    print(f"   Tests Passed: {tester.tests_passed}")
    print(f"   Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "No tests run")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All backend tests passed!")
        return 0
    else:
        print("⚠️  Some backend tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())