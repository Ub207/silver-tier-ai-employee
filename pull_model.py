"""
pull_model.py - Pull Ollama model with proper streaming
"""
import http.client
import json
import sys
import io

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MODEL = "llama3.2"

def pull_model():
    print(f"Pulling {MODEL} model...")
    print("This may take 5-10 minutes (~2GB download)")
    print()
    
    try:
        conn = http.client.HTTPConnection("localhost", 11434)
        
        # Send pull request
        body = json.dumps({"name": MODEL})
        conn.request("POST", "/api/pull", body, {"Content-Type": "application/json"})
        
        # Get response (this is a streaming response)
        response = conn.getresponse()
        
        if response.status != 200:
            print(f"Error: {response.status} {response.reason}")
            print(response.read().decode())
            return False
        
        # Read streaming response line by line
        last_status = ""
        while True:
            line = response.readline().decode('utf-8').strip()
            if not line:
                break
            
            try:
                data = json.loads(line)
                status = data.get('status', '')
                
                if status != last_status:
                    print(f"\r{status:50}", end="", flush=True)
                    last_status = status
                
                # Show progress if available
                if 'completed' in data and 'total' in data and data['total'] > 0:
                    pct = (data['completed'] / data['total']) * 100
                    print(f"\r{status}: {pct:.1f}%", end="", flush=True)
                    
            except json.JSONDecodeError:
                pass
        
        print()
        print()
        print("[OK] Pull complete!")
        
        # Verify
        conn = http.client.HTTPConnection("localhost", 11434)
        conn.request("GET", "/api/tags")
        response = conn.getresponse()
        data = json.loads(response.read().decode())
        
        models = data.get('models', [])
        print(f"Available models: {len(models)}")
        for m in models:
            name = m.get('name', 'unknown')
            if MODEL in name:
                print(f"  ✓ {name}")
                return True
        
        print(f"  ✗ {MODEL} not found in model list")
        return False
        
    except Exception as e:
        print(f"\nError: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = pull_model()
    sys.exit(0 if success else 1)
