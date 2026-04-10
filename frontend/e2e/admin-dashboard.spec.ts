import { test, expect } from '@playwright/test'

test('admin login and view dashboard', async ({ page }) => {
  // Mock login API
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

  // Mock tasks API
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

  // Mock task stats API
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

  // Mock notifications API
  await page.route('**/api/v1/admin/notifications', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ notifications: [] }),
    })
  })

  // Navigate to admin entry point (HashRouter in dev)
  await page.goto('/admin.html#/login')

  // Login
  await page.getByPlaceholder('输入管理员用户名').fill('adminuser')
  await page.getByPlaceholder('输入密码').fill('password')
  await page.getByRole('button', { name: '登录' }).click()

  // Assert dashboard appears
  await expect(page.getByText('审核控制台')).toBeVisible()
  await expect(page.getByText('待审核: 1').first()).toBeVisible()

  // Assert mocked task text appears in the task list
  await expect(page.getByText('我要退货')).toBeVisible()
})
