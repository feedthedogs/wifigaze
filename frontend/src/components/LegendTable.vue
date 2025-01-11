<template>
  <h2>SSIDs</h2>
  <div id="legend-items">
    <div class="legend-item" v-for="(ssid, index) in limitedSsids" :key="index">
      <div class="legend-color" :style="{ backgroundColor: ssidColours[index] }"></div>
      <span>{{ ssid }}</span>
    </div>
  </div>
  </template>
  
  <script>
  export default {
    props: {
      ssids: {
        type: Object,
        required: true,
      },
      ssidColours: {
        type: Array,
        required: true,
      },
    },
    computed: {
      limitedSsids() {
        return Object.keys(this.ssids).slice(0, this.ssidColours.length);
      },
    },
  };
  </script>
  
  <style>
  .legend-item {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
  }
  
  .legend-color {
    width: 20px;
    height: 20px;
    margin-right: 10px;
    border: 1px solid #333;
  }
  </style>
  