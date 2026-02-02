# Resume Enhancement Agent 🚀

一个智能简历优化代理，能够从 GitHub、Reddit、Twitter 等平台自动收集最新技术趋势，分析简历与目标岗位的技能差距，并提供个性化的学习路径和资源推荐。

## ✨ 核心功能

### 1. 多平台技术趋势爬取
- **GitHub**: 爬取趋势项目和相关代码仓库
- **Reddit**: 收集技术社区讨论和热门话题
- **Twitter/X**: 提供技术话题搜索链接和推荐账号

### 2. 智能技能分析
- 自动提取简历中的技能
- 解析职位描述的技能要求
- 计算技能匹配度
- 识别技能差距

### 3. 学习路径生成
- 根据技能差距优先级排序
- 结合当前技术趋势
- 提供学习资源链接（官方文档、教程、课程）

### 4. GitHub 项目推荐
- 推荐相关开源项目供学习
- 匹配缺失技能的实战代码
- 按相关性和星标排序

## 🎯 测试结果

刚刚完成的测试分析了一个**传统后端工程师简历**与**高级AI工程师岗位**的匹配度：

### 关键发现

**技能匹配度**: 10.0%
- **已具备**: Python
- **缺失**: LangChain, LangGraph, OpenAI API, 向量数据库(Weaviate, Chroma, Pinecone), RAG, FastAPI, Prompt Engineering

### 推荐学习路径（按优先级）

1. **Weaviate** 🔥 - 向量数据库（优先级分数: 16）
2. **Chroma** 🔥 - 向量数据库（优先级分数: 16）
3. **LangChain** - LLM 应用框架（优先级分数: 10）
4. **OpenAI API** - GPT 集成（优先级分数: 10）
5. **LangGraph** - Agent 工作流（优先级分数: 10）

### 推荐 GitHub 项目

1. **langchain-ai/langchain** ⭐ 125k - LLM 应用开发平台
2. **FlowiseAI/Flowise** ⭐ 48k - 可视化 AI Agent 构建
3. **weaviate/Verba** ⭐ 7.5k - RAG 聊天机器人实战
4. **langchain4j/langchain4j** ⭐ 10k - Java LLM 集成

### 技术趋势识别

当前热门技术: `llm`, `agentic-ai`, `chroma`, `weaviate`, `vectors`, `rag`, `hybrid-search`

## 📁 项目结构

```
resume_agent/
├── main.py                      # 主程序入口
├── scrapers/                    # 爬虫模块
│   ├── github_scraper.py       # GitHub 趋势爬取
│   ├── reddit_scraper.py       # Reddit 讨论爬取
│   └── twitter_scraper.py      # Twitter 搜索建议
├── analyzer/                    # 分析模块
│   └── gap_analyzer.py         # 技能差距分析
├── test_resume.txt             # 测试简历
├── test_job.txt                # 测试职位描述
└── resume_analysis_report.txt  # 生成的分析报告
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests beautifulsoup4
```

### 2. 准备文件

创建两个文本文件：
- `my_resume.txt` - 你的简历内容
- `target_job.txt` - 目标岗位描述

### 3. 运行分析

```bash
python main.py
```

或者在代码中自定义：

```python
from main import ResumeEnhancementAgent

agent = ResumeEnhancementAgent()
agent.run(
    resume_file="my_resume.txt",
    job_file="target_job.txt",
    output_file="my_report.txt"
)
```

## 📊 报告内容

生成的报告包含：

1. **技能匹配度分析** - 已具备 vs 缺失技能
2. **学习路径推荐** - 按优先级排序，包含具体学习资源
3. **GitHub 项目推荐** - 实战代码学习
4. **技术趋势总结** - 当前热门技术
5. **Twitter 跟踪建议** - 相关话题搜索链接

## 🔧 自定义配置

### 添加 API 认证（可选）

创建 `.env` 文件：

```bash
# GitHub API (提高请求限制)
GITHUB_TOKEN=your_token

# Reddit API (更多功能)
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret

# Twitter API (需要付费订阅)
TWITTER_API_KEY=your_key
```

### 扩展技能库

编辑 `analyzer/gap_analyzer.py` 中的 `tech_categories` 字典来添加更多技能类别。

### 添加学习资源

在 `_get_learning_resources()` 方法中添加预定义的资源链接。

## 💡 使用建议

1. **定期更新简历**: 每次分析后根据建议更新简历
2. **追踪技术趋势**: 使用生成的 Twitter 搜索链接保持信息同步
3. **实战学习**: 克隆推荐的 GitHub 项目进行学习
4. **优先级学习**: 专注于标记为 🔥 的趋势技术

## 🎓 学习路径示例

基于测试结果，一个从传统后端到 AI 工程师的学习路径：

**第1-2周**: FastAPI + Python 进阶
- 学习现代 Python Web 框架
- 了解异步编程

**第3-4周**: LangChain 基础
- 官方文档教程
- 简单的 LLM 应用开发

**第5-6周**: 向量数据库
- Chroma 或 Weaviate
- 理解 Embedding 和相似度搜索

**第7-8周**: RAG 架构
- 构建实际的 RAG 应用
- 学习 Prompt Engineering

**第9-10周**: LangGraph 和 AI Agents
- 多代理系统
- 工作流编排

## ⚠️ 注意事项

1. **API 限制**:
   - GitHub: 未认证 60 次/小时，认证 5000 次/小时
   - Reddit: 公开 API 有速率限制
   - Twitter: 现在需要付费订阅

2. **爬虫礼仪**:
   - 代码中已添加 `time.sleep()` 避免请求过快
   - 遵守各平台的使用条款

3. **结果仅供参考**:
   - AI 分析可能有误差
   - 需要结合实际情况判断

## 🔮 未来改进方向

- [ ] 集成 LLM (OpenAI/Claude) 进行更智能的分析
- [ ] 添加简历自动改写功能
- [ ] 支持更多技术社区 (Stack Overflow, HackerNews)
- [ ] 提供 Web UI 界面
- [ ] 自动生成项目学习计划
- [ ] 职位市场薪资分析

## 📝 License

MIT License - 随意使用和修改

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**Made with ❤️ for job seekers everywhere**
