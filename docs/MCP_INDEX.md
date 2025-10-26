# MCP 文档索引

Model Context Protocol (MCP) 集成完整文档导航。

## 快速导航

### 🚀 新手入门

1. **[快速开始](MCP_QUICKSTART.md)** ⭐ 推荐第一步
   - 5 分钟快速上手
   - 安装和配置
   - 第一个 MCP 工具

2. **[测试结果](../TEST_RESULTS.md)**
   - 测试状态总结
   - 已验证功能
   - 使用建议

### 📚 深入学习

3. **[完整集成指南](MCP_INTEGRATION.md)**
   - 架构设计
   - 配置详解
   - 高级用法
   - 故障排除

4. **[测试指南](TESTING_MCP.md)**
   - 运行测试
   - 测试开发
   - CI/CD 集成

5. **[实现总结](MCP_IMPLEMENTATION_SUMMARY.md)**
   - 实现细节
   - 设计决策
   - 文件清单
   - 性能特性

## 文档结构

```
docs/
├── MCP_INDEX.md                    # 本文档（索引）
├── MCP_QUICKSTART.md              # ⭐ 快速开始
├── MCP_INTEGRATION.md             # 完整集成指南
├── TESTING_MCP.md                 # 测试指南
└── MCP_IMPLEMENTATION_SUMMARY.md  # 实现总结

TEST_RESULTS.md                    # 测试结果
```

## 代码位置

### 核心代码

```
generalAgent/tools/mcp/
├── __init__.py                    # 模块导出
├── connection.py                  # 连接层（stdio/SSE）
├── manager.py                     # 生命周期管理
├── wrapper.py                     # LangChain 集成
└── loader.py                      # 配置加载
```

### 配置文件

```
generalAgent/config/
├── mcp_servers.yaml               # 用户配置（不提交）
└── mcp_servers.yaml.example       # 配置示例
```

### 测试代码

```
tests/test_mcp/
├── conftest.py                    # Pytest 配置
├── test_connection.py             # 连接层测试
├── test_manager.py                # 管理器测试
├── test_wrapper.py                # 包装器测试
├── test_loader.py                 # 加载器测试
├── test_integration.py            # 集成测试
└── test_e2e.py                    # 端到端测试

tests/mcp_servers/
└── test_stdio_server.py           # 测试服务器
```

### 工具脚本

```
scripts/
├── test_mcp_quick.sh              # 快速测试脚本
└── test_mcp_integration.py        # 集成测试脚本
```

## 使用场景

### 场景 1: 我是新用户

1. 阅读 [快速开始](MCP_QUICKSTART.md)
2. 创建配置文件
3. 运行测试验证
4. 启动使用

### 场景 2: 我想了解架构

1. 阅读 [实现总结](MCP_IMPLEMENTATION_SUMMARY.md)
2. 查看 [完整集成指南](MCP_INTEGRATION.md)
3. 浏览代码结构

### 场景 3: 我遇到问题

1. 查看 [测试结果](../TEST_RESULTS.md) 确认状态
2. 查阅 [完整集成指南](MCP_INTEGRATION.md) 的故障排除章节
3. 运行诊断脚本: `python scripts/test_mcp_integration.py`

### 场景 4: 我想开发测试

1. 阅读 [测试指南](TESTING_MCP.md)
2. 查看现有测试代码
3. 运行测试套件

### 场景 5: 我想创建自定义 MCP 服务器

1. 参考 `tests/mcp_servers/test_stdio_server.py`
2. 阅读 [完整集成指南](MCP_INTEGRATION.md) 的自定义服务器章节
3. 测试验证

## 常用命令

```bash
# 快速验证
python scripts/test_mcp_integration.py

# 运行测试
pytest tests/test_mcp/test_loader.py -v

# 查看配置示例
cat generalAgent/config/mcp_servers.yaml.example

# 启动应用
python main.py
```

## 版本信息

- 实现日期: 2025-10-26
- MCP SDK 版本: 1.7.1
- Python 版本要求: 3.12+

## 相关资源

- [MCP 官方文档](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [官方 MCP 服务器](https://github.com/modelcontextprotocol)

## 更新记录

- 2025-10-26: 初始实现和文档
