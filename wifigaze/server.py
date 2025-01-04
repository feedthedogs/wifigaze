"""
WLAN Channel Hopper and Server Setup.

Usage:
  wifigaze --interfaces=<interfaces> [--channels=<channels>...] [--channel-dwell-time=<seconds>] [--preload-graph=<path to json>] [--listen-ip=<ip>] [--listen-port=<port>] [--log-level=<level>]
  wifigaze (-h | --help)

Examples:
  wifigaze --interfaces=wlan0
  wifigaze --interfaces=wlan1 --channels=1,6,11  (if you have an 802.11bg interface)

Options:
  --interfaces=<interfaces>          List of WLAN interfaces to use (e.g. wlan0,wlan1).
  --channels=<channels>              List of channels to scan [default: 1,6,11,36,40,44,48,149,153,157,161].
  --channel-dwell-time=<seconds>     Time interface should listen on channel before moving to the next [default: 1]
  --preload-graph=<path to json>     Preload graph that was previously exported [default: None]
  --listen-ip=<ip>                   IP address to listen on [default: 127.0.0.1].
  --listen-port=<port>               Port to listen on [default: 8765].
  --log-level=<level>                Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL) [default: INFO].
  -h --help                          Show this help message and exit.
"""

import asyncio
import subprocess
from quart import Quart, websocket, send_from_directory
import asyncio
import os
import sys
import signal
from enum import StrEnum
from docopt import docopt
from loguru import logger

# Define channels to monitor for 2.4 GHz and 5 GHz
#channels_24ghz = [1, 6, 11]
#channels_5ghz = [36, 40, 44, 48, 149, 153, 157, 161]
#channels = [1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161]  # Channels to hop through

async def run_command_with_signal_handling(command):
    # Start the subprocess
    process = await asyncio.create_subprocess_exec(*command)
    
    def handle_signal():
        print("Received SIGINT, terminating subprocess...")
        process.terminate()  # Send SIGTERM to the subprocess
        # Alternatively: process.send_signal(signal.SIGINT) for SIGINT
        loop.stop()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, handle_signal)

    try:
        # Wait for the process to complete
        await process.communicate()
    finally:
        # Cleanup: Ensure no signal handlers are left behind
        loop.remove_signal_handler(signal.SIGINT)

async def start_tshark(interface):
    """Start a tshark process to capture packets on an interface."""
    tshark_command = [
            "tshark",
            "-i", interface,
            "-l",  # Line-buffered output
            "-Y", "wlan",
            '-T', 'fields', 
            '-e', 'wlan.ta', '-e', 'wlan.ra', '-e', 'wlan.sa', '-e', 'wlan.da', '-e', 'frame.len', '-e', 'wlan.ssid', '-e', 'wlan.bssid', '-e', 'radiotap.channel.freq', '-e', 'wlan.flags.str', '-e', 'wlan.fc.type', '-e', 'wlan.fc.type_subtype',
            '-E', 'separator=,'
        ]
    logger.trace(f"tshark: running command: {tshark_command}")
    try:
        process = await asyncio.create_subprocess_exec(
            *tshark_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
            , preexec_fn=os.setpgrp
        )
        last_line = ''
        async for line in process.stdout:
            decoded_line = bytes.decode(line).strip()
            if last_line == decoded_line:
                logger.trace(f"tshark: ignored duplicate frame: {decoded_line}")
                continue
            last_line = decoded_line
            ta, ra, sa, da, length, ssid, bssid, frequency, flags, frame_type, frame_subtype = decoded_line.split(',')
            if filter_macs(ta):
                logger.trace(f"tshark: ignored mac ta: {decoded_line}")
                continue
            if filter_macs(ra):
                logger.trace(f"tshark: ignored mac ra: {decoded_line}")
                continue
            if filter_macs(sa):
                logger.trace(f"tshark: ignored mac sa: {decoded_line}")
                continue
            if filter_macs(da): 
                logger.trace(f"tshark: ignored mac da: {decoded_line}")
                continue

            if frame_type == '1':
                logger.trace(f"tshark: ignore control frames: {decoded_line}")
                continue # control frames
            if frame_type == '0' and frame_subtype in [ WLANFrameSubtype.ATIM,
                                                        WLANFrameSubtype.DISASSOCIATION,
                                                        WLANFrameSubtype.AUTHENTICATION,  
                                                        WLANFrameSubtype.ACTION,
                                                        WLANFrameSubtype.ACTION_NO_ACK]:
                logger.trace(f"tshark: ignore some management frames: {decoded_line}")
                continue # management frames
            if frame_type == '2' and frame_subtype in [WLANFrameSubtype.NULL]:
                logger.trace(f"tshark: ignore null data frames: {decoded_line}")
                continue # data frames
            logger.trace(f"tshark: data: {decoded_line}")
            await broadcast(decoded_line)  # Send parsed data to WebSocket clients
        if process.stderr:
            logger.error(f"tshark: {process.stderr}")
    except FileNotFoundError:
        logger.error("Tshark is not installed or not in the system PATH.")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Tshark exists but there was an error executing it: {e}")
        return False
    finally:
        process.terminate()
        try:
            await process.wait()
        except Exception as e:
            logger.error(f"tshark: {e}")

