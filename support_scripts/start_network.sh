#!/bin/bash


SSID="TikiTime"
PASSWORD=""

start_adhoc() {
	echo "Starting ad-hoc networking..."
	sudo systemctl stop wpa_supplicant
	sudo systemctl stop dhcpd
	sudo systemctl start dnsmasq
	sudo systemctl start hostapd
}

# Function to connect to TikiTime
connect_to_tikitime() {
	echo "Connecting to $SSID..."
	sudo systemctl stop hotapd
	sudo systemctl stop dnsmasq

	cat <<EOF > /etc/wpa_supplicant/wpa_supplicant.conf
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
  ssid="$SSID"
  psk="$PASSWORD"
  key_mgmt=WPA-PSK
}
EOF

  sudo systemctl daemon-reload
  sudo systemctl restart dhcpd
  sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
  sudo dhclient wlan0
}

# Check if TikiTime is available
if iwlist wlan0 scan | grep -q "$SSID"; then
    connect_to_tikitime
else
    start_adhoc
fi
