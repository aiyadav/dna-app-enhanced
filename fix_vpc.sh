#!/bin/bash
cd /home/ec2-user/dna-app-enhanced
sudo sed -i '307,310d' app.py
sudo sed -i '306a\        sts = session.client('"'"'sts'"'"', region_name=region)' app.py
sudo pkill -9 python3.11
sleep 2
sudo nohup python3.11 app.py > nohup.out 2>&1 &
sleep 3
ps aux | grep app.py | grep -v grep
