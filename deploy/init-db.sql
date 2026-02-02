-- 初始化脚本：创建所需的数据库
-- PostgreSQL 会在首次启动时自动执行此脚本

-- 创建应用数据库（用户认证、会话管理）
CREATE DATABASE resume_agent;

-- langgraph 数据库会通过 POSTGRES_DB 环境变量自动创建
