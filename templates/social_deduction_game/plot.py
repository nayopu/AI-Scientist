import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Dictionary mapping run numbers to labels for the plot
labels = {
    "run_1": "Baseline",
    # Add more runs as needed
}

def load_results(run_dir):
    """Load results from a run directory"""
    with open(Path(run_dir) / "final_info.json", "r") as f:
        return json.load(f)

def plot_results():
    """Plot the experiment results"""
    # Create figure
    plt.figure(figsize=(10, 6))
    
    # Load and plot data for each run
    for run_name, label in labels.items():
        results = load_results(run_name)
        # Modify this section to plot your specific metrics
        plt.plot(results["results"]["metric1"]["means"], label=label)
    
    plt.xlabel("X Axis Label")
    plt.ylabel("Y Axis Label")
    plt.title("Experiment Results")
    plt.legend()
    plt.grid(True)
    
    # Save plot
    plt.savefig("results.png")
    plt.close()

if __name__ == "__main__":
    plot_results() 