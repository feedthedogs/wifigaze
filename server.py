import asyncio
import subprocess
import websockets
import ssl

# WebSocket server port
websocket_port = 8765

# Define channels to monitor for 2.4 GHz and 5 GHz
#channels_24ghz = [1, 6, 11]
#channels_5ghz = [36, 40, 44, 48, 149, 153, 157, 161]
channels = [1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161]  # Channels to hop through

hopping_interval = 0.2  # Time (in seconds) between channel changes

# Define dwell time (in seconds) on each channel
#dwell_time = 1

# Assign interfaces to channels (you can modify this)
#interfaces = {
#    "wlan1": channels_24ghz,
#    "wlan2": channels_5ghz,
#}
interfaces = ["wlan1", "wlan2"]

# Dictionary to hold tshark processes
tshark_processes = {}

global_websocket = None
# WebSocket clients
websocket_clients = set()

async def websocket_server(websocket):
    """Handle WebSocket connections."""
    global websocket_clients
    global global_websocket
    global_websocket = websocket
    websocket_clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        websocket_clients.remove(websocket)

async def broadcast(data):
    """Send data to all connected WebSocket clients."""
    #if websocket_clients:
    #    await asyncio.wait([client.send(data) for client in websocket_clients])
    if global_websocket and len(websocket_clients) > 0:
        try:
            await global_websocket.send(data)
        except Exception as e:
            print(e)


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
    process = await asyncio.create_subprocess_exec(
        *tshark_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    async for line in process.stdout:
        decoded_line = bytes.decode(line).strip()
        ta, ra, sa, da, length, ssid, bssid, frequency, flags, frame_type, frame_subtype = decoded_line.split(',')
        #packet_type = decoded_line[-8:-7]
        #packet_subtype = decoded_line[-6:]
        if filter_macs(ta): continue
        if filter_macs(ra): continue
        if filter_macs(sa): continue
        if filter_macs(da): continue

        if frame_type == '1':
            continue # control frames
        if frame_type == '0' and frame_subtype not in ['0x0000', '0x0001', '0x0002', '0x0003', '0x0004', '0x0005', '0x0008', '0x000c']:
            continue # management frames
        if frame_type == '2' and frame_subtype in ['0x0024']:
            continue # data frames
        #if decoded_line[18:35] == 'ff:ff:ff:ff:ff:ff': continue # broadcasts - can we trust the ssid here?
        #if decoded_line[0] == ',': continue # no transmit address (probably an ack)
        #if decoded_line[-8:-7] == '1': continue # control packets

        #if ta == '5a:ca:59:30:c1:e6' or ra == '5a:ca:59:30:c1:e6' or sa == '5a:ca:59:30:c1:e6' or da == '5a:ca:59:30:c1:e6':
        #    print("odd")
        #if ta == '4a:29:52:ef:e4:66' or ra == '4a:29:52:ef:e4:66' or sa == '4a:29:52:ef:e4:66' or da == '4a:29:52:ef:e4:66':            
        #    print("odd")

        await broadcast(decoded_line)  # Send parsed data to WebSocket clients
    if process.stderr:
        print(process.stderr)
    tshark_processes[interface] = process

def stop_tshark(interface):
    """Stop a tshark process."""
    if interface in tshark_processes:
        tshark_processes[interface].terminate()
        tshark_processes[interface].wait()
        del tshark_processes[interface]

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

async def hop_channels():
    """Continuously change channels on all interfaces."""
    loop_count = 0
    while True:
        selected_items = evenly_distributed_selection(channels, len(interfaces), loop_count)
        for index, channel in enumerate(selected_items):
            #print(f"Changing interface {interfaces[index]} to channel {str(channel)}")
            process = await asyncio.create_subprocess_exec(
                "sudo", "iwconfig", interfaces[index], "channel", str(channel)
            )
            await process.wait()
            if process.stderr is not None:
                for line in process.stderr:
                    print(line)  
        loop_count += 1
        if loop_count > 1000000: loop_count = 0
        await asyncio.sleep(hopping_interval)

# WebSocket server setup
async def start_websocket_server():
    """Start the WebSocket server."""
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)  # Might need to use ssl.PROTOCOL_TLS for older versions of Python
        context.load_cert_chain(certfile='cert.pem', keyfile='key.pem', password='123456')
        print(f"Starting WebSocket server on port {websocket_port}...")
        async with websockets.serve(websocket_server, "0.0.0.0", websocket_port, ssl=context) as server:
            await server.wait_closed()
    except Exception as e:
        print(f"WebSocket server failed to start: {e}")

def evenly_distributed_selection(arr, count, loop_count):
    """Select `count` evenly distributed items from `arr` for the current `loop_count`."""
    step = len(arr) // count
    indices = [(i + loop_count) % len(arr) for i in range(0, len(arr), step)][:count]
    return [arr[i] for i in indices]        

async def run_tasks():
    tasks = list()
    # Start tshark processes for all interfaces
    for interface in interfaces:
        tasks.append(asyncio.create_task(start_tshark(interface)))

    # Start channel hopping in a separate thread
    #threading.Thread(target=hop_channels, daemon=True).start()
    tasks.append(asyncio.create_task(hop_channels()))

    # Start the WebSocket server
    tasks.append(asyncio.create_task(start_websocket_server()))
    await asyncio.gather(*tasks)
    print("here?")

def main():
    """Main function to start tshark and channel hopping."""
    try:
        #loop = asyncio.get_event_loop()
        
        asyncio.run(run_tasks())

        #loop.run_until_complete()
        #loop.close()

    except KeyboardInterrupt:
        print("Stopping...")
        # Stop all tshark processes
        for interface in interfaces:
            stop_tshark(interface)

if __name__ == "__main__":
    main()
