import urllib.request
import urllib.error
import time
import json
import sys
import ssl

# Updated URLs for LAN testing
DEFAULT_URLS = [
    ("Local", "http://localhost:11434"),
    ("LAN", "http://192.168.10.100:11434"),
    ("ZeroTier", "http://10.156.108.251:11434"),
    # Add more LAN IPs here if needed
]

# Qwen3-Coder specific prompts for testing
PROMPTS = [
    ("轻量(短)", "Write a Python function to calculate fibonacci."),
    ("中等", "Explain the concept of transformer models in deep learning, including attention mechanisms, positional encoding, training strategies, and practical applications in computer vision and natural language processing."),
    ("重度(长)", "Please write a comprehensive, detailed explanation of quantum computing principles, including qubits, superposition, entanglement, quantum gates, and quantum algorithms like Shor's algorithm and Grover's algorithm. Discuss the potential applications in cryptography, drug discovery, and materials science. Include the historical development of quantum computing, current state of the art, major players in the field, and future outlook."),
]

def http_request(url, data=None, method="GET"):
    """Make an HTTP request returning (status_code, json_data) or (None, None)."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')
    body = json.dumps(data).encode('utf-8') if data else None
    try:
        with urllib.request.urlopen(req, data=body, timeout=120, context=ctx) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return resp.status, result
    except Exception:
        return None, None


def detect_model(url):
    """Detect available models on the Ollama instance."""
    status, data = http_request(f"{url}/api/tags")
    if status == 200 and data and data.get("models"):
        # Look for Qwen3-Coder models specifically
        for model in data["models"]:
            if "qwen3-coder" in model["name"].lower():
                return model["name"]
        # Return first model if no Qwen3-Coder found
        return data["models"][0]["name"]
    return None


def test_speed(url, model, prompt_text, label=""):
    """Test token/s for a single generation."""
    body = {
        "model": model,
        "prompt": prompt_text,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    print(f"\n  [{label}] Prompt: {prompt_text[:60]}...")
    print(f"  [{'=' * 50}]")
    try:
        start = time.time()
        status, data = http_request(f"{url}/api/generate", body, "POST")
        elapsed = time.time() - start
        if status != 200 or not data:
            print(f"  HTTP error or invalid response (status={status})")
            return None
        token_count = data.get("eval_count", 0)
        if token_count == 0:
            print("  Cannot get token count")
            return None
        speed = token_count / elapsed
        summary = data.get("response", "")[:80]
        print(f"  Tokens: {token_count}  |  Time: {elapsed:.2f}s  |  Speed: {speed:.2f} tok/s")
        print(f"  Preview: {summary}...")
        print(f"  [{'=' * 50}]")
        return {"tokens": token_count, "elapsed": elapsed, "speed": speed}
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def main():
    model_name = None
    target_url = None

    print("Testing Qwen3-Coder latency on LAN...")
    print("Searching for available Ollama instances...")
    
    for label, url in DEFAULT_URLS:
        print(f"--- Checking {label}: {url} ---")
        m = detect_model(url)
        if m:
            model_name = m
            target_url = url
            print(f"  OK! Model detected: {m}")
            break
        else:
            print("  FAILED")

    if not model_name:
        print("\nNone of the default URLs responded.")
        print("Please ensure Ollama is running on one of these addresses:")
        for label, url in DEFAULT_URLS:
            print(f"  {label}: {url}")
        print("Then run this script again.")
        print("\nAlternative usage:")
        print("请修改脚本顶部 DEFAULT_URLS 后重新运行。")
        sys.exit(1)

    print(f"\nUsing model: {model_name}")
    print(f"Using URL: {target_url}")

    # Test with specific Qwen3-Coder prompts
    print("\nRunning latency tests with Qwen3-Coder prompts...")
    results = {}
    for label, prompt_text in PROMPTS:
        res = test_speed(target_url, model_name, prompt_text, label)
        if res:
            results[label] = res

    print("\n" + "=" * 60)
    print(f"{'Test':<12} {'Tokens':>8} {'Time(s)':>9} {'tok/s':>10}")
    print("-" * 60)
    for label, res in results.items():
        print(f"{label:<12} {res['tokens']:>8} {res['elapsed']:>9.2f} {res['speed']:>10.2f}")
    print("=" * 60)
    
    print("\nSummary:")
    print(f"- Testing model: {model_name}")
    print(f"- Target server: {target_url}")
    print(f"- Test prompts: {len(PROMPTS)} variations")


if __name__ == "__main__":
    main()
