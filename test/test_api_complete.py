#!/usr/bin/env python3
"""
v2.0 API 完整验收测试
"""
import requests
import json
from app.core.security import create_access_token


BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"


def test_api():
    print("=" * 60)
    print("🚀 开始 v2.0 API 验收测试")
    print("=" * 60)
    
    # 生成 Token
    token_user_1 = create_access_token(user_id=1)
    token_user_2 = create_access_token(user_id=2)
    
    headers_user_1 = {
        "Authorization": f"Bearer {token_user_1}",
        "Content-Type": "application/json"
    }
    
    headers_user_2 = {
        "Authorization": f"Bearer {token_user_2}",
        "Content-Type":  "application/json"
    }
    
    # 测试场景
    test_cases = [
        {
            "name": "场景1: 用户1查询自己的订单",
            "headers": headers_user_1,
            "data": {"question": "查询订单 SN20240001", "thread_id": "test1"},
            "expect": "应返回订单详情",
        },
        {
            "name": "场景2: 用户2尝试查询用户1的订单",
            "headers": headers_user_2,
            "data": {"question": "查询订单 SN20240001", "thread_id": "test2"},
            "expect": "应返回'未找到'",
        },
        {
            "name": "场景3: 政策咨询",
            "headers": headers_user_1,
            "data": {"question": "内衣拆封了可以退吗？", "thread_id": "test3"},
            "expect": "应从知识库检索",
        },
        {
            "name": "场景4: 查询最近订单",
            "headers": headers_user_1,
            "data":  {"question": "我的最近订单怎么样了？", "thread_id": "test4"},
            "expect": "应返回最近订单",
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{'=' * 60}")
        print(f"📋 测试 {i}/{len(test_cases)}: {case['name']}")
        print(f"{'=' * 60}")
        print(f"❓ 问题: {case['data']['question']}")  # ty:ignore[invalid-argument-type]
        print(f"🎯 预期: {case['expect']}")
        
        try:
            response = requests.post(
                f"{API_V1}/chat",
                headers=case["headers"],
                json=case["data"],
                stream=True,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}: {response.text}")
                continue
            
            print(f"\n🤖 Agent 回答:")
            full_answer = ""
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # 去掉 "data: " 前缀
                        
                        if data_str == '[DONE]':
                            print("\n✅ 响应完成")
                            break
                        
                        try: 
                            data = json.loads(data_str)
                            if 'token' in data:
                                token = data['token']
                                full_answer += token
                                print(token, end='', flush=True)
                            elif 'error' in data: 
                                print(f"\n❌ 错误:  {data['error']}")
                        except json.JSONDecodeError:
                            pass
            
            print(f"\n\n📄 完整回答:  {full_answer[: 200]}...")
            
            # 简单验证
            if i == 1:
                assert 'SN20240001' in full_answer or '订单' in full_answer
                print("✅ 测试通过")
            elif i == 2:
                assert '未找到' in full_answer or '无法查到' in full_answer or '不存在' in full_answer
                print("✅ 测试通过")
            elif i == 3:
                assert '退' in full_answer or '政策' in full_answer
                print("✅ 测试通过")
            elif i == 4:
                assert '订单' in full_answer
                print("✅ 测试通过")
                
        except Exception as e: 
            print(f"❌ 测试失败: {e}")
    
    print(f"\n{'=' * 60}")
    print("🎉 所有 API 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_api()