# ai-sim-company 常用命令
# Windows 下若无 make，可直接使用 docker compose 子命令。

# ═══ 启动 ═══
up:
	docker compose up -d

down:
	docker compose down

# ═══ 日志 ═══
logs:
	docker compose logs -f

logs-ceo:
	docker compose logs -f agent-ceo

logs-company:
	docker compose logs -f company

# ═══ 重置 (清除所有数据) ═══
reset:
	docker compose down -v
	rm -rf data/

# ═══ 新增 Agent (手动，调试用) ═══
agent:
	docker run -d \
	  --name aisim-agent-$(NAME) \
	  --network ai-sim-company_aisim-net \
	  -e REDIS_URL=redis://redis:6379 \
	  -e AGENT_ID=$(NAME) \
	  -v ai-sim-company_agent_$(NAME):/workspace/$(NAME) \
	  -v ai-sim-company_company_files:/workspace/shared \
	  ai-sim-company-agent:latest

# ═══ 本地开发 ═══
lint:
	ruff check aisim tests
	mypy aisim

test:
	pytest

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev
