import json
import os
import time

import requests

# 配置目标服务器
SERVER_URL = os.getenv("VLLM_BASE_URL", "http://192.168.10.100:8000").rstrip("/")
MODEL_NAME = os.getenv("VLLM_MODEL", "qwen3.6-35b-a3b")

# 测试提示词
TEST_PROMPTS = [
    ("轻量(短)", "Write a Python function to calculate fibonacci."),
    ("中等", "Explain the concept of transformer models in deep learning, including attention mechanisms, positional encoding, training strategies, and practical applications in computer vision and natural language processing."),
    ("重度(长)", "Please write a comprehensive, detailed explanation of quantum computing principles, including qubits, superposition, entanglement, quantum gates, and quantum algorithms like Shor's algorithm and Grover's algorithm. Discuss the potential applications in cryptography, drug discovery, and materials science. Include the historical development of quantum computing, current state of the art, major players in the field, and future outlook."),
]

def test_streaming_latency():
    """测试流式延迟：首字时间(TTFT) + 生成速度"""
    api_key = os.getenv("VLLM_API_KEY")
    if not api_key:
        raise RuntimeError("请先设置环境变量 VLLM_API_KEY。")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    print("测试 vLLM 流式延迟")
    print(f"服务器地址: {SERVER_URL}")
    print(f"模型名称: {MODEL_NAME}")
    print("=" * 60)

    results = []
    for label, prompt_text in TEST_PROMPTS:
        print(f"\n测试类型: {label}")
        print(f"提示词: {prompt_text[:60]}...")

        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0.1,
            "max_tokens": 1024,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        try:
            start_time = time.time()
            first_token_time = None
            total_tokens = 0
            prompt_tokens = 0
            completion_tokens = 0

            response = requests.post(
                f"{SERVER_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=120
            )

            if response.status_code != 200:
                print(f"  错误: HTTP {response.status_code}, {response.text}")
                continue

            # 逐块读取
            for chunk in response.iter_lines(decode_unicode=True):
                if not chunk:
                    continue
                line = chunk.strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # 第一块到达即记录 TTFT
                    if first_token_time is None:
                        first_token_time = time.time()
                        ttft = first_token_time - start_time
                        print(f"  TTFT(首字延迟): {ttft:.3f} 秒")

                    # 统计 token
                    usage = data.get("usage", {})
                    if usage:
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
                        total_tokens = usage.get("total_tokens", 0)

            end_time = time.time()
            elapsed = end_time - start_time
            ttft = first_token_time - start_time if first_token_time else elapsed
            gen_time = elapsed - ttft
            gen_speed = completion_tokens / gen_time if gen_time > 0 else 0

            print(f"  总耗时: {elapsed:.2f} 秒")
            print(f"  生成时间: {gen_time:.2f} 秒")
            print(f"  Token: {prompt_tokens}(提示) + {completion_tokens}(完成) = {total_tokens}")
            print(f"  生成速度: {gen_speed:.2f} token/秒")

            results.append({
                "label": label,
                "ttft": ttft,
                "total_time": elapsed,
                "gen_time": gen_time,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "gen_speed": gen_speed,
            })

        except Exception as e:
            print(f"  错误: {str(e)}")

    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总:")
    print(f"{'类型':<10} {'TTFT(s)':>10} {'总耗时(s)':>10} {'生成(s)':>10} {'Prompt':>8} {'Completion':>10} {'速度(t/s)':>10}")
    print("-" * 60)

    for r in results:
        print(f"{r['label']:<10} {r['ttft']:>10.3f} {r['total_time']:>10.2f} {r['gen_time']:>10.2f} {r['prompt_tokens']:>8} {r['completion_tokens']:>10} {r['gen_speed']:>10.2f}")
    print("=" * 60)

    return results

if __name__ == "__main__":
    test_streaming_latency()
