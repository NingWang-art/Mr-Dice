#!/bin/bash

# 停止服务 - 精确匹配
pkill -f "server.py.*50001"
pkill -f "adk web.*50002"

# 重启 MOF Server
source /home/Mr-Dice/mofdbsql_database/Mofdb_Server/bohrium_setup_env.sh
cd /home/Mr-Dice/mofdbsql_database/Mofdb_Server
source export_test_env.sh
nohup python server.py --port 50001 > server.log 2>&1 &

# 重启 Agent
cd /home/Mr-Dice/mofdbsql_database
nohup adk web --port 50002 --host 0.0.0.0 > agent_web.log 2>&1 &