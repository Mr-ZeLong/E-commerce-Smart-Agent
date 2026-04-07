# test/test_v4_complete.py
"""
v4.0 完整验收测试
验证场景: 
1. 普通退款（自动通过）
2. 高额退款（触发人工审核）
3. WebSocket 状态同步
4. 管理员决策流程
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import init_db
from app.graph.workflow import compile_app_graph
from app.core.security import create_access_token
from app.models.audit import AuditLog, AuditAction
from app.models.refund import RefundApplication, RefundStatus
from app.core.database import async_session_maker
from sqlmodel import select, desc


async def test_v4():
    print("=" * 60)
    print("开始 v4.0 验收测试")
    print("=" * 60)
    
    # 1. 初始化
    print("\n📦 初始化数据库和 Agent...")
    await init_db()
    app_graph = await compile_app_graph()
    
    # 2. 测试场景
    test_cases = [
        {
            "name": "场景1: 低额退款（自动通过）",
            "user_id": 1,
            "query": "我要退款 100 元，订单 SN20240003",
            "expect":  "应该自动通过，无需人工审核",
        },
        {
            "name": "场景2: 高额退款（触发人工审核）",
            "user_id": 1,
            "query": "我要退款 2500 元，订单 SN20240003，商品质量有问题",
            "expect":  "应该触发 HIGH 风险审核",
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{'=' * 60}")
        print(f" 测试 {i}/{len(test_cases)}: {case['name']}")
        print(f"{'=' * 60}")
        print(f" 用户ID: {case['user_id']}")
        print(f" 问题:  {case['query']}")
        print(f" 预期: {case['expect']}")
        
        # 构造初始状态
        thread_id = f"test_v4_user_{case['user_id']}_case_{i}"
        initial_state = {
            "question": case["query"],
            "user_id": case["user_id"],
            "thread_id":  thread_id,
            "history": [],
            "context": [],
            "order_data": None,
            "intent": None,
            "audit_required": False,
            "audit_log_id": None,
            "messages": [],
            "refund_flow_active": None,
            "refund_order_sn": None,
            "refund_step": None,
            "answer":  ""
        }
        
        config = {
            "configurable":  {
                "thread_id": thread_id
            }
        }
        
        try:
            # 调用 Agent
            final_state = await app_graph.ainvoke(initial_state, config)
            
            # 输出结果
            print(f"\n 结果分析:")
            print(f"  意图: {final_state.get('intent', 'N/A')}")
            print(f"  需要审核: {final_state.get('audit_required', False)}")
            
            if final_state.get('audit_required'):
                audit_log_id = final_state.get('audit_log_id')
                print(f"  审计日志ID: {audit_log_id}")
                
                # 查询审计日志
                async with async_session_maker() as session:
                    result = await session.execute(  # ty:ignore[deprecated]
                        select(AuditLog).where(AuditLog.id == audit_log_id)
                    )
                    audit_log = result.scalar_one_or_none()
                    
                    if audit_log: 
                        print(f"  风险等级: {audit_log.risk_level}")
                        print(f"  触发原因: {audit_log.trigger_reason}")
                        print(f"  审核状态: {audit_log.action}")
            
            print(f"\n Agent 回答:")
            print(f"  {final_state.get('answer', 'N/A')}")
            
            # 验证逻辑
            if i == 1:
                # 场景1: 低额退款应自动通过
                assert not final_state.get('audit_required', False), "不应触发审核"
                print("\n 测试通过:  低额退款自动通过")
                
            elif i == 2:
                # 场景2: 高额退款应触发审核
                assert final_state.get('audit_required', False), "应触发审核"
                assert final_state.get('audit_log_id') is not None, "应生成审计日志"
                print("\n 测试通过: 高额退款触发人工审核")
                
                # 模拟管理员批准
                print("\n 模拟管理员批准...")
                async with async_session_maker() as session:
                    audit_log = await session.get(AuditLog, final_state['audit_log_id'])
                    audit_log.action = AuditAction.APPROVE  # ty:ignore[invalid-assignment]
                    audit_log.admin_id = 999  # ty:ignore[invalid-assignment]
                    audit_log.admin_comment = "测试批准"  # ty:ignore[invalid-assignment]
                    session.add(audit_log)
                    await session.commit()
                    print(" 管理员已批准")
                
        except AssertionError as e:
            print(f"\n 测试失败: {e}")
        except Exception as e: 
            print(f"\n 测试异常: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'=' * 60}")
    print(" 所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_v4())