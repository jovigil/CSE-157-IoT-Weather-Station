#! /usr/bin/sh

# set up the pi for ad-hoc networking mode
sudo cp /etc/network/interfaces.adhoc /etc/network/interfaces
sudo systemctl stop dhcpcd
sudo systemctl disable dhcpcd
sudo ifup wlan0
sudo systemctl enable isc-dhcp-server
sudo systemctl start isc-dhcp-server
#sudo reboot
