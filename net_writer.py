from flask import Flask, jsonify, render_template, request
import os
import pypsa
import pandas as pd
import numpy as np

app = Flask(__name__)

# Path to the folder where networks are stored
NETWORK_FOLDER = 'SavedNetworks'

# Initialize a global variable for storing the loaded network
loaded_network = None

# Function to list available networks
def list_saved_networks():
    """Returns a list of available .h5 network files in the NETWORK_FOLDER."""
    try:
        return [f for f in os.listdir(NETWORK_FOLDER) if f.endswith('.h5')]
    except FileNotFoundError:
        return []

# Function to load the network based on the filename
def load_network(network_filename):
    """Loads a network from the .h5 file and returns the network object."""
    global loaded_network
    try:
        network = pypsa.Network()
        network_path = os.path.join(NETWORK_FOLDER, network_filename)
        network.import_from_hdf5(network_path)
        loaded_network = network  # Save the loaded network globally
        return network
    except FileNotFoundError:
        print(f"Error: The network file '{network_filename}' does not exist.")
        return None

# Route to display the PyPSA viewer with network selection
@app.route('/')
def index():
    networks = list_saved_networks()  # Get available networks
    return render_template('pypsa_viewer.html', networks=networks)

# Route to load the selected network
@app.route('/load_network', methods=['POST'])
def load_selected_network():
    network_filename = request.form.get('network')
    network = load_network(network_filename)
    if network:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Failed to load the network."})

# Route to get components from the loaded network
@app.route('/get_components', methods=['GET'])
def get_components():
    if loaded_network:
        components = []  # Initialize the components list
        
        # Iterate through all components and check if they have data
        for component in loaded_network.all_components:
            
            # Access component data, assuming it's a dictionary
            component_data = loaded_network.components.get(component, None)
            
            # Check if component_data is not None and contains data (not empty)
            if component_data and bool(component_data):  # 'bool(component_data)' ensures it's not an empty dictionary
                components.append(component)
        
        return jsonify(components=components)
    else:
        return jsonify({"status": "error", "message": "No network loaded."})



# Route to get attributes (static/varying) for a specific component
@app.route('/get_attributes/<component>', methods=['GET'])
def get_attributes(component):
    if loaded_network:
        component_attrs = loaded_network.component_attrs[component]
        static_attributes = [attr for attr in component_attrs.index if attr not in component_attrs[component_attrs['varying'] == True].index]
        varying_attributes = list(component_attrs[component_attrs['varying'] == True].index)
        return jsonify({'static': static_attributes, 'varying': varying_attributes})
    else:
        return jsonify({"status": "error", "message": "No network loaded."})
    
# Route to get static data for all attributes
@app.route('/get_data/<component>/all/static', methods=['GET'])
def get_all_static_data(component):
    if loaded_network:
        component_data = getattr(loaded_network, loaded_network.components[component]['list_name'])
        if isinstance(component_data, pd.DataFrame):
            # Replace NaN and Infinity values with None
            sanitized_data = component_data.replace([np.inf, -np.inf, np.nan], None).to_dict(orient='list')
            return jsonify(sanitized_data)
    return jsonify({"status": "error", "message": "No static data available."})

@app.route('/get_data/<component>/<attr>/varying', methods=['GET'])
def get_varying_data(component, attr):
    if loaded_network:
        try:
            # Check if time-series data for the component exists
            if hasattr(loaded_network, f'{loaded_network.components[component]["list_name"]}_t'):
                varying_data = getattr(loaded_network, f'{loaded_network.components[component]["list_name"]}_t')
                
                # If the time-series data is a DataFrame
                if isinstance(varying_data, pd.DataFrame):
                    if attr in varying_data.columns:
                        varying_attr_data = varying_data[[attr]].replace([np.inf, -np.inf, np.nan], None).to_dict(orient='list')

                        # Start with an empty dictionary
                        response_data = {}

                        # Add snapshots as the first entry
                        if hasattr(loaded_network, 'snapshots'):
                            response_data['snapshots'] = loaded_network.snapshots.tolist()  # Add snapshots

                        # Add the rest of the data (this preserves the order with snapshots first)
                        response_data.update(varying_attr_data)

                        return jsonify(response_data)
                    else:
                        return jsonify({"status": "error", "message": f"Attribute '{attr}' not found in varying data."})
                
                # If the time-series data is a dictionary of DataFrames
                elif isinstance(varying_data, dict):
                    if attr in varying_data:
                        df = varying_data[attr]
                        if not df.empty and len(df.columns) > 0:
                            varying_attr_data = df.replace([np.inf, -np.inf, np.nan], None).to_dict(orient='list')

                            # Start with an empty dictionary
                            response_data = {}

                            # Add snapshots as the first entry
                            if hasattr(loaded_network, 'snapshots'):
                                response_data['snapshots'] = loaded_network.snapshots.tolist()

                            # Add the rest of the data
                            response_data.update(varying_attr_data)

                            return jsonify(response_data)
                        else:
                            return jsonify({"status": "error", "message": f"Attribute '{attr}' has no valid data."})
                    else:
                        return jsonify({"status": "error", "message": f"Attribute '{attr}' not found in varying data."})
                else:
                    return jsonify({"status": "error", "message": "Invalid data structure for varying data."})
        except Exception as e:
            print(f"Error while fetching varying data for component '{component}', attribute '{attr}': {e}")
            return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "error", "message": "No varying data available."})




if __name__ == '__main__':
    app.run(debug=True)

