import forceAtlas2 from 'graphology-layout-forceatlas2';

// Function to normalize and scale values
export const normalize = (value, min, max, scaledMin, scaledMax) => {
    return (
        ((value - min) / (max - min)) * (scaledMax - scaledMin) + scaledMin
    );
};

export const graphLayout = (graph) => {
    // Apply ForceAtlas2 layout
    const settings = forceAtlas2.inferSettings(graph);
    forceAtlas2.assign(graph, { settings, iterations: 60 });
}

export const downloadFile = (graph) => {
    const filename = 'wifi-graph-export.json';
    const content = JSON.stringify(graph.export());

    // Create a Blob with the content
    const blob = new Blob([content], { type: 'application/json' });

    // Create a temporary URL for the Blob
    const url = URL.createObjectURL(blob);

    // Create a temporary anchor element
    const a = document.createElement('a');
    a.href = url;
    a.download = filename; // Set the desired file name

    // Append the anchor to the document and trigger the download
    document.body.appendChild(a);
    a.click();

    // Clean up: remove the anchor and revoke the Blob URL
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }