"""
WLAN Channel Hopper and Server Setup.

Usage:
  wifigaze --interfaces=<interfaces> [--channels=<channels>...] [--channel-dwell-time=<seconds>] [--no-monitormode] [--preload-graph=<path to json>] [--listen-ip=<ip>] [--listen-port=<port>] [--no-browser] [--log-level=<level>]
  wifigaze (-h | --help)

Examples:
  wifigaze --interfaces=wlan0
  wifigaze --interfaces=wlan1 --channels=1,6,11  (if you have an 802.11bg interface)

Options:
  --interfaces=<interfaces>          List of WLAN interfaces to use (e.g. wlan0,wlan1).
  --channels=<channels>              List of channels to scan [default: 1,6,11,36,40,44,48,149,153,157,161].
  --channel-dwell-time=<seconds>     Time interface should listen on channel before moving to the next [default: 1]
  --no-monitormode                   Launches the interface without listening to the wlan interfaces
  --preload-graph=<path to json>     Preload graph that was previously exported [default: None]
  --listen-ip=<ip>                   IP address to listen on [default: 127.0.0.1].
  --listen-port=<port>               Port to listen on [default: 8765].
  --no-browser                       Do not launch the browser interface
  --log-level=<level>                Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL) [default: INFO].
  -h --help                          Show this help message and exit.
"""

import asyncio
import sys
import webbrowser

from docopt import docopt
from loguru import logger

from .webserver import run_quart

async def main(arguments):

    # Parse arguments
    interfaces = arguments["--interfaces"].split(',')
    channels = list(map(int, arguments["--channels"][0].split(',')))
    channel_dwell_time = int(arguments["--channel-dwell-time"])
    no_monitormode = arguments["--no-monitormode"]
    graph_json = arguments["--preload-graph"]
    listen_ip = arguments["--listen-ip"]
    listen_port = int(arguments["--listen-port"])
    no_browser = arguments["--no-browser"]
    log_level = arguments["--log-level"].upper()

    if type(interfaces) != list:
        interfaces = [interfaces]
    if type(channels) != list:
        channels = [channels]

    logger.remove(0)
    logger.add(sys.stdout, level=log_level)

    logger.info("Script started with the following arguments:")
    if not no_monitormode:
        logger.info(f"WLAN Interfaces: {interfaces}")
        logger.info(f"Channels: {channels}")
        logger.info(f"Channel dwell time: {channel_dwell_time}s")
    else:
        logger.info(f"Not listening to wlan interfaces due to no-monitormode flag")
    logger.info(f"Preload graph: {graph_json}")
    logger.info(f"Listen IP: {listen_ip}")
    logger.info(f"Listen Port: {listen_port}")
    logger.info(f"Log Level: {log_level}")

    if not no_browser:
        url = f"http://{listen_ip}:{listen_port}/"
        webbrowser.open(url)

    """Main function to start tshark and channel hopping."""
    await run_quart(listen_ip, listen_port, interfaces, channels, channel_dwell_time, no_monitormode, graph_json)

def main_cli():
    """
    Command-line entry point for the module.
    """

    # Parse arguments using docopt
    arguments = docopt(__doc__)  

    # Run the async main logic
    try:
        asyncio.run(main(arguments))
    except KeyboardInterrupt:
        logger.info("Closing")

if __name__ == "__main__":
    main_cli()