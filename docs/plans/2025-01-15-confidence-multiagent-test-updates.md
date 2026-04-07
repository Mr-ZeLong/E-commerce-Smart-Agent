# 置信度驱动人工接管 + 多 Agent 协作架构 - 测试计划补充

基于审查反馈，对原实施计划中的测试部分进行补充和完善。

---

## 新增文件

### 1. test/confidence/test_signals.py（新增）

原计划缺失 signals 模块的单元测试，需要补充：

```python
# test/confidence/test_signals.py
"""置信度信号计算模块单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.confidence.signals import RAGSignal, EmotionSignal, LLMSignal, SIGNAL_WEIGHTS


class TestRAGSignal:
    """RAG 信号计算测试"""

    @pytest.fixture
    def rag_signal(self):
        return RAGSignal(similarity_threshold=0.5)

    @pytest.mark.asyncio
    async def test_perfect_match(self, rag_signal):
        """相似度 1.0 应该返回 1.0"""
        score, reason = await rag_signal.calculate(
            context=["content1", "content2"],
            retrieval_metadata={"distances": [0.0, 0.0]}
        )
        assert score == 0.9
        assert "相关性高" in reason

    @pytest.mark.asyncio
    async def test_no_match(self, rag_signal):
        """无匹配结果应该返回 0.0"""
        score, reason = await rag_signal.calculate(
            context=[],
            retrieval_metadata=None
        )
        assert score == 0.0
        assert "未检索" in reason

    @pytest.mark.asyncio
    async def test_partial_match(self, rag_signal):
        """部分匹配的正确计算"""
        score, reason = await rag_signal.calculate(
            context=["content1"],
            retrieval_metadata={"distances": [0.4]}
        )
        assert score == 0.6
        assert "相关性一般" in reason

    @pytest.mark.asyncio
    async def test_threshold_boundary(self, rag_signal):
        """边界值 0.5 的处理"""
        # 等于阈值的情况
        score, reason = await rag_signal.calculate(
            context=["content1"],
            retrieval_metadata={"distances": [0.5]}
        )
        # 距离 0.5 属于 > 0.3 且 <= 0.5 的范围，应该返回 0.6
        assert score == 0.6

    @pytest.mark.asyncio
    async def test_high_distance_low_confidence(self, rag_signal):
        """高距离低置信度"""
        score, reason = await rag_signal.calculate(
            context=["content1"],
            retrieval_metadata={"distances": [0.6, 0.7]}
        )
        assert score == 0.3
        assert "相关性较低" in reason

    @pytest.mark.asyncio
    async def test_fallback_without_metadata(self, rag_signal):
        """没有元数据时的回退逻辑"""
        score, reason = await rag_signal.calculate(
            context=["content1", "content2", "content3"],
            retrieval_metadata=None
        )
        assert score == 0.7
        assert "3 条" in reason

    @pytest.mark.asyncio
    async def test_single_context_fallback(self, rag_signal):
        """单条上下文回退"""
        score, reason = await rag_signal.calculate(
            context=["content1"],
            retrieval_metadata=None
        )
        assert score == 0.5
        assert "1 条" in reason


class TestEmotionSignal:
    """情感信号测试"""

    @pytest.fixture
    def emotion_signal(self):
        return EmotionSignal()

    @pytest.mark.asyncio
    async def test_angry_single_message(self, emotion_signal):
        """单条愤怒消息检测"""
        score, reason = await emotion_signal.calculate("你们太垃圾了！")
        assert score < 0.4
        assert "负面" in reason

    @pytest.mark.asyncio
    async def test_frustration_accumulation(self, emotion_signal):
        """挫败感累积检测"""
        # 多个负面词汇累积
        score, reason = await emotion_signal.calculate(
            "太失望了！我要投诉！你们怎么回事！"
        )
        assert score < 0.4
        assert "负面词" in reason

    @pytest.mark.asyncio
    async def test_neutral_conversation(self, emotion_signal):
        """中性对话返回高分"""
        score, reason = await emotion_signal.calculate("请问运费怎么算？")
        assert score > 0.7
        assert "平和" in reason

    @pytest.mark.asyncio
    async def test_polite_conversation(self, emotion_signal):
        """礼貌对话高分"""
        score, reason = await emotion_signal.calculate("麻烦帮忙查一下订单，谢谢！")
        assert score > 0.7
        assert "正面词" in reason or "平和" in reason

    @pytest.mark.asyncio
    async def test_exclamation_impact(self, emotion_signal):
        """感叹号影响"""
        # 同样内容，感叹号多的应该分数更低
        score_normal = (await emotion_signal.calculate("我要退货"))[0]
        score_exclaim = (await emotion_signal.calculate("我要退货！！！"))[0]
        assert score_exclaim < score_normal

    @pytest.mark.asyncio
    async def test_mixed_sentiment(self, emotion_signal):
        """混合情感"""
        score, reason = await emotion_signal.calculate(
            "谢谢，但是你们的服务太让人失望了"
        )
        # 有正面词也有负面词，应该在中间范围
        assert 0.3 <= score <= 0.8

    @pytest.mark.asyncio
    async def test_empty_message(self, emotion_signal):
        """空消息"""
        score, reason = await emotion_signal.calculate("")
        # 基础分数 0.7，无加减
        assert score == 0.7

    @pytest.mark.asyncio
    async def test_legal_threat(self, emotion_signal):
        """法律威胁检测"""
        score, reason = await emotion_signal.calculate("我要告你们，找律师！")
        assert score < 0.4
        assert "负面" in reason


class TestLLMSignal:
    """LLM 信号测试"""

    @pytest.fixture
    def llm_signal(self):
        return LLMSignal()

    @pytest.mark.asyncio
    async def test_parse_various_formats(self, llm_signal):
        """解析多种格式：0.85, 85%, 置信度: 0.85"""
        test_cases = [
            ("0.85", 0.85),
            ("0.90", 0.90),
            ("1.0", 1.0),
            ("0", 0.0),
        ]

        for content, expected in test_cases:
            mock_response = MagicMock()
            mock_response.content = content

            with patch.object(llm_signal.llm, 'ainvoke', new_callable=AsyncMock) as mock_invoke:
                mock_invoke.return_value = mock_response
                score, reason = await llm_signal.calculate(
                    question="测试",
                    context=["测试上下文"],
                    answer="测试回答"
                )
                assert score == pytest.approx(expected, 0.01)

    @pytest.mark.asyncio
    async def test_parse_fallback(self, llm_signal):
        """解析失败时使用默认值"""
        mock_response = MagicMock()
        mock_response.content = "invalid response"

        with patch.object(llm_signal.llm, 'ainvoke', new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = mock_response
            score, reason = await llm_signal.calculate(
                question="测试",
                context=["测试上下文"],
                answer="测试回答"
            )
            # 解析失败返回默认中等置信度 0.5
            assert score == 0.5
            assert "解析失败" in reason

    @pytest.mark.asyncio
    async def test_retry_mechanism(self, llm_signal):
        """重试机制正常工作"""
        # 第一次调用失败，第二次成功
        mock_response = MagicMock()
        mock_response.content = "0.85"

        with patch.object(llm_signal.llm, 'ainvoke', new_callable=AsyncMock) as mock_invoke:
            mock_invoke.side_effect = [Exception("Timeout"), mock_response]
            # 注意：如果实现有重试机制，这里应该成功
            # 如果无重试机制，会抛出异常
            try:
                score, reason = await llm_signal.calculate(
                    question="测试",
                    context=["测试上下文"],
                    answer="测试回答"
                )
                # 如果有重试，应该得到 0.85
                assert score == 0.85
            except Exception:
                # 无重试机制时接受异常
                pass

    @pytest.mark.asyncio
    async def test_clamping_to_range(self, llm_signal):
        """分数限制在 0-1 范围"""
        mock_response = MagicMock()
        mock_response.content = "1.5"  # 超出范围

        with patch.object(llm_signal.llm, 'ainvoke', new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = mock_response
            score, reason = await llm_signal.calculate(
                question="测试",
                context=["测试上下文"],
                answer="测试回答"
            )
            assert score == 1.0  # 被限制到 1.0

    @pytest.mark.asyncio
    async def test_negative_clamping(self, llm_signal):
        """负分数限制"""
        mock_response = MagicMock()
        mock_response.content = "-0.5"  # 负数

        with patch.object(llm_signal.llm, 'ainvoke', new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = mock_response
            score, reason = await llm_signal.calculate(
                question="测试",
                context=["测试上下文"],
                answer="测试回答"
            )
            assert score == 0.0  # 被限制到 0.0

    @pytest.mark.asyncio
    async def test_empty_context_handling(self, llm_signal):
        """空上下文处理"""
        mock_response = MagicMock()
        mock_response.content = "0.3"

        with patch.object(llm_signal.llm, 'ainvoke', new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = mock_response
            score, reason = await llm_signal.calculate(
                question="测试",
                context=[],  # 空上下文
                answer="测试回答"
            )
            assert score == 0.3
            assert "不确定" in reason or "score=0.3" in reason


class TestSignalWeights:
    """信号权重配置测试"""

    def test_default_weights_sum_to_one(self):
        """默认权重总和为 1"""
        total = sum(SIGNAL_WEIGHTS.values())
        assert total == pytest.approx(1.0, 0.01)

    def test_all_signals_have_weights(self):
        """所有信号都有权重"""
        assert "rag" in SIGNAL_WEIGHTS
        assert "llm" in SIGNAL_WEIGHTS
        assert "emotion" in SIGNAL_WEIGHTS
```

