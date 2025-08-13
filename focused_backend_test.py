import requests
import json
import asyncio
import websockets
from datetime import datetime
import sys

class FocusedBackendTester:
    def __init__(self, base_url="https://linux-deploy-script.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

    def log_test(self, name, success, details=""):
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
        if details:
            print(f"   {details}")

    def test_basic_endpoints(self):
        """Test basic API endpoints"""
        print("\n📡 Testing Basic API Endpoints")
        print("-" * 40)
        
        # Test root endpoint
        try:
            response = requests.get(f"{self.api_base}/", timeout=10)
            success = response.status_code == 200
            self.log_test("Root API endpoint", success, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Root API endpoint", False, f"Error: {str(e)}")

        # Test status endpoints
        try:
            test_data = {"client_name": f"test_client_{datetime.now().strftime('%H%M%S')}"}
            response = requests.post(f"{self.api_base}/status", json=test_data, timeout=10)
            success = response.status_code == 200
            self.log_test("Status creation endpoint", success, f"Status: {response.status_code}")
            
            if success:
                response = requests.get(f"{self.api_base}/status", timeout=10)
                success = response.status_code == 200
                self.log_test("Status retrieval endpoint", success, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Status endpoints", False, f"Error: {str(e)}")

    def test_ftp_endpoints(self):
        """Test FTP endpoints"""
        print("\n📁 Testing FTP Endpoints")
        print("-" * 40)
        
        # Test FTP list with invalid config (should return 400)
        dummy_config = {
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
        
        try:
            response = requests.post(f"{self.api_base}/ftp/list", json=dummy_config, timeout=10)
            success = response.status_code == 400
            self.log_test("FTP list error handling", success, f"Status: {response.status_code}")
            
            if response.status_code == 400:
                try:
                    error_json = response.json()
                    has_detail = "detail" in error_json
                    self.log_test("FTP error response format", has_detail, f"Has detail field: {has_detail}")
                except:
                    self.log_test("FTP error response format", False, "Response not valid JSON")
        except Exception as e:
            self.log_test("FTP list endpoint", False, f"Error: {str(e)}")

    async def test_websocket_core(self):
        """Test core WebSocket functionality"""
        print("\n🔌 Testing WebSocket Core Functionality")
        print("-" * 40)
        
        session_id = f"test_session_{datetime.now().strftime('%H%M%S')}"
        ws_base = self.base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        ws_url = f"{ws_base}/api/ws/session/{session_id}"
        
        # Test 1: Basic connection and join
        try:
            async with websockets.connect(ws_url) as websocket:
                client_id = f"test_client_{datetime.now().strftime('%H%M%S')}"
                
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
                
                success = msg.get("type") == "peers" and client_id in msg.get("peers", [])
                self.log_test("WebSocket connection and join", success, f"Peers: {msg.get('peers', [])}")
                
        except Exception as e:
            self.log_test("WebSocket connection and join", False, f"Error: {str(e)}")

        # Test 2: Ping/Pong
        try:
            async with websockets.connect(ws_url) as websocket:
                client_id = f"ping_client_{datetime.now().strftime('%H%M%S')}"
                
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
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                msg = json.loads(response)
                
                success = msg.get("type") == "pong"
                self.log_test("WebSocket ping/pong", success, f"Response type: {msg.get('type')}")
                
        except Exception as e:
            self.log_test("WebSocket ping/pong", False, f"Error: {str(e)}")

        # Test 3: Message routing between two clients
        try:
            host_id = f"host_{datetime.now().strftime('%H%M%S')}"
            guest_id = f"guest_{datetime.now().strftime('%H%M%S')}"
            
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
                
                # Guest should receive the offer
                response = await asyncio.wait_for(guest_ws.recv(), timeout=5)
                msg = json.loads(response)
                
                success = (msg.get("type") == "sdp-offer" and 
                          msg.get("from") == host_id and 
                          msg.get("sdp") == "fake-sdp-offer-data")
                self.log_test("WebSocket message routing", success, f"Message routed correctly: {success}")
                
        except Exception as e:
            self.log_test("WebSocket message routing", False, f"Error: {str(e)}")

    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Focused Backend Tests...")
        print("=" * 50)
        
        # Test basic endpoints
        self.test_basic_endpoints()
        
        # Test FTP endpoints
        self.test_ftp_endpoints()
        
        # Test WebSocket functionality
        try:
            asyncio.run(self.test_websocket_core())
        except Exception as e:
            print(f"❌ WebSocket test setup failed: {str(e)}")
            self.tests_run += 3  # Account for the 3 WebSocket tests that failed
        
        # Print results
        print("\n" + "=" * 50)
        print(f"📊 Test Results Summary:")
        print(f"   Tests Run: {self.tests_run}")
        print(f"   Tests Passed: {self.tests_passed}")
        if self.tests_run > 0:
            success_rate = (self.tests_passed / self.tests_run) * 100
            print(f"   Success Rate: {success_rate:.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print("⚠️  Some tests failed")
            return False

if __name__ == "__main__":
    tester = FocusedBackendTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)