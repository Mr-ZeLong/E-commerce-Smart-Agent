#!/usr/bin/env python3
"""Generate golden_dataset_v2.jsonl with 160 records across 8 dimensions."""

from __future__ import annotations

import json
import random
from pathlib import Path

# Seed for reproducibility
random.seed(42)

# Valid intent categories from app/intent/models.py
VALID_INTENTS = {
    "ORDER",
    "AFTER_SALES",
    "POLICY",
    "ACCOUNT",
    "PROMOTION",
    "PAYMENT",
    "LOGISTICS",
    "PRODUCT",
    "CART",
    "COMPLAINT",
    "OTHER",
}

# Valid audit levels
VALID_AUDIT_LEVELS = {"auto", "medium", "manual"}


def make_record(
    query: str,
    expected_intent: str,
    expected_slots: dict,
    expected_answer_fragment: str,
    expected_audit_level: str,
    dimension: str,
) -> dict:
    """Create a golden dataset record with validation."""
    if expected_intent not in VALID_INTENTS:
        raise ValueError(f"Invalid intent: {expected_intent}")
    if expected_audit_level not in VALID_AUDIT_LEVELS:
        raise ValueError(f"Invalid audit level: {expected_audit_level}")
    return {
        "query": query,
        "expected_intent": expected_intent,
        "expected_slots": expected_slots,
        "expected_answer_fragment": expected_answer_fragment,
        "expected_audit_level": expected_audit_level,
        "dimension": dimension,
    }


def generate_order_query_records() -> list[dict]:
    """Generate 30 order query records."""
    dimension = "order_query"
    records = [
        make_record("查一下我的订单", "ORDER", {}, "订单", "auto", dimension),
        make_record(
            "订单SN20240001状态", "ORDER", {"order_sn": "SN20240001"}, "订单", "auto", dimension
        ),
        make_record(
            "帮我看看订单SN20240002到哪了",
            "ORDER",
            {"order_sn": "SN20240002"},
            "物流",
            "auto",
            dimension,
        ),
        make_record("我的订单什么时候发货", "ORDER", {}, "发货", "medium", dimension),
        make_record(
            "订单号SN20240003的商品到了吗",
            "ORDER",
            {"order_sn": "SN20240003"},
            "订单",
            "auto",
            dimension,
        ),
        make_record(
            "我想取消订单SN20240004",
            "ORDER",
            {"order_sn": "SN20240004"},
            "取消",
            "medium",
            dimension,
        ),
        make_record(
            "修改订单SN20240005的收货地址",
            "ORDER",
            {"order_sn": "SN20240005"},
            "地址",
            "medium",
            dimension,
        ),
        make_record("查询最近的一笔订单", "ORDER", {}, "订单", "auto", dimension),
        make_record(
            "订单SN20240006为什么还没发货",
            "ORDER",
            {"order_sn": "SN20240006"},
            "发货",
            "medium",
            dimension,
        ),
        make_record("帮我查一下我在你们平台买的上一单", "ORDER", {}, "订单", "auto", dimension),
        make_record(
            "订单SN20240007可以合并发货吗",
            "ORDER",
            {"order_sn": "SN20240007"},
            "合并",
            "medium",
            dimension,
        ),
        make_record(
            "我想确认订单SN20240008的付款状态",
            "ORDER",
            {"order_sn": "SN20240008"},
            "付款",
            "auto",
            dimension,
        ),
        make_record("我的订单被拆分了请问怎么回事", "ORDER", {}, "拆分", "medium", dimension),
        make_record(
            "订单SN20240009的备注内容是什么",
            "ORDER",
            {"order_sn": "SN20240009"},
            "备注",
            "auto",
            dimension,
        ),
        make_record(
            "订单SN20240010怎么还没出库",
            "ORDER",
            {"order_sn": "SN20240010"},
            "出库",
            "medium",
            dimension,
        ),
        make_record(
            "查询订单SN20240011的历史记录",
            "ORDER",
            {"order_sn": "SN20240011"},
            "历史",
            "auto",
            dimension,
        ),
        make_record(
            "帮我看看订单SN20240012的详细信息",
            "ORDER",
            {"order_sn": "SN20240012"},
            "详细",
            "auto",
            dimension,
        ),
        make_record(
            "订单SN20240013的物流单号是什么",
            "ORDER",
            {"order_sn": "SN20240013"},
            "物流单号",
            "auto",
            dimension,
        ),
        make_record(
            "我的订单SN20240014可以开发票吗",
            "ORDER",
            {"order_sn": "SN20240014"},
            "发票",
            "medium",
            dimension,
        ),
        make_record(
            "订单SN20240015什么时候能到",
            "ORDER",
            {"order_sn": "SN20240015"},
            "送达",
            "auto",
            dimension,
        ),
        make_record(
            "查询订单SN20240016的退款进度",
            "ORDER",
            {"order_sn": "SN20240016"},
            "退款",
            "medium",
            dimension,
        ),
        make_record(
            "订单SN20240017的商品缺货怎么办",
            "ORDER",
            {"order_sn": "SN20240017"},
            "缺货",
            "medium",
            dimension,
        ),
        make_record(
            "帮我催一下订单SN20240018",
            "ORDER",
            {"order_sn": "SN20240018"},
            "催单",
            "medium",
            dimension,
        ),
        make_record(
            "订单SN20240019为什么显示已关闭",
            "ORDER",
            {"order_sn": "SN20240019"},
            "关闭",
            "medium",
            dimension,
        ),
        make_record("查询所有待发货订单", "ORDER", {}, "待发货", "auto", dimension),
        make_record(
            "订单SN20240020可以修改商品规格吗",
            "ORDER",
            {"order_sn": "SN20240020"},
            "规格",
            "medium",
            dimension,
        ),
        make_record(
            "我的订单SN20240021总金额是多少",
            "ORDER",
            {"order_sn": "SN20240021"},
            "金额",
            "auto",
            dimension,
        ),
        make_record(
            "订单SN20240022的优惠券使用情况",
            "ORDER",
            {"order_sn": "SN20240022"},
            "优惠券",
            "auto",
            dimension,
        ),
        make_record(
            "查询订单SN20240023的售后服务",
            "ORDER",
            {"order_sn": "SN20240023"},
            "售后",
            "auto",
            dimension,
        ),
        make_record(
            "订单SN20240024为什么被拦截了",
            "ORDER",
            {"order_sn": "SN20240024"},
            "拦截",
            "manual",
            dimension,
        ),
    ]
    return records