def filter_macs(mac):
    if mac.startswith("01:00:5e"):
        return True # multicast group
    if mac.startswith("33:33"):
        return True # ipv6 multicast group
    #if decoded_line[0:17] in ["ff:ff:ff:ff:ff:ff", '00:00:00:00:00:00', '01:00:00:00:00:00', '00:00:00:00:00:ff'] or decoded_line[18:35] in ["ff:ff:ff:ff:ff:ff", '00:00:00:00:00:00', '01:00:00:00:00:00', '00:00:00:00:00:ff']:
    #    continue # broadcast, special mac addresses, wps setup, vendor special management
    if mac.startswith("01:80:c2:00:00"):
        return True # IEEE Std 802.1D and IEEE Std 802.1Q Reserved Addresses
    if mac.startswith("03:00:00:00:00"):
        return True # Locally Administered Group MAC Addresses Used by IEEE Std 802.5
    if mac in ['09:00:2B:00:00:04', '09:00:2B:00:00:04']:
        return True # Group MAC Addresses Used in ISO 9542 ES-IS Protocol
    if mac in ['01:00:0c:cc:cc:cc', '01:00:0c:cc:cc:cd', '01:1b:19:00:00:00']:
        return True # Cisco Systems, IEEE
    if mac.startswith("01:0c:cd:01:00") or mac.startswith("01:0c:cd:02:0") or mac.startswith("01:0c:cd:04:0"):
        return True # IEC
    return False

async def hop_channels(interfaces, channels, channel_dwell_time):
    """Continuously change channels on all interfaces."""
    loop_count = 0
    while True:
        selected_items = evenly_distributed_selection(channels, len(interfaces), loop_count)
        for index, channel in enumerate(selected_items):
            logger.trace(f"channels: sudo iwconfig {interfaces[index]} channel {str(channel)}")
            #process = await asyncio.create_subprocess_exec(
            #    "sudo", "iwconfig", interfaces[index], "channel", str(channel)
            #)
            command = ["sudo", "iwconfig", interfaces[index], "channel", str(channel)]
            await run_command_with_signal_handling(command)

        # if we have same number of channels per interfaces we don't need to rotate, so exit
        if len(interfaces) == len(channels):
            logger.trace(f"channels: quitting due to having the same number of channels as interfaces, no need to rotate")
            break

        loop_count += 1
        if loop_count > 1000000: loop_count = 0

        await asyncio.sleep(channel_dwell_time)

# Create Quart app
app = Quart(__name__, static_folder='static')

@app.route('/')
async def serve_index():
    logger.info(f"webserver: 404 not found: {app.static_folder} index.html")
    return await send_from_directory(app.static_folder, "index.html")

@app.route('/<path:path>')
async def serve_static_files(path):
    """
    Serve static files like JavaScript, CSS, and assets from Vue.js build folder.
    """
    file_path = os.path.join(app.static_folder, path)
    if os.path.exists(file_path):
        logger.info(f"webserver: {app.static_folder}: {path}")
        return await send_from_directory(app.static_folder, path)
    logger.info(f"webserver: 404 not found: {path}")
    return "File not found", 404

# WebSocket connections storage
connected_clients = set()

# WebSocket endpoint
@app.websocket('/ws')
async def ws():
    # Add client to the connected_clients set
    connected_clients.add(websocket._get_current_object())
    logger.info(f"websocket: client connected")
    try:
        while True:
            # Receive data from the client
            data = await websocket.receive()
            logger.trace(f"websocket: recieved data: {data}")
    except asyncio.CancelledError:
        pass
    finally:
        # Remove client from the set when they disconnect
        connected_clients.remove(websocket._get_current_object())
        logger.info(f"websocket: client disconnected")

