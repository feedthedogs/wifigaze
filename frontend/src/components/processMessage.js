import { ssidString, ieee80211_frequency_to_channel, WlanFrametype, WlanFrameSubtype, WlanFrameSubtypes, WlanFrametypes } from './wifiUtils.js';
import getVendor from 'mac-oui-lookup';

const parseFrameValue = (value) => {
    if (value === null || value === undefined) return null;
    if (typeof value === 'number') return value;

    const hex = parseInt(value, 16);
    if (!Number.isNaN(hex)) return hex;

    const decimal = parseInt(value, 10);
    return Number.isNaN(decimal) ? null : decimal;
};

const NOISE_MANAGEMENT_SUBTYPES = new Set([
    WlanFrameSubtypes.PROBE_REQUEST,
    WlanFrameSubtypes.PROBE_RESPONSE,
    WlanFrameSubtypes.BEACON,
    WlanFrameSubtypes.ATIM,
    WlanFrameSubtypes.ACTION,
    WlanFrameSubtypes.ACTION_NO_ACK,
]);

const LINK_MANAGEMENT_SUBTYPES = new Set([
    WlanFrameSubtypes.ASSOCIATION_REQUEST,
    WlanFrameSubtypes.ASSOCIATION_RESPONSE,
    WlanFrameSubtypes.REASSOCIATION_REQUEST,
    WlanFrameSubtypes.REASSOCIATION_RESPONSE,
    WlanFrameSubtypes.AUTHENTICATION,
    WlanFrameSubtypes.DEAUTHENTICATION,
    WlanFrameSubtypes.DISASSOCIATION,
]);

const ALERT_WINDOW_MS = 60_000;
const ALERT_REARM_MS = 120_000;
const MAX_ALERTS = 200;

const detectionState = {
    deauth: new Map(),
    disassoc: new Map(),
    probeFlood: new Map(),
    authFlood: new Map(),
};

