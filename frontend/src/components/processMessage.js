import { ssidString, ieee80211_frequency_to_channel, WlanFrametype, WlanFrameSubtype, WlanFrameSubtypes } from './wifiUtils.js';
import getVendor from 'mac-oui-lookup';

export const processMessage = (graph, event, ssids, ssidColours) => {
    const packets = JSON.parse(event.data);
    packets.forEach(packet => {
        const ta = packet['wlan_ta'];
        const ra = packet['wlan_ra'];
        const sa = packet['wlan_sa'];
        const da = packet['wlan_da'];
        const packetLength = packet['frame_len'];
        const ssid = packet['wlan_ssid'];
        const bssid = packet['wlan_bssid'];
        const radio_channel = packet['radiotap_channel_freq'];
        const flags = packet['wlan_flags_str'];
        const packet_type = packet['wlan_fc_type'];
        const packet_subtype = packet['wlan_fc_type_subtype'];

        // eslint-disable-next-line
        //const [ta, ra, sa, da, packetLength, ssid, bssid, radio_channel, flags, packet_type, packet_subtype] = elements.map((e) => e.trim());
        if (!packetLength || ta == '' || ra == '') return;

        if (ta == '00:00:00:00:00:00') {
            console.log("unusal client: " + event.data);
            return;
        }

        processNode(graph, ssids, ssidColours, ta, ssid, bssid, radio_channel, flags, packet_type, packet_subtype)
        if (![WlanFrameSubtypes.PROBE_REQUEST, WlanFrameSubtypes.BEACON].includes(packet_subtype)) { // don't process some management packets on any other than the source
            processNode(graph, ssids, ssidColours, ra, ssid, bssid, radio_channel, flags, packet_type, null)
            if (![WlanFrameSubtypes.PROBE_RESPONSE].includes(packet_subtype)) { // don't process some management packets on any other than the source
                processNode(graph, ssids, ssidColours, sa, ssid, bssid, radio_channel, flags, packet_type, null)
                processNode(graph, ssids, ssidColours, da, ssid, bssid, radio_channel, flags, packet_type, null)

                processEdges(graph, ta, ra, sa, da)
            }
        }
    });
}

