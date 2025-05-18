# Template Template

This is a template for creating new experiment templates in the AI Scientist framework.

## Structure

- `experiment.py`: Main experiment implementation
- `plot.py`: Visualization of experiment results
- `prompt.json`: Main experiment prompt
- `seed_ideas.json`: Example experiment ideas
- `README.md`: This file

## How to Use

1. Copy this template directory to create a new experiment template
2. Modify the following files:
   - `experiment.py`: Implement your experiment logic
   - `plot.py`: Customize plotting for your specific metrics
   - `prompt.json`: Update with your experiment description
   - `seed_ideas.json`: Add your experiment ideas

## Required Files

- `experiment.py` must implement:
  - Command line argument parsing with `--out_dir`
  - Results saving in JSON format
  - Main experiment logic

- `plot.py` must implement:
  - Loading of experiment results
  - Visualization of metrics
  - Saving plots to file

## Notes

- All experiment results should be saved in JSON format
- Plots should be saved as image files
- Use the provided structure to ensure compatibility with the AI Scientist framework 