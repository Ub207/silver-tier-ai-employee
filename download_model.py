"""
download_model.py - Download Ollama model with progress
"""
import urllib.request
import json
import sys
import io

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3.2"

def download_model():
    print("=" * 60)
    print(f"Downloading {MODEL} model from Ollama")
    print("=" * 60)
    print()
    
    try:
        # Check if Ollama is running
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = data.get('models', [])
            
            # Check if model already exists
            for m in models:
                if MODEL in m.get('name', ''):
                    print(f"[OK] {MODEL} is already downloaded!")
                    return True
        
        print(f"Starting download of {MODEL}...")
        print("(This will take 2-5 minutes, ~2GB)")
        print()
        
        # Start pull
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/pull",
            data=json.dumps({"name": MODEL}).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        # Use stream to show progress
        with urllib.request.urlopen(req, timeout=600) as resp:
            # Read response line by line
            buffer = ""
            while True:
                chunk = resp.read(4096).decode('utf-8')
                if not chunk:
                    break
                buffer += chunk
                
                # Parse complete JSON objects
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            data = json.loads(line)
                            status = data.get('status', '')
                            completed = data.get('completed', 0)
                            total = data.get('total', 0)
                            
                            if total > 0:
                                percent = (completed / total) * 100
                                print(f"\rProgress: {percent:.1f}% - {status}", end="", flush=True)
                            else:
                                print(f"\r{status}", end="", flush=True)
                                
                        except json.JSONDecodeError:
                            pass
        
        print()
        print()
        print("[OK] Model download complete!")
        
        # Verify
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = data.get('models', [])
            print(f"Available models: {len(models)}")
            for m in models:
                print(f"  - {m.get('name', 'unknown')}")
        
        return True
        
    except Exception as e:
        print()
        print(f"[ERROR] Download failed: {e}")
        print()
        print("Manual steps:")
        print(f"  1. Open PowerShell or CMD")
        print(f"  2. Run: ollama pull {MODEL}")
        return False

if __name__ == "__main__":
    success = download_model()
    sys.exit(0 if success else 1)