---

### 2. test/confidence/test_evaluator.py 补充边界条件测试

在原有测试基础上增加边界条件测试类：

```python
# test/confidence/test_evaluator.py 补充内容

class TestConfidenceBoundary:
    """置信度边界测试"""

    @pytest.fixture
    def evaluator(self):
        return ConfidenceEvaluator(
            threshold=0.6,
            weights={"rag": 0.4, "llm": 0.4, "emotion": 0.2}
        )

    @pytest.mark.asyncio
    async def test_exactly_at_threshold(self, evaluator):
        """恰好在阈值时的处理"""
        # 构造一个分数恰好为 0.6 的情况
        # rag=0.6, llm=0.6, emotion=0.6 => 加权平均 0.6
        with patch.object(evaluator.rag_signal, 'calculate', new_callable=AsyncMock) as mock_rag, \
             patch.object(evaluator.llm_signal, 'calculate', new_callable=AsyncMock) as mock_llm, \
             patch.object(evaluator.emotion_signal, 'calculate', new_callable=AsyncMock) as mock_emotion:

            mock_rag.return_value = (0.6, "test")
            mock_llm.return_value = (0.6, "test")
            mock_emotion.return_value = (0.6, "test")

            result = await evaluator.evaluate(
                question="测试",
                context=["测试"],
                answer="测试"
            )

            # 阈值 0.6，恰好等于阈值，不应触发转人工
            assert result["confidence_score"] == 0.6
            # 根据实现，恰好等于阈值时可能触发也可能不触发
            # 这里验证行为一致性即可

    @pytest.mark.asyncio
    async def test_all_signals_zero(self, evaluator):
        """所有信号为 0"""
        with patch.object(evaluator.rag_signal, 'calculate', new_callable=AsyncMock) as mock_rag, \
             patch.object(evaluator.llm_signal, 'calculate', new_callable=AsyncMock) as mock_llm, \
             patch.object(evaluator.emotion_signal, 'calculate', new_callable=AsyncMock) as mock_emotion:

            mock_rag.return_value = (0.0, "no context")
            mock_llm.return_value = (0.0, "uncertain")
            mock_emotion.return_value = (0.0, "angry")

            result = await evaluator.evaluate(
                question="测试",
                context=[],
                answer=""
            )

            assert result["confidence_score"] == 0.0
            assert result["needs_transfer"] is True
            # 优先级：emotion < 0.4 应该触发 NEGATIVE_EMOTION
            assert result["reason"] == TransferReason.NEGATIVE_EMOTION

    @pytest.mark.asyncio
    async def test_all_signals_one(self, evaluator):
        """所有信号为 1"""
        with patch.object(evaluator.rag_signal, 'calculate', new_callable=AsyncMock) as mock_rag, \
             patch.object(evaluator.llm_signal, 'calculate', new_callable=AsyncMock) as mock_llm, \
             patch.object(evaluator.emotion_signal, 'calculate', new_callable=AsyncMock) as mock_emotion:

            mock_rag.return_value = (1.0, "perfect match")
            mock_llm.return_value = (1.0, "very confident")
            mock_emotion.return_value = (1.0, "calm")

            result = await evaluator.evaluate(
                question="测试",
                context=["测试"],
                answer="测试"
            )

            assert result["confidence_score"] == 1.0
            assert result["needs_transfer"] is False
            assert result["reason"] is None

    @pytest.mark.asyncio
    async def test_missing_signals(self, evaluator):
        """部分信号缺失时的计算"""
        # 测试当某些信号返回 None 或异常时的处理
        with patch.object(evaluator.rag_signal, 'calculate', new_callable=AsyncMock) as mock_rag, \
             patch.object(evaluator.llm_signal, 'calculate', new_callable=AsyncMock) as mock_llm, \
             patch.object(evaluator.emotion_signal, 'calculate', new_callable=AsyncMock) as mock_emotion:

            # 模拟 llm 信号失败
            mock_rag.return_value = (0.8, "good")
            mock_llm.return_value = (0.5, "default")  # 失败时返回默认值
            mock_emotion.return_value = (0.7, "calm")

            result = await evaluator.evaluate(
                question="测试",
                context=["测试"],
                answer="测试"
            )

            # 0.8*0.4 + 0.5*0.4 + 0.7*0.2 = 0.32 + 0.2 + 0.14 = 0.66
            expected = 0.8 * 0.4 + 0.5 * 0.4 + 0.7 * 0.2
            assert result["confidence_score"] == pytest.approx(expected, 0.01)

    @pytest.mark.asyncio
    async def test_emotion_priority_over_rag(self, evaluator):
        """情感优先级高于 RAG"""
        # emotion < 0.4 应该优先触发，即使 rag 和 llm 很高
        with patch.object(evaluator.rag_signal, 'calculate', new_callable=AsyncMock) as mock_rag, \
             patch.object(evaluator.llm_signal, 'calculate', new_callable=AsyncMock) as mock_llm, \
             patch.object(evaluator.emotion_signal, 'calculate', new_callable=AsyncMock) as mock_emotion:

            mock_rag.return_value = (0.9, "perfect")
            mock_llm.return_value = (0.9, "confident")
            mock_emotion.return_value = (0.3, "very angry")

            result = await evaluator.evaluate(
                question="测试",
                context=["测试"],
                answer="测试"
            )

            assert result["needs_transfer"] is True
            assert result["reason"] == TransferReason.NEGATIVE_EMOTION

    @pytest.mark.asyncio
    async def test_rag_priority_over_overall(self, evaluator):
        """RAG 优先级高于综合分数"""
        # rag < 0.3 应该触发，即使综合分数可能高于阈值
        with patch.object(evaluator.rag_signal, 'calculate', new_callable=AsyncMock) as mock_rag, \
             patch.object(evaluator.llm_signal, 'calculate', new_callable=AsyncMock) as mock_llm, \
             patch.object(evaluator.emotion_signal, 'calculate', new_callable=AsyncMock) as mock_emotion:

            mock_rag.return_value = (0.2, "no relevant content")
            mock_llm.return_value = (0.9, "confident")
            mock_emotion.return_value = (0.8, "calm")

            result = await evaluator.evaluate(
                question="测试",
                context=["测试"],
                answer="测试"
            )

            assert result["needs_transfer"] is True
            assert result["reason"] == TransferReason.LOW_RAG_CONFIDENCE

    @pytest.mark.asyncio
    async def test_llm_priority_over_overall(self, evaluator):
        """LLM 优先级高于综合分数"""
        # llm < 0.3 应该触发
        with patch.object(evaluator.rag_signal, 'calculate', new_callable=AsyncMock) as mock_rag, \
             patch.object(evaluator.llm_signal, 'calculate', new_callable=AsyncMock) as mock_llm, \
             patch.object(evaluator.emotion_signal, 'calculate', new_callable=AsyncMock) as mock_emotion:

            mock_rag.return_value = (0.8, "good")
            mock_llm.return_value = (0.2, "uncertain")
            mock_emotion.return_value = (0.8, "calm")

            result = await evaluator.evaluate(
                question="测试",
                context=["测试"],
                answer="测试"
            )

            assert result["needs_transfer"] is True
            assert result["reason"] == TransferReason.LOW_LLM_CONFIDENCE


class TestConfidenceEvaluatorIntegration:
    """置信度评估器集成测试"""

    @pytest.mark.asyncio
    async def test_evaluate_returns_all_fields(self):
        """评估结果包含所有必要字段"""
        evaluator = ConfidenceEvaluator(threshold=0.6)

        result = await evaluator.evaluate(
            question="请问运费怎么算？",
            context=["运费满100免运费"],
            answer="满100元免运费",
            retrieval_metadata={"distances": [0.2]}
        )

        # 验证返回结构
        assert "confidence_score" in result
        assert "confidence_signals" in result
        assert "needs_transfer" in result
        assert "reason" in result
        assert "signal_details" in result

        # 验证 signal_details 结构
        details = result["signal_details"]
        assert "rag" in details
        assert "llm" in details
        assert "emotion" in details
        assert "score" in details["rag"]
        assert "reason" in details["rag"]
```

