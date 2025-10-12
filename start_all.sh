pkill -f "python"

cd /home/Mr-Dice/bohriumpublic_database/Bohriumpublic_Server
source bohrium_setup_env.sh
source export_test_env.sh
nohup python server.py --port 50001 2>&1 &
echo "Bohrium public server started"

cd /home/Mr-Dice/mofdbsql_database/Mofdb_Server
nohup python server.py --port 50002 2>&1 &
echo "MOFdb SQL server started"

cd /home/Mr-Dice/openlam_database/Openlam_Server
nohup python server.py --port 50003 2>&1 &
echo "OpenLAM server started"

cd /home/Mr-Dice/optimade_database/Optimade_Server
nohup python server.py --port 50004 2>&1 &
echo "Optimade server started"

ps -ef | grep "python"