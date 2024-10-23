import os
import pandas as pd
from ipywidgets import interact, fixed
from IPython.display import display, clear_output
import ipywidgets as widgets
from datetime import datetime, timedelta
import shutil
import logging
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pypsa
from IPython.display import clear_output
network = pypsa.Network()
from pathlib import Path

# Gets File Path for Excel Files
def get_path(dataDict, parentFolder, childFolder, dataFile):
    folder = parentFolder / dataDict[childFolder]["Folder"]
    file_name = f"{dataDict[childFolder][dataFile]}"
    return folder / file_name

# Convert Excel sheets to CSV files
def convert_sheet_to_csv(xls, sheet_name, csv_folder_path):
    df = xls.parse(sheet_name)
    csv_file_path = os.path.join(csv_folder_path, f"{sheet_name}.csv")
    df.to_csv(csv_file_path, index=False)
    return csv_file_path

def convert_excel_to_csv(excel_file_path, csv_folder_path):
    """
    Converts sheets in an Excel file to CSV, filtering by predefined components.
    """
    components = {"buses", "carriers", "generators", "generators-p_max_pu", "generators-p_min_pu", 
                  "generators-p_set", "line_types", "lines", "links", "links-p_max_pu", "links-p_min_pu", 
                  "links-p_set", "loads", "loads-p_set", "shapes", "shunt_impedances", "snapshots", 
                  "storage_units", "stores", "sub_networks", "transformer_types", "transformers"}
    created_csv_files = []

    os.makedirs(csv_folder_path, exist_ok=True)
    for item in os.listdir(csv_folder_path):
        if item.endswith(".csv") and item.replace(".csv", "") in components:
            os.remove(os.path.join(csv_folder_path, item))

    try:
        xls = pd.ExcelFile(excel_file_path)
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(convert_sheet_to_csv, xls, sheet_name, csv_folder_path)
                       for sheet_name in xls.sheet_names if sheet_name in components]
            for future in futures:
                created_csv_files.append(future.result())
    except Exception as e:
        print(f"Error converting Excel to CSV: {e}")
        return []
    finally:
        if xls is not None:
            xls.close()

    print(f"Conversion complete. CSV files saved in '{csv_folder_path}'")
    return created_csv_files

# Importing components from Excel into the network
def import_from_excel(network, file_name):
    """
    Import components from an Excel file into the PyPSA network.
    """
    with pd.ExcelFile(file_name) as xls:
        for key in network.components:
            sheet_name = network.components[key]['list_name']
            if sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, index_col=0)
                valid_columns = network.component_attrs[key].index
                df = df.loc[:, df.columns.intersection(valid_columns)]
                for idx, row in df.iterrows():
                    network.add(key, name=idx, **row.dropna().to_dict())

# Function to generate the next file name
def get_next_filename(folder, base_name, extension):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    contains = os.listdir(folder)

    existing_numbers = []
    for filename in contains:
        # Match filenames that start with the base name and end with the extension
        if filename.startswith(base_name) and filename.endswith(f'.{extension}'):
            try:
                # Extract the number from the filename, assuming the number is between base name and extension
                number = int(filename[len(base_name):-len(f'.{extension}')])
                existing_numbers.append(number)
            except ValueError:
                pass  # Ignore files that don't match the expected format

    # Determine the next number to use
    next_number = max(existing_numbers, default=0) + 1
    return f"{base_name}{next_number}.{extension}"

def solver_selected():

    def simple_network(solver_name):
        try:
            # Initialize the test_network
            test_network = pypsa.Network()

            # Add snapshots (3 hours)
            snapshots = pd.date_range('2024-01-01 00:00', periods=3, freq='h')
            test_network.set_snapshots(snapshots)

            test_network.add("Carrier", "AC")

            # Add buses
            test_network.add("Bus", "Bus1", carrier='AC')
            test_network.add("Bus", "Bus2", carrier='AC')
            test_network.add("Bus", "Bus3", carrier='AC')

            # Add links between buses
            test_network.add("Link", "Link1", bus0="Bus1", bus1="Bus2", p_nom=100)
            test_network.add("Link", "Link2", bus0="Bus2", bus1="Bus3", p_nom=100)

            # Add load on Bus3
            test_network.add("Load", "Load1", bus="Bus3", p_set=[10, 15, 20])

            # Add generators
            test_network.add("Generator", "Gen1", bus="Bus1", p_nom=30, marginal_cost=50)
            test_network.add("Generator", "Gen2", bus="Bus2", p_nom=40, marginal_cost=30)

            # Solve the test_network
            solved = test_network.optimize(solver_name=solver_name)
            
            # Clear output after solving (optional for cleaner output)
            clear_output(wait=True)
            
            return solved  # Return the solved network object if successful
        except Exception as e:
            print(f"Solver {solver_name} failed: {e}")
            return None  # Return None if the solver fails


    def find_solver():
        # List solvers to test, ordered by preference
        solver_options = ['gurobi', 'cplex','mosek', 'highs','glpk']

        # Iterate over the solver options and try to solve the simple network
        for solver in solver_options:
            print(f"Testing solver: {solver}")
            result = simple_network(solver_name=solver)
            if result is not None:
                print(f"Solver {solver} succeeded!")
                return solver  # Return the first working solver
        
        # If no solver works, raise an error
        raise ValueError("No suitable solver found. Please install one of the solvers: " + ', '.join(solver_options))


    # Example usage
    try:
        # Find the first working solver by testing them all
        solver = find_solver()
        print(f"Selected solver: {solver}")
    except ValueError as e:
        print(e)
    return solver

