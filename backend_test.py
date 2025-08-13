import requests
import sys
import json
import asyncio
import websockets
from datetime import datetime

class BackendAPITester:
    def __init__(self, base_url="https://easyftp-1.preview.emergentagent.com"):
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
        """Test WebSocket signaling endpoint"""
        session_id = f"test_session_{datetime.now().strftime('%H%M%S')}"
        client_id = f"test_client_{datetime.now().strftime('%H%M%S')}"
        
        # Convert HTTP URL to WebSocket URL
        ws_base = self.base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        ws_url = f"{ws_base}/api/ws/session/{session_id}"
        
        print(f"\n🔍 Testing WebSocket Signaling...")
        print(f"   WS URL: {ws_url}")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print("✅ WebSocket connection established")
                
                # Send join message
                join_msg = {
                    "type": "join",
                    "clientId": client_id,
                    "role": "host"
                }
                await websocket.send(json.dumps(join_msg))
                print("✅ Join message sent")
                
                # Wait for peers response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                msg = json.loads(response)
                
                if msg.get("type") == "peers":
                    print(f"✅ Received peers message: {msg}")
                    self.tests_passed += 1
                    return True
                else:
                    print(f"❌ Unexpected message type: {msg}")
                    return False
                    
        except Exception as e:
            print(f"❌ WebSocket test failed: {str(e)}")
            return False
        finally:
            self.tests_run += 1

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