"""
Quick test script to verify API server works
"""

import requests
import json

API_URL = "http://localhost:8000"

print("🧪 Testing Core Coder V5 API Server")
print("="*50)

# Test 1: Health check
print("\n1️⃣ Testing health endpoint...")
try:
    response = requests.get(f"{API_URL}/health")
    print(f"   ✅ Status: {response.status_code}")
    print(f"   📊 Response: {response.json()}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("   ⚠️  Make sure to run: python api_server.py")

# Test 2: Get status
print("\n2️⃣ Testing status endpoint...")
try:
    response = requests.get(f"{API_URL}/api/status")
    data = response.json()
    print(f"   ✅ Agent: {data.get('name')}")
    print(f"   ✅ Model: {data.get('model')}")
    print(f"   ✅ CWD: {data.get('cwd')}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: List commands
print("\n3️⃣ Testing commands list...")
try:
    response = requests.get(f"{API_URL}/api/commands")
    data = response.json()
    print(f"   ✅ Found {data.get('total')} commands:")
    for cmd in data.get('commands', [])[:5]:
        print(f"      • {cmd['name']}: {cmd['description']}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: Execute command
print("\n4️⃣ Testing command execution (//status)...")
try:
    response = requests.post(
        f"{API_URL}/api/command",
        json={"command": "status"}
    )
    data = response.json()
    print(f"   ✅ Success: {data.get('success')}")
    print(f"   ✅ Has ANSI codes: {data.get('ansi')}")
    print(f"   📝 Result preview: {data.get('result', '')[:100]}...")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 5: Get current directory
print("\n5️⃣ Testing pwd command...")
try:
    response = requests.post(
        f"{API_URL}/api/command",
        json={"command": "pwd"}
    )
    data = response.json()
    print(f"   ✅ Current directory: {data.get('cwd')}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*50)
print("✅ API Server is working!")
print("📖 See API_README.md for Next.js integration")
print("🌐 API Docs: http://localhost:8000/docs")
