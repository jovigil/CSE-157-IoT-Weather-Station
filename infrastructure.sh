#! /usr/bin/sh

# setup the pi for infrastructure networking
sudo cp /etc/network/interfaces.default /etc/network/interfaces
sudo systemctl enable dhcpcd
sudo systemctl start dhcpcd
#sudo reboot
