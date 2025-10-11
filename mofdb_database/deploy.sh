#!/bin/bash

# 停止服务 - 精确匹配
pkill -f "server.py.*50003"
pkill -f "adk web.*50004"

# 重启 MOF Server
source /home/Mr-Dice/mofdb_database/Mofdb_Server/bohrium_setup_env.sh
cd /home/Mr-Dice/mofdb_database/Mofdb_Server
source export_test_env.sh
nohup python server.py --port 50003 > server.log 2>&1 &

# 重启 Agent
cd /home/Mr-Dice/mofdb_database
nohup adk web --port 50004 --host 0.0.0.0 > agent_web.log 2>&1 &