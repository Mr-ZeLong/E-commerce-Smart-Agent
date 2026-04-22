import { test, expect } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const screenshotsDir = path.join(__dirname, '..', 'test-results', 'screenshots')

test.describe('Visual and UX Audit', () => {
  test('customer app - visual quality check', async ({ page }) => {
    await page.route('**/api/v1/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'test-token',
          token_type: 'bearer',
          user_id: 1,
          username: 'testuser',
          full_name: 'Test User',
          is_admin: false,
        }),
      })
    })

    await page.route('**/api/v1/chat', async (route) => {
      const encoder = new TextEncoder()
      const chunks = [
        'data: {"token": "您好"}\n\n',
        'data: {"token": "，"}\n\n',
        'data: {"token": "有什么"}\n\n',
        'data: {"token": "可以"}\n\n',
        'data: {"token": "帮您的吗"}\n\n',
        'data: {"token": "？"}\n\n',
        'data: [DONE]\n\n'
      ]
      const stream = new ReadableStream({
        start(controller) {
          for (const chunk of chunks) {
            controller.enqueue(encoder.encode(chunk))
          }
          controller.close()
        },
      })
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        body: stream,
      })
    })

    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await page.screenshot({
      path: path.join(screenshotsDir, 'customer-login.png'),
      fullPage: true,
    })

    const loginContainer = page.locator('div.min-h-screen').first()
    await expect(loginContainer).toHaveCSS('background-color', 'rgb(249, 250, 251)')
    await expect(page.getByText('用户登录')).toBeVisible()

    await page.getByPlaceholder('请输入用户名').fill('testuser')
    await page.getByPlaceholder('请输入密码').fill('password')
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('/')
    await page.waitForLoadState('networkidle')

    await page.screenshot({
      path: path.join(screenshotsDir, 'customer-chat.png'),
      fullPage: true,
    })

    await expect(page.getByText('智能客服助手')).toBeVisible()
    const header = page.locator('header').first()
    await expect(header).toBeVisible()

    const startTime = Date.now()
    await page.getByPlaceholder('输入消息...').fill('你好')
    await page.getByRole('button', { name: '发送' }).click()

    await expect(page.getByText(/您好/)).toBeVisible({ timeout: 3000 })
    const responseTime = Date.now() - startTime
    console.log(`Response time: ${responseTime}ms`)
    expect(responseTime).toBeLessThan(3000)

    await page.waitForTimeout(500)
    await page.screenshot({
      path: path.join(screenshotsDir, 'customer-chat-response.png'),
      fullPage: true,
    })

    const inputArea = page.locator('[placeholder="输入消息..."]')
    await expect(inputArea).toBeVisible()
    const sendButton = page.getByRole('button', { name: '发送' })
    await expect(sendButton).toBeVisible()

    const botIcon = page.locator('svg[class*="text-blue"]').first()
    await expect(botIcon).toBeVisible()
  })

  test('admin app - visual quality check', async ({ page }) => {
    await page.route('**/api/v1/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'admin-test-token',
          token_type: 'bearer',
          user_id: 2,
          username: 'adminuser',
          full_name: 'Admin User',
          is_admin: true,
          role: 'ADMIN',
        }),
      })
    })

    await page.route('**/api/v1/admin/tasks?*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            audit_log_id: 1,
            thread_id: 'thread_1',
            user_id: 1,
            trigger_reason: '我要退货',
            risk_level: 'HIGH',
            context_snapshot: {
              question: '我要退货',
              order_data: {
                order_sn: 'ORD001',
                total_amount: 199.0,
                status: '已发货',
                items: [{ name: '商品A', qty: 1 }],
              },
            },
            created_at: '2024-01-01T00:00:00Z',
          },
        ]),
      })
    })

    await page.route('**/api/v1/admin/tasks-all', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          risk_tasks: 1,
          confidence_tasks: 0,
          manual_tasks: 0,
          total: 1,
        }),
      })
    })

    await page.route('**/api/v1/admin/notifications', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ notifications: [] }),
      })
    })

    await page.route('**/api/v1/admin/execution-logs?*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          logs: [
            {
              log_id: 1,
              thread_id: 'thread_1',
              agent_name: 'order_agent',
              intent: 'query_order',
              latency_ms: 245,
              created_at: '2024-01-01T00:00:00Z',
            },
          ],
          total: 1,
        }),
      })
    })

    await page.route('**/api/v1/admin/conversations?*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          threads: [
            {
              thread_id: 'thread_1',
              user_id: 1,
              message_count: 5,
              last_updated: '2024-01-01T00:00:00Z',
              intent_category: 'ORDER',
            },
            {
              thread_id: 'thread_2',
              user_id: 2,
              message_count: 3,
              last_updated: '2024-01-02T00:00:00Z',
              intent_category: 'POLICY',
            },
          ],
          total: 2,
          offset: 0,
          limit: 20,
        }),
      })
    })

    await page.goto('/admin.html#/login')
    await page.waitForLoadState('networkidle')

    await page.screenshot({
      path: path.join(screenshotsDir, 'admin-login.png'),
      fullPage: true,
    })

    await expect(page.getByPlaceholder('输入管理员用户名')).toBeVisible()
    await expect(page.getByPlaceholder('输入密码')).toBeVisible()

    await page.getByPlaceholder('输入管理员用户名').fill('adminuser')
    await page.getByPlaceholder('输入密码').fill('password')
    await page.getByRole('button', { name: '登录' }).click()
    await page.waitForURL('/admin.html#/')
    await page.waitForLoadState('networkidle')

    await page.screenshot({
      path: path.join(screenshotsDir, 'admin-dashboard.png'),
      fullPage: true,
    })

    await expect(page.getByText('审核控制台')).toBeVisible()
    await expect(page.getByText('我要退货')).toBeVisible()

    const tabsList = page.locator('[role="tablist"]').first()
    await expect(tabsList).toBeVisible()

    await page.getByRole('tab', { name: /会话日志/ }).click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    await page.screenshot({
      path: path.join(screenshotsDir, 'admin-conversation-logs.png'),
      fullPage: true,
    })

    await expect(page.getByText('会话列表')).toBeVisible()
  })
})
