export const ssidString = (hex) => {
    if (hex == undefined) return '';
    if (hex == '<MISSING>') return '<HIDDEN>';
    if (/^0+$/.test(hex)) return '<HIDDEN>';
    return hex.match(/.{1,2}/g).map(function (v) {
        return String.fromCharCode(parseInt(v, 16));
        }).join('')
}

export const ieee80211_frequency_to_channel = (freq) => {
    if (freq == 2484) return 14;

    if (freq < 2484)
        return (freq - 2407) / 5;

    return freq / 5 - 1000;
}

export const WlanFrameSubtypes = Object.freeze({
    ASSOCIATION_REQUEST: 0x0000,
    ASSOCIATION_RESPONSE: 0x0001,
    REASSOCIATION_REQUEST: 0x0002,
    REASSOCIATION_RESPONSE: 0x0003,
    PROBE_REQUEST: 0x0004,
    PROBE_RESPONSE: 0x0005,
    BEACON: 0x0008,
    ATIM: 0x0009,  
    // Announcement Traffic Indication Message
    DISASSOCIATION: 0x000A,
    AUTHENTICATION: 0x000B,
    DEAUTHENTICATION: 0x000C,
    ACTION: 0x000D,
    ACTION_NO_ACK: 0x000E,
    
    // Control Frame Subtypes
    BLOCK_ACK_REQUEST: 0x0018,
    BLOCK_ACK: 0x0019,
    PS_POLL: 0x001A,
    RTS: 0x001B,
    CTS: 0x001C,
    ACK: 0x001D,
    CF_END: 0x001E,
    CF_END_ACK: 0x001F,
    
    // Data Frame Subtypes
    DATA: 0x0020,
    DATA_CF_ACK: 0x0021,
    DATA_CF_POLL: 0x0022,
    DATA_CF_ACK_CF_POLL: 0x0023,
    NULL: 0x0024,
    CF_ACK: 0x0025,
    CF_POLL: 0x0026,
    CF_ACK_CF_POLL: 0x0027,
    QOS_DATA: 0x0028,
    QOS_DATA_CF_ACK: 0x0029,
    QOS_DATA_CF_POLL: 0x002A,
    QOS_DATA_CF_ACK_CF_POLL: 0x002B,
    QOS_NULL: 0x002C,
    QOS_CF_POLL: 0x002E,
    QOS_CF_ACK_CF_POLL: 0x002F,   
});

export const WlanFrametypes = Object.freeze({
    MANAGEMENT: 0x00,
    CONTROL: 0x01,
    DATA: 0x02,
    RESERVED: 0x03,
});

export const WlanFrametype = (value) => {
    // eslint-disable-next-line
    const entry = Object.entries(WlanFrametypes).find(([_, v]) => v === parseInt(value,16));
    if (entry == undefined && value != null) console.log(value)
    return entry ? entry[0] : "UNKNOWN (" + value + ")";
}

export const WlanFrameSubtype = (value) => {
    // eslint-disable-next-line
    const entry = Object.entries(WlanFrameSubtypes).find(([_, v]) => v === parseInt(value,16));
    if (entry == undefined && value != null) console.log(value)
    return entry ? entry[0] : "UNKNOWN (" + value + ")";
}