def generate_refund_apply_records() -> list[dict]:
    """Generate 25 refund/after-sales records."""
    dimension = "refund_apply"
    records = [
        make_record("我要退货", "AFTER_SALES", {}, "退货", "medium", dimension),
        make_record(
            "这个商品能退吗", "AFTER_SALES", {"product_name": "这个商品"}, "退", "auto", dimension
        ),
        make_record(
            "我要申请退货订单号是SN20240025",
            "AFTER_SALES",
            {"order_sn": "SN20240025"},
            "退货",
            "medium",
            dimension,
        ),
        make_record(
            "商品到货发现有破损我要退款",
            "AFTER_SALES",
            {"refund_reason": "商品破损"},
            "退款",
            "medium",
            dimension,
        ),
        make_record(
            "订单SN20240026的售后进度如何",
            "AFTER_SALES",
            {"order_sn": "SN20240026"},
            "售后",
            "auto",
            dimension,
        ),
        make_record(
            "我想换货买大了",
            "AFTER_SALES",
            {"refund_reason": "尺码不合适"},
            "换货",
            "medium",
            dimension,
        ),
        make_record(
            "申请七天无理由退货",
            "AFTER_SALES",
            {"refund_reason": "七天无理由退货"},
            "退货",
            "auto",
            dimension,
        ),
        make_record("退款什么时候到账", "AFTER_SALES", {}, "退款", "medium", dimension),
        make_record(
            "订单SN20240027维修服务怎么申请",
            "AFTER_SALES",
            {"order_sn": "SN20240027"},
            "维修",
            "medium",
            dimension,
        ),
        make_record("退货物流单号填错了怎么改", "AFTER_SALES", {}, "物流单号", "medium", dimension),
        make_record(
            "我的售后申请被拒绝了原因是什么", "AFTER_SALES", {}, "拒绝", "manual", dimension
        ),
        make_record(
            "订单SN20240028的退款金额不对",
            "AFTER_SALES",
            {"order_sn": "SN20240028"},
            "退款金额",
            "medium",
            dimension,
        ),
        make_record("售后电话是多少", "AFTER_SALES", {}, "电话", "auto", dimension),
        make_record(
            "我想撤销售后申请SN20240029",
            "AFTER_SALES",
            {"order_sn": "SN20240029"},
            "撤销",
            "medium",
            dimension,
        ),
        make_record("商品质保期多久", "AFTER_SALES", {}, "质保", "auto", dimension),
        make_record(
            "这个商品质量问题怎么售后",
            "AFTER_SALES",
            {"refund_reason": "质量问题"},
            "售后",
            "medium",
            dimension,
        ),
        make_record(
            "订单SN20240030少发了配件",
            "AFTER_SALES",
            {"order_sn": "SN20240030"},
            "少发",
            "medium",
            dimension,
        ),
        make_record(
            "我要申请仅退款不退货",
            "AFTER_SALES",
            {"refund_reason": "仅退款"},
            "退款",
            "medium",
            dimension,
        ),
        make_record(
            "售后单号SN20240031的状态",
            "AFTER_SALES",
            {"order_sn": "SN20240031"},
            "售后单",
            "auto",
            dimension,
        ),
        make_record("退货快递员不上门取件怎么办", "AFTER_SALES", {}, "取件", "medium", dimension),
        make_record(
            "订单SN20240032的换货进度",
            "AFTER_SALES",
            {"order_sn": "SN20240032"},
            "换货",
            "auto",
            dimension,
        ),
        make_record("退款原路返回需要多久", "AFTER_SALES", {}, "原路返回", "medium", dimension),
        make_record(
            "售后申请已经超过七天还能退吗", "AFTER_SALES", {}, "超过七天", "manual", dimension
        ),
        make_record(
            "商品SN20240033坏了怎么保修",
            "AFTER_SALES",
            {"order_sn": "SN20240033"},
            "保修",
            "medium",
            dimension,
        ),
        make_record("退货仓库拒收了是什么原因", "AFTER_SALES", {}, "拒收", "medium", dimension),
    ]
    return records


