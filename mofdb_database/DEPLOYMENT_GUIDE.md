# MOFdb 部署和连接指南

## 🚀 部署状态

### ✅ 已完成的部署

1. **MOF Server** (端口 50004)
   - 状态: ✅ 运行中
   - 进程: `python server.py --port 50004 --host 0.0.0.0`
   - 日志: `/home/Mr-Dice/mofdb_database/Mofdb_Server/server.log`

2. **MOF Agent** (端口 50005)
   - 状态: ✅ 运行中
   - 进程: `adk web --port 50005 --host 0.0.0.0 Mofdb_Agent`
   - 日志: `/home/Mr-Dice/mofdb_database/agent_web.log`

### 📁 目录结构
```
/home/Mr-Dice/mofdb_database/
├── DEPLOYMENT_GUIDE.md          # 部署指南 (本文件)
├── agent_web.log               # Agent Web 日志
├── Mofdb_Agent/                # Agent 目录
│   ├── __init__.py
│   ├── agent.py               # Agent 主文件
│   └── agent.log              # Agent 日志
├── mofdb_client/               # MOFdb 客户端库
│   ├── __init__.py
│   ├── main.py
│   └── ... (其他客户端文件)
├── Mofdb_Server/               # MOF Server 目录
│   ├── server.py              # Server 主文件
│   ├── utils.py               # 工具函数
│   ├── server.log             # Server 日志
│   └── materials_data_mofdb/  # 输出数据目录
└── mofdb_test/                 # 测试目录
    ├── test_server.py
    └── ... (测试文件)
```

## 🌐 连接信息

### 📡 服务器信息
- **服务器内网 IP:** `10.5.96.245`
- **MOF Server 端口:** `50004`
- **Agent Web UI 端口:** `50005`

### 🔗 访问地址

**本地访问 (服务器内部):**
- MOF Server: `http://localhost:50004`
- Agent Web UI: `http://localhost:50005`

**远程访问 (从您的本地电脑):**
- MOF Server: `http://10.5.96.245:50004`
- Agent Web UI: `http://10.5.96.245:50005`

**注意:** 请将 `10.5.96.245` 替换为您服务器的实际公网 IP 地址

## 🌐 本地连接方式

### 方法 1: 直接访问 Web UI
```
http://10.5.96.245:50005
```

### 方法 2: API 调用
```bash
# 获取 Agent 信息
curl http://10.5.96.245:50005/agents

# 与 Agent 对话
curl -X POST http://10.5.96.245:50005/agents/MOFdb_Agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "我想查找原子数小于50的MOF"}'
```

### 方法 3: 使用 ADK 客户端
```python
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner

# 连接到远程 Agent
agent_url = "http://10.5.96.245:50005/agents/MOFdb_Agent"
# 使用相应的客户端代码连接
```

## 🔧 环境配置

### 服务器端环境变量
```bash
# 在 /home/Mr-Dice/mofdb_database/Mofdb_Agent/.env
SERVER_URL=http://localhost:50004
BOHRIUM_ACCESS_KEY=your_key_here
BOHRIUM_PROJECT_ID=your_project_id_here
```

### 本地客户端配置
```python
# 设置服务器地址
SERVER_URL = "http://10.5.96.245:50004"  # MOF Server
AGENT_URL = "http://10.5.96.245:50005"   # Agent Web UI
```

## 📋 测试连接

### 1. 测试 MOF Server
```bash
curl http://10.5.96.245:50004/health
```

### 2. 测试 Agent Web UI
```bash
curl http://10.5.96.245:50005/docs
```

### 3. 测试 Agent 功能
```bash
curl -X POST http://10.5.96.245:50005/agents/MOFdb_Agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "查找原子数小于10的MOF"}'
```

## 🛠️ 故障排除

### 检查进程状态
```bash
ps aux | grep -E "(server.py|adk)" | grep -v grep
```

### 查看日志
```bash
# MOF Server 日志
tail -f /home/Mr-Dice/mofdb_database/Mofdb_Server/server.log

# Agent Web 日志
tail -f /home/Mr-Dice/mofdb_database/agent_web.log
```

### 重启服务
```bash
# 停止服务
pkill -f server.py
pkill -f adk

# 重启 MOF Server
cd /home/Mr-Dice/mofdb_database/Mofdb_Server
nohup python server.py --port 50004 --host 0.0.0.0 --log-level INFO > server.log 2>&1 &

# 重启 Agent
cd /home/Mr-Dice/mofdb_database
nohup adk web --port 50005 --host 0.0.0.0 Mofdb_Agent > agent_web.log 2>&1 &
```

## 📝 使用示例

### 通过 Web UI
1. 打开浏览器访问 `http://10.5.96.245:50005`
2. 选择 "MOFdb_Agent"
3. 在聊天界面输入查询，例如：
   - "查找原子数小于50的MOF"
   - "查找比表面积大于1000 m²/g的MOF"
   - "查找CoREMOF 2019数据库中的MOF"

### 通过 API
```python
import requests

# 发送查询到 Agent
response = requests.post(
    "http://10.5.96.245:50005/agents/MOFdb_Agent/chat",
    json={"message": "查找原子数小于50的MOF"}
)

print(response.json())
```

## 🔒 安全注意事项

1. 确保防火墙允许端口 50004 和 50005
2. 考虑使用 HTTPS 进行生产环境
3. 设置适当的访问控制
4. 定期更新依赖包

## 📞 支持

如果遇到问题，请检查：
1. 服务器进程是否正在运行
2. 端口是否可访问
3. 环境变量是否正确设置
4. 日志文件中的错误信息