@app.before_serving
async def startup():
    # Start tshark processes for all interfaces
    for interface in app.interfaces:
        app.add_background_task(start_tshark, interface) 

    # Start channel hopping for each interface
    app.add_background_task(hop_channels, app.interfaces, app.channels, app.channel_dwell_time)
    logger.info(f"webserver: Started")

async def broadcast(data):
    # Broadcast the data to all connected clients
    for client in connected_clients:
        await client.send(data)

# Function for running Hypercorn
async def run_quart(listen_ip, listen_port, interfaces, channels, channel_dwell_time):
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"{listen_ip}:{listen_port}"]

    app.interfaces = interfaces
    app.channels = channels
    app.channel_dwell_time = channel_dwell_time

    # Run the Hypercorn server
    await serve(app, config)

def evenly_distributed_selection(arr, count, loop_count):
    """Select `count` evenly distributed items from `arr` for the current `loop_count`."""
    if not arr or count <= 1 or len(arr) == 1:
        return [arr[loop_count % len(arr)]]
    
    # Regular case
    step = len(arr) // count
    indices = [(i + loop_count) % len(arr) for i in range(0, len(arr), step)][:count]
    return [arr[i] for i in indices]

class WLANFrameSubtype(StrEnum):
    # Management Frame Subtypes
    ASSOCIATION_REQUEST = "0x0000"
    ASSOCIATION_RESPONSE = "0x0001"
    REASSOCIATION_REQUEST = "0x0002"
    REASSOCIATION_RESPONSE = "0x0003"
    PROBE_REQUEST = "0x0004"
    PROBE_RESPONSE = "0x0005"
    BEACON = "0x0008"
    ATIM = "0x0009"  # Announcement Traffic Indication Message
    DISASSOCIATION = "0x000A"
    AUTHENTICATION = "0x000B"
    DEAUTHENTICATION = "0x000C"
    ACTION = "0x000D"
    ACTION_NO_ACK = "0x000E"

    # Control Frame Subtypes
    BLOCK_ACK_REQUEST = "0x0018"
    BLOCK_ACK = "0x0019"
    PS_POLL = "0x001A"
    RTS = "0x001B"
    CTS = "0x001C"
    ACK = "0x001D"
    CF_END = "0x001E"
    CF_END_ACK = "0x001F"

    # Data Frame Subtypes
    DATA = "0x0020"
    DATA_CF_ACK = "0x0021"
    DATA_CF_POLL = "0x0022"
    DATA_CF_ACK_CF_POLL = "0x0023"
    NULL = "0x0024"
    CF_ACK = "0x0025"
    CF_POLL = "0x0026"
    CF_ACK_CF_POLL = "0x0027"
    QOS_DATA = "0x0028"
    QOS_DATA_CF_ACK = "0x0029"
    QOS_DATA_CF_POLL = "0x002A"
    QOS_DATA_CF_ACK_CF_POLL = "0x002B"
    QOS_NULL = "0x002C"
    QOS_CF_POLL = "0x002E"
    QOS_CF_ACK_CF_POLL = "0x002F"   

async def main(arguments):

    # Parse arguments
    interfaces = arguments["--interfaces"].split(',')
    channels = list(map(int, arguments["--channels"][0].split(',')))
    channel_dwell_time = int(arguments["--channel-dwell-time"])
    graph_json = arguments["--preload-graph"]
    listen_ip = arguments["--listen-ip"]
    listen_port = int(arguments["--listen-port"])
    log_level = arguments["--log-level"].upper()

    if type(interfaces) != list:
        interfaces = [interfaces]
    if type(channels) != list:
        channels = [channels]

    logger.remove(0)
    logger.add(sys.stdout, level=log_level)

    logger.info("Script started with the following arguments:")
    logger.info(f"WLAN Interfaces: {interfaces}")
    logger.info(f"Channels: {channels}")
    logger.info(f"Channel dwell time: {channel_dwell_time}s")
    logger.info(f"Preload graph: {graph_json}")
    logger.info(f"Listen IP: {listen_ip}")
    logger.info(f"Listen Port: {listen_port}")
    logger.info(f"Log Level: {log_level}") 

    """Main function to start tshark and channel hopping."""
    await run_quart(listen_ip, listen_port, interfaces, channels, channel_dwell_time)

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