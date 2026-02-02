"""简历增强 Agent

基于 deepagents 框架构建，支持：
- 多轮对话
- 文件系统工具 (ls, read_file, edit_file, glob, grep)
- GitHub 搜索和趋势查询
"""

from .builder import _build_graph, build_resume_enhancer, graph

__all__ = ["_build_graph", "build_resume_enhancer", "graph"]