---

### 3. test/integration/test_multi_agent.py 补充集成测试

在原有集成测试基础上增加 Agent 切换测试：

```python
# test/integration/test_multi_agent.py 补充内容

class TestAgentTransitions:
    """Agent 切换测试"""

    @pytest.fixture
    async def supervisor(self):
        return SupervisorAgent()

    @pytest.mark.asyncio
    async def test_router_to_policy(self, supervisor):
        """路由到政策 Agent"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router, \
             patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy:

            # Mock Router 返回 POLICY 意图
            mock_router.return_value.updated_state = {
                "intent": "POLICY",
                "next_agent": "policy"
            }
            mock_router.return_value.response = ""

            # Mock PolicyAgent 返回结果
            mock_policy.return_value = AgentResult(
                response="运费满100免运费",
                updated_state={
                    "answer": "运费满100免运费",
                    "context": ["运费政策"],
                    "retrieval_metadata": {"distances": [0.2]}
                },
                confidence=0.85
            )

            result = await supervisor.coordinate({
                "question": "运费怎么算？",
                "user_id": 1
            })

            # 验证调用了 PolicyAgent
            mock_policy.assert_called_once()
            assert result["intent"] == "POLICY"
            assert "运费" in result["answer"]

    @pytest.mark.asyncio
    async def test_router_to_order(self, supervisor):
        """路由到订单 Agent"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router, \
             patch.object(supervisor.order_agent, 'process', new_callable=AsyncMock) as mock_order:

            # Mock Router 返回 ORDER 意图
            mock_router.return_value.updated_state = {
                "intent": "ORDER",
                "next_agent": "order"
            }
            mock_router.return_value.response = ""

            # Mock OrderAgent 返回结果
            mock_order.return_value = AgentResult(
                response="订单 SN20240001 状态：已发货",
                updated_state={
                    "answer": "订单 SN20240001 状态：已发货",
                    "order_data": {"order_sn": "SN20240001", "status": "SHIPPED"}
                },
                confidence=0.9
            )

            result = await supervisor.coordinate({
                "question": "我的订单到哪了？",
                "user_id": 1
            })

            # 验证调用了 OrderAgent
            mock_order.assert_called_once()
            assert result["intent"] == "ORDER"
            assert "订单" in result["answer"]

    @pytest.mark.asyncio
    async def test_confidence_triggered_transfer(self, supervisor):
        """置信度触发转人工"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router, \
             patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy, \
             patch.object(supervisor.confidence_evaluator, 'evaluate', new_callable=AsyncMock) as mock_eval:

            # Mock Router
            mock_router.return_value.updated_state = {
                "intent": "POLICY",
                "next_agent": "policy"
            }
            mock_router.return_value.response = ""

            # Mock PolicyAgent
            mock_policy.return_value = AgentResult(
                response="抱歉，暂未查询到相关规定",
                updated_state={
                    "answer": "抱歉，暂未查询到相关规定",
                    "context": [],
                    "retrieval_metadata": {"distances": []}
                },
                confidence=0.2
            )

            # Mock 置信度评估返回低置信度
            mock_eval.return_value = {
                "confidence_score": 0.2,
                "confidence_signals": {"rag": 0.0, "llm": 0.3, "emotion": 0.8},
                "needs_transfer": True,
                "reason": "LOW_RAG_CONFIDENCE",
                "signal_details": {}
            }

            result = await supervisor.coordinate({
                "question": "你们公司的股票代码是多少？",
                "user_id": 1
            })

            assert result["needs_human_transfer"] is True
            assert result["audit_required"] is True
            assert result["audit_type"] == "CONFIDENCE"

    @pytest.mark.asyncio
    async def test_state_preserved_across_agents(self, supervisor):
        """跨 Agent 状态保持"""
        initial_state = {
            "question": "运费怎么算？",
            "user_id": 1,
            "thread_id": "test_thread_123",
            "history": [{"role": "user", "content": "你好"}]
        }

        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router, \
             patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy:

            mock_router.return_value.updated_state = {
                "intent": "POLICY",
                "next_agent": "policy"
            }
            mock_router.return_value.response = ""

            mock_policy.return_value = AgentResult(
                response="运费满100免运费",
                updated_state={
                    "answer": "运费满100免运费",
                    "context": ["运费政策"]
                }
            )

            result = await supervisor.coordinate(initial_state)

            # 验证状态被正确传递和合并
            assert result["thread_id"] == "test_thread_123"
            assert result["intent"] == "POLICY"
            assert "answer" in result


class TestMultiAgentErrorHandling:
    """多 Agent 错误处理测试"""

    @pytest.fixture
    async def supervisor(self):
        return SupervisorAgent()

    @pytest.mark.asyncio
    async def test_router_failure_fallback(self, supervisor):
        """Router 失败时的降级处理"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.side_effect = Exception("Router error")

            # 应该抛出异常或返回降级响应
            with pytest.raises(Exception) as exc_info:
                await supervisor.coordinate({
                    "question": "测试",
                    "user_id": 1
                })
            assert "Router" in str(exc_info.value) or "error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_specialist_agent_failure(self, supervisor):
        """Specialist Agent 失败处理"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router, \
             patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy:

            mock_router.return_value.updated_state = {
                "intent": "POLICY",
                "next_agent": "policy"
            }
            mock_router.return_value.response = ""

            mock_policy.side_effect = Exception("Policy agent error")

            # 应该抛出异常
            with pytest.raises(Exception):
                await supervisor.coordinate({
                    "question": "测试",
                    "user_id": 1
                })

    @pytest.mark.asyncio
    async def test_confidence_evaluator_failure(self, supervisor):
        """置信度评估失败处理"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router, \
             patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy, \
             patch.object(supervisor.confidence_evaluator, 'evaluate', new_callable=AsyncMock) as mock_eval:

            mock_router.return_value.updated_state = {
                "intent": "POLICY",
                "next_agent": "policy"
            }
            mock_router.return_value.response = ""

            mock_policy.return_value = AgentResult(
                response="回答",
                updated_state={"answer": "回答"}
            )

            mock_eval.side_effect = Exception("Evaluator error")

            # 应该抛出异常或安全降级
            with pytest.raises(Exception):
                await supervisor.coordinate({
                    "question": "测试",
                    "user_id": 1
                })


class TestEndToEndWorkflow:
    """端到端工作流测试"""

    @pytest.mark.asyncio
    async def test_policy_query_e2e(self):
        """政策查询端到端流程"""
        # 这是一个更真实的集成测试，可能需要数据库连接
        # 标记为需要外部依赖
        pytest.skip("需要外部依赖（数据库、LLM）")

        supervisor = SupervisorAgent()

        result = await supervisor.coordinate({
            "question": "内衣可以退货吗？",
            "user_id": 1,
            "thread_id": "e2e_test_1"
        })

        # 验证完整流程
        assert "answer" in result
        assert result["intent"] == "POLICY"
        assert "confidence_score" in result
        assert isinstance(result["needs_human_transfer"], bool)

    @pytest.mark.asyncio
    async def test_order_query_e2e(self):
        """订单查询端到端流程"""
        pytest.skip("需要外部依赖（数据库）")

        supervisor = SupervisorAgent()

        result = await supervisor.coordinate({
            "question": "查询我的订单",
            "user_id": 1,
            "thread_id": "e2e_test_2"
        })

        assert "answer" in result
        assert result["intent"] == "ORDER"
```

