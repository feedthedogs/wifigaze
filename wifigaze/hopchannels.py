import signal
import asyncio
import os

from loguru import logger

async def run_command_with_signal_handling(command):
    # Check if running as root
    if os.geteuid() == 0 and command[0] == "sudo":
        command = command[1:]  # Remove 'sudo' if running as root
    
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

# Define channels to monitor for 2.4 GHz and 5 GHz
#channels_24ghz = [1, 6, 11]
#channels_5ghz = [36, 40, 44, 48, 149, 153, 157, 161]
#channels = [1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161]  # Channels to hop through

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

def evenly_distributed_selection(arr, count, loop_count):
    """Select `count` evenly distributed items from `arr` for the current `loop_count`."""
    if not arr or count <= 1 or len(arr) == 1:
        return [arr[loop_count % len(arr)]]
    
    # Regular case
    step = len(arr) // count
    indices = [(i + loop_count) % len(arr) for i in range(0, len(arr), step)][:count]
    return [arr[i] for i in indices] 