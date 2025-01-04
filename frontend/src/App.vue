<template>
    <GraphViewer :websocket-url="wsUrl" />
</template>

<script>
import GraphViewer from './components/GraphViewer.vue'
import { ref } from "vue";

export default {
  name: 'App',
  components: {
    GraphViewer
  },
  setup() {
    // Determine WebSocket URL based on the current location
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const host = window.location.host; // Includes hostname and port (if present)
    const path = window.location.pathname.replace("/index.html","ws/");
    const wsUrl = ref(`${protocol}://${host}/${path}`);

    return { wsUrl };
  }
}
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  width: 100%;
  padding: 0;
  margin: 0;
  border: 0;
  overflow: auto;
}
body, html {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 0;
  border: 0;
  overflow: auto;
}
canvas {
  left: 0;
}
</style>
