<template>
  <div v-if="isLandscape" class="app-container" :style="gridStyle"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
      @touchmove="onTouchMove"
      @touchend="onTouchEnd">

    <!-- Legend Panel -->
    <div class="panel legend-panel">
      <LegendTable :ssids="ssids" :ssidColours="ssidColours" @highlightNode="highlightNode" @gotoNode="gotoNode" />
      <div
          class="resizer resizer-left"
          @mousedown="startResize('left', $event)"
          @touchstart="startResize('left', $event)"
        ></div>
    </div>

    <main id="container" ref="container" class="graph-container">
    </main>

    <div id="counter">Nodes: 0</div>

    <div class="panel properties-panel">
      <AttributesTable :attributes="attributes" />
      <SearchComponent :updateSearch="updateSearch" />
      <NodeList :filteredNodes="filteredNodes" @highlightNode="highlightNode" @gotoNode="gotoNode" />
      
      <!-- WebSocket Status and Packet Count -->
      <div id="websocket-status">
        <span :class="websocketStatusClass">{{ websocketStatus }}</span>
        <span>Packets per 10 seconds: {{ packetCount }}</span>
        <button v-if="websocketStatus == 'Disconnected'" @click="reconnectWebSocket">Reconnect</button>
      </div>

      <div id="export-panel">
        <button @click="exportGraph()">Export Graph</button>
      </div>
      
      <div
          class="resizer resizer-right"
          @mousedown="startResize('right', $event)"
          @touchstart="startResize('right', $event)"
        ></div>
    </div>
  </div>
  <div v-else class="rotate-message">
      <p>Width too small, please turn your device sideways and refresh.</p>
    </div>
</template>

<script>
import { ref, onMounted, onUnmounted, onBeforeUnmount, computed } from "vue";
import Sigma from "sigma";
import Graph from "graphology";

import LegendTable from './LegendTable.vue';
import AttributesTable from './AttributesTable.vue';
import SearchComponent from "./SearchComponent.vue";
import NodeList from "./NodeList.vue";

import { ssidColours } from './ssidColours';
import { processMessage } from './processMessage';
import { normalize, graphLayout, downloadFile } from './graphUtils';

