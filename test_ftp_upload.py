import requests
import json
import io
from datetime import datetime

def test_ftp_upload_endpoint():
    """Test FTP upload endpoint with various scenarios"""
    base_url = "https://stable-qr-transfer.preview.emergentagent.com"
    api_base = f"{base_url}/api"
    
    print("🔍 Testing FTP Upload Endpoint")
    print("-" * 40)
    
    # Test 1: Invalid config JSON
    print("\n📝 Test 1: Invalid config JSON")
    try:
        files = {'file': ('test.txt', io.BytesIO(b'test content'), 'text/plain')}
        params = {'config': 'invalid json', 'dest_dir': '/'}
        
        response = requests.post(f"{api_base}/ftp/upload", files=files, params=params, timeout=10)
        
        if response.status_code == 400:
            try:
                error_json = response.json()
                if "Invalid config" in error_json.get("detail", ""):
                    print("✅ Invalid config JSON properly rejected")
                else:
                    print(f"❌ Unexpected error message: {error_json}")
            except:
                print("❌ Response not valid JSON")
        else:
            print(f"❌ Expected 400, got {response.status_code}")
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
    
    # Test 2: Valid config format but invalid FTP server
    print("\n📝 Test 2: Valid config format, invalid FTP server")
    try:
        dummy_config = {
            "host": "invalid.ftp.server.com",
            "port": 21,
            "user": "testuser",
            "password": "testpass",
            "passive": True,
            "cwd": "/"
        }
        
        files = {'file': ('test.txt', io.BytesIO(b'test content'), 'text/plain')}
        params = {
            'config': json.dumps(dummy_config),
            'dest_dir': '/',
            'filename': 'test_upload.txt'
        }
        
        response = requests.post(f"{api_base}/ftp/upload", files=files, params=params, timeout=15)
        
        if response.status_code == 400:
            try:
                error_json = response.json()
                if "FTP connect failed" in error_json.get("detail", ""):
                    print("✅ Invalid FTP server properly rejected")
                    print(f"   Error detail: {error_json.get('detail')}")
                else:
                    print(f"❌ Unexpected error message: {error_json}")
            except:
                print("❌ Response not valid JSON")
        else:
            print(f"❌ Expected 400, got {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
    
    # Test 3: Missing file
    print("\n📝 Test 3: Missing file parameter")
    try:
        dummy_config = {
            "host": "test.ftp.com",
            "port": 21,
            "user": "test",
            "password": "test"
        }
        
        params = {
            'config': json.dumps(dummy_config),
            'dest_dir': '/'
        }
        
        response = requests.post(f"{api_base}/ftp/upload", params=params, timeout=10)
        
        if response.status_code == 422:  # FastAPI validation error
            print("✅ Missing file parameter properly rejected")
        else:
            print(f"❌ Expected 422, got {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")

    print("\n📊 FTP Upload Endpoint Testing Complete")

if __name__ == "__main__":
    test_ftp_upload_endpoint()