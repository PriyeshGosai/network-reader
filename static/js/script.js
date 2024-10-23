// Function to load the selected network
function loadNetwork() {
    const network = document.getElementById("network").value;
    if (network !== "") {
        fetch(`/load_network`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ network: network })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(data.message);
                updateComponentList();
            } else {
                alert(data.message);
            }
        });
    }
}

// Function to get components for the loaded network
function updateComponentList() {
    fetch('/get_components')
        .then(response => response.json())
        .then(data => {
            console.log("Response from server:", data);  // Debugging output
            if (Array.isArray(data.components)) {
                let componentSelect = document.getElementById("component");
                componentSelect.innerHTML = ""; // Clear previous options
                data.components.forEach(component => {
                    let option = document.createElement("option");
                    option.value = component;
                    option.text = component;
                    componentSelect.appendChild(option);
                });
            } else {
                console.error("Expected an array but got something else", data);
            }
        });
}

// Function to update attributes and view
function updateComponent() {
    const component = document.getElementById("component").value;
    const type = document.getElementById("type").value;
    let outputDiv = document.getElementById("output_div");
    outputDiv.innerHTML = "Loading...";  // Show loading message

    // Show/hide dropdowns based on "static" or "varying" selection
    const attrSelectContainers = document.getElementsByClassName("attr_select_container");
    const viewTypeContainers = document.getElementsByClassName("view_type_container");

    if (type === 'static') {
        // Hide the attribute and view type dropdowns
        attrSelectContainers[0].style.display = 'none';
        viewTypeContainers[0].style.display = 'none';

        // Your existing logic for fetching static or varying data
        fetch(`/get_data/${component}/all/static`)
            .then(response => response.json())
            .then(data => {
                outputDiv.innerHTML = "";  // Clear loading message
                // Assuming 'data' is your dataset
                let filteredData = filterEmptyColumns(data);

                // Now use filteredData to render your DataTable
                renderTable(filteredData, false);
            })
            .catch(error => {
                outputDiv.innerHTML = "Error fetching data. Please try again.";  // Display error message
                console.error("Error fetching static data:", error);
            });

    } else if (type === 'varying') {
        // Show the attribute and view type dropdowns
        attrSelectContainers[0].style.display = 'block';
        viewTypeContainers[0].style.display = 'block';

        // Fetch attributes for the component and populate the attribute dropdown
        fetch(`/get_attributes/${component}`)
            .then(response => response.json())
            .then(data => {
                let attrSelect = document.getElementById("attr_select");
                attrSelect.innerHTML = "";  // Clear previous options

                // Populate the attribute dropdown with varying attributes
                data.varying.forEach(attr => {
                    let option = document.createElement("option");
                    option.value = attr;
                    option.text = attr;
                    attrSelect.appendChild(option);
                });

                // Automatically trigger the updateView() function to display the data
                updateView();
            });
    }
}

// Function to fetch and display data based on attribute and view type selection with pagination
function updateView() {
    const component = document.getElementById("component").value;
    const attr = document.getElementById("attr_select").value;
    const type = document.getElementById("type").value;
    const view = document.getElementById("view_type").value;

    if (type === 'varying') {
        fetch(`/get_data/${component}/${attr}/varying`)
            .then(response => response.json())
            .then(data => {
                let outputDiv = document.getElementById("output_div");
                outputDiv.innerHTML = "";  // Clear previous output

                if (data.status === "error") {
                    console.error(data.message);
                    outputDiv.innerHTML = data.message;
                    return;
                }

                if (view === 'Table') {
                    // Assuming 'data' is your dataset
                    let filteredData = filterEmptyColumns(data);

                    // Now use filteredData to render your DataTable
                    renderTable(filteredData, true);
                } else if (view === 'Plot') {
                    renderPlot(data, component, attr);
                }
            })
            .catch(error => {
                console.error("Error fetching varying data:", error);
            });
    }
}


// Variables For Column Pages
let currentPage = 0;           // Current column page
let columnsPerPage = 25;       // Limit the columns per page
let dataTable;                 // This will store the DataTable instance

