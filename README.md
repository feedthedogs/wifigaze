# WifiGaze
WifiGaze is a network security tool designed to:
- Observe WiFi devices in your proximity.
- Create a graph of all devices they communicate with, including non-wireless devices if a WiFi device is interacting with them.
- Incrementally discover more devices as it hops through all available WiFi channels.

Features:
- Reveals devices on networks without decrypting any traffic.
- Web interface that can be accessed locally or configured remotely
- Supports exporting and importing of graphs.

### Requirements
To use WifiGaze, you need:
1. Python3
2. Wireless network interface(s) in monitor mode - See [Example configuring of Monitor mode](https://github.com/aircrack-ng/rtl8812au).
3. Sudo/root access - root is required to hop between wifi channels, if you have the same number of channels as wlan interfaces there is no requirement for root

### Running WifiGaze

Run WifiGaze with default settings and the first WLAN interface:
```
  wifigaze --interfaces=wlan0
```

For WLAN interfaces that don't support 5GHz, limit the channels to scan:
```
  wifigaze --interfaces=wlan1 --channels=1,6,11
```

Command Line Options:

| Option | Description | Default |
| ------ | ----------- | ------- |
| --interfaces=<interfaces> | List of WLAN interfaces to use (e.g., wlan0,wlan1). | |
| --channels=<channels> | List of channels to scan. | 1,6,11,36,40,44,48,149,153,157,161 |
| --channel-dwell-time=<seconds> | Time to listen on each channel before switching. | 1 |
| --no-monitormode | Launches without listening to WLAN interfaces. | |
| --preload-graph=<path to json> | Preload a previously exported graph. | None |
| --listen-ip=<ip> | IP address to listen on. | 127.0.0.1 |
| --listen-port=<port> | Port to listen on. | 8765 |
| --no-browser | Do not launch the browser interface. | |
| --log-level=<level> | Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL). | INFO |
| -h, --help | Display help message and exit. | |

## Building the Project

WifiGaze requires Python 3 and Node.js to build. Use the following commands: 
```
python -m pip install --user setuptools wheel
python setup.py sdist bdist_wheel
```



