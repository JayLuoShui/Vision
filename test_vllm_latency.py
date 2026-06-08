import requests
import time
import json
from typing import Dict, List, Tuple

# 配置目标服务器
SERVER_URL = "http://192.168.10.100:8000"  # vLLM API 端口
MODEL_NAME = "qwen3.6-35b-a3b"  # 模型名称

# 测试提示词
TEST_PROMPTS = [
    ("轻量(短)", "Write a Python function to calculate fibonacci."),
    ("中等", "Explain the concept of transformer models in deep learning, including attention mechanisms, positional encoding, training strategies, and practical applications in computer vision and natural language processing."),
    ("重度(长)", "Please write a comprehensive, detailed explanation of quantum computing principles, including qubits, superposition, entanglement, quantum gates, and quantum algorithms like Shor's algorithm and Grover's algorithm. Discuss the potential applications in cryptography, drug discovery, and materials science. Include the historical development of quantum computing, current state of the art, major players in the field, and future outlook."),
]

def test_vllm_latency():
    """测试 vLLM 模型延迟"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer team-vllm",
    }
    
    # 构造请求体
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": ""}],  # 将在循环中填充
        "temperature": 0.1,
        "max_tokens": 1024,
        "stream": False
    }
    
    print(f"测试 vLLM 模型延迟")
    print(f"服务器地址: {SERVER_URL}")
    print(f"模型名称: {MODEL_NAME}")
    print("=" * 60)
    
    # 测试每种提示词
    results = []
    for label, prompt_text in TEST_PROMPTS:
        print(f"\n测试类型: {label}")
        print(f"提示词: {prompt_text[:60]}...")
        
        # 更新消息内容
        payload["messages"][0]["content"] = prompt_text
        
        try:
            start_time = time.time()
            
            # 发送请求
            response = requests.post(
                f"{SERVER_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                # 提取 token 信息
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                
                # 获取响应文本
                response_text = data["choices"][0]["message"]["content"]
                response_preview = response_text[:80] + "..." if len(response_text) > 80 else response_text
                
                # 计算速度
                if elapsed_time > 0:
                    tokens_per_second = total_tokens / elapsed_time
                else:
                    tokens_per_second = 0
                
                print(f"  响应时间: {elapsed_time:.2f} 秒")
                print(f"  Token 数量: {prompt_tokens}(提示) + {completion_tokens}(完成) = {total_tokens}")
                print(f"  速度: {tokens_per_second:.2f} token/秒")
                print(f"  响应预览: {response_preview}")
                
                results.append({
                    "label": label,
                    "prompt": prompt_text,
                    "time": elapsed_time,
                    "tokens": total_tokens,
                    "speed": tokens_per_second,
                    "response_preview": response_preview
                })
            else:
                print(f"  错误: HTTP {response.status_code}")
                print(f"  响应: {response.text}")
                
        except Exception as e:
            print(f"  错误: {str(e)}")
    
    # 输出汇总
    print("\n" + "=" * 60)
    print("测试汇总:")
    print(f"{'测试类型':<12} {'时间(s)':>10} {'Token数':>10} {'速度(t/s)':>10}")
    print("-" * 60)
    for result in results:
        print(f"{result['label']:<12} {result['time']:>10.2f} {result['tokens']:>10} {result['speed']:>10.2f}")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    test_vllm_latency()