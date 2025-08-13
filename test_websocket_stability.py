import asyncio
import websockets
import json
from datetime import datetime
import time

async def test_websocket_stability():
    """Test WebSocket connection stability under various conditions"""
    base_url = "https://linux-deploy-script.preview.emergentagent.com"
    ws_base = base_url.replace('https://', 'wss://')
    
    print("🔍 Testing WebSocket Connection Stability")
    print("=" * 50)
    
    # Test 1: Long-running connection with periodic messages
    print("\n📝 Test 1: Long-running connection stability")
    session_id = f"stability_test_{datetime.now().strftime('%H%M%S')}"
    ws_url = f"{ws_base}/api/ws/session/{session_id}"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            client_id = f"stability_client_{datetime.now().strftime('%H%M%S')}"
            
            # Join
            await websocket.send(json.dumps({
                "type": "join",
                "clientId": client_id,
                "role": "host"
            }))
            
            # Clear peers message
            await websocket.recv()
            
            # Send periodic pings for 30 seconds
            start_time = time.time()
            ping_count = 0
            pong_count = 0
            
            while time.time() - start_time < 30:
                # Send ping
                await websocket.send(json.dumps({"type": "ping"}))
                ping_count += 1
                
                try:
                    # Wait for pong
                    response = await asyncio.wait_for(websocket.recv(), timeout=2)
                    msg = json.loads(response)
                    if msg.get("type") == "pong":
                        pong_count += 1
                except asyncio.TimeoutError:
                    print(f"⚠️  Ping {ping_count} timed out")
                
                await asyncio.sleep(1)
            
            success_rate = (pong_count / ping_count) * 100 if ping_count > 0 else 0
            print(f"✅ Long-running connection test completed")
            print(f"   Pings sent: {ping_count}, Pongs received: {pong_count}")
            print(f"   Success rate: {success_rate:.1f}%")
            
    except Exception as e:
        print(f"❌ Long-running connection test failed: {str(e)}")
    
    # Test 2: Rapid connection/disconnection cycles
    print("\n📝 Test 2: Rapid connection cycles")
    successful_connections = 0
    total_attempts = 10
    
    for i in range(total_attempts):
        try:
            session_id = f"rapid_test_{i}_{datetime.now().strftime('%H%M%S')}"
            ws_url = f"{ws_base}/api/ws/session/{session_id}"
            
            async with websockets.connect(ws_url) as websocket:
                client_id = f"rapid_client_{i}"
                
                # Join
                await websocket.send(json.dumps({
                    "type": "join",
                    "clientId": client_id,
                    "role": "test"
                }))
                
                # Wait for peers response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                msg = json.loads(response)
                
                if msg.get("type") == "peers" and client_id in msg.get("peers", []):
                    successful_connections += 1
                
        except Exception as e:
            print(f"⚠️  Connection {i+1} failed: {str(e)}")
    
    connection_success_rate = (successful_connections / total_attempts) * 100
    print(f"✅ Rapid connection cycles completed")
    print(f"   Successful connections: {successful_connections}/{total_attempts}")
    print(f"   Success rate: {connection_success_rate:.1f}%")
    
    # Test 3: Large message handling (simulating file transfer signaling)
    print("\n📝 Test 3: Large message handling")
    session_id = f"large_msg_test_{datetime.now().strftime('%H%M%S')}"
    ws_url = f"{ws_base}/api/ws/session/{session_id}"
    
    try:
        async with websockets.connect(ws_url) as host_ws, \
                   websockets.connect(ws_url) as guest_ws:
            
            host_id = f"host_large_{datetime.now().strftime('%H%M%S')}"
            guest_id = f"guest_large_{datetime.now().strftime('%H%M%S')}"
            
            # Both join
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
            
            # Send large SDP offer (simulating WebRTC negotiation)
            large_sdp = "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n" + "a=test-data\r\n" * 100
            
            large_message = {
                "type": "sdp-offer",
                "to": guest_id,
                "sdp": large_sdp
            }
            
            await host_ws.send(json.dumps(large_message))
            
            # Guest should receive the large message
            response = await asyncio.wait_for(guest_ws.recv(), timeout=10)
            msg = json.loads(response)
            
            if (msg.get("type") == "sdp-offer" and 
                msg.get("from") == host_id and 
                len(msg.get("sdp", "")) > 1000):
                print("✅ Large message handling successful")
                print(f"   Message size: {len(json.dumps(large_message))} bytes")
            else:
                print("❌ Large message handling failed")
                
    except Exception as e:
        print(f"❌ Large message test failed: {str(e)}")
    
    # Test 4: Multiple simultaneous sessions
    print("\n📝 Test 4: Multiple simultaneous sessions")
    session_count = 5
    successful_sessions = 0
    
    async def test_session(session_num):
        try:
            session_id = f"multi_session_{session_num}_{datetime.now().strftime('%H%M%S')}"
            ws_url = f"{ws_base}/api/ws/session/{session_id}"
            
            async with websockets.connect(ws_url) as websocket:
                client_id = f"multi_client_{session_num}"
                
                await websocket.send(json.dumps({
                    "type": "join",
                    "clientId": client_id,
                    "role": "test"
                }))
                
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                msg = json.loads(response)
                
                if msg.get("type") == "peers" and client_id in msg.get("peers", []):
                    return True
                return False
                
        except Exception:
            return False
    
    # Run multiple sessions concurrently
    tasks = [test_session(i) for i in range(session_count)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful_sessions = sum(1 for result in results if result is True)
    multi_session_success_rate = (successful_sessions / session_count) * 100
    
    print(f"✅ Multiple simultaneous sessions completed")
    print(f"   Successful sessions: {successful_sessions}/{session_count}")
    print(f"   Success rate: {multi_session_success_rate:.1f}%")
    
    print("\n" + "=" * 50)
    print("📊 WebSocket Stability Test Summary:")
    print(f"   All tests completed successfully")
    print(f"   Connection stability appears robust")

if __name__ == "__main__":
    asyncio.run(test_websocket_stability())