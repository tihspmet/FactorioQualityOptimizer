import argparse
import itertools
import json
import os
from collections import defaultdict
from ortools.linear_solver import pywraplp

JUMP_QUALITY_PROBABILITY = 0.1
QUALITY_NAMES = ['normal', 'uncommon', 'rare', 'epic', 'legendary']

QUALITY_PROBABILITIES = [
    [.01, .013, .016, .019, .025],
    [.02, .026, .032, .038, .05],
    [.025, .032, .04, .047, .062]
]

QUALITY_SPEED_PENALTIES = [-0.05, -0.05, -0.05]

PROD_BONUSES = [
    [.04, .05, .06, .07, 0.1],
    [.06, .07, .09, .11, .15],
    [.1, .13, .16, .19, .25]
]

PROD_SPEED_PENALTIES = [-0.05, -0.1, -0.15]

def calculate_quality_probability_factor(starting_quality, ending_quality, max_quality_unlocked, quality_percent):
    if (starting_quality > max_quality_unlocked):
        raise ValueError('Starting quality cannot be above max quality unlocked')
    if(ending_quality > max_quality_unlocked):
        raise ValueError('Ending quality cannot be above max quality unlocked')
    if ending_quality < starting_quality:
        raise ValueError('Ending quality cannot be below starting quality')

    if  (ending_quality == starting_quality) and (starting_quality == max_quality_unlocked):
        # in this case there are no further qualities we can advance to, so quality remains the same with 100% probability.
        return 1

    elif ending_quality == starting_quality:
        # the probability that quality remains the same is (1 - probability-to-advance)
        return (1 - quality_percent)

    elif (ending_quality > starting_quality) and (ending_quality < max_quality_unlocked):
        # in this case we are producing a higher level quality with probability of quality_percent,
        # and jumped (ending_quality - starting_quality - 1) extra qualities with JUMP_QUALITY_PROBABILITY each time,
        # and the chance it doesn't advance further is 1-JUMP_QUALITY_PROBABILITY
        return quality_percent * (1-JUMP_QUALITY_PROBABILITY) * JUMP_QUALITY_PROBABILITY**(ending_quality - starting_quality - 1)

    elif (ending_quality > starting_quality) and (ending_quality == max_quality_unlocked):
        # this is the same case as above but without any probability of jumping further
        return quality_percent * JUMP_QUALITY_PROBABILITY**(ending_quality - starting_quality - 1)

    else:
        print(f'starting_quality: {starting_quality}')
        print(f'ending_quality: {starting_quality}')
        print(f'max_quality_unlocked: {max_quality_unlocked}')
        raise RuntimeError('Reached impossible condition in calculate_quality_probability_factor')

def calculate_craft_amount(ingredient_quality, product_quality, max_quality_unlocked, quality_percent, prod_bonus):
    # going from ingredient -> product
    return calculate_quality_probability_factor(ingredient_quality, product_quality, max_quality_unlocked, quality_percent) * (1 + prod_bonus)

def get_recipe_id(recipe_key, quality, num_qual_modules, num_prod_modules):
    return f'{QUALITY_NAMES[quality]}__{recipe_key}__{num_qual_modules}-qual__{num_prod_modules}-prod'

def get_item_id(item_name, quality):
    return f'{QUALITY_NAMES[quality]}__{item_name}'

def get_input_id(item_id):
    return f'input__{item_id}'

def get_byproduct_id(item_id):
    return f'byproduct__{item_id}'

def get_output_id(item_id):
    return f'output__{item_id}'

