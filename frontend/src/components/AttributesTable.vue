<template>
    <h2>Node/Edge Attributes</h2>
      <table>
        <thead>
          <tr>
            <th>Attribute</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          <!-- Display a message if no attributes are available -->
          <tr v-if="!attributes || Object.keys(attributes).length === 0">
            <td colspan="2">No attributes</td>
          </tr>
          <!-- Loop through the attributes and display rows -->
          <tr v-else v-for="(value, key) in filteredAttributes" :key="key">
            <td>{{ key }}</td>
            <td>
              <span v-if="key === 'lastseen'">{{ timeSince(value) }}</span>
              <span v-else-if="key === 'channels'">{{ sortedChannels(value).join(', ') }}</span>
              <span v-else>{{ value }}</span>
            </td>
          </tr>
        </tbody>
      </table>
  </template>
  
  <script>
  export default {
    props: {
      attributes: {
        type: Object,
        required: true,
      },
    },
    computed: {
      // Exclude specific keys like 'x', 'y', 'size'
      filteredAttributes() {
        return Object.entries(this.attributes)
          .filter(([key]) => !['x', 'y', 'size', 'forceLabel'].includes(key))
          .reduce((acc, [key, value]) => {
            acc[key] = value;
            return acc;
          }, {});
      },
    },
    methods: {
      timeSince(timestamp) {
        const now = new Date();
        const diff = now - new Date(timestamp);
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
  
        if (days > 0) return `${days} day(s) ago`;
        if (hours > 0) return `${hours} hour(s) ago`;
        if (minutes > 0) return `${minutes} minute(s) ago`;
        return `${seconds} second(s) ago`;
      },
      sortedChannels(channels) {
        return [...channels].sort((a, b) => b - a); // Sort channels in descending order
      },
    },
  };
  </script>
  
  <style>
  thead th {
    text-align: left;
    background: #f4f4f4;
    padding: 8px;
  }
  tbody td {
    padding: 8px;
    border: 1px solid #ddd;
  }
  </style>
  