def generate_policy_inquiry_records() -> list[dict]:
    """Generate 25 policy inquiry records."""
    dimension = "policy_inquiry"
    records = [
        make_record("你们的退换货政策是什么", "POLICY", {}, "退换货政策", "auto", dimension),
        make_record("运费险怎么理赔", "POLICY", {}, "运费险", "auto", dimension),
        make_record("会员积分有效期是多久", "POLICY", {}, "积分", "auto", dimension),
        make_record("隐私政策里我的数据会共享给谁", "POLICY", {}, "隐私政策", "medium", dimension),
        make_record("平台支持price match吗", "POLICY", {}, "price match", "auto", dimension),
        make_record("发货时效承诺是多久", "POLICY", {}, "发货时效", "auto", dimension),
        make_record("三包政策具体包含什么", "POLICY", {}, "三包", "auto", dimension),
        make_record("满减活动和折扣券能叠加吗", "POLICY", {}, "叠加", "auto", dimension),
        make_record("国际订单的关税怎么算", "POLICY", {}, "关税", "medium", dimension),
        make_record("取消订单后多久退款", "POLICY", {}, "退款", "auto", dimension),
        make_record("平台对假货的赔偿标准是什么", "POLICY", {}, "赔偿", "medium", dimension),
        make_record("预售商品的规则是什么", "POLICY", {}, "预售", "auto", dimension),
        make_record("投诉商家的处理流程是怎样的", "POLICY", {}, "投诉", "auto", dimension),
        make_record("七天无理由退货的条件", "POLICY", {}, "七天无理由", "auto", dimension),
        make_record("运费怎么算", "POLICY", {}, "运费", "auto", dimension),
        make_record("会员等级权益有哪些", "POLICY", {}, "会员权益", "auto", dimension),
        make_record("平台禁止销售的商品有哪些", "POLICY", {}, "禁售", "medium", dimension),
        make_record("价保规则是什么", "POLICY", {}, "价保", "auto", dimension),
        make_record("食品类商品的售后政策", "POLICY", {}, "食品售后", "auto", dimension),
        make_record("电子产品的保修政策", "POLICY", {}, "保修", "auto", dimension),
        make_record("跨境购物的退换货流程", "POLICY", {}, "跨境退换", "medium", dimension),
        make_record("优惠券的使用规则", "POLICY", {}, "优惠券规则", "auto", dimension),
        make_record("账户注销后数据保留多久", "POLICY", {}, "数据保留", "medium", dimension),
        make_record("纠纷处理时效是多久", "POLICY", {}, "纠纷", "auto", dimension),
        make_record("商家入驻需要什么资质", "POLICY", {}, "入驻", "auto", dimension),
    ]
    return records