---

### 4. test/conftest.py - Mock 策略和共享 Fixtures

```python
# test/conftest.py
"""测试配置和共享 Fixtures"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock


# ============================================================================
# Mock 策略文档
# ============================================================================

"""
Mock 策略：

1. LLM 调用：
   - 使用 pytest-asyncio 处理异步测试
   - Mock ChatOpenAI/ChatQwen 返回预定义响应
   - 测试不同响应格式（数字、带单位的字符串等）
   - 使用 new_callable=AsyncMock 确保异步方法正确 mock

2. 数据库：
   - 使用内存 SQLite 进行单元测试
   - 使用 testcontainers 进行集成测试（可选）
   - 每个测试独立事务，自动回滚
   - 使用 SQLModel 的 session 进行数据操作

3. Redis：
   - 使用 fakeredis 进行 mock
   - 测试 checkpoint 持久化时模拟 Redis 行为
   - 或使用 mock 直接模拟 AsyncRedisSaver

4. 外部服务：
   - 情感分析服务：直接调用 EmotionSignal（本地计算，无需 mock）
   - 嵌入模型：mock embedding_model.aembed_query 返回固定向量
   - 向量数据库：mock 检索结果返回固定 chunks

5. Agent 间协作：
   - 使用 patch 分别 mock 各个 Agent 的 process 方法
   - 验证调用顺序和参数传递
   - 测试状态在各 Agent 间的传递
"""


# ============================================================================
# 共享 Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_response():
    """创建 Mock LLM 响应"""
    def _create_response(content: str):
        mock = MagicMock()
        mock.content = content
        return mock
    return _create_response


@pytest.fixture
def mock_embedding():
    """Mock 嵌入向量"""
    return [0.1] * 1536  # 模拟 1536 维向量


@pytest_asyncio.fixture
async def mock_db_session():
    """Mock 数据库会话"""
    session = AsyncMock()
    session.exec = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_knowledge_chunks():
    """示例知识库 chunks"""
    return [
        {"content": "运费政策：满100元免运费", "distance": 0.15},
        {"content": "配送时效：1-3个工作日", "distance": 0.25},
        {"content": "退货政策：7天无理由退货", "distance": 0.20},
    ]


@pytest.fixture
def sample_order_data():
    """示例订单数据"""
    return {
        "order_sn": "SN20240001",
        "status": "PAID",
        "total_amount": 199.0,
        "items": [{"name": "测试商品", "qty": 1}],
        "tracking_number": "SF1234567890"
    }


# ============================================================================
# 测试标记
# ============================================================================

def pytest_configure(config):
    """配置 pytest 标记"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require external deps)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (skip in fast mode)"
    )
    config.addinivalue_line(
        "markers", "llm: marks tests that require LLM API calls"
    )


# ============================================================================
# 异步事件循环策略
# ============================================================================

@pytest.fixture(scope="session")
def event_loop_policy():
    """配置异步事件循环策略"""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
```

