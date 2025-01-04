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
    const host = window.location.host.replace("8080","8765"); // replace is only for dev
    const path = window.location.pathname.replace("index.html","") + "ws";
    const wsUrl = ref(`${protocol}://${host}${path}`);

    return { wsUrl };
  }
}
</script>

<style>
body, html {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 0;
  border: 0;
}
#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
</style>
