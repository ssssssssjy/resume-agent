"""Routes 模块 - 路由工厂函数"""

from .threads import add_thread_base_routes, add_thread_param_routes
from .runs import add_runs_routes
from .assistants import create_assistants_router
from .system import add_system_routes

__all__ = [
    "add_thread_base_routes",
    "add_thread_param_routes",
    "add_runs_routes",
    "create_assistants_router",
    "add_system_routes",
]