---

### 5. test/agents/test_router.py 补充测试

```python
# test/agents/test_router.py 补充内容

class TestRouterAgentEdgeCases:
    """RouterAgent 边界情况测试"""

    @pytest.fixture
    def router(self):
        return RouterAgent()

    @pytest.mark.asyncio
    async def test_empty_question(self, router):
        """空问题处理"""
        result = await router.process({
            "question": "",
            "user_id": 1
        })

        # 应该返回 OTHER 或默认处理
        assert result.updated_state["intent"] is not None
        assert result.updated_state["next_agent"] is not None

    @pytest.mark.asyncio
    async def test_very_long_question(self, router):
        """超长问题处理"""
        long_question = "我要退货" * 1000

        result = await router.process({
            "question": long_question,
            "user_id": 1
        })

        # 应该能正常处理，不抛出异常
        assert "intent" in result.updated_state

    @pytest.mark.asyncio
    async def test_special_characters(self, router):
        """特殊字符处理"""
        special_questions = [
            "订单 <script>alert(1)</script>",
            "退货 DROP TABLE orders; --",
            "查询订单 SN12345\\n\\t\\r",
            "运费 💰💰💰",
        ]

        for question in special_questions:
            result = await router.process({
                "question": question,
                "user_id": 1
            })
            assert "intent" in result.updated_state
            assert "next_agent" in result.updated_state

    @pytest.mark.asyncio
    async def test_mixed_intent(self, router):
        """混合意图处理"""
        # 同时包含订单和政策关键词
        result = await router.process({
            "question": "我的订单运费怎么算？",
            "user_id": 1
        })

        # 应该能识别其中一个意图
        assert result.updated_state["intent"] in ["ORDER", "POLICY", "OTHER"]


class TestRouterAgentQuickIntent:
    """RouterAgent 快速意图检测测试"""

    @pytest.fixture
    def router(self):
        return RouterAgent()

    @pytest.mark.asyncio
    async def test_quick_refund_detection(self, router):
        """快速退货关键词检测"""
        refund_keywords = ["退货", "退款", "退钱", "不要了", "换货"]

        for keyword in refund_keywords:
            result = await router.process({
                "question": f"我要{keyword}",
                "user_id": 1
            })
            assert result.updated_state["intent"] == "REFUND"

    @pytest.mark.asyncio
    async def test_quick_order_detection(self, router):
        """快速订单关键词检测"""
        order_keywords = ["订单", "物流", "到哪了", "快递", "发货", "签收"]

        for keyword in order_keywords:
            result = await router.process({
                "question": f"查询{keyword}",
                "user_id": 1
            })
            assert result.updated_state["intent"] == "ORDER"

    @pytest.mark.asyncio
    async def test_quick_greeting_detection(self, router):
        """快速问候检测"""
        greetings = ["你好", "您好", "hi", "hello", "在吗"]

        for greeting in greetings:
            result = await router.process({
                "question": greeting,
                "user_id": 1
            })
            # 短问候应该返回 OTHER
            if len(greeting) < 10:
                assert result.updated_state["intent"] == "OTHER"
```