// Function to render a table with sorting, pagination, and column visibility using DataTables
function renderTable(data, hasSnapshots) {
    const outputDiv = document.getElementById("output_div");
    outputDiv.innerHTML = "";  // Clear previous content

    let table = document.createElement("table");
    table.setAttribute("id", "fancyTable");  // Set an ID for the table
    table.setAttribute("class", "display");  // DataTables requires 'display' class

    let header = table.createTHead(); // Create the table header
    let headerRow = header.insertRow(0); // Insert a row into the header

    // Conditionally add 'Snapshot' header if it's varying data (hasSnapshots is true)
    if (hasSnapshots) {
        let snapshotHeader = headerRow.insertCell();
        snapshotHeader.innerHTML = "Snapshot";  // Add snapshot as the first column header
    }

    // Add the rest of the headers (skip 'snapshots' if present)
    Object.keys(data).forEach(key => {
        if (key !== 'snapshots') {
            let cell = headerRow.insertCell();
            cell.innerHTML = key;  // Add other headers
        }
    });

    let body = table.createTBody(); // Create the table body for the data

    let numRows = 0;

    // Check if data.snapshots and data content is defined before trying to access its length
    if (hasSnapshots && data.snapshots && Array.isArray(data.snapshots)) {
        numRows = data.snapshots.length;  // Get number of rows based on snapshots if available
    } else if (Object.values(data).length > 0 && Object.values(data)[0] && Array.isArray(Object.values(data)[0])) {
        numRows = Object.values(data)[0].length;  // Get number of rows from the first attribute
    } else {
        outputDiv.innerHTML = "No data available.";
        return;
    }

    // Populate table rows
    for (let i = 0; i < numRows; i++) {
        let row = body.insertRow(); // Add row to the table body, not header

        // Conditionally add the 'snapshots' as the first cell in each row if varying data (hasSnapshots is true)
        if (hasSnapshots && data.snapshots && data.snapshots[i]) {
            let snapshotCell = row.insertCell(0);
            snapshotCell.innerHTML = data.snapshots[i];  // Add snapshot value in the first column
        }

        // Add data cells for the rest of the columns, formatting numbers to 2 decimal places
        Object.keys(data).forEach(key => {
            if (key !== 'snapshots') {
                let cell = row.insertCell();
                let value = data[key] && data[key][i] !== undefined ? data[key][i] : "N/A";

                // Check if the value is a number and format to 2 decimal places
                if (!isNaN(value) && value !== null) {
                    cell.innerHTML = parseFloat(value).toFixed(2);
                } else {
                    cell.innerHTML = value;  // Non-numeric values remain unchanged
                }
            }
        });
    }

    outputDiv.appendChild(table);  // Append the table to the output div

    // Initialize DataTables with scrolling, and pagination
    dataTable = $('#fancyTable').DataTable({
        "processing": true,
        "deferRender": true,     // Defer rendering for performance
        "scrollY": 800,          // Height of the scrollable area in pixels
        "scrollX": true,         // Enable horizontal scrolling for wide tables
        "scrollCollapse": true,  // Collapse scrollable area if rows are fewer
        "pageLength": 20,        // Number of rows per page
        "lengthMenu": [20, 50, 100],  // Options for number of rows per page
        "destroy": true,         // Destroy existing table when reinitializing
        "paging": true,          // Enable pagination for rows
        "order": [],             // Disable initial ordering to improve performance
        "autoWidth": true,        // Automatically adjust column widths
        "fixedColumns": { 
            leftColumns: 1 
        }
    });
}

function renderPlot(data, component, attr) {
    let outputDiv = document.getElementById("output_div");
    let plotData = [];

    // Ensure snapshots are available in data
    if (data.snapshots) {
        Object.keys(data).forEach(key => {
            if (key !== 'snapshots') {
                plotData.push({
                    x: data.snapshots,  // Use snapshots from data
                    y: data[key],
                    mode: 'lines',
                    name: key
                });
            }
        });
    }

    let layout = {
        title: `${component} ${attr} Time Series`,
        xaxis: { title: 'Time' },
        yaxis: { title: 'Value' }
    };
    Plotly.newPlot(outputDiv, plotData, layout);
}


document.addEventListener("DOMContentLoaded", function() {
    // Ensure event listeners are only added once
    if (!document.getElementById('component').listenerAdded) {
        document.getElementById('component').addEventListener('change', updateComponent);
        document.getElementById('component').listenerAdded = true;
    }

    if (!document.getElementById('type').listenerAdded) {
        document.getElementById('type').addEventListener('change', updateComponent);
        document.getElementById('type').listenerAdded = true;
    }

    if (!document.getElementById('attr_select').listenerAdded) {
        document.getElementById('attr_select').addEventListener('change', updateView);
        document.getElementById('attr_select').listenerAdded = true;
    }
});





function filterEmptyColumns(data) {
    const filteredData = {};
    const keys = Object.keys(data); // Assuming data is in the form of an object with column keys

    // Loop through each column
    keys.forEach(key => {
        const column = data[key];
        let hasNonZeroValue = false;

        // Check if any value in the column is neither null nor zero
        for (let i = 0; i < column.length; i++) {
            if (column[i] !== 0 && column[i] !== null) {
                hasNonZeroValue = true;
                break;
            }
        }

        // If column has at least one non-zero, non-null value, keep it
        if (hasNonZeroValue) {
            filteredData[key] = column;
        }
    });

    return filteredData;  // Return the filtered dataset
}

