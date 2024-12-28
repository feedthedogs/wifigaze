<template>
  <div id="container" ref="container" class="graph-container">
  </div>
  <div id="counter">Nodes: 0</div>
  <div id="legend">
    <h2>Legend</h2>
    <div id="legend-items"></div>
  </div>
  <div id="infopanel" ref="infopanel">
    <h2>Node/Edge Attributes</h2>
    <table id="attributes-table">
      <thead>
        <tr>
          <th>Key</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td colspan="2">Click a node or edge to see its attributes</td>
        </tr>
      </tbody>
    </table>
  </div>
  <div id="search-panel">
    <input type="text" id="search-box" placeholder="Search nodes by label or attribute">
    <ul id="node-list"></ul>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from "vue";
import Sigma from "sigma";
import Graph from "graphology";
import forceAtlas2 from 'graphology-layout-forceatlas2';
import getVendor from 'mac-oui-lookup';

export default {
  props: {
    websocketUrl: {
      type: String,
      required: true,
    },
  },
  setup(props) {
    const container = ref(null);
    let sigmaInstance = null;
    let graph = new Graph();
    let socket = null;
    const infopanel = ref(null);
    const ssids = [];
    let theme = 'light'

    const initializeGraph = () => {
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
      //sigmaInstance.on("clickNode", ({ node }) => {
        //const attributes = graph.getNodeAttributes(node);
        //updateAttributesTable(attributes);
      //});

      // Handle edge click events
      sigmaInstance.on("clickEdge", ({ edge }) => {
        const attributes = graph.getEdgeAttributes(edge);
        updateAttributesTable(attributes);
      });

      // Handle click outside of nodes/edges
      sigmaInstance.on("clickStage", () => {
        updateAttributesTable(null);
      });

      // Add event listeners
      sigmaInstance.on('enterNode', ({ node }) => {
        highlightNode(node);
        const attributes = graph.getNodeAttributes(node);
        attributes['connections'] = makeUL(graph.neighbors(node));
        updateAttributesTable(attributes);
      });

      sigmaInstance.on('leaveNode', () => {
        resetHighlight();
        //document.getElementById('details').innerHTML = 'Hover over a node to see its connections';
      });

      sigmaInstance.bind('graphUpdated', function() {
        updateCounter();
      });

      const searchBox = document.getElementById("search-box");
      const nodeList = document.getElementById("node-list");

      searchBox.addEventListener("input", () => {
        const searchTerm = searchBox.value.toLowerCase();
        nodeList.innerHTML = ""; // Clear the list

        if (searchTerm.trim()) {
          graph.forEachNode((node, attributes) => {
            if (
              (attributes.label && attributes.label.toLowerCase().includes(searchTerm)) ||
              Object.values(attributes).some(
                (value) =>
                  typeof value === "string" &&
                  value.toLowerCase().includes(searchTerm)
              )
            ) {
              const listItem = document.createElement("li");
              listItem.textContent = attributes.label || node;
              listItem.addEventListener("click", () => highlightNode(node));
              nodeList.appendChild(listItem);
            }
          });
        }
      });

      applyTheme(theme);
    };

    const nodeReducer = (key, attributes) => {
      let color = themes[theme].nodeColor
      if (attributes.ssid == '' || attributes.ssid == '<MISSING>') return { ...attributes, color };
      color = ssids[attributes.ssid[0]]['color'];
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

    const handleWebSocketMessage = (event) => {
      try {
        //for (const line of event.data) {
          const elements = event.data.split(",");
          if (elements.length < 3) return;

          // eslint-disable-next-line
          const [ta, ra, sa, da, packetLength, ssid, bssid, radio_channel, flags, packet_type, packet_subtype] = elements.map((e) => e.trim());
          if (!packetLength || ta == '' || ra == '') return;
          
          if (ta == '00:00:00:00:00:00') {
            console.log("unusal client: " + event.data);
            return;
          }

          processNode(ta, ssid, bssid, radio_channel, flags, packet_type, packet_subtype)
          if (!['0x0004', '0x0008'].includes(packet_subtype)) { // don't process some management packets on any other than the source
            processNode(ra, ssid, bssid, radio_channel, flags, packet_type, null)
            if (!['0x0005'].includes(packet_subtype)) { // don't process some management packets on any other than the source
              processNode(sa, ssid, bssid, radio_channel, flags, packet_type, null)
              processNode(da, ssid, bssid, radio_channel, flags, packet_type, null)

              processEdges(ta, ra, sa, da)
            }
          }

          //}
        /*
        console.log("Collated Data:", event.data);
        const rfEvents = JSON.parse(event.data);
        for (const rfEvent of rfEvents.list) {
          const lines = rfEvent.data.trim().split("\n");
          for (const line of lines) {
            const elements = line.split(",");
            if (elements.length < 3) continue;

            // eslint-disable-next-line
            const [ta, ra, sa, da, packetLength, ssid, bssid, radio_channel] = elements.map((e) => e.trim());
            if (!packetLength || ta == '' || ra == '') continue;
            
            processNode(ta, ssid, bssid, radio_channel)
            processNode(ra, ssid, bssid, radio_channel)
            processNode(sa, ssid, bssid, radio_channel)
            processNode(da, ssid, bssid, radio_channel)

            processEdges(ta, ra, sa, da)
          }
        }
        */
        scaleNodes();
        populateLegend();

        // Apply ForceAtlas2 layout
        const settings = forceAtlas2.inferSettings(graph);
        forceAtlas2.assign(graph, { settings, iterations: 60 });
        //sigmaInstance.refresh();
      } catch (err) {
        console.error("Error processing WebSocket message:", err);
      }
    };

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

    const processNode = (mac, ssidHex, bssid, radio_channel, flags, packet_type, packet_subtype) => {
      if (mac == '' || mac == 'ff:ff:ff:ff:ff:ff') return;

      const channel = ieee80211_frequency_to_channel(radio_channel);
      const isAP = mac == bssid || packet_subtype == '0x0008';
      
      const ssid_string = ssidString(ssidHex);
      const ssid = isAP ? ssid_string : ""
      const lookingFor = isAP ? "" : ssid_string;

      if (packet_type == 2 && mac == '01:00:5e:00:00:fb')
        console.log(mac)

      if (packet_type < 2 && !['0x0008', '0x0004', '0x0005', null].includes(packet_subtype))
        console.log(mac)

      if (ssid_string != '' && ssid_string != '<MISSING>') {
        if (ssids[ssid_string] == null) {
          var nodeColor = themes.light.nodeColor
          if (Object.keys(ssids).length <= ssidColours.length)
            nodeColor = ssidColours[(Object.keys(ssids).length)]
          ssids[ssid_string] = {
            nodes: [mac],
            color: nodeColor
          }
        }
        if (!ssids[ssid_string]['nodes'].includes(mac)) {
          ssids[ssid_string]['nodes'].push(mac);
        }
      }
      
      if (!graph.hasNode(mac)) {
        const label = isAP ? 'AP: ' + getVendor(mac, 'unknown') : getVendor(mac, 'unknown')

        graph.addNode(mac, { 
          label: ssid == '' && !isAP ? label : ssid,
          mac: mac,
          isAP: isAP.toString(),
          x: Math.random() * 10,
          y: Math.random() * 10,
          ssid: ssid == '' ? [] : [ssid],
          lookingFor: [lookingFor],
          channels: [channel],
          lastseen: Date.now()
        });
      } else {
        // Client of Network
        if (lookingFor != ''){
          const nodeLookingFor = graph.getNodeAttribute(mac, 'lookingFor');
          if (Array.isArray(nodeLookingFor))
            if (!nodeLookingFor.includes(lookingFor)) {
              nodeLookingFor.push(lookingFor);
              graph.setNodeAttribute(mac, 'lookingFor', nodeLookingFor);
            }
          else
            if (nodeLookingFor != lookingFor) graph.setNodeAttribute(mac, 'lookingFor', [nodeLookingFor, lookingFor]);            
        }
        // AP of network
        if (ssidHex != '' && ssid != '' && ssid != '<MISSING>') {
          const nodeSSID = graph.getNodeAttribute(mac, 'ssid');
          if (Array.isArray(nodeSSID))
            if (!nodeSSID.includes(ssid)) {
              nodeSSID.push(ssid);
              graph.setNodeAttribute(mac, 'ssid', nodeSSID);
            }
          else
            if (nodeSSID != ssid) graph.setNodeAttribute(mac, 'ssid', [nodeSSID, ssid]);                
        }
        // AP Update label
        if (isAP)
          if (!graph.getNodeAttribute(mac, 'isAP') == 'true') {
            graph.setNodeAttribute(mac, 'label', getVendor(mac, 'unknown'));
            graph.setNodeAttribute(mac, 'isAP', 'true');
          }
        // Node Channel
        const channels = graph.getNodeAttribute(mac, 'channels');
        if (Array.isArray(channels)) {
          if (!channels.includes(channel)) {
            channels.push(channel);
            graph.setNodeAttribute(mac, 'channels', channels);
          }
        }
        else
          if (channel != channels) graph.setNodeAttribute(mac, 'channels', [channels, channel]);
        // Node last seen
        graph.setNodeAttribute(mac, 'lastseen', Date.now());
      }
    }

    const processEdges = (ta, ra, sa, da) => {
      if (ra == 'ff:ff:ff:ff:ff:ff') {
        // add edge to self
        if (!graph.hasEdge(ta, ta)) graph.addUndirectedEdge(ta, ta, { size: 2, linktype: "broadcast" });
      } else {
        if (!graph.hasEdge(ta, ra)) graph.addUndirectedEdge(ta, ra, { size: 3, linktype: "physical" });
      }
      if (sa == '' || (ta == sa && ra == da)) return // no need to double link if they are the same
      if (da == 'ff:ff:ff:ff:ff:ff') {
        // add edge to self
        if (!graph.hasEdge(sa, sa)) graph.addUndirectedEdge(sa, sa, { size: 2, linktype: "broadcast" });
      } else {
        if (!graph.hasEdge(sa, da)) graph.addUndirectedEdge(sa, da, { size: 1, linktype: "logical" });
      }
    }

    const ssidString = (hex) => {
      if (hex == '') return '';
      if (hex == '<MISSING>') return hex;
      return hex.match(/.{1,2}/g).map(function (v) {
              return String.fromCharCode(parseInt(v, 16));
            }).join('')
    }

    // Function to normalize and scale values
    const normalize = (value, min, max, scaledMin, scaledMax) => {
      return (
        ((value - min) / (max - min)) * (scaledMax - scaledMin) + scaledMin
      );
    };

    function scaleNodes() {
      // Scale node sizes based on degree
      graph.forEachNode((node) => {
        const size = normalize(graph.degree(node), 1, 10, 5, 15); // Adjust min/max as needed
        graph.setNodeAttribute(node, "size", size);
      });
    }

    function ieee80211_frequency_to_channel(freq)
    {
      if (freq == 2484) return 14;

      if (freq < 2484)
        return (freq - 2407) / 5;

      return freq / 5 - 1000;
    }

    function updateAttributesTable(attributes) {
      const tbody = infopanel.value.querySelector("tbody");
      tbody.innerHTML = ""; // Clear existing rows

      if (!attributes || Object.keys(attributes).length === 0) {
        tbody.innerHTML = "<tr><td colspan='2'>No attributes</td></tr>";
        return;
      }

      for (const [key, value] of Object.entries(attributes)) {
        if (['x', 'y', 'size'].includes(key)) continue;
        const row = document.createElement("tr");
        const keyCell = document.createElement("td");
        const valueCell = document.createElement("td");

        keyCell.textContent = key;
        if (key == 'connections')
          valueCell.appendChild(value);
        else if (key == 'lastseen')
          valueCell.textContent = timeSince(value);
        else
          valueCell.textContent = value;

        row.appendChild(keyCell);
        row.appendChild(valueCell);
        tbody.appendChild(row);
      }
    }

    // Function to update the counter
    function updateCounter() {
        const nodeCount = sigmaInstance.graph.nodes().length;
        const edgeCount = sigmaInstance.graph.edges().length;
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

    const ssidColours = [
      //"#1f77b4", // Blue
      "#ff7f0e", // Orange
      "#2ca02c", // Green
      "#d62728", // Red
      "#9467bd", // Purple
      "#8c564b", // Brown
      "#e377c2", // Pink
      "#7f7f7f", // Gray
      "#bcbd22", // Yellow-Green
      "#17becf", // Cyan
      "#aec7e8", // Light Blue
      "#ffbb78", // Light Orange
      "#98df8a", // Light Green
      "#ff9896", // Light Red
      "#c5b0d5", // Light Purple
      "#c49c94", // Light Brown
      "#f7b6d2", // Light Pink
      "#c7c7c7", // Light Gray
      "#dbdb8d", // Light Yellow-Green
      "#9edae5", // Light Cyan
      "#393b79", // Dark Blue
      "#637939", // Dark Green
      "#8c6d31", // Dark Brown
      "#843c39", // Dark Red
      "#7b4173", // Dark Purple
      "#5254a3", // Indigo
      "#9c9ede", // Periwinkle
      "#6b6ecf", // Violet
      "#b5cf6b", // Lime Green
      "#e7ba52", // Goldenrod
      "#e7969c", // Salmon
      "#d6616b", // Crimson
      "#7b6888", // Lavender
      "#c7c7c7", // Silver
      "#e6550d", // Burnt Orange
      "#31a354", // Forest Green
      "#3182bd", // Sky Blue
      "#756bb1", // Amethyst
      "#636363", // Charcoal
      "#fd8d3c", // Coral
      "#74c476", // Mint Green
      "#6baed6", // Baby Blue
      "#9e9ac8", // Orchid
      "#969696", // Neutral Gray
      "#fdae6b", // Peach
      "#a1d99b", // Pale Green
      "#9ecae1", // Ice Blue
      "#dadaeb", // Pale Lavender
      "#bdbdbd", // Ash Gray
      "#fdd0a2", // Light Peach
      "#c7e9c0", // Pale Mint
    ];

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

    function makeUL(array) {
      // Create the list element:
      var list = document.createElement('ul');
      for (var i = 0; i < array.length; i++) {
          // Create the list item:
          var item = document.createElement('li');
          // Set its contents:
          item.appendChild(document.createTextNode(array[i]));
          // Add it to the list:
          list.appendChild(item);
      }
      // Finally, return the constructed list:
      return list;
    }

    function timeSince(date) {
      var seconds = Math.floor((new Date() - date) / 1000);
      var interval = seconds / 31536000;

      if (interval > 1) {
        return Math.floor(interval) + " years";
      }
      interval = seconds / 2592000;
      if (interval > 1) {
        return Math.floor(interval) + " months";
      }
      interval = seconds / 86400;
      if (interval > 1) {
        return Math.floor(interval) + " days";
      }
      interval = seconds / 3600;
      if (interval > 1) {
        return Math.floor(interval) + " hours";
      }
      interval = seconds / 60;
      if (interval > 1) {
        return Math.floor(interval) + " minutes";
      }
      return Math.floor(seconds) + " seconds";
    }

    function populateLegend() {
      // Populate the legend
      const legendContainer = document.getElementById('legend-items');
      legendContainer.innerHTML = ""; // Clear existing rows
      for (var i=0; i < ssidColours.length; i++) {
      //Object.entries(categories).forEach((color) => {
        if (i == Object.keys(ssids).length) break;
        const legendItem = document.createElement('div');
        legendItem.classList.add('legend-item');

        const colorBox = document.createElement('div');
        colorBox.classList.add('legend-color');
        colorBox.style.backgroundColor = ssidColours[i];

        const label = document.createElement('span');
        label.textContent = Object.keys(ssids)[i];

        legendItem.appendChild(colorBox);
        legendItem.appendChild(label);
        legendContainer.appendChild(legendItem);
      }
    }

    return { container, infopanel };
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
  #legend {
    position: absolute;
    left: 5px;
    top: 5px;
    padding: 10px;
    background-color: #f8f8f8;
    border-left: 1px solid #ccc;
    overflow-y: auto;
  }
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
