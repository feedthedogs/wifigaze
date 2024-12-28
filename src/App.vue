<template>
    <GraphViewer websocket-url="wss://192.168.2.134:8765" />
</template>

<script>
import GraphViewer from './components/GraphViewer.vue'

export default {
  name: 'App',
  components: {
    GraphViewer
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