def import_river_inflows(network, filePath):
    # Import and filter river inflow data to match network snapshots

    river_flow_path = filePath
    river_flow_df = pd.read_csv(river_flow_path, parse_dates=['date'], comment="#", index_col='date')
    river_flow_df = river_flow_df.loc[network.snapshots]

    # Check if the time series data matches the network snapshots
    if not river_flow_df.index.equals(network.snapshots):
        print("Warning: Time series data does not match network snapshots!")

    # Get matching and missing inflows based on network generators
    matching_inflows = river_flow_df.columns.intersection(network.generators.index)
    missing_inflows = river_flow_df.columns.difference(network.generators.index)

    # If matching inflows exist, assign them to the network's generators
    if not matching_inflows.empty:
        network.generators_t.p_set = river_flow_df[matching_inflows]
    else:
        print("Warning: No matching river inflows found in the network!")

def import_demand(network, filename):
    # Add the demand data
    demand_file = filename # Insert demand file name
    demand_df = pd.read_csv(demand_file, parse_dates=['date']).set_index('date')
    demand_df = demand_df.loc[network.snapshots]

    # 1. Ensure that time series data matches network snapshots
    if not demand_df.index.equals(network.snapshots):
        print("Warning: The time series data does not match the network's time steps!")

    # 2. Only add data if the load exists in the network
    # Find the intersection of loads in the demand file and the network
    matching_loads = demand_df.columns.intersection(network.loads.index)
    missing_loads = demand_df.columns.difference(network.loads.index)

    if matching_loads.empty:
        print("Warning: No matching loads found in the network!")
    else:
        # Assign the matching loads time series to the network
        network.loads_t.p_set = demand_df[matching_loads]

# Function to add plant data
def add_plant_data(network, row):
    """
    Add plant data to the network based on component type and whether to add to the model.
    """
    if row['Add to model']:
        if row['Component Type'] == 'Link':
            add_link(network, row)
            if row['Has Dam']:
                add_store(network, row)
        elif row['Component Type'] == 'Generator':
            add_generator(network, row)

# Network element addition functions
def add_link(network, row):
    """
    Add a link to the network and log the operation.
    """
    try:
        for gen_type in ['Station Name']:
            if pd.notna(row[gen_type]):
                network.add("Link", row[gen_type],
                            bus0=row['Upstream Hydro Bus'], bus1=row['Downstream Hydro Bus'],
                            bus2=row['Demand Bus'], 
                            p_nom=row[f'p_nom'],
                            efficiency=1, efficiency2=row['efficiency2'], committable=True,
                            min_up_time=row['min_up_time'], marginal_cost=row['marginal_cost'],
                            type=row['Plant Type'], carrier='water')
                network.links_t.p_min_pu.loc[row['p_min_pu']]
    except Exception as e:
        print(f"Error adding link for {row.name}: {e}")

def add_generator(network, row):
    """
    Add a generator to the network and log the operation.
    """
    try:
        for gen_type in ['Station Name']:
            if pd.notna(row[gen_type]):
                network.add("Generator", row[gen_type],
                            bus=row[f'{gen_type.split()[0]} Demand Bus'], p_nom=row[f'{gen_type.split()[0]} Capacity [MW]'],
                            efficiency=1, committable=True, marginal_cost=row['marginal_cost'],
                            min_up_time=row['min_up_time'], p_min_pu=row['p_min_pu'], type=row['Plant type'], carrier='AC')

                if pd.notna(row['p_max_pu-filename']):
                    subfolder = 'solar_data' if "solar" in row['Plant type'].lower() else 'wind_data' if "wind" in row['Plant type'].lower() else None
                    if subfolder:
                        p_max_pu_data = pd.read_csv(f"{subfolder}/{row['p_max_pu-filename']}.csv",
                                                    index_col=0, parse_dates=True, comment = "#" )
                        p_max_pu_data_filtered = p_max_pu_data.loc[network.snapshots[0]:network.snapshots[-1]]
                        network.generators_t.p_max_pu[row[gen_type]] = p_max_pu_data_filtered
    except Exception as e:
        print(f"Error adding generator for {row.name}: {e}")

def add_store(network, row):
    """
    Add a store to the network and log the operation.
    """
    try:
        network.add("Store", row['Store Name'], bus=row['store_bus'], e_nom=row['e_nom'],
                    e_initial_per_period=False, e_cyclic=True, e_cyclic_per_period=True, carrier='water')
        # logger.info(f"Added store for {row.name}.")
    except Exception as e:
        print(f"Error adding store for {row.name}: {e}")

