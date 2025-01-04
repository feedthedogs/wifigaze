export const ssidString = (hex) => {
    if (hex == '') return '';
    if (hex == '<MISSING>') return hex;
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