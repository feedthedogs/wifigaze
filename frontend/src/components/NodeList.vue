<template>
    <ul class="node-list">
      <li
        v-for="node in filteredNodes"
        :key="node"
        @mousemove="$emit('highlightNode', node)"
        @touchmove="$emit('highlightNode', node)"
        @click="$emit('gotoNode', node)"
      >
        {{ node }}
      </li>
    </ul>
  </template>
  
  <script>
  export default {
    props: {
      filteredNodes: {
        type: Array,
        required: true,
      },
    },
  };
  </script>
  
  <style>
  .node-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  
  .node-list li {
    padding: 8px;
    cursor: pointer;
    border-bottom: 1px solid #ddd;
  }
  
  .node-list li:hover {
    background-color: #f0f0f0;
  }
  </style>
  