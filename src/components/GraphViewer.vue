<template>
  <div id="container" ref="container" class="graph-container">
  </div>
  <div id="counter">Nodes: 0</div>
  <div id="legend">
    <LegendTable :ssids="ssids" :ssidColours="ssidColours" />
  </div>
  <div id="infopanel">
    <AttributesTable :attributes="attributes" />
    <SearchComponent :updateSearch="updateSearch" />
    <NodeList :filteredNodes="filteredNodes" @highlightNode="highlightNode" />
    <div id="export-panel">
      <button @click="downloadFile(graph)">Export Graph</button>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from "vue";
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
    //let ssidColours = ref(null);
    let theme = 'light'

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
          edgeReducer: edgeReducer
        }
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

    const updateSearch = (searchTerm) => {
      const term = searchTerm.toLowerCase();
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
      if (attributes.ssid == '' || attributes.ssid == '<MISSING>') return { ...attributes, color };
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

    // Helper function to highlight connected nodes and edges
    function highlightNode(nodeKey) {
      sigmaInstance.setSetting('nodeReducer', (node, data) => {
        if (node === nodeKey || graph.neighbors(nodeKey).includes(node)) {
          return { ...data, color: data.color };
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
      initializeGraph();

      // Connect to WebSocket
      socket = new WebSocket(props.websocketUrl);
      socket.onmessage = handleWebSocketMessage;
      socket.onerror = (error) => {
        console.error("WebSocket error:", error);
      };
    });

    onUnmounted(() => {
      if (socket) socket.close();
      if (sigmaInstance) sigmaInstance.kill();
    });

    // Function to update the counter
    function updateCounter() {
        const nodeCount = graph.nodes().length;
        const edgeCount = graph.edges().length;
        const counterElement = document.getElementById('counter');
        counterElement.innerText = `Nodes: ${nodeCount}, Edges: ${edgeCount}`;
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

    return { container, infopanel, downloadFile, attributes, ssids, ssidColours, filteredNodes, updateSearch, highlightNode };
  },
};
</script>

<style>
  .graph-container {
    width: 70%;
    height: 100vh;
    border-right: 1px solid #ccc;
    float: left;
  }
  #legend {
    position: absolute;
    left: 5px;
    top: 5px;
    padding: 10px;
    background-color: #f8f8f8;
    border-left: 1px solid #ccc;
    height: 100%;
  }  
  #infopanel {
    width: 28%;
    padding: 10px;
    float: left;
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
</style>