export const processMessage = (graph, event, ssids, ssidColours, alertsRef = null) => {
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

        const packetTypeValue = parseFrameValue(packet_type);
        const packetSubtypeValue = parseFrameValue(packet_subtype);

        const isNoiseManagement = packetTypeValue === WlanFrametypes.MANAGEMENT && packetSubtypeValue !== null && NOISE_MANAGEMENT_SUBTYPES.has(packetSubtypeValue);
        const shouldCreateEdges = (() => {
            if (packetTypeValue === WlanFrametypes.DATA) return true;
            if (packetTypeValue === WlanFrametypes.MANAGEMENT && packetSubtypeValue !== null) {
                return LINK_MANAGEMENT_SUBTYPES.has(packetSubtypeValue);
            }
            return false;
        })();
        const skipResponderNodes = packetSubtypeValue === WlanFrameSubtypes.PROBE_RESPONSE;
        const now = Date.now();

        // eslint-disable-next-line
        //const [ta, ra, sa, da, packetLength, ssid, bssid, radio_channel, flags, packet_type, packet_subtype] = elements.map((e) => e.trim());
        if (!packetLength || ta == '' || ra == '') return;

        if (ta == '00:00:00:00:00:00') {
            console.log("unusal client: " + event.data);
            return;
        }

        evaluateForAlerts({
            packetTypeValue,
            packetSubtypeValue,
            ta,
            ra,
            ssidHex: ssid,
            bssid,
            now,
            alertsRef,
        });

        processNode(graph, ssids, ssidColours, ta, ssid, bssid, radio_channel, flags, packet_type, packet_subtype)
        if (isNoiseManagement) return;

        processNode(graph, ssids, ssidColours, ra, ssid, bssid, radio_channel, flags, packet_type, null)
        if (skipResponderNodes) return;

        processNode(graph, ssids, ssidColours, sa, ssid, bssid, radio_channel, flags, packet_type, null)
        processNode(graph, ssids, ssidColours, da, ssid, bssid, radio_channel, flags, packet_type, null)

        processEdges(graph, ta, ra, sa, da, shouldCreateEdges)
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

const processEdges = (graph, ta, ra, sa, da, allowEdges) => {
    if (!allowEdges) return;
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

const evaluateForAlerts = ({ packetTypeValue, packetSubtypeValue, ta, ra, ssidHex, bssid, now, alertsRef }) => {
    if (!alertsRef || packetTypeValue === null || packetSubtypeValue === null) return;

    if (packetTypeValue === WlanFrametypes.MANAGEMENT) {
        if (packetSubtypeValue === WlanFrameSubtypes.DEAUTHENTICATION) {
            const key = `${ta}->${ra}`;
            const entry = trackEvent(detectionState.deauth, key, now);
            if (entry.count >= 5 && canTriggerAlert(entry, now)) {
                entry.lastAlert = now;
                recordAlert(alertsRef, {
                    id: `deauth-${now}-${key}`,
                    type: 'DEAUTH_FLOOD',
                    severity: 'high',
                    time: new Date(now).toISOString(),
                    source: ta,
                    target: ra,
                    transmitter: ta,
                    receiver: ra,
                    bssid,
                    ssid: ssidString(ssidHex),
                    windowMs: ALERT_WINDOW_MS,
                    count: entry.count,
                    description: `Detected ${entry.count} deauthentication frames from ${ta} to ${ra} within the last ${Math.round(ALERT_WINDOW_MS / 1000)} seconds.`,
                });
            }
        } else if (packetSubtypeValue === WlanFrameSubtypes.DISASSOCIATION) {
            const key = `${ta}->${ra}`;
            const entry = trackEvent(detectionState.disassoc, key, now);
            if (entry.count >= 5 && canTriggerAlert(entry, now)) {
                entry.lastAlert = now;
                recordAlert(alertsRef, {
                    id: `disassoc-${now}-${key}`,
                    type: 'DISASSOC_FLOOD',
                    severity: 'medium',
                    time: new Date(now).toISOString(),
                    source: ta,
                    target: ra,
                    transmitter: ta,
                    receiver: ra,
                    bssid,
                    ssid: ssidString(ssidHex),
                    windowMs: ALERT_WINDOW_MS,
                    count: entry.count,
                    description: `Detected ${entry.count} disassociation frames from ${ta} to ${ra} within the last ${Math.round(ALERT_WINDOW_MS / 1000)} seconds.`,
                });
            }
        } else if (packetSubtypeValue === WlanFrameSubtypes.PROBE_REQUEST) {
            const key = ta;
            const entry = trackEvent(detectionState.probeFlood, key, now);
            if (entry.count >= 60 && canTriggerAlert(entry, now)) {
                entry.lastAlert = now;
                recordAlert(alertsRef, {
                    id: `probe-${now}-${key}`,
                    type: 'PROBE_FLOOD',
                    severity: 'medium',
                    time: new Date(now).toISOString(),
                    source: ta,
                    transmitter: ta,
                    receiver: ra,
                    bssid,
                    ssid: ssidString(ssidHex),
                    windowMs: ALERT_WINDOW_MS,
                    count: entry.count,
                    description: `Device ${ta} sent ${entry.count} probe requests within the last ${Math.round(ALERT_WINDOW_MS / 1000)} seconds.`,
                });
            }
        } else if (packetSubtypeValue === WlanFrameSubtypes.AUTHENTICATION) {
            const key = `${ta}->${ra}`;
            const entry = trackEvent(detectionState.authFlood, key, now);
            if (entry.count >= 30 && canTriggerAlert(entry, now)) {
                entry.lastAlert = now;
                recordAlert(alertsRef, {
                    id: `auth-${now}-${key}`,
                    type: 'AUTH_FLOOD',
                    severity: 'medium',
                    time: new Date(now).toISOString(),
                    source: ta,
                    target: ra,
                    transmitter: ta,
                    receiver: ra,
                    bssid,
                    ssid: ssidString(ssidHex),
                    windowMs: ALERT_WINDOW_MS,
                    count: entry.count,
                    description: `Detected ${entry.count} authentication frames from ${ta} to ${ra} within the last ${Math.round(ALERT_WINDOW_MS / 1000)} seconds.`,
                });
            }
        }
    }
};

const trackEvent = (map, key, now) => {
    let entry = map.get(key);
    if (!entry) {
        entry = { timestamps: [], lastAlert: 0 };
        map.set(key, entry);
    }

    entry.timestamps.push(now);
    while (entry.timestamps.length && now - entry.timestamps[0] > ALERT_WINDOW_MS) {
        entry.timestamps.shift();
    }
    entry.count = entry.timestamps.length;
    return entry;
};

const canTriggerAlert = (entry, now) => now - entry.lastAlert > ALERT_REARM_MS;

const recordAlert = (alertsRef, alert) => {
    const list = Array.isArray(alertsRef.value) ? alertsRef.value : [];
    const updated = [alert, ...list].slice(0, MAX_ALERTS);
    alertsRef.value = updated;
};