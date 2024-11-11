import json
import os
from linear_solver import LinearSolver

def main():
    codebase_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    examples_path = os.path.join(codebase_path, 'examples')
    for example_config in os.listdir(examples_path):
        example_config_filename = os.path.join(examples_path, example_config)
        with open(example_config_filename) as f:
            example_config_data = json.load(f)
        solver = LinearSolver(config=example_config_data)
        solver.run()

if __name__=='__main__':
    main()