def generate_product_query_records() -> list[dict]:
    """Generate 20 product query records."""
    dimension = "product_query"
    records = [
        make_record(
            "这款手机有红色吗", "PRODUCT", {"product_name": "这款手机"}, "颜色", "auto", dimension
        ),
        make_record("这个多少钱", "PRODUCT", {"product_name": "这个"}, "价格", "auto", dimension),
        make_record(
            "商品的保质期多久", "PRODUCT", {"product_name": "商品"}, "保质期", "auto", dimension
        ),
        make_record(
            "有没有更大容量的版本",
            "PRODUCT",
            {"product_name": "这个商品"},
            "容量",
            "auto",
            dimension,
        ),
        make_record(
            "产品的成分表是什么", "PRODUCT", {"product_name": "产品"}, "成分", "auto", dimension
        ),
        make_record(
            "这个商品通过了哪些认证",
            "PRODUCT",
            {"product_name": "这个商品"},
            "认证",
            "auto",
            dimension,
        ),
        make_record(
            "商品尺寸是多少厘米", "PRODUCT", {"product_name": "商品"}, "尺寸", "auto", dimension
        ),
        make_record(
            "充电功率多少瓦", "PRODUCT", {"product_name": "充电器"}, "功率", "auto", dimension
        ),
        make_record(
            "支持七天无理由吗", "PRODUCT", {"product_name": "商品"}, "七天无理由", "auto", dimension
        ),
        make_record("产地是哪里", "PRODUCT", {"product_name": "商品"}, "产地", "auto", dimension),
        make_record(
            "有没有套装组合", "PRODUCT", {"product_name": "这个商品"}, "套装", "auto", dimension
        ),
        make_record(
            "商品重量是多少", "PRODUCT", {"product_name": "商品"}, "重量", "auto", dimension
        ),
        make_record("保修期多久", "PRODUCT", {"product_name": "商品"}, "保修", "auto", dimension),
        make_record(
            "iPhone 16 Pro Max有现货吗",
            "PRODUCT",
            {"product_name": "iPhone 16 Pro Max"},
            "现货",
            "auto",
            dimension,
        ),
        make_record(
            "这款笔记本电脑的配置参数",
            "PRODUCT",
            {"product_name": "笔记本电脑"},
            "配置",
            "auto",
            dimension,
        ),
        make_record(
            "面膜适合敏感肌使用吗", "PRODUCT", {"product_name": "面膜"}, "敏感肌", "auto", dimension
        ),
        make_record(
            "运动鞋的尺码偏大还是偏小",
            "PRODUCT",
            {"product_name": "运动鞋"},
            "尺码",
            "auto",
            dimension,
        ),
        make_record(
            "保温杯的保温时长", "PRODUCT", {"product_name": "保温杯"}, "保温", "auto", dimension
        ),
        make_record(
            "蓝牙耳机的续航时间", "PRODUCT", {"product_name": "蓝牙耳机"}, "续航", "auto", dimension
        ),
        make_record(
            "洗衣液的香味类型", "PRODUCT", {"product_name": "洗衣液"}, "香味", "auto", dimension
        ),
    ]
    return records


