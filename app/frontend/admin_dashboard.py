# app/frontend/admin_dashboard.py
"""
基于 Gradio 的 B 端管理员工作台 - v4.0
支持任务队列、会话回放、一键决策
"""
import os
from typing import Any

import gradio as gr
import requests
from gradio import themes

# 配置
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
DEFAULT_ADMIN_ID = 999  # 默认管理员ID


class AdminClient:
    """管理员客户端"""

    def __init__(self, admin_id: int = DEFAULT_ADMIN_ID):
        self.admin_id = admin_id
        self.token = None
        self._init_token()

    def _init_token(self):
        """初始化管理员 Token"""
        from app.core.security import create_access_token
        self.token = create_access_token(user_id=self.admin_id, is_admin=True)
        print(" 管理员 Token 已生成")

    def get_pending_tasks(self, risk_level: str | None = None) -> list[dict[str, Any]]:
        """获取待审核任务列表"""
        headers = {
            "Authorization": f"Bearer {self.token}",
        }

        try:
            url = f"{API_BASE_URL}/admin/tasks"
            if risk_level:
                url += f"?risk_level={risk_level}"

            print(f" 请求任务列表: {url}")
            response = requests.get(url, headers=headers, timeout=10)

            print(f" 响应状态:  {response.status_code}")

            if response.status_code == 200:
                tasks = response.json()
                print(f" 获取到 {len(tasks)} 个任务")
                return tasks
            else:
                print(f" 获取任务失败: {response.status_code}")
                return []
        except Exception as e:
            print(f" 请求异常: {e}")
            return []

    def make_decision(self, audit_log_id: int, action: str, comment: str = "") -> dict[str, Any]:
        """做出审核决策"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            print(f" 提交决策: ID={audit_log_id}, Action={action}")

            response = requests.post(
                f"{API_BASE_URL}/admin/resume/{audit_log_id}",
                headers=headers,
                json={
                    "action": action,
                    "admin_comment": comment
                },
                timeout=10
            )

            print(f" 响应状态: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(" 决策成功")
                return result
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f":  {error_detail.get('detail', response.text)}"
                except:
                    error_msg += f": {response.text[:200]}"
                print(f" {error_msg}")
                return {"success": False, "message": error_msg}
        except Exception as e:
            print(f" 请求异常:  {e}")
            return {"success": False, "message": str(e)}


def create_admin_dashboard():
    """创建管理员工作台"""

    custom_css = """
    . high-risk { background-color: #f8d7da; font-weight: bold; }
    .medium-risk { background-color: #fff3cd; }
    .low-risk { background-color: #d4edda; }
    . task-header { font-size: 1.1em; font-weight: 600; margin-bottom: 12px; }
    .context-box { background-color: #f8f9fa; padding: 16px; border-radius: 8px; margin:  8px 0; }
    .order-box { background-color: #e7f3ff; padding: 16px; border-radius: 8px; margin: 8px 0; border-left: 4px solid #007bff; }
    . decision-success { color: #28a745; font-weight: 600; }
    .decision-error { color: #dc3545; font-weight: 600; }
    """

    with gr.Blocks(
        title="Admin Dashboard v4.0",
        theme=themes.Monochrome(),
        css=custom_css
    ) as demo:

        gr.Markdown("# 🛡️ 管理员工作台 - v4.0")
        gr.Markdown("### 人工审核 · 上帝视角 · 3秒决策")

        # 状态存储
        client_state = gr.State(None)
        tasks_state = gr.State([])
        selected_task_state = gr.State(None)

        with gr.Row():
            # === 左侧:  任务队列 ===
            with gr.Column(scale=1):
                gr.Markdown("###  待审核任务队列")

                with gr.Row():
                    risk_filter = gr.Radio(
                        choices=["全部", "HIGH", "MEDIUM", "LOW"],
                        value="全部",
                        label=" 风险等级筛选",
                        scale=3
                    )
                    refresh_btn = gr.Button(" 刷新", variant="secondary", scale=1, size="sm")

                task_count = gr.Markdown("**任务数量**: 0")

                task_list = gr.Dataframe(
                    headers=["选择", "ID", "用户", "风险", "原因", "时间"],
                    datatype=["str", "number", "number", "str", "str", "str"],
                    label="",
                    interactive=False,
                    wrap=True
                )

            # === 中间: 上下文回放 ===
            with gr.Column(scale=2):
                gr.Markdown("###  上下文回放")

                task_detail_md = gr.Markdown("*请从左侧选择任务*")

                with gr.Accordion("完整上下文快照", open=False):
                    context_json = gr.JSON(label="")

                gr.Markdown("---")
                gr.Markdown("### 订单详情")

                order_detail_html = gr.HTML("<p style='color: #666;'>*暂无订单信息*</p>")

            # === 右侧: 决策面板 ===
            with gr.Column(scale=1):
                gr.Markdown("###  决策面板")

                selected_info = gr.Markdown("*请先选择任务*")

                admin_comment = gr.Textbox(
                    label=" 审核备注",
                    placeholder="请输入审核意见（拒绝时必填）",
                    lines=4,
                    max_lines=10
                )

                with gr.Row():
                    approve_btn = gr.Button(
                        " 批准",
                        variant="primary",
                        size="lg",
                        scale=1
                    )
                    reject_btn = gr.Button(
                        " 拒绝",
                        variant="stop",
                        size="lg",
                        scale=1
                    )

                decision_result = gr.Markdown("")

                gr.Markdown("---")
                gr.Markdown("### 系统信息")
                _admin_id_display = gr.Textbox(
                    label="管理员ID",
                    value=str(DEFAULT_ADMIN_ID),
                    interactive=False
                )
                api_status = gr.Textbox(
                    label="API 状态",
                    value="未检测",
                    interactive=False
                )

        # === 功能函数 ===

        def init_admin_client():
            """初始化管理员客户端"""
            try:
                client = AdminClient(admin_id=DEFAULT_ADMIN_ID)

                # 测试 API 连接
                try:
                    health_response = requests.get(f"{API_BASE_URL.replace('/api/v1', '')}/health", timeout=5)
                    if health_response.status_code == 200:
                        api_status_text = "已连接"
                    else:
                        api_status_text = f"异常 ({health_response.status_code})"
                except:
                    api_status_text = "无法连接"

                return client, api_status_text
            except Exception as e:
                print(f" 初始化失败: {e}")
                return None, f"错误: {str(e)}"

        def load_tasks(client:  AdminClient, risk_level: str):
            """加载任务列表"""
            if not client:
                return (
                    [],
                    [],
                    "**任务数量**: 0 (客户端未初始化)",
                    "*客户端未初始化*",
                    {},
                    "<p style='color: #666;'>*暂无订单信息*</p>",
                    "*请先初始化客户端*",
                    ""
                )

            filter_value = None if risk_level == "全部" else risk_level
            tasks = client.get_pending_tasks(filter_value)

            if not tasks:
                return (
                    [],
                    [],
                    f"**任务数量**: 0 (筛选:  {risk_level})",
                    "*暂无待审核任务*",
                    {},
                    "<p style='color: #666;'>*暂无订单信息*</p>",
                    "*请先选择任务*",
                    ""
                )

            # 转换为表格数据
            table_data = []
            for i, task in enumerate(tasks):
                table_data.append([
                    f" 点击第{i+1}行",
                    task["audit_log_id"],
                    task["user_id"],
                    task["risk_level"],
                    task["trigger_reason"][: 40] + "..." if len(task["trigger_reason"]) > 40 else task["trigger_reason"],
                    task["created_at"][: 19]
                ])

            count_md = f"**任务数量**: {len(tasks)} (筛选: {risk_level})"

            return (
                table_data,
                tasks,
                count_md,
                "*请从左侧任务列表点击一行选择任务*",
                {},
                "<p style='color:  #666;'>*暂无订单信息*</p>",
                "*请先选择任务*",
                ""
            )

        def select_task(tasks: list[dict], evt:  gr.SelectData):
            """选择任务"""
            if not tasks or evt.index[0] >= len(tasks):
                return (
                    None,
                    "*任务不存在*",
                    {},
                    "<p style='color: #666;'>*暂无订单信息*</p>",
                    "*任务不存在*"
                )

            task = tasks[evt.index[0]]
            context = task["context_snapshot"]

            # 任务详情
            detail_md = f"""
<div class="context-box">
<p class="task-header">任务 #{task['audit_log_id']}</p>
<p><strong>用户问题:</strong> {context.get('question', '无')}</p>
<p><strong>会话ID:</strong> {task['thread_id']}</p>
<p><strong>触发时间:</strong> {task['created_at']}</p>
</div>
            """

            # 提取订单信息
            order_data = context.get("order_data", {})
            if order_data:
                items_list = order_data.get('items', [])
                items_html = "<ul>"
                for item in items_list:
                    items_html += f"<li>{item.get('name', '未知')} x {item.get('qty', 0)}</li>"
                items_html += "</ul>"

                order_html = f"""
<div class="order-box">
<p style="font-size: 1.1em; font-weight: 600; margin-bottom: 8px;"> 订单信息</p>
<p><strong>订单号:</strong> {order_data.get('order_sn', '无')}</p>
<p><strong>订单金额:</strong> <span style="color: #dc3545; font-size: 1.2em; font-weight: bold;">¥{order_data.get('total_amount', 0)}</span></p>
<p><strong>订单状态:</strong> {order_data.get('status', '无')}</p>
<p><strong>商品列表:</strong></p>
{items_html}
</div>
                """
            else:
                order_html = "<p style='color: #666;'>*该任务无关联订单*</p>"

            # 选中信息
            selected_md = f"""
**已选中任务 #{task['audit_log_id']}**

- 风险等级: **{task['risk_level']}**
- 用户ID: {task['user_id']}
- 触发原因: {task['trigger_reason']}
            """

            return (
                task,
                detail_md,
                context,
                order_html,
                selected_md
            )

        def make_approve_decision(client: AdminClient, selected_task: dict, comment: str):
            """批准决策"""
            if not client:
                return " 客户端未初始化"

            if not selected_task:
                return " 请先选择任务"

            audit_log_id = selected_task["audit_log_id"]
            result = client.make_decision(audit_log_id, "APPROVE", comment)

            if result.get("success"):
                return f'<p class="decision-success"> 审核通过 - 任务 #{audit_log_id} 已批准</p><p>请点击"刷新"更新任务列表</p>'
            else:
                return f'<p class="decision-error"> 操作失败:  {result.get("message", "未知错误")}</p>'

        def make_reject_decision(client:  AdminClient, selected_task: dict, comment: str):
            """拒绝决策"""
            if not client:
                return " 客户端未初始化"

            if not selected_task:
                return " 请先选择任务"

            if not comment.strip():
                return '<p class="decision-error"> 拒绝时必须填写审核备注</p>'

            audit_log_id = selected_task["audit_log_id"]
            result = client.make_decision(audit_log_id, "REJECT", comment)

            if result.get("success"):
                return f'<p class="decision-success">审核拒绝 - 任务 #{audit_log_id} 已拒绝</p><p>请点击"刷新"更新任务列表</p>'
            else:
                return f'<p class="decision-error">操作失败: {result.get("message", "未知错误")}</p>'

        # === 事件绑定 ===

        # 初始化
        demo.load(
            init_admin_client,
            outputs=[client_state, api_status]
        )

        # 加载任务列表
        demo.load(
            load_tasks,
            inputs=[client_state, risk_filter],
            outputs=[
                task_list,
                tasks_state,
                task_count,
                task_detail_md,
                context_json,
                order_detail_html,
                selected_info,
                decision_result
            ]
        )

        # 刷新任务
        refresh_btn.click(
            load_tasks,
            inputs=[client_state, risk_filter],
            outputs=[
                task_list,
                tasks_state,
                task_count,
                task_detail_md,
                context_json,
                order_detail_html,
                selected_info,
                decision_result
            ]
        )

        # 筛选变更
        risk_filter.change(
            load_tasks,
            inputs=[client_state, risk_filter],
            outputs=[
                task_list,
                tasks_state,
                task_count,
                task_detail_md,
                context_json,
                order_detail_html,
                selected_info,
                decision_result
            ]
        )

        # 选择任务
        task_list.select(
            select_task,
            inputs=[tasks_state],
            outputs=[
                selected_task_state,
                task_detail_md,
                context_json,
                order_detail_html,
                selected_info
            ]
        )

        # 批准决策
        approve_btn.click(
            make_approve_decision,
            inputs=[client_state, selected_task_state, admin_comment],
            outputs=decision_result
        )

        # 拒绝决策
        reject_btn.click(
            make_reject_decision,
            inputs=[client_state, selected_task_state, admin_comment],
            outputs=decision_result
        )

    return demo


if __name__ == "__main__":
    print(" 启动管理员工作台...")
    print(f" API 地址: {API_BASE_URL}")
    print(f" 默认管理员ID: {DEFAULT_ADMIN_ID}")

    demo = create_admin_dashboard()
    demo.queue()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        show_error=True
    )
