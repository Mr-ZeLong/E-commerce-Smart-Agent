import { test, expect } from '@playwright/test'

test('customer login and send chat message', async ({ page }) => {
  // Mock login API
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

  // Mock chat API with SSE stream
  await page.route('**/api/v1/chat', async (route) => {
    const encoder = new TextEncoder()
    const chunks = ['data: {"token": "您好"}\n\n', 'data: {"token": "！"}\n\n', 'data: [DONE]\n\n']
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

  // Navigate to customer entry point
  await page.goto('/')

  // Login
  await page.getByPlaceholder('请输入用户名').fill('testuser')
  await page.getByPlaceholder('请输入密码').fill('password')
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL('/')

  // Assert chat page appears
  await expect(page.getByText('智能客服助手')).toBeVisible()

  // Send chat message
  await page.getByPlaceholder('输入消息...').fill('你好')
  await page.getByRole('button', { name: '发送' }).click()

  // Assert assistant response appears
  await expect(page.getByText('您好！')).toBeVisible()
})