class QualityLinearSolver:

    def __init__(self, config, verbose=False):
        quality_module_tier = config['quality_module_tier']
        quality_module_quality_level = config['quality_module_quality_level']
        self.quality_module_probability = QUALITY_PROBABILITIES[quality_module_tier][quality_module_quality_level]

        prod_module_tier = config['prod_module_tier']
        prod_module_prod_level = config['prod_module_quality_level']
        self.prod_module_bonus = PROD_BONUSES[prod_module_tier][prod_module_prod_level]

        self.quality_speed_penalty = QUALITY_SPEED_PENALTIES[quality_module_tier]
        self.prod_speed_penalty = PROD_SPEED_PENALTIES[prod_module_tier]

        self.max_quality_unlocked = config['max_quality_unlocked']
        self.items = config['items']
        self.module_cost = config['module_cost']
        self.inputs = config['inputs']
        self.byproducts = config['byproducts']
        self.outputs = config['outputs']

        self.recipe_vars = config['recipe_vars']
        self.crafting_machines = config['crafting_machines']
        self.recipes = config['recipes']

        # keys are '{quality_name}__{item_name}', values are lists of solver variables
        # mostly [(recipe)*(amount)]'s) that get summed to a constraint (i.e. zero)
        self.solver_items = {}
        # keys are are '{quality_name}__{recipe_name}__{num_qual_modules}-qual__{num_prod_modules}-prod'
        # each quality level of crafting, and each separate combination of qual/prod, is a separate allowable recipe
        # solved result is equivalent to number of buildings in units where craft_time=1 and craft_speed=1
        self.solver_recipes = {}
        self.solver_inputs = {}
        self.solver_byproducts = {}
        self.solver_outputs = {}
        self.num_modules_var = None
        self.solver_costs = []
        self.verbose = verbose
        self.solver = pywraplp.Solver.CreateSolver("GLOP")
        if not self.solver:
            raise RuntimeError('error setting up solver')

    def setup_item(self, item_name):
        for quality in range(self.max_quality_unlocked+1):
            item_id = get_item_id(item_name, quality)
            self.solver_items[item_id] = []

    def setup_recipe_var(self, recipe_data, crafting_machine_data):
        recipe_key = recipe_data['key']
        allow_productivity = recipe_data['allow_productivity']
        ingredients = recipe_data['ingredients']
        results = recipe_data['results']
        energy_required = recipe_data['energy_required']

        crafting_machine_speed = crafting_machine_data['crafting_speed']
        crafting_machine_module_slots = crafting_machine_data['module_slots']
        crafting_machine_prod_bonus = crafting_machine_data['prod_bonus']

        recipe_qualities = list(range(self.max_quality_unlocked+1))
        num_qual_modules = list(range(crafting_machine_module_slots+1))
        for recipe_quality, num_qual_modules in itertools.product(recipe_qualities, num_qual_modules):
            if allow_productivity:
                num_prod_modules = crafting_machine_module_slots - num_qual_modules
            else:
                num_prod_modules = 0

            prod_factor = 1 + num_prod_modules * self.prod_module_bonus + crafting_machine_prod_bonus
            speed_factor = crafting_machine_speed * (1 - (num_qual_modules * self.quality_speed_penalty + num_prod_modules * self.prod_speed_penalty))

            # we want recipe_var to represent the number of buildings when all is finished
            # that way (recipe_var * module_cost) accurately represents the number of modules used per recipe
            recipe_id = get_recipe_id(recipe_key=recipe_key, quality=recipe_quality, num_prod_modules=num_prod_modules, num_qual_modules=num_qual_modules)
            recipe_var = self.solver.NumVar(0, self.solver.infinity(), name=recipe_id)
            self.solver_recipes[recipe_id] = recipe_var
            self.num_modules_var += recipe_var

            for ingredient in ingredients:
                # ingredient quality is same as recipe quality
                ingredient_item_id = get_item_id(ingredient['name'], recipe_quality)

                ingredient_amount_per_second_per_building = ingredient['amount'] * speed_factor / energy_required

                # negative because it is consumed
                self.solver_items[ingredient_item_id].append( (-1) * ingredient_amount_per_second_per_building * recipe_var)
                if self.verbose:
                    print(f'recipe {recipe_id} consumes {ingredient["amount"]} {ingredient_item_id}')
            # ingredient qualities can produce all possible higher qualities
            result_qualities = list(range(recipe_quality, self.max_quality_unlocked+1))
            for result, result_quality in itertools.product(results, result_qualities):
                result_item_id = get_item_id(result['name'], result_quality)

                quality_percent = num_qual_modules * self.quality_module_probability
                quality_probability_factor = calculate_quality_probability_factor(recipe_quality, result_quality, self.max_quality_unlocked, quality_percent)
                result_amount_per_second_per_building = result['amount'] * speed_factor * quality_probability_factor * prod_factor / energy_required

                self.solver_items[result_item_id].append(result_amount_per_second_per_building * recipe_var)
                if self.verbose:
                    print(f'recipe {recipe_id} produces {result_amount_per_second_per_building} {result_item_id}')

    def run(self):
        self.num_modules_var = self.solver.NumVar(0, self.solver.infinity(), name='num-modules')

        # needs to happen first as setup_recipe depends on self.items being initialized
        for item in self.items:
            self.setup_item(item)

        for recipe_var in self.recipe_vars:
            crafting_machine_key = recipe_var['crafting_machine']
            recipe_key = recipe_var['recipe']
            crafting_machine_data = [c for c in self.crafting_machines if c['key']==crafting_machine_key][0]
            recipe_data = [r for r in self.recipes if r['key']==recipe_key][0]
            self.setup_recipe_var(recipe_data, crafting_machine_data)

        for input in self.inputs:
            # Create variable for free production of input
            item_id = input['item_id']
            cost = input['cost']
            input_id = get_input_id(item_id)
            solver_item_var = self.solver.NumVar(0, self.solver.infinity(), name=input_id)
            self.solver_inputs[item_id] = solver_item_var
            self.solver_items[item_id].append(solver_item_var)
            self.solver_costs.append(cost * solver_item_var)

        for item_id in self.byproducts:
            # Create variable for free production of input
            byproduct_id = get_byproduct_id(item_id)
            solver_item_var = self.solver.NumVar(0, self.solver.infinity(), name=byproduct_id)
            self.solver_byproducts[item_id] = solver_item_var
            self.solver_items[item_id].append( (-1) * solver_item_var)

        for output in self.outputs:
            item_id = output['item_id']
            amount = output['amount']
            output_id = get_output_id(item_id)
            self.solver_items[item_id].append(-amount)

        for item_id, solver_vars in self.solver_items.items():
            self.solver.Add(sum(solver_vars)==0)

        self.solver_costs.append(self.num_modules_var * self.module_cost)
        self.solver.Minimize(sum(self.solver_costs))

        # Solve the system.
        print(f"Solving...")
        print('')
        status = self.solver.Solve()

        if status == pywraplp.Solver.OPTIMAL:
            print("Solution:")
            print(f"Objective value = {self.solver.Objective().Value()}")
            print('')
            print('Inputs used:')
            for input_var in self.solver_inputs.values():
                print(f'{input_var.name()}: {input_var.solution_value()}')
            print('')
            print('Recipes used:')
            for recipe_var in self.solver_recipes.values():
                if(recipe_var.solution_value()>0):
                    print(f'{recipe_var.name()}: {recipe_var.solution_value()}')
            print('')
            print(f'Modules used: {self.num_modules_var.solution_value()}')

        else:
            print("The problem does not have an optimal solution.")

def main():
    codebase_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    default_config_path = os.path.join(codebase_path, 'examples', 'generic_linear_solver', 'one_step_example.json')

    parser = argparse.ArgumentParser(
        prog='Generic Linear Solver',
        description='This program optimizes prod/qual ratios in factories in order to minimize inputs needed for a given output',
    )
    parser.add_argument('-c', '--config', type=str, default=default_config_path, help='Config file. Defaults to \'examples/one_step_example.json\'.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose mode. Prints out item and recipe information during setup.')
    args = parser.parse_args()
    with open(args.config) as f:
        config = json.load(f)
    solver = QualityLinearSolver(config=config, verbose=args.verbose)
    solver.run()

if __name__=='__main__':
    main()
