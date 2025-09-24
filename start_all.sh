pkill -f "python"

cd /home/Mr_Dice/bohriumpublic_database/Bohriumpublic_Server
source bohrium_setup_env.sh
source export_test_env.sh
nohup python server.py 2>&1 &

cd /home/Mr_Dice/mofdb_database/Mofdb_Server
nohup python server.py 2>&1 &

cd /home/Mr_Dice/openlam_database/Openlam_Server
nohup python server.py 2>&1 &

cd /home/Mr_Dice/optimade_database/Optimade_Server
nohup python server.py 2>&1 &