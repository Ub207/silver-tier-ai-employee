"""
test_ollama.py — Test Ollama Connection

Quick test to verify Ollama is installed and working.
"""

import urllib.request
import json
import sys
import io

# Fix Windows encoding
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def test_ollama():
    model = "llama3.2"
    base_url = "http://localhost:11434"
    
    print("Testing Ollama Connection...")
    print(f"   Model: {model}")
    print(f"   URL: {base_url}")
    print()
    
    try:
        # Test 1: Check if Ollama is running
        print("1. Checking if Ollama server is running...")
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            print(f"   [OK] Ollama is running!")
            print(f"   Available models: {len(data.get('models', []))}")
            for m in data.get('models', []):
                print(f"      - {m.get('name', 'unknown')}")
    except urllib.error.URLError as e:
        print(f"   [ERROR] Ollama is NOT running!")
        print(f"   Error: {e}")
        print()
        print("   Solution:")
        print("   1. Install Ollama from: https://ollama.com/download/windows")
        print("   2. Run: ollama pull llama3.2")
        print("   3. Keep Ollama running in background")
        return False
    
    try:
        # Test 2: Generate a simple response
        print()
        print("2. Testing model generation...")
        prompt = "Say 'Hello, I am working!' in exactly 5 words."
        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False
            }).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            response = result.get("response", "")
            print(f"   [OK] Model responded!")
            print(f"   Prompt: {prompt}")
            print(f"   Response: {response}")
    except Exception as e:
        print(f"   [ERROR] Model generation failed!")
        print(f"   Error: {e}")
        print()
        print(f"   Try pulling the model: ollama pull {model}")
        return False
    
    print()
    print("[SUCCESS] All tests passed! Ollama is ready to use.")
    print()
    print("Next steps:")
    print("  python workflow_runner.py")
    return True

if __name__ == "__main__":
    success = test_ollama()
    sys.exit(0 if success else 1)