def generate_ambiguous_intent_records() -> list[dict]:
    """Generate 20 ambiguous intent records."""
    dimension = "ambiguous_intent"
    records = [
        make_record("那个东西", "OTHER", {}, "那个", "auto", dimension),
        make_record("帮我处理一下", "OTHER", {}, "处理", "auto", dimension),
        make_record("这个怎么办", "OTHER", {}, "怎么办", "auto", dimension),
        make_record("帮我看看这个", "OTHER", {}, "看看", "auto", dimension),
        make_record("那个问题", "OTHER", {}, "问题", "auto", dimension),
        make_record("帮我弄一下", "OTHER", {}, "弄", "auto", dimension),
        make_record("这个怎么搞", "OTHER", {}, "怎么搞", "auto", dimension),
        make_record("那个情况", "OTHER", {}, "情况", "auto", dimension),
        make_record("帮我解决一下", "OTHER", {}, "解决", "auto", dimension),
        make_record(
            "这个东西有问题", "OTHER", {"product_name": "这个东西"}, "问题", "auto", dimension
        ),
        make_record("我上次买的那个", "OTHER", {}, "上次", "auto", dimension),
        make_record("帮我查一下那个", "OTHER", {}, "查", "auto", dimension),
        make_record("那个订单有问题", "ORDER", {"order_sn": ""}, "订单", "auto", dimension),
        make_record(
            "这个商品不太对", "PRODUCT", {"product_name": "这个商品"}, "不太对", "auto", dimension
        ),
        make_record("我的那个东西到了吗", "ORDER", {}, "到了", "auto", dimension),
        make_record("帮我处理一下售后", "AFTER_SALES", {}, "售后", "auto", dimension),
        make_record("那个活动还有吗", "PROMOTION", {}, "活动", "auto", dimension),
        make_record("我想问一下那个政策", "POLICY", {}, "政策", "auto", dimension),
        make_record("我的账户好像有问题", "ACCOUNT", {}, "账户", "auto", dimension),
        make_record("那个包裹怎么回事", "LOGISTICS", {}, "包裹", "auto", dimension),
    ]
    return records


def generate_multi_intent_records() -> list[dict]:
    """Generate 15 multi-intent records."""
    dimension = "multi_intent"
    records = [
        make_record("查订单并申请退款", "ORDER", {"order_sn": ""}, "订单", "medium", dimension),
        make_record("我想查物流顺便问一下售后政策", "LOGISTICS", {}, "物流", "auto", dimension),
        make_record(
            "帮我查订单SN20240034状态然后申请退货",
            "ORDER",
            {"order_sn": "SN20240034"},
            "订单",
            "medium",
            dimension,
        ),
        make_record(
            "这个商品有优惠吗可以开发票吗",
            "PROMOTION",
            {"product_name": "这个商品"},
            "优惠",
            "auto",
            dimension,
        ),
        make_record("我要修改地址并催单", "ORDER", {}, "地址", "medium", dimension),
        make_record("查一下优惠券和账户余额", "ACCOUNT", {}, "优惠券", "auto", dimension),
        make_record(
            "订单SN20240035的物流和售后进度",
            "ORDER",
            {"order_sn": "SN20240035"},
            "物流",
            "auto",
            dimension,
        ),
        make_record("我想退货并查询退款到账时间", "AFTER_SALES", {}, "退货", "medium", dimension),
        make_record(
            "商品有问题我要投诉并申请售后",
            "COMPLAINT",
            {"complaint_reason": "商品有问题"},
            "投诉",
            "manual",
            dimension,
        ),
        make_record("帮我查一下积分和会员等级", "ACCOUNT", {}, "积分", "auto", dimension),
        make_record(
            "这个商品多少钱有现货吗",
            "PRODUCT",
            {"product_name": "这个商品"},
            "价格",
            "auto",
            dimension,
        ),
        make_record("我要修改订单并更换支付方式", "ORDER", {}, "修改", "medium", dimension),
        make_record("查询发货时间和运费险", "POLICY", {}, "发货", "auto", dimension),
        make_record("帮我查最近订单和购物车", "ORDER", {}, "订单", "auto", dimension),
        make_record("我要开发票并查询订单详情", "ORDER", {}, "发票", "medium", dimension),
    ]
    return records


