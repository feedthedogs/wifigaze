import asyncio
import os
import json

from quart import Quart, websocket, send_from_directory, send_file, Response
from loguru import logger

from .tshark import start_tshark
from .hopchannels import hop_channels

# Create Quart app
app = Quart(__name__, static_folder='static')

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
    if not app.no_monitormode:
        # Create a queue for broadcasting data
        app.queue = asyncio.Queue(maxsize=100)

        # Start tshark processes for all interfaces
        for interface in app.interfaces:
            app.add_background_task(start_tshark, interface, app.queue) 

        # Start channel hopping for each interface
        app.add_background_task(hop_channels, app.interfaces, app.channels, app.channel_dwell_time)

        # Start the broadcast task
        app.add_background_task(broadcast)

    logger.info(f"webserver: Started")

async def broadcast():
    while True:
        items = []
        items.append(await app.queue.get())
        # Read data from the queue up to 10 items at a time
        while not app.queue.empty() and len(items) < 10:
            items.append(await app.queue.get())
        # Broadcast the data to all connected clients
        for client in connected_clients:
            await client.send(json.dumps(items))

# Function for running Hypercorn
async def run_quart(listen_ip, listen_port, interfaces, channels, channel_dwell_time, no_monitormode, graph_json):
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"{listen_ip}:{listen_port}"]

    app.interfaces = interfaces
    app.channels = channels
    app.channel_dwell_time = channel_dwell_time
    app.graph_json = graph_json
    app.no_monitormode = no_monitormode

    # Run the Hypercorn server
    await serve(app, config)