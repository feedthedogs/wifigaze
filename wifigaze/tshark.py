import asyncio
import subprocess
import os

from loguru import logger

from .processframe import filter_frames

async def start_tshark(interface, broadcast):
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
    logger.trace(f"running command: {tshark_command}")
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
                logger.trace(f"ignored duplicate frame: {decoded_line}")
                continue
            last_line = decoded_line

            if not filter_frames(decoded_line): continue

            logger.trace(f"data: {decoded_line}")
            await broadcast(decoded_line)  # Send parsed data to WebSocket clients
        if process.stderr:
            logger.error(f"{process.stderr}")
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
            logger.error(f"{e}")