from enum import StrEnum
from loguru import logger

def filter_frames(packet):
    if packet['wlan_fc_type'] == '1':
        logger.trace(f"ignore control frames")
        return False # control frames

    if filter_macs(packet['wlan_ta']):
        logger.trace(f"ignored mac ta")
        return False
    if filter_macs(packet['wlan_ra']):
        logger.trace(f"ignored mac ra")
        return False
    if filter_macs(packet['wlan_sa']):
        logger.trace(f"ignored mac sa")
        return False
    if filter_macs(packet['wlan_da']): 
        logger.trace(f"ignored mac da")
        return False

    if packet['wlan_fc_type'] == '0' and packet['wlan_fc_type_subtype'] in [ WLANFrameSubtype.ATIM,
                                                WLANFrameSubtype.DISASSOCIATION,
                                                WLANFrameSubtype.AUTHENTICATION,  
                                                WLANFrameSubtype.ACTION,
                                                WLANFrameSubtype.ACTION_NO_ACK]:
        logger.trace(f"ignore some management frames")
        return False # management frames
    if packet['wlan_fc_type'] == '2' and packet['wlan_fc_type_subtype'] in [WLANFrameSubtype.NULL]:
        logger.trace(f"ignore null data frames")
        return False # data frames
    return True

def filter_macs(mac):
    if mac is None: return False
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