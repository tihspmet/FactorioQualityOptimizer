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

PROD_BONUSES = [
    [.04, .05, .06, .07, 0.1],
    [.06, .07, .09, .11, .15],
    [.1, .13, .16, .19, .25]
]

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

def get_unconstrained_input_id(item_id):
    return f'unconstrained-input__{item_id}'

class QualityLinearSolver:

    def __init__(self, config, verbose=False):
        quality_module_tier = config['quality_module_tier']
        quality_module_quality_level = config['quality_module_quality_level']
        self.quality_module_probability = QUALITY_PROBABILITIES[quality_module_tier][quality_module_quality_level]

        prod_module_tier = config['prod_module_tier']
        prod_module_prod_level = config['prod_module_quality_level']
        self.prod_module_bonus = PROD_BONUSES[prod_module_tier][prod_module_prod_level]

        self.max_quality_unlocked = config['max_quality_unlocked']
        self.items = config['items']
        self.inputs = config['inputs']
        self.output = config['output']
        self.minimize = config['minimize']
        self.recipes = config['recipes']
        # keys are '{quality_name}-{item_name}', values are lists of solver variables
        # mostly [(recipe)*(amount)]'s) that get summed to a constraint (i.e. zero)
        self.solver_items = {}
        # keys are are '{quality_name}__{recipe_name}__{num_qual_modules}-qual__{num_prod_modules}-prod'
        # each quality level of crafting, and each separate combination of qual/prod, is a separate allowable recipe
        # solved result is equivalent to number of buildings in units where craft_time=1 and craft_speed=1
        self.solver_recipes = {}
        # keys are '{quality_name}-{item_name}', values are solver vars that act as unconstrained inputs to the system
        self.solver_inputs = {}
        self.verbose = verbose
        self.solver = pywraplp.Solver.CreateSolver("GLOP")
        if not self.solver:
            raise RuntimeError('error setting up solver')
    
    def setup_item(self, item_name):
        for quality in range(self.max_quality_unlocked+1):
            item_id = get_item_id(item_name, quality)
            self.solver_items[item_id] = []
    
    def calculate_result_amount(self, base_amount, recipe_quality, product_quality, num_qual_modules, num_prod_modules, additional_prod):
        quality_percent = num_qual_modules * self.quality_module_probability
        prod_module_bonus = num_prod_modules * self.prod_module_bonus + additional_prod
        quality_probability_factor = calculate_quality_probability_factor(recipe_quality, product_quality, self.max_quality_unlocked, quality_percent)
        result_amount = base_amount * quality_probability_factor * (1 + prod_module_bonus + additional_prod)
        return result_amount

    def setup_recipe(self, recipe):
        key = recipe['key']
        allow_productivity = recipe['allow_productivity']
        module_slots = recipe['module_slots']
        additional_prod = recipe['additional_prod']
        ingredients = recipe['ingredients']
        results = recipe['results']

        recipe_qualities = list(range(self.max_quality_unlocked+1))
        num_qual_modules = list(range(module_slots+1))
        for recipe_quality, num_qual_modules in itertools.product(recipe_qualities, num_qual_modules):
            if allow_productivity:
                num_prod_modules = module_slots - num_qual_modules
            else:
                num_prod_modules = 0
            recipe_id = get_recipe_id(recipe_key=recipe['key'], quality=recipe_quality, num_prod_modules=num_prod_modules, num_qual_modules=num_qual_modules)
            recipe_var = self.solver.NumVar(0, self.solver.infinity(), name=recipe_id)
            self.solver_recipes[recipe_id] = recipe_var
            for ingredient in ingredients:
                # ingredient quality is same as recipe quality
                ingredient_item_id = get_item_id(ingredient['name'], recipe_quality)
                # negative because it is consumed
                self.solver_items[ingredient_item_id].append(-ingredient['amount']*recipe_var)
                if self.verbose:
                    print(f'recipe {recipe_id} consumes {ingredient["amount"]} {ingredient_item_id}')
            # ingredient qualities can produce all possible higher qualities
            result_qualities = list(range(recipe_quality, self.max_quality_unlocked+1))
            for result, result_quality in itertools.product(results, result_qualities):
                result_item_id = get_item_id(result['name'], result_quality)
                result_amount = self.calculate_result_amount(result["amount"], recipe_quality, result_quality, num_qual_modules, num_prod_modules, additional_prod)
                self.solver_items[result_item_id].append(result_amount*recipe_var)
                if self.verbose:
                    print(f'recipe {recipe_id} produces {result_amount} {result_item_id}')
    
    def run(self):
        # needs to happen first as setup_recipe depends on self.items being initialized
        for item in self.items:
            self.setup_item(item)
        
        for recipe in self.recipes:
            self.setup_recipe(recipe)

        for item_id in self.inputs:
            # Create variable for free production of input
            unconstrained_input_id = get_unconstrained_input_id(item_id)
            solver_item_var = self.solver.NumVar(0, self.solver.infinity(), name=unconstrained_input_id)
            self.solver_inputs[item_id] = solver_item_var
            self.solver_items[item_id].append(solver_item_var)
        
        output_item_id = self.output['item_id']
        self.solver_items[output_item_id].append(-self.output['amount'])
        
        for item_id, solver_vars in self.solver_items.items():
            self.solver.Add(sum(solver_vars)==0)
        
        self.solver.Minimize(self.solver_inputs[self.minimize])

        # Solve the system.
        print(f"Solving...")
        print('')
        status = self.solver.Solve()

        if status == pywraplp.Solver.OPTIMAL:
            print("Solution:")
            print(f"Objective value = {self.solver.Objective().Value():0.1f}")
            print('')
            print('Recipes used:')
            for recipe_var in self.solver_recipes.values():
                if(recipe_var.solution_value()>0):
                    print(f'{recipe_var.name()}: {recipe_var.solution_value():0.1f}')
        else:
            print("The problem does not have an optimal solution.")

def main():
    codebase_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    default_config_path = os.path.join(codebase_path, 'examples', 'generic_linear_solver', 'one_step_example.json')

    parser = argparse.ArgumentParser(
        prog='Generic Linear Solver',
        description='This program optimizes prod/qual ratios in factories, and calculates outputs for a given input',
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
