"""应用配置管理

环境指定方式：
  通过环境变量 ENVIRONMENT 指定运行环境
  支持值: test, production, local 等

  示例：
    export ENVIRONMENT=local && python main.py
    ENVIRONMENT=test python main.py

环境配置文件命名规则：
  .env.{ENVIRONMENT}

  例如：
    ENVIRONMENT=local     -> 加载 .env.local
    ENVIRONMENT=test      -> 加载 .env.test
"""
import os
from pathlib import Path

from dotenv import load_dotenv


class Config:
    """配置管理类"""

    def __init__(self):
        # 获取环境变量，默认为 local
        self.env = os.getenv("ENVIRONMENT", "local")

        # 后端目录 (从 apps/backend/config/app_config.py 向上两级到 apps/backend/)
        self.base_dir = Path(__file__).parent.parent
        self._load_env()

    def _load_env(self):
        """加载对应环境的配置文件"""
        env_file = self.base_dir / f".env.{self.env}"

        # 如果环境特定配置不存在，尝试加载 .env
        if not env_file.exists():
            env_file = self.base_dir / ".env"

        if env_file.exists():
            load_dotenv(env_file, override=False)
            print(f"✅ 加载配置: {env_file}")
        else:
            print(f"⚠️  配置文件不存在: {env_file}，使用环境变量")

        print(f"🌍 当前环境: {self.env}")

    @property
    def openai_api_base(self) -> str:
        value = os.getenv("OPENAI_API_BASE")
        if not value:
            raise RuntimeError("❌ OPENAI_API_BASE 未配置")
        return value

    @property
    def openai_api_key(self) -> str:
        value = os.getenv("OPENAI_API_KEY")
        if not value:
            raise RuntimeError("❌ OPENAI_API_KEY 未配置")
        return value

    @property
    def github_token(self) -> str | None:
        """GitHub Token (可选)"""
        return os.getenv("GITHUB_TOKEN")

    @property
    def workflow_database_url(self) -> str | None:
        """PostgreSQL 连接字符串（可选，用于 LangGraph Checkpointer）"""
        return os.getenv("WORKFLOW_DATABASE_URL")

    @property
    def workflow_sqlite_path(self) -> str | None:
        """SQLite 数据库路径（可选，用于本地持久化）"""
        return os.getenv("WORKFLOW_SQLITE_PATH")

    @property
    def is_local(self) -> bool:
        """是否为本地开发环境"""
        return self.env == "local"


# 全局配置实例
config = Config()

# 向后兼容的导出
CURRENT_ENVIRONMENT = config.env
OPENAI_API_BASE = config.openai_api_base
OPENAI_API_KEY = config.openai_api_key