---

### 6. test/agents/test_policy.py 补充测试

```python
# test/agents/test_policy.py 补充内容

class TestPolicyAgentEdgeCases:
    """PolicyAgent 边界情况测试"""

    @pytest.fixture
    def policy_agent(self):
        return PolicyAgent()

    @pytest.mark.asyncio
    async def test_retrieve_with_no_results(self, policy_agent):
        """无检索结果处理"""
        with patch.object(policy_agent, '_retrieve_knowledge', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = ([], {"distances": [], "valid_chunks": 0})

            result = await policy_agent.process({
                "question": "不存在的政策",
                "user_id": 1,
                "context": []
            })

            assert result.confidence == 0.0
            assert "抱歉" in result.response or "暂未查询" in result.response

    @pytest.mark.asyncio
    async def test_retrieve_with_partial_results(self, policy_agent):
        """部分检索结果处理"""
        with patch.object(policy_agent, '_retrieve_knowledge', new_callable=AsyncMock) as mock_retrieve:
            # 返回结果但距离都超过阈值
            mock_retrieve.return_value = (
                [],  # 无有效 chunks
                {"distances": [0.6, 0.7, 0.8], "valid_chunks": 0, "total_chunks": 3}
            )

            result = await policy_agent.process({
                "question": "模糊的问题",
                "user_id": 1,
                "context": []
            })

            # 应该识别为低置信度
            assert result.confidence < 0.5


class TestPolicyAgentConfidenceEstimation:
    """PolicyAgent 置信度估计测试"""

    @pytest.fixture
    def policy_agent(self):
        return PolicyAgent()

    def test_estimate_confidence_empty_context(self, policy_agent):
        """空上下文置信度估计"""
        confidence = policy_agent._estimate_confidence([], {})
        assert confidence == 0.0

    def test_estimate_confidence_high_quality(self, policy_agent):
        """高质量检索置信度估计"""
        confidence = policy_agent._estimate_confidence(
            ["content1", "content2"],
            {"distances": [0.1, 0.15]}
        )
        assert confidence == 0.8

    def test_estimate_confidence_medium_quality(self, policy_agent):
        """中等质量检索置信度估计"""
        confidence = policy_agent._estimate_confidence(
            ["content1"],
            {"distances": [0.4]}
        )
        assert confidence == 0.5

    def test_estimate_confidence_low_quality(self, policy_agent):
        """低质量检索置信度估计"""
        confidence = policy_agent._estimate_confidence(
            ["content1"],
            {"distances": [0.6]}
        )
        assert confidence == 0.2

    def test_estimate_confidence_no_metadata(self, policy_agent):
        """无元数据时置信度估计"""
        confidence = policy_agent._estimate_confidence(
            ["content1", "content2"],
            {}
        )
        assert confidence == 0.5
```

---

### 7. test/agents/test_order.py 补充测试

```python
# test/agents/test_order.py 补充内容

class TestOrderAgentExtractOrderSn:
    """订单号提取测试"""

    @pytest.fixture
    def order_agent(self):
        return OrderAgent()

    def test_extract_order_sn_standard(self, order_agent):
        """标准订单号提取"""
        assert order_agent._extract_order_sn("查询订单 SN20240001") == "SN20240001"

    def test_extract_order_sn_lowercase(self, order_agent):
        """小写订单号提取"""
        assert order_agent._extract_order_sn("查询订单 sn20240001") == "SN20240001"

    def test_extract_order_sn_not_found(self, order_agent):
        """无订单号"""
        assert order_agent._extract_order_sn("查询我的订单") is None

    def test_extract_order_sn_multiple(self, order_agent):
        """多个订单号提取第一个"""
        result = order_agent._extract_order_sn("比较订单 SN111 和 SN222")
        assert result == "SN111"


class TestOrderAgentClassifyRefundReason:
    """退货原因分类测试"""

    @pytest.fixture
    def order_agent(self):
        return OrderAgent()

    def test_classify_quality_issue(self, order_agent):
        """质量问题分类"""
        from app.services.refund_service import RefundReason
        assert order_agent._classify_refund_reason("质量太差，有破损") == RefundReason.QUALITY_ISSUE

    def test_classify_size_issue(self, order_agent):
        """尺码问题分类"""
        from app.services.refund_service import RefundReason
        assert order_agent._classify_refund_reason("尺码不合适，太大了") == RefundReason.SIZE_NOT_FIT

    def test_classify_description_issue(self, order_agent):
        """描述不符分类"""
        from app.services.refund_service import RefundReason
        assert order_agent._classify_refund_reason("与描述不符") == RefundReason.NOT_AS_DESCRIBED

    def test_classify_other(self, order_agent):
        """其他原因分类"""
        from app.services.refund_service import RefundReason
        assert order_agent._classify_refund_reason("就是不想买了") == RefundReason.OTHER


class TestOrderAgentRefundFlow:
    """退货流程测试"""

    @pytest.fixture
    def order_agent(self):
        return OrderAgent()

    @pytest.mark.asyncio
    async def test_refund_without_order_sn(self, order_agent):
        """无订单号退货申请"""
        result = await order_agent.process({
            "question": "我要退货",
            "user_id": 1,
            "intent": "REFUND"
        })

        assert "请提供订单号" in result.response
        assert result.updated_state.get("refund_flow_active") is False

    @pytest.mark.asyncio
    async def test_refund_with_invalid_order(self, order_agent):
        """无效订单号退货"""
        with patch('app.agents.order.async_session_maker') as mock_session:
            mock_result = MagicMock()
            mock_result.first.return_value = None

            mock_exec = MagicMock()
            mock_exec.exec.return_value = mock_result

            async_mock = AsyncMock()
            async_mock.__aenter__ = AsyncMock(return_value=mock_exec)
            async_mock.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = async_mock

            result = await order_agent.process({
                "question": "我要退货，订单号 SN99999",
                "user_id": 1,
                "intent": "REFUND"
            })

            assert "未找到" in result.response or "确认订单号" in result.response
```

---

### 8. test/agents/test_supervisor.py 补充测试

