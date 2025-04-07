sudo systemctl stop url-checker.service
yes | cp /home/url-checker/url-checker.service /usr/lib/systemd/system
systemctl daemon-reload
sudo systemctl start url-checker.service