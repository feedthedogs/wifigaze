import asyncio
import json
from concurrent.futures import ThreadPoolExecutor, CancelledError
from typing import Any, Dict, Optional

import pyshark
from loguru import logger
from pyshark.packet.packet import Packet

from .processframe import filter_frames

CAPTURE_FIELDS = [
    '-e', 'wlan.ta',
    '-e', 'wlan.ra',
    '-e', 'wlan.sa',
    '-e', 'wlan.da',
    '-e', 'frame.len',
    '-e', 'wlan.ssid',
    '-e', 'wlan.bssid',
    '-e', 'radiotap.channel.freq',
    '-e', 'wlan.flags.str',
    '-e', 'wlan.fc.type',
    '-e', 'wlan.fc.type_subtype',
]

PACKET_DEFAULTS: Dict[str, Optional[str]] = {
    'wlan_ta': '',
    'wlan_ra': '',
    'wlan_sa': '',
    'wlan_da': '',
    'frame_len': None,
    'wlan_ssid': None,
    'wlan_bssid': None,
    'radiotap_channel_freq': None,
    'wlan_flags_str': None,
    'wlan_fc_type': None,
    'wlan_fc_type_subtype': None,
}

def _ensure_thread_event_loop() -> Optional[asyncio.AbstractEventLoop]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop
    return None

def capture_packets(interface, queue, main_loop):
    """Capture packets using pyshark and process them."""
    thread_loop = _ensure_thread_event_loop()
    pyshark.tshark.output_parser.tshark_ek.packet_from_ek_packet = packet_from_ek_packet

    capture = pyshark.LiveCapture(
        interface=interface,
        display_filter='wlan',
        only_summaries=False,
        use_ek=True,
        custom_parameters=CAPTURE_FIELDS,
    )
    capture.keep_packets = False
    logger.trace(f"running pyshark capture on interface: {interface}")

    try:
        for packet in capture.sniff_continuously():
            _process_packet(packet, queue, main_loop)
    finally:
        capture.close()
        if thread_loop is not None:
            thread_loop.close()


def capture_packets_from_pcap(pcap_path: str, queue, main_loop) -> None:
    """Replay packets from a PCAP file."""

    thread_loop = _ensure_thread_event_loop()
    pyshark.tshark.output_parser.tshark_ek.packet_from_ek_packet = packet_from_ek_packet

    capture = pyshark.FileCapture(
        input_file=pcap_path,
        display_filter='wlan',
        only_summaries=False,
        use_ek=True,
        keep_packets=False,
        custom_parameters=CAPTURE_FIELDS,
    )
    capture.keep_packets = False
    logger.info(f"replay: reading packets from {pcap_path}")

    try:
        for packet in capture:
            _process_packet(packet, queue, main_loop)
    finally:
        capture.close()
        logger.info("replay: completed pcap playback")
        if thread_loop is not None:
            thread_loop.close()

def _process_packet(packet: Packet, queue, main_loop: asyncio.AbstractEventLoop) -> None:
    try:
        dist_packet = make_packet_dictionary(packet)
        if not filter_frames(dist_packet):
            return
        logger.trace(f"data: {dist_packet}")
        future = asyncio.run_coroutine_threadsafe(queue.put(dist_packet), main_loop)
        try:
            future.result()
        except CancelledError:
            logger.debug("Queue put cancelled; shutting down capture thread")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Error processing packet: {exc}")


def make_packet_dictionary(packet: Packet) -> Dict[str, Optional[str]]:
    layers = packet.layers.get('layers', {})
    return normalize_packet(layers)


def normalize_packet(layers: Dict[str, Any]) -> Dict[str, Optional[str]]:
    normalized: Dict[str, Optional[str]] = {}
    for field, default in PACKET_DEFAULTS.items():
        value = layers.get(field, default)
        normalized[field] = _coerce_field(value, default)
    return normalized


def _coerce_field(value: Any, default: Optional[str]) -> Optional[str]:
    if isinstance(value, list):
        if not value:
            return default
        value = value[0]
    if isinstance(value, dict):
        # Nested EK structures are not part of the supported schema.
        return default
    if value in (None, ''):
        return default
    return str(value)

async def start_tshark(interface, queue, main_loop):
    """Start a pyshark process to capture packets on an interface."""
    runner_loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        await runner_loop.run_in_executor(pool, capture_packets, interface, queue, main_loop)

    logger.trace("Pyshark capture started.")


async def replay_pcap(pcap_path: str, queue, main_loop) -> None:
    """Replay packets from a PCAP file in the background."""

    runner_loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        await runner_loop.run_in_executor(pool, capture_packets_from_pcap, pcap_path, queue, main_loop)

def packet_from_ek_packet(json_pkt):
    pkt_dict = json.loads(json_pkt.decode('utf-8'))

    return Packet(layers=pkt_dict, frame_info=None,
                  number=0,
                  length=1,
                  sniff_time=0,
                  interface_captured=None)