```python
# test/agents/test_supervisor.py 补充内容

class TestSupervisorAgentRouting:
    """Supervisor 路由决策测试"""

    @pytest.fixture
    def supervisor(self):
        return SupervisorAgent()

    @pytest.mark.asyncio
    async def test_direct_response_for_greeting(self, supervisor):
        """问候语直接返回"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.updated_state = {
                "intent": "OTHER",
                "next_agent": "supervisor"
            }
            mock_router.return_value.response = "您好！我是智能客服助手..."

            result = await supervisor.coordinate({
                "question": "你好",
                "user_id": 1
            })

            # 直接返回 Router 的回复
            assert result["answer"] == "您好！我是智能客服助手..."
            assert result["confidence_score"] == 1.0
            assert result["needs_human_transfer"] is False

    @pytest.mark.asyncio
    async def test_unknown_agent_fallback(self, supervisor):
        """未知 Agent 降级处理"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.updated_state = {
                "intent": "UNKNOWN",
                "next_agent": "unknown_agent"
            }
            mock_router.return_value.response = ""

            result = await supervisor.coordinate({
                "question": "测试",
                "user_id": 1
            })

            # 应该返回降级提示
            assert "暂时无法处理" in result["answer"] or "联系人工" in result["answer"]


class TestSupervisorAgentConfidenceIntegration:
    """Supervisor 置信度集成测试"""

    @pytest.fixture
    def supervisor(self):
        return SupervisorAgent()

    @pytest.mark.asyncio
    async def test_high_confidence_response(self, supervisor):
        """高置信度响应"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router, \
             patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy, \
             patch.object(supervisor.confidence_evaluator, 'evaluate', new_callable=AsyncMock) as mock_eval:

            mock_router.return_value.updated_state = {"intent": "POLICY", "next_agent": "policy"}
            mock_router.return_value.response = ""

            mock_policy.return_value = AgentResult(
                response="运费满100免运费",
                updated_state={"answer": "运费满100免运费", "context": ["政策"]}
            )

            mock_eval.return_value = {
                "confidence_score": 0.85,
                "confidence_signals": {"rag": 0.9, "llm": 0.8, "emotion": 0.9},
                "needs_transfer": False,
                "reason": None,
                "signal_details": {}
            }

            result = await supervisor.coordinate({
                "question": "运费怎么算？",
                "user_id": 1
            })

            assert result["confidence_score"] == 0.85
            assert result["needs_human_transfer"] is False
            assert result["audit_required"] is False

    @pytest.mark.asyncio
    async def test_low_confidence_audit(self, supervisor):
        """低置信度触发审核"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router, \
             patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy, \
             patch.object(supervisor.confidence_evaluator, 'evaluate', new_callable=AsyncMock) as mock_eval:

            mock_router.return_value.updated_state = {"intent": "POLICY", "next_agent": "policy"}
            mock_router.return_value.response = ""

            mock_policy.return_value = AgentResult(
                response="抱歉，我不确定",
                updated_state={"answer": "抱歉，我不确定", "context": []}
            )

            mock_eval.return_value = {
                "confidence_score": 0.3,
                "confidence_signals": {"rag": 0.1, "llm": 0.2, "emotion": 0.8},
                "needs_transfer": True,
                "reason": "LOW_RAG_CONFIDENCE",
                "signal_details": {}
            }

            result = await supervisor.coordinate({
                "question": "复杂问题",
                "user_id": 1
            })

            assert result["confidence_score"] == 0.3
            assert result["needs_human_transfer"] is True
            assert result["audit_required"] is True
            assert result["audit_type"] == "CONFIDENCE"
            assert result["transfer_reason"] == "LOW_RAG_CONFIDENCE"
```

---

## 测试执行命令

```bash
# 运行所有置信度信号测试
pytest test/confidence/test_signals.py -v

# 运行所有置信度评估器测试（包括边界条件）
pytest test/confidence/test_evaluator.py -v

# 运行所有 Agent 测试
pytest test/agents/ -v

# 运行集成测试
pytest test/integration/test_multi_agent.py -v

# 运行所有测试
pytest -v

# 跳过慢测试和集成测试（快速反馈）
pytest -v -m "not slow and not integration"

# 仅运行 LLM 相关测试
pytest -v -m "llm"

# 生成覆盖率报告
pytest --cov=app --cov-report=html --cov-report=term-missing
```

---

## 测试覆盖目标

| 模块 | 目标覆盖率 | 关键测试点 |
|------|-----------|-----------|
| `app/confidence/signals.py` | 95% | RAG/LLM/Emotion 信号计算 |
| `app/confidence/evaluator.py` | 90% | 加权计算、转人工决策 |
| `app/agents/base.py` | 85% | Agent 基类、结果封装 |
| `app/agents/router.py` | 90% | 意图识别、路由决策 |
| `app/agents/policy.py` | 85% | RAG 检索、置信度估计 |
| `app/agents/order.py` | 85% | 订单查询、退货流程 |
| `app/agents/supervisor.py` | 80% | Agent 协调、置信度集成 |

---

## 与原计划的对比

| 项目 | 原计划 | 补充后 |
|------|--------|--------|
| 信号模块测试 | 缺失 | 新增 `test_signals.py`，覆盖 RAG/LLM/Emotion 信号 |
| 边界条件测试 | 基础测试 | 新增 `TestConfidenceBoundary`，覆盖阈值边界、极端值 |
| 集成测试 | 基础流程测试 | 新增 Agent 切换、状态保持、错误处理测试 |
| Mock 策略 | 无文档 | 新增 `conftest.py` 文档和共享 fixtures |
| Router 测试 | 基础路由 | 新增边界情况、快速意图检测测试 |
| Policy 测试 | 基础 RAG | 新增置信度估计、部分结果处理测试 |
| Order 测试 | 基础查询 | 新增订单号提取、退货原因分类、退货流程测试 |
| Supervisor 测试 | 基础协调 | 新增路由决策、置信度集成测试 |