export default {
  props: {
    websocketUrl: {
      type: String,
      required: true,
    },
  },
  components: {
    LegendTable,
    AttributesTable,
    SearchComponent,
    NodeList
  },
  setup(props) {
    const container = ref(null);
    let sigmaInstance = null;
    let graph = new Graph();
    const attributes = ref([]);
    const filteredNodes = ref([]);
    let socket = null;
    const infopanel = ref(null);
    let ssids = ref({});
    let theme = 'light'

    const isLandscape = ref(window.innerWidth > 414);
    const showLeftPanel = ref(true);
    const showRightPanel = ref(true);
    const leftPanelWidth = ref(200); // Initial width in pixels
    const rightPanelWidth = ref(350); // Initial width in pixels
    const resizing = ref(null); // Track which panel is being resized  
    const startX = ref(0); // Track the starting x-coordinate for touch/mouse  

    const websocketStatus = ref("Disconnected");
    const websocketStatusClass = ref("disconnected");
    const packetCount = ref(0);
    let packetCounter = 0;

    function initializeGraph() {
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        theme = 'dark';
        // dark mode
      }
      theme = 'light' // until we fix dark mode theme
      sigmaInstance = new Sigma(
        graph, 
        container.value,
        {
          defaultNodeColor: themes[theme].nodeColor,
          labelColor: themes[theme].textColor,
          enableEdgeHovering: true,
          minEdgeSize: 2,
          nodeReducer: nodeReducer,
          edgeReducer: edgeReducer,
          allowInvalidContainer: true
        },
      );
      // Handle node click events
      sigmaInstance.on("clickNode", ({ node }) => {
        attributes.value = graph.getNodeAttributes(node);
      });

      // Handle edge click events
      sigmaInstance.on("clickEdge", ({ edge }) => {
        attributes.value = graph.getEdgeAttributes(edge);
      });

      // Handle click outside of nodes/edges
      sigmaInstance.on("clickStage", () => {
        attributes.value = [];
      });

      // Add event listeners
      sigmaInstance.on('enterNode', ({ node }) => {
        highlightNode(node);
        attributes.value = graph.getNodeAttributes(node);
        attributes.value['connections'] = graph.neighbors(node);
      });

      sigmaInstance.on('leaveNode', () => {
        resetHighlight();
        //document.getElementById('details').innerHTML = 'Hover over a node to see its connections';
      });

      graph.on('nodeAdded', function({key}) {
        updateCounter(key);
      });

      applyTheme(theme);
    }

    const gridStyle = computed(() => {
      return `
        grid-template-columns: ${showLeftPanel.value ? `${leftPanelWidth.value}px` : "0"} 1fr ${
        showRightPanel.value ? `${rightPanelWidth.value}px` : "0"
      };
      `;
    });

    const handleResize = () => {
      isLandscape.value = window.innerWidth > 414;
    };

    const startResize = (panel, event) => {
      resizing.value = panel;
      startX.value = event.touches ? event.touches[0].clientX : event.clientX;
      event.preventDefault();
    };

    const onMouseMove = (event) => {
      if (!resizing.value) return;

      const delta = event.clientX - startX.value;
      if (resizing.value === "left") {
        leftPanelWidth.value = Math.max(150, leftPanelWidth.value + delta);
      } else if (resizing.value === "right") {
        rightPanelWidth.value = Math.max(150, rightPanelWidth.value - delta);
      }
      startX.value = event.clientX;
    };

    const onTouchMove = (event) => {
      if (!resizing.value) return;

      const delta = event.touches[0].clientX - startX.value;
      if (resizing.value === "left") {
        leftPanelWidth.value = Math.max(150, leftPanelWidth.value + delta);
      } else if (resizing.value === "right") {
        rightPanelWidth.value = Math.max(150, rightPanelWidth.value - delta);
      }
      startX.value = event.touches[0].clientX;
    };

    const onMouseUp = () => {
      resizing.value = null;
    };

    const onTouchEnd = () => {
      resizing.value = null;
    };

    const updateSearch = (searchTerm) => {
      const term = searchTerm.toLowerCase();
      if (term == "") {
        filteredNodes.value = [];
        return;
      }
      filteredNodes.value = graph.nodes().filter((node) => {
        const attributes = graph.getNodeAttributes(node);
        return (
          (attributes.label && attributes.label.toLowerCase().includes(term)) ||
          Object.values(attributes).some(
            (value) =>
              typeof value === "string" &&
              value.toLowerCase().includes(term)
          )
        );
      });
    };

    const handleWebSocketMessage = (event) => {
      try {
        processMessage(graph, event, ssids.value, ssidColours);
        packetCounter++;
        scaleNodes();
        //populateLegend();

        graphLayout(graph);

        //sigmaInstance.refresh();
      } catch (err) {
        console.error("Error processing WebSocket message:", err);
      }
    }

    function scaleNodes() {
      // Scale node sizes based on degree
      graph.forEachNode((node) => {
        const size = normalize(graph.degree(node), 1, 10, 5, 15); // Adjust min/max as needed
        graph.setNodeAttribute(node, "size", size);
      });
    }

    const nodeReducer = (key, attributes) => {
      let color = themes[theme].nodeColor
      if (attributes.ssid == '') return { ...attributes, color };
      color = ssids.value[attributes.ssid[0]]['color'];
      return { ...attributes, color };
    }

    const edgeReducer = (key, attributes) => {
      let color;
      if (attributes.linktype === "logical") color = themes[theme].edgeColors.logical;
      else if (attributes.linktype === "physical") color = themes[theme].edgeColors.physical;
      else if (attributes.linktype === "broadcast") color = themes[theme].edgeColors.broadcast;
      return { ...attributes, color };
    }

    function gotoNode(nodeKey) {
    // Get the node display data (ie. its coordinate relative to the actual camera state)
    const nodeDisplayData = sigmaInstance.getNodeDisplayData(nodeKey);
    if (nodeDisplayData) {
      // calling the animate function to go to the node coordinates
      sigmaInstance.getCamera().animate(nodeDisplayData);
   }
}

    // Helper function to highlight connected nodes and edges
    function highlightNode(nodeKey) {
      sigmaInstance.setSetting('nodeReducer', (node, data) => {
        if (node === nodeKey || graph.neighbors(nodeKey).includes(node)) {
          return { ...data, color: data.color, labelColor: '#000000' };
        }
        return { ...data, color: '#E0E0E0' };
      });

      sigmaInstance.setSetting('edgeReducer', (edge, data) => {
        if (graph.source(edge) === nodeKey || graph.target(edge) === nodeKey) {
          return { ...data, color: '#333', size: 2 };
        }
        return { ...data, color: '#E0E0E0', size: 0.5 };
      });
      sigmaInstance.refresh();
    }

    // Restore default styles
    function resetHighlight() {
      sigmaInstance.setSetting('nodeReducer', nodeReducer);
      sigmaInstance.setSetting('edgeReducer', edgeReducer);
      sigmaInstance.refresh();
    }    

    onMounted(() => {
      graphPreload();
      initializeGraph();

      // Connect to WebSocket
      connectWebSocket();

      window.addEventListener("resize", handleResize);

      // Set interval to update packet count every 10 seconds
      setInterval(() => {
        packetCount.value = packetCounter;
        packetCounter = 0;
      }, 10000);
    });

    onBeforeUnmount(() => {
      window.removeEventListener("resize", handleResize);
    });    

    onUnmounted(() => {
      if (socket) socket.close();
      if (sigmaInstance) sigmaInstance.kill();
    });

    const connectWebSocket = () => {
      socket = new WebSocket(props.websocketUrl);
      socket.onopen = () => {
        websocketStatus.value = "Connected";
        websocketStatusClass.value = "connected";
      };
      socket.onclose = () => {
        websocketStatus.value = "Disconnected";
        websocketStatusClass.value = "disconnected";
      };
      socket.onmessage = handleWebSocketMessage;
      socket.onerror = (error) => {
        console.error("WebSocket error:", error);
        websocketStatus.value = "Error";
        websocketStatusClass.value = "error";
      };
    };

    const reconnectWebSocket = () => {
      if (socket) socket.close();
      connectWebSocket();
    };

    const graphPreload = async () => {
      try {
        // fetch the preload graph if it exists
        const preloadURL = props.websocketUrl.replace("ws://","http://").replace("/ws","/preload")
        const response = await fetch(preloadURL);
        if (response.ok) {
          const preloadGraph = await response.json();
          // replace the ssids object with ssids derived from json
          const tempObj = {};
          var counter = 0;
          for (const node of preloadGraph.nodes) {
            const { ssidlist } = node.attributes;
            if (ssidlist && ssidlist.length > 0) {
              for (const ssid of ssidlist) {
                if (!tempObj[ssid]) {
                  tempObj[ssid] = {
                    color: ssidColours[counter],
                    nodes: [node.key]
                  };
                  counter++;
                } else {
                  tempObj[ssid].nodes.push(node.key);
                }
              }
            }
          }
          ssids.value = tempObj;
          graph.import(preloadGraph);
        } else {
          console.info('Not preloading graph:', response.status);
        }
      } catch (error) {
        console.info('Not preloading graph:', error);
      }
    }

    // Function to update the counter
    function updateCounter() {
        const nodeCount = graph.nodes().length;
        const edgeCount = graph.edges().length;
        const counterElement = document.getElementById('counter');
        counterElement.innerText = `Nodes: ${nodeCount}, Edges: ${edgeCount}`;
    }  
    
    function exportGraph() {
      downloadFile(graph);
    }

    // Define themes
    const themes = {
      light: {
        backgroundColor: "#FFFFFF",
        textColor: "#000000",
        nodeColor: "#1F77B4",
        edgeColors: {
          logical: "#FF7F0E",
          physical: "#9467BD",
          broadcast: "#2CA02C",
        },
      },
      dark: {
        backgroundColor: "#000000",
        textColor: "#FFFFFF",
        nodeColor: "#17BECF",
        edgeColors: {
          logical: "#FFD700",
          physical: "#FF69B4",
          broadcast: "#32CD32",
        },
      },
    };

    // Apply theme
    function applyTheme(themeName) {
      const theme = themes[themeName];
      document.documentElement.style.setProperty("background-color", theme.backgroundColor);
      document.documentElement.style.setProperty("text-color", theme.textColor);

      sigmaInstance.setSetting({
        defaultNodeColor: theme.nodeColor,
        labelColor: theme.textColor,
        enableEdgeHovering: true,
        minEdgeSize: 2,        
        nodeReducer: nodeReducer,
        edgeReducer: edgeReducer
      });

      // Re-render
      sigmaInstance.refresh();
    }

    return { container, 
      infopanel,
      exportGraph, 
      attributes, 
      ssids, 
      ssidColours, 
      filteredNodes, 
      updateSearch, 
      highlightNode,
      gotoNode,
      leftPanelWidth,
      rightPanelWidth,
      isLandscape,
      gridStyle,
      startResize,
      onMouseMove,
      onMouseUp,
      onTouchMove,
      onTouchEnd,
      websocketStatus,
      websocketStatusClass,
      packetCount,
      reconnectWebSocket };
  },
};
</script>

