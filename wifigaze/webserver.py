import asyncio
import os
import json
from asyncio import QueueEmpty

from quart import Quart, websocket, send_from_directory, send_file, Response
from loguru import logger

from .tshark import start_tshark, replay_pcap
from .hopchannels import hop_channels

QUEUE_MAXSIZE = 20000
BATCH_MAX_ITEMS = 200
BATCH_MAX_LATENCY_SECONDS = 0.02

# Create Quart app
app = Quart(__name__, static_folder='static')
app.replay_task_started = False

@app.route('/')
async def serve_index():
    logger.info(f"webserver: {app.static_folder} index.html")
    return await send_from_directory(app.static_folder, "index.html")

@app.route('/preload')
async def serve_preload():
    if app.graph_json != 'None':
        logger.info(f"webserver: preloading json: {app.graph_json}")
        response = await send_file(app.graph_json)
        add_api_headers(response) 
        return response
    else:
        logger.info(f"webserver: no preload")
        response = await app.make_response((Response("No preload graph found"), 404))
        add_api_headers(response) 
        return response

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

def add_api_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")  # Allow all origins
    response.headers.add("Access-Control-Allow-Methods", "GET, OPTIONS")  # Specify allowed methods
    response.headers.add("Access-Control-Allow-Headers", "Content-Type") 
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

# WebSocket connections storage
connected_clients = set()

# WebSocket endpoint
@app.websocket('/ws')
async def ws():
    # Add client to the connected_clients set
    connected_clients.add(websocket._get_current_object())
    if app.pcap_file and not app.replay_task_started:
        app.replay_task_started = True
        app.add_background_task(replay_pcap, app.pcap_file, app.queue, app.loop)
    logger.info(f"websocket: client connected")
    try:
        while True:
            # Receive data from the client
            data = await websocket.receive()
            logger.trace(f"websocket: received data: {data}")
    except asyncio.CancelledError:
        pass
    finally:
        # Remove client from the set when they disconnect
        connected_clients.remove(websocket._get_current_object())
        logger.info(f"websocket: client disconnected")

@app.before_serving
async def startup():
    capture_started = False
    app.loop = asyncio.get_running_loop()
    app.replay_task_started = False

    if app.pcap_file:
        app.queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        app.add_background_task(broadcast)
        capture_started = True
    elif not app.no_monitormode:
        # Create a queue for broadcasting data
        app.queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)

        # Start tshark processes for all interfaces
        for interface in app.interfaces:
            app.add_background_task(start_tshark, interface, app.queue, app.loop) 

        # Start channel hopping for each interface
        app.add_background_task(hop_channels, app.interfaces, app.channels, app.channel_dwell_time)

        # Start the broadcast task
        app.add_background_task(broadcast)
        capture_started = True

    if capture_started:
        logger.info("webserver: Started")
    else:
        logger.info("webserver: Started without capture source")

async def broadcast():
    loop = asyncio.get_running_loop()
    while True:
        batch = [await app.queue.get()]
        deadline = loop.time() + BATCH_MAX_LATENCY_SECONDS

        while len(batch) < BATCH_MAX_ITEMS:
            try:
                batch.append(app.queue.get_nowait())
                continue
            except QueueEmpty:
                pass

            timeout = deadline - loop.time()
            if timeout <= 0:
                break

            try:
                batch.append(await asyncio.wait_for(app.queue.get(), timeout=timeout))
            except asyncio.TimeoutError:
                break

        payload = json.dumps(batch, separators=(',', ':'))

        if not connected_clients:
            continue

        clients_snapshot = tuple(connected_clients)
        send_tasks = [client.send(payload) for client in clients_snapshot]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        for client, result in zip(clients_snapshot, results):
            if isinstance(result, Exception):
                connected_clients.discard(client)
                logger.debug(f"websocket: removed client after send failure: {result}")

# Function for running Hypercorn
async def run_quart(listen_ip, listen_port, interfaces, channels, channel_dwell_time, no_monitormode, graph_json, pcap_file):
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"{listen_ip}:{listen_port}"]

    app.interfaces = interfaces
    app.channels = channels
    app.channel_dwell_time = channel_dwell_time
    app.graph_json = graph_json
    app.no_monitormode = no_monitormode
    app.pcap_file = pcap_file

    # Run the Hypercorn server
    await serve(app, config)