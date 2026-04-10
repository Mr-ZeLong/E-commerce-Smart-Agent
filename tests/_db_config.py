import os
from pathlib import Path


def _configure_test_database() -> None:
    """在导入 app 模块前配置测试数据库，确保测试数据隔离。"""
    # 如果已设置 TEST_DATABASE_URL，直接提取数据库名并覆盖 POSTGRES_DB
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        import urllib.parse

        parsed = urllib.parse.urlparse(test_url)
        db_name = parsed.path.lstrip("/")
        os.environ["POSTGRES_DB"] = db_name
        return

    # 获取原始 POSTGRES_DB（优先环境变量，其次 .env 文件）
    original_db = os.environ.get("POSTGRES_DB")
    if not original_db:
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("POSTGRES_DB="):
                    original_db = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if original_db and not original_db.startswith("test_"):
        os.environ["POSTGRES_DB"] = f"test_{original_db}"
    elif not original_db:
        os.environ["POSTGRES_DB"] = "test_ecommerce_agent"


_configure_test_database()