def generate_abnormal_input_records() -> list[dict]:
    """Generate 15 abnormal input records."""
    dimension = "abnormal_input"
    records = [
        make_record("你是个笨蛋", "OTHER", {}, "", "auto", dimension),
        make_record("12345", "OTHER", {}, "", "auto", dimension),
        make_record("asdfghjkl", "OTHER", {}, "", "auto", dimension),
        make_record("!!!!!!!!!!!!!!!!!!", "OTHER", {}, "", "auto", dimension),
        make_record("SELECT * FROM users", "OTHER", {}, "", "auto", dimension),
        make_record("<script>alert('xss')</script>", "OTHER", {}, "", "auto", dimension),
        make_record("     ", "OTHER", {}, "", "auto", dimension),
        make_record(
            "订单SN@#$%^&*()", "ORDER", {"order_sn": "SN@#$%^&*()"}, "订单", "auto", dimension
        ),
        make_record("退款!!!!!!!", "AFTER_SALES", {}, "退款", "auto", dimension),
        make_record(
            "SN99999999999999999999",
            "ORDER",
            {"order_sn": "SN99999999999999999999"},
            "订单",
            "auto",
            dimension,
        ),
        make_record("\u0000\u0001\u0002", "OTHER", {}, "", "auto", dimension),
        make_record("我要退货我要退货我要退货", "AFTER_SALES", {}, "退货", "auto", dimension),
        make_record(
            "\u6d4b\u8bd5\u6d4b\u8bd5\u6d4b\u8bd5", "OTHER", {}, "", "auto", dimension
        ),  # "测试测试测试"
        make_record("DROP TABLE orders;", "OTHER", {}, "", "auto", dimension),
        make_record("\n\n\n\n\n", "OTHER", {}, "", "auto", dimension),
    ]
    return records


def generate_long_conversation_records() -> list[dict]:
    """Generate 10 long conversation scenario records."""
    dimension = "long_conversation"
    records = [
        make_record(
            "用户: 你好 客服: 您好有什么可以帮您 用户: 我想查订单 客服: 请提供订单号 用户: SN20240036 客服: 订单正在配送中 用户: 预计什么时候到 客服: 预计明天送达 用户: 可以改地址吗 客服: 可以帮您修改 用户: 改成北京市朝阳区 客服: 已记录 用户: 谢谢 客服: 不客气",
            "ORDER",
            {"order_sn": "SN20240036"},
            "地址",
            "medium",
            dimension,
        ),
        make_record(
            "用户: 在吗 客服: 在的 用户: 我要退货 客服: 请问订单号是多少 用户: SN20240037 客服: 请问原因 用户: 质量不好 客服: 可以退货 用户: 怎么退 客服: 请填写退货单 用户: 填好了 客服: 已提交审核 用户: 多久能退 客服: 3-5个工作日",
            "AFTER_SALES",
            {"order_sn": "SN20240037", "refund_reason": "质量不好"},
            "退货",
            "medium",
            dimension,
        ),
        make_record(
            "用户: 咨询一下 客服: 请说 用户: 退换货政策 客服: 支持七天无理由 用户: 运费谁出 客服: 质量问题商家承担 用户: 怎么判断质量问题 客服: 需提供照片 用户: 照片发哪里 客服: 售后系统 用户: 好的 客服: 还有其他问题吗",
            "POLICY",
            {},
            "退换货政策",
            "auto",
            dimension,
        ),
        make_record(
            "用户: 查一下账户 客服: 请登录 用户: 已登录 客服: 余额100元 用户: 积分多少 客服: 500分 用户: 优惠券呢 客服: 3张可用 用户: 会过期吗 客服: 有一张明天过期 用户: 帮我看看是哪张 客服: 满100减10",
            "ACCOUNT",
            {},
            "优惠券",
            "auto",
            dimension,
        ),
        make_record(
            "用户: 这个商品怎么样 客服: 请问是哪款 用户: iPhone 16 Pro 客服: 好评率98% 用户: 有优惠吗 客服: 目前满减活动 用户: 能分期吗 客服: 支持12期免息 用户: 赠品有什么 客服: 送充电器 用户: 保修多久 客服: 一年",
            "PRODUCT",
            {"product_name": "iPhone 16 Pro"},
            "优惠",
            "auto",
            dimension,
        ),
        make_record(
            "用户: 投诉 客服: 请问什么问题 用户: 商家态度差 客服: 请提供订单号 用户: SN20240038 客服: 已记录 用户: 怎么处理 客服: 我们会核实 用户: 多久有结果 客服: 1-3个工作日 用户: 能赔偿吗 客服: 视情况而定 用户: 好吧",
            "COMPLAINT",
            {"order_sn": "SN20240038", "complaint_target": "商家", "complaint_reason": "态度差"},
            "投诉",
            "manual",
            dimension,
        ),
        make_record(
            "用户: 物流查询 客服: 单号多少 用户: SF20240002 客服: 已到达北京 用户: 什么时候派送 客服: 预计下午 用户: 可以自提吗 客服: 可以 用户: 自提点在哪 客服: 朝阳区网点 用户: 营业时间 客服: 9-18点 用户: 谢谢",
            "LOGISTICS",
            {"tracking_number": "SF20240002"},
            "自提",
            "auto",
            dimension,
        ),
        make_record(
            "用户: 支付问题 客服: 什么问题 用户: 支付失败 客服: 什么支付方式 用户: 微信 客服: 显示什么错误 用户: 余额不足 客服: 请充值或换卡 用户: 换支付宝可以吗 客服: 可以 用户: 怎么改 客服: 订单页面修改 用户: 好的",
            "PAYMENT",
            {"payment_method": "微信"},
            "支付",
            "medium",
            dimension,
        ),
        make_record(
            "用户: 活动咨询 客服: 请说 用户: 双11活动 客服: 满300减50 用户: 预售什么时候开始 客服: 10月20日 用户: 定金多少 客服: 50元 用户: 能退吗 客服: 付尾款后可退 用户: 尾款什么时候付 客服: 11月1日 用户: 知道了",
            "PROMOTION",
            {},
            "双11",
            "auto",
            dimension,
        ),
        make_record(
            "用户: 购物车问题 客服: 什么问题 用户: 加购失败 客服: 什么商品 用户: 耳机 客服: 库存不足 用户: 什么时候补货 客服: 预计下周 用户: 能预约吗 客服: 可以到货提醒 用户: 怎么设置 客服: 商品页面点击提醒 用户: 好的谢谢",
            "CART",
            {"product_name": "耳机"},
            "库存",
            "medium",
            dimension,
        ),
    ]
    return records


def main() -> None:
    all_records = []
    all_records.extend(generate_order_query_records())  # 30
    all_records.extend(generate_refund_apply_records())  # 25
    all_records.extend(generate_policy_inquiry_records())  # 25
    all_records.extend(generate_product_query_records())  # 20
    all_records.extend(generate_ambiguous_intent_records())  # 20
    all_records.extend(generate_multi_intent_records())  # 15
    all_records.extend(generate_abnormal_input_records())  # 15
    all_records.extend(generate_long_conversation_records())  # 10

    # Shuffle records for randomness
    random.shuffle(all_records)

    total = len(all_records)
    print(f"Total records generated: {total}")

    # Verify dimension counts
    dimension_counts = {}
    for r in all_records:
        dim = r["dimension"]
        dimension_counts[dim] = dimension_counts.get(dim, 0) + 1
    for dim, count in sorted(dimension_counts.items()):
        print(f"  {dim}: {count}")

    output_path = Path("data/golden_dataset_v2.jsonl")
    with output_path.open("w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Dataset written to {output_path}")


if __name__ == "__main__":
    main()
