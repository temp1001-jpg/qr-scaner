#!/usr/bin/env python3
"""
Focused Backend Health Test
Tests specific requirements from review request:
1. GET /api/ returns 200 and Hello World JSON
2. WebSocket /api/ws/session/{sid} can accept connection and respond to ping with pong
3. FTP endpoints return 400 errors (not 500s) for invalid configs
"""

import requests
import json
import asyncio
import websockets
from datetime import datetime
import sys

class FocusedBackendHealthTester:
    def __init__(self):
        # Use the production URL from frontend/.env
        self.base_url = "https://linux-deploy-script.preview.emergentagent.com"
        self.api_base = f"{self.base_url}/api"
        self.results = []

    def log_result(self, test_name, success, details):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        self.results.append({
            'test': test_name,
            'success': success,
            'details': details
        })
        return success

    def test_root_api_endpoint(self):
        """Test 1: GET /api/ returns 200 and Hello World JSON"""
        print(f"\n🔍 Test 1: Root API Endpoint")
        print(f"   URL: {self.api_base}/")
        
        try:
            response = requests.get(f"{self.api_base}/", timeout=10)
            
            if response.status_code != 200:
                return self.log_result(
                    "Root API Endpoint", 
                    False, 
                    f"Expected status 200, got {response.status_code}"
                )
            
            try:
                json_data = response.json()
                if json_data.get("message") == "Hello World":
                    return self.log_result(
                        "Root API Endpoint", 
                        True, 
                        f"Status: {response.status_code}, Response: {json_data}"
                    )
                else:
                    return self.log_result(
                        "Root API Endpoint", 
                        False, 
                        f"Expected 'Hello World' message, got: {json_data}"
                    )
            except Exception as e:
                return self.log_result(
                    "Root API Endpoint", 
                    False, 
                    f"Response not valid JSON: {response.text[:100]}"
                )
                
        except Exception as e:
            return self.log_result(
                "Root API Endpoint", 
                False, 
                f"Request failed: {str(e)}"
            )

    async def test_websocket_ping_pong(self):
        """Test 2: WebSocket can accept connection and respond to ping with pong"""
        print(f"\n🔍 Test 2: WebSocket Ping/Pong")
        
        session_id = f"health_test_{datetime.now().strftime('%H%M%S')}"
        ws_base = self.base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        ws_url = f"{ws_base}/api/ws/session/{session_id}"
        
        print(f"   WS URL: {ws_url}")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Send join message first (required by server)
                join_msg = {
                    "type": "join",
                    "clientId": f"health_client_{datetime.now().strftime('%H%M%S')}",
                    "role": "test"
                }
                await websocket.send(json.dumps(join_msg))
                
                # Wait for peers response
                peers_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                peers_msg = json.loads(peers_response)
                
                if peers_msg.get("type") != "peers":
                    return self.log_result(
                        "WebSocket Ping/Pong", 
                        False, 
                        f"Expected peers message, got: {peers_msg}"
                    )
                
                # Send ping
                await websocket.send(json.dumps({"type": "ping"}))
                
                # Wait for pong
                pong_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                pong_msg = json.loads(pong_response)
                
                if pong_msg.get("type") == "pong":
                    return self.log_result(
                        "WebSocket Ping/Pong", 
                        True, 
                        f"Successfully connected and received pong response"
                    )
                else:
                    return self.log_result(
                        "WebSocket Ping/Pong", 
                        False, 
                        f"Expected pong, got: {pong_msg}"
                    )
                    
        except Exception as e:
            return self.log_result(
                "WebSocket Ping/Pong", 
                False, 
                f"WebSocket test failed: {str(e)}"
            )

    def test_ftp_endpoints_error_handling(self):
        """Test 3: FTP endpoints return 400 errors (not 500s) for invalid configs"""
        print(f"\n🔍 Test 3: FTP Endpoints Error Handling")
        
        # Test FTP list endpoint with invalid config
        print(f"   Testing /api/ftp/list with invalid config")
        
        invalid_ftp_config = {
            "config": {
                "host": "invalid.nonexistent.host.example.com",
                "port": 21,
                "user": "invalid_user",
                "password": "invalid_pass",
                "passive": True,
                "cwd": "/"
            },
            "path": "."
        }
        
        try:
            response = requests.post(
                f"{self.api_base}/ftp/list", 
                json=invalid_ftp_config, 
                timeout=15
            )
            
            if response.status_code == 400:
                try:
                    error_json = response.json()
                    if "detail" in error_json and "FTP connect failed" in error_json["detail"]:
                        ftp_list_success = self.log_result(
                            "FTP List Error Handling", 
                            True, 
                            f"Status: {response.status_code}, Error: {error_json['detail'][:100]}"
                        )
                    else:
                        ftp_list_success = self.log_result(
                            "FTP List Error Handling", 
                            False, 
                            f"Status 400 but missing proper error detail: {error_json}"
                        )
                except:
                    ftp_list_success = self.log_result(
                        "FTP List Error Handling", 
                        False, 
                        f"Status 400 but response not valid JSON: {response.text[:100]}"
                    )
            elif response.status_code == 500:
                ftp_list_success = self.log_result(
                    "FTP List Error Handling", 
                    False, 
                    f"Got 500 error instead of 400: {response.text[:100]}"
                )
            else:
                ftp_list_success = self.log_result(
                    "FTP List Error Handling", 
                    False, 
                    f"Expected 400, got {response.status_code}: {response.text[:100]}"
                )
                
        except Exception as e:
            ftp_list_success = self.log_result(
                "FTP List Error Handling", 
                False, 
                f"Request failed: {str(e)}"
            )
        
        # Test FTP upload endpoint with invalid config
        print(f"   Testing /api/ftp/upload with invalid config")
        
        try:
            # Create a dummy file for upload
            files = {'file': ('test.txt', 'dummy content', 'text/plain')}
            
            # FTP upload expects config as query parameter
            config_json = json.dumps({
                "host": "invalid.nonexistent.host.example.com",
                "port": 21,
                "user": "invalid_user",
                "password": "invalid_pass",
                "passive": True,
                "cwd": "/"
            })
            
            params = {
                'config': config_json,
                'dest_dir': '/'
            }
            
            response = requests.post(
                f"{self.api_base}/ftp/upload", 
                files=files,
                params=params,
                timeout=15
            )
            
            if response.status_code == 400:
                try:
                    error_json = response.json()
                    if "detail" in error_json and "FTP connect failed" in error_json["detail"]:
                        ftp_upload_success = self.log_result(
                            "FTP Upload Error Handling", 
                            True, 
                            f"Status: {response.status_code}, Error: {error_json['detail'][:100]}"
                        )
                    else:
                        ftp_upload_success = self.log_result(
                            "FTP Upload Error Handling", 
                            False, 
                            f"Status 400 but missing proper error detail: {error_json}"
                        )
                except:
                    ftp_upload_success = self.log_result(
                        "FTP Upload Error Handling", 
                        False, 
                        f"Status 400 but response not valid JSON: {response.text[:100]}"
                    )
            elif response.status_code == 500:
                ftp_upload_success = self.log_result(
                    "FTP Upload Error Handling", 
                    False, 
                    f"Got 500 error instead of 400: {response.text[:100]}"
                )
            else:
                ftp_upload_success = self.log_result(
                    "FTP Upload Error Handling", 
                    False, 
                    f"Expected 400, got {response.status_code}: {response.text[:100]}"
                )
                
        except Exception as e:
            ftp_upload_success = self.log_result(
                "FTP Upload Error Handling", 
                False, 
                f"Request failed: {str(e)}"
            )
        
        return ftp_list_success and ftp_upload_success

    async def run_all_tests(self):
        """Run all focused health tests"""
        print("🚀 Starting Focused Backend Health Tests...")
        print("=" * 60)
        
        # Test 1: Root API endpoint
        test1_success = self.test_root_api_endpoint()
        
        # Test 2: WebSocket ping/pong
        test2_success = await self.test_websocket_ping_pong()
        
        # Test 3: FTP error handling
        test3_success = self.test_ftp_endpoints_error_handling()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Focused Backend Health Test Results:")
        print("-" * 40)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        
        for result in self.results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}")
        
        print(f"\nSummary: {passed_tests}/{total_tests} tests passed")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "No tests run")
        
        if passed_tests == total_tests:
            print("🎉 All backend health tests passed!")
            return True
        else:
            print("⚠️  Some backend health tests failed")
            return False

def main():
    tester = FocusedBackendHealthTester()
    
    try:
        success = asyncio.run(tester.run_all_tests())
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Test execution failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())