const processNode = (graph, ssids, ssidColours, mac, ssidHex, bssid, radio_channel, flags, packet_type, packet_subtype) => {
    if (mac == '' || mac == 'ff:ff:ff:ff:ff:ff') return;

    const channel = ieee80211_frequency_to_channel(radio_channel);
    const isAP = mac == bssid || packet_subtype == WlanFrameSubtypes.BEACON; //'0x0008'

    const ssid_string = ssidString(ssidHex);
    const ssid = isAP ? ssid_string : "";
    const lookingFor = isAP ? "" : ssid_string;

    // if (packet_type >= 0 && mac == 'd2:0c:6b:e4:c2:2e')
    //     console.log(mac);
    // if (packet_type < 2 && !['0x0008', '0x0004', '0x0005', null].includes(packet_subtype))
    //     console.log(mac);

    if (ssid_string != '') {
        if (!ssids[ssid_string]) {
            let nodeColor = "#1F77B4"; // Default color (themes.light.nodeColor)
            if (Object.keys(ssids).length < ssidColours.length) {
                nodeColor = ssidColours[Object.keys(ssids).length];
            }
            ssids[ssid_string] = {
                nodes: [mac],
                color: nodeColor
            };
        } else {
            if (!ssids[ssid_string].nodes.includes(mac)) {
                ssids[ssid_string].nodes.push(mac);
            }
        }
    }

    if (!graph.hasNode(mac)) {
        const vendor = ['2', '6', 'a', 'e'].includes(mac[1])
            ? "private MAC address"
            : getVendor(mac, 'unknown');
        const label = isAP ? 'AP: ' + ssid_string : vendor

        graph.addNode(mac, {
            label: label,
            mac: mac,
            vendor: vendor,
            isAP: isAP.toString(),
            x: Math.random() * 10,
            y: Math.random() * 10,
            ssid: ssid == '' ? [] : [ssid],
            lookingFor: [lookingFor],
            channels: [channel],
            lastseen: Date.now(),
            forceLabel: vendor == 'unknown' ? false : true,
            stats: { 
                [packet_type]: 1, 
                [WlanFrameSubtype(packet_subtype)]: 1 
            }
        });
    } else {
        const attributes = graph.getNodeAttributes(mac);
        // Client of Network
        if (lookingFor != '') {
            if (Array.isArray(attributes['lookingFor'])) {
                if (!attributes['lookingFor'].includes(lookingFor)) {
                    const nodeLookingFor = attributes['lookingFor'];
                    nodeLookingFor.push(lookingFor);
                    graph.setNodeAttribute(mac, 'lookingFor', nodeLookingFor);
                }
            } else {
                if (attributes['lookingFor'] != lookingFor) graph.setNodeAttribute(mac, 'lookingFor', [attributes['lookingFor'], lookingFor]);
            }
        }
        // AP Update label and SSID
        if (isAP) {
            // is AP
            if (attributes['isAP'] != 'true') {
                graph.setNodeAttribute(mac, 'isAP', 'true');
            }
            // ssid
            if (ssid_string != '') {
                if (Array.isArray(attributes['ssid'])) {
                    if (!attributes['ssid'].includes(ssid)) {
                        const nodeSSID = graph.getNodeAttribute(mac, 'ssid');
                        nodeSSID.push(ssid);
                        graph.setNodeAttribute(mac, 'ssid', nodeSSID);
                    }
                } else {
                    if (attributes['ssid'] != ssid) graph.setNodeAttribute(mac, 'ssid', [attributes['ssid'], ssid]);
                }
                if (attributes['label'].length < 4) {
                    graph.setNodeAttribute(mac, 'label', 'AP: ' + ssid_string);
                }
            }
        }
        // Node Channel
        if (Array.isArray(attributes['channels'])) {
            if (!attributes['channels'].includes(channel)) {
                const channels = graph.getNodeAttribute(mac, 'channels');
                channels.push(channel);
                graph.setNodeAttribute(mac, 'channels', channels);
            }
        }
        else {
            if (channel != attributes['channels']) graph.setNodeAttribute(mac, 'channels', [attributes['channels'], channel]);
        }
        // Node last seen
        graph.setNodeAttribute(mac, 'lastseen', Date.now());
        // Packettype stats
        attributes['stats'][WlanFrametype(packet_type)] = (attributes['stats'][WlanFrametype(packet_type)] ?? 0) + 1;
        if (packet_subtype != null)
            attributes['stats'][WlanFrameSubtype(packet_subtype)] = (attributes['stats'][WlanFrameSubtype(packet_subtype)] ?? 0) + 1;
        graph.setNodeAttribute(mac, 'stats', attributes['stats']);
    }
}

const processEdges = (graph, ta, ra, sa, da) => {
    if (ra == 'ff:ff:ff:ff:ff:ff') {
        // add edge to self
        if (!graph.hasEdge(ta, ta)) graph.addUndirectedEdge(ta, ta, { size: 2, linktype: "broadcast" });
    } else {
        if (!graph.hasEdge(ta, ra)) graph.addUndirectedEdge(ta, ra, { size: 3, linktype: "physical" });
    }
    if (sa == '' || (ta == sa && ra == da)) return // no need to double link if they are the same
    if (da == 'ff:ff:ff:ff:ff:ff') {
        // add edge to self
        if (!graph.hasEdge(sa, sa)) graph.addUndirectedEdge(sa, sa, { size: 2, linktype: "broadcast" });
    } else {
        if (!graph.hasEdge(sa, da)) graph.addUndirectedEdge(sa, da, { size: 1, linktype: "logical" });
    }
}