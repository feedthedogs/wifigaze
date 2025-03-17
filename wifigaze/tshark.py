import asyncio
import json
import pyshark
from pyshark.packet.packet import Packet
from loguru import logger
from concurrent.futures import ThreadPoolExecutor

from .processframe import filter_frames

def capture_packets(interface, queue):
    """Capture packets using pyshark and process them."""
    pyshark.tshark.output_parser.tshark_ek.packet_from_ek_packet = packet_from_ek_packet
    
    capture = pyshark.LiveCapture(
        interface=interface,
        display_filter='wlan',
        only_summaries=False,
        use_ek=True,
        custom_parameters=[
            '-e', 'wlan.ta', '-e', 'wlan.ra', '-e', 'wlan.sa', '-e', 'wlan.da', '-e', 'frame.len', '-e', 'wlan.ssid', '-e', 'wlan.bssid', '-e', 'radiotap.channel.freq', '-e', 'wlan.flags.str', '-e', 'wlan.fc.type', '-e', 'wlan.fc.type_subtype'
        ]
    )
    logger.trace(f"running pyshark capture on interface: {interface}")

    for packet in capture.sniff_continuously():
        try:
            dist_packet = make_packet_dictionary(packet)
            if not filter_frames(dist_packet):
                continue
            logger.trace(f"data: {dist_packet}")
            packet_string = dist_packet
            if queue.full():
                logger.warning("Queue is full, dropping packet")
            else:
                asyncio.run(queue.put(packet_string))  # Put parsed data into the queue
        except Exception as e:
            logger.error(f"Error processing packet: {e}")
            continue

def make_packet_dictionary(packet):
    packet_dict = {}
    for field in packet.layers['layers']:
        packet_dict[field] = packet.layers['layers'][field][0]
    return packet_dict

async def start_tshark(interface, queue):
    """Start a pyshark process to capture packets on an interface."""
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, capture_packets, interface, queue)

    logger.trace("Pyshark capture started.")

def packet_from_ek_packet(json_pkt):
    pkt_dict = json.loads(json_pkt.decode('utf-8'))

    return Packet(layers=pkt_dict, frame_info=None,
                  number=0,
                  length=1,
                  sniff_time=0,
                  interface_captured=None)