<style>
  /* Root Layout */
  .app-container {
    display: grid;
    grid-template-rows: auto 1fr;
    grid-template-columns: 200px 1fr 200px; /* Default sizes */
    gap: 1rem;
    height: 100%;
    position: relative;
    overflow: hidden;
  }

  /* Panels */
  .panel {
    padding: 1rem;
    background-color: #f4f4f4;
    border: 1px solid #ddd;
    overflow-y: auto;
  }

  /* Resizer Handles */
  .resizer {
    width: 5px;
    cursor: ew-resize;
    position: absolute;
    top: 0;
    bottom: 0;
  }

  .resizer-left {
    right: -2.5px;
    background-color: #ccc;
  }

  .resizer-right {
    left: -2.5px;
    background-color: #ccc;
  }  

  /* Panels */
  .properties-panel {
    background: #f4f4f4;
    padding: 10px;
    height: 100vh;
    overflow-y: auto;
  }

  .legend-panel {
    position: relative;
  }

  .properties-panel {
    position: relative;
  }

  .graph-container {
    overflow: hidden;
  }

  /* Buttons */
  .toggle-btn {
    position: absolute;
    z-index: 10;
    background-color: #007bff;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    cursor: pointer;
  }
  .toggle-btn.left {
    top: 1rem;
    left: 1rem;
  }
  .toggle-btn.right {
    top: 1rem;
    right: 1rem;
  }

  /* Responsive Design */
  @media (max-width: 768px) {
    .legend-panel,
    .properties-panel {
      display: none;
    }
    .graph-container {
      grid-column: 1 / -1;
    }
    .resizer {
      width: 10px;
    }
  }

  #counter {
    position: absolute;
    top: 10px;
    right: 10px;
    background-color: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 10px;
    border-radius: 5px;
    font-size: 16px;
  }  

  #websocket-status {
    margin-top: 10px;
    display: flex;
    align-items: center;
  }

  #websocket-status span {
    margin-right: 10px;
  }

  .connected {
    color: green;
  }

  .disconnected {
    color: red;
  }

  .error {
    color: orange;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
  }
  table, th, td {
    border: 1px solid #ccc;
  }
  th, td {
    padding: 8px;
    text-align: left;
  }

  button {
    margin-left: 10px;
    padding: 5px 10px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 3px;
    cursor: pointer;
  }

  button:hover {
    background-color: #0056b3;
  }
</style>
