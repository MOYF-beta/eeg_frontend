# 后端测试
cd backend && /home/zch/Documents/eeg_frontend/.venv/bin/python -m pytest eeg_app/tests/ -v

# 前端单元测试
cd frontend && npx vitest run

# 前端 E2E 测试（需要所有服务运行中）
cd frontend && npx playwright test e2e/virtual-device-e2e.spec.ts