import { ssidString, ieee80211_frequency_to_channel } from './wifiUtils.js';
import getVendor from 'mac-oui-lookup';

export const processMessage = (graph, event, ssids, ssidColours) => {
    //for (const line of event.data) {
    const elements = event.data.split(",");
    if (elements.length < 3) return;

    // eslint-disable-next-line
    const [ta, ra, sa, da, packetLength, ssid, bssid, radio_channel, flags, packet_type, packet_subtype] = elements.map((e) => e.trim());
    if (!packetLength || ta == '' || ra == '') return;
    
    if (ta == '00:00:00:00:00:00') {
        console.log("unusal client: " + event.data);
        return;
    }

    processNode(graph, ssids, ssidColours, ta, ssid, bssid, radio_channel, flags, packet_type, packet_subtype)
    if (!['0x0004', '0x0008'].includes(packet_subtype)) { // don't process some management packets on any other than the source
        processNode(graph, ssids, ssidColours, ra, ssid, bssid, radio_channel, flags, packet_type, null)
        if (!['0x0005'].includes(packet_subtype)) { // don't process some management packets on any other than the source
        processNode(graph, ssids, ssidColours, sa, ssid, bssid, radio_channel, flags, packet_type, null)
        processNode(graph, ssids, ssidColours, da, ssid, bssid, radio_channel, flags, packet_type, null)

        processEdges(graph, ta, ra, sa, da)
        }
    }
}

const processNode = (graph, ssids, ssidColours, mac, ssidHex, bssid, radio_channel, flags, packet_type, packet_subtype) => {
    if (mac == '' || mac == 'ff:ff:ff:ff:ff:ff') return;

    const channel = ieee80211_frequency_to_channel(radio_channel);
    const isAP = mac == bssid || packet_subtype == '0x0008';

    const ssid_string = ssidString(ssidHex);
    const ssid = isAP ? ssid_string : "";
    const lookingFor = isAP ? "" : ssid_string;

    if (packet_type >= 0 && mac == 'd2:0c:6b:e4:c2:2e')
        console.log(mac);

    if (packet_type < 2 && !['0x0008', '0x0004', '0x0005', null].includes(packet_subtype))
        console.log(mac);

    if (ssid_string != '' && ssid_string != '<MISSING>') {
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
        const vendor = getVendor(mac, 'unknown')
        const label = isAP ? 'AP: ' + vendor : vendor

        graph.addNode(mac, { 
        label: ssid == '' && !isAP ? label : ssid,
        mac: mac,
        vendor: vendor,
        isAP: isAP.toString(),
        x: Math.random() * 10,
        y: Math.random() * 10,
        ssid: ssid == '' ? [] : [ssid],
        lookingFor: [lookingFor],
        channels: [channel],
        lastseen: Date.now()
        });
    } else {
        // Client of Network
        if (lookingFor != ''){
        const nodeLookingFor = graph.getNodeAttribute(mac, 'lookingFor');
        if (Array.isArray(nodeLookingFor)) {
            if (!nodeLookingFor.includes(lookingFor)) {
            nodeLookingFor.push(lookingFor);
            graph.setNodeAttribute(mac, 'lookingFor', nodeLookingFor);
            }
        } else
            if (nodeLookingFor != lookingFor) graph.setNodeAttribute(mac, 'lookingFor', [nodeLookingFor, lookingFor]);            
        }
        // AP of network
        if (ssidHex != '' && ssid != '' && ssid != '<MISSING>') {
        const nodeSSID = graph.getNodeAttribute(mac, 'ssid');
        if (Array.isArray(nodeSSID)) {
            if (!nodeSSID.includes(ssid)) {
            nodeSSID.push(ssid);
            graph.setNodeAttribute(mac, 'ssid', nodeSSID);
            }
        } else
            if (nodeSSID != ssid) graph.setNodeAttribute(mac, 'ssid', [nodeSSID, ssid]);                
        }
        // AP Update label
        if (isAP)
        if (!graph.getNodeAttribute(mac, 'isAP') == 'true') {
            graph.setNodeAttribute(mac, 'label', getVendor(mac, 'unknown'));
            graph.setNodeAttribute(mac, 'isAP', 'true');
        }
        // Node Channel
        const channels = graph.getNodeAttribute(mac, 'channels');
        if (Array.isArray(channels)) {
        if (!channels.includes(channel)) {
            channels.push(channel);
            graph.setNodeAttribute(mac, 'channels', channels);
        }
        }
        else
        if (channel != channels) graph.setNodeAttribute(mac, 'channels', [channels, channel]);
        // Node last seen
        graph.setNodeAttribute(mac, 'lastseen', Date.now());
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