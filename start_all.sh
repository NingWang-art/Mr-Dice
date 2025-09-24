pkill -f "python"

cd /home/Mr_Dice/bohriumpublic_database/Bohriumpublic_Server
source bohrium_setup_env.sh
source export_test_env.sh
nohup python server.py 2>&1 &
echo "Bohrium public server started"

cd /home/Mr_Dice/mofdb_database/Mofdb_Server
nohup python server.py 2>&1 &
echo "MOFdb server started"

cd /home/Mr_Dice/openlam_database/Openlam_Server
nohup python server.py 2>&1 &
echo "OpenLAM server started"

cd /home/Mr_Dice/optimade_database/Optimade_Server
nohup python server.py 2>&1 &
echo "Optimade server started"

ps -ef | grep "python"