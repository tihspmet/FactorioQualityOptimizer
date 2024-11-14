#!/usr/bin/env python3

'''
Wrapper for `linear_solver.py` that is more user-friendly than linear_solver.py
Contains many convenience args to make it quick and easy to optimize actual factorio setups.
'''
import argparse
import json
import os
from linear_solver import LinearSolver

CODEBASE_PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
FACTORIO_DATA_FILENAME = os.path.join('data', 'space-age-2.0.11.json')
FACTORIO_DATA_PATH = os.path.join(CODEBASE_PATH, FACTORIO_DATA_FILENAME)
with open(FACTORIO_DATA_PATH) as f:
    FACTORIO_DATA = json.load(f)

DEFAULT_OUTPUT_ITEM = 'electronic-circuit'
DEFAULT_OUTPUT_AMOUNT = 1.0
DEFAULT_OUTPUT_QUALITY = 'legendary'
DEFAULT_INPUT_QUALITY = 'normal'
DEFAULT_PROD_MODULE_TIER = 3
DEFAULT_QUALITY_MODULE_TIER = 3
DEFAULT_MODULE_QUALITY = 'legendary'
DEFAULT_BUILDING_QUALITY = 'legendary'
DEFAULT_MAX_QUALITY_UNLOCKED = 'legendary'
DEFAULT_OFFSHORE_COST = 0.1
DEFAULT_RESOURCE_COST = 1.0
DEFAULT_MODULE_COST = 1.0
DEFAULT_BUILDING_COST = 1.0

def setup_inputs(resource_cost, offshore_cost):
    inputs = []
    for planet in FACTORIO_DATA['planets']:
        for offshore_key in planet['resources']['offshore']:
            input = {
                'key': offshore_key,
                'quality': 'normal',
                'resource': False,
                'cost': offshore_cost
            }
            inputs.append(input)
        # skip plants for now
        for resource_key in planet['resources']['resource']:
            input = {
                'key': resource_key,
                'quality': 'normal',
                'resource': True,
                'cost':resource_cost
            }
            inputs.append(input)
    return inputs

def parse_input_list(items, input_quality):
    inputs = []
    for item in items:
        item_key, item_cost_str = item.split('=')
        item_cost = float(item_cost_str)
        input = {
            'key': item_key,
            'quality': input_quality,
            'resource': False,
            'cost': item_cost
        }
        inputs.append(input)
    return inputs

def parse_resources_list(items):
    inputs = []
    for item in items:
        item_key, item_cost_str = item.split('=')
        item_cost = float(item_cost_str)
        input = {
            'key': item_key,
            'quality': 'normal',
            'resource': True,
            'cost': item_cost
        }
        inputs.append(input)
    return inputs

def parse_recipe_prod_modifiers(recipes):
    recipe_prod_modifiers = {}
    for recipe in recipes:
        recipe_key, recipe_bonus_str = recipe.split('=')
        recipe_prod_modifiers[recipe_key] = float(recipe_bonus_str)
    return recipe_prod_modifiers

def main():
    codebase_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    default_config_path = os.path.join(codebase_path, 'examples', 'generic_linear_solver', 'one_step_example.json')

    parser = argparse.ArgumentParser(
        prog='Factorio Solver',
        description='This program optimizes prod/qual ratios in factories in order to optimize a given output',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-oi', '--output-item', type=str, default=DEFAULT_OUTPUT_ITEM, help='Output item to optimize. See data/space-age-2.0.11.json for item keys.')
    parser.add_argument('-oa', '--output-amount', type=float, default=DEFAULT_OUTPUT_AMOUNT, help='Output item amount per sec')
    parser.add_argument('-oq', '--output-quality', type=str, default=DEFAULT_OUTPUT_QUALITY, help='Output item quality')
    parser.add_argument('-pt', '--prod-module-tier', type=int, default=3, help='Prod module tier')
    parser.add_argument('-qt', '--quality-module-tier', type=int, default=3, help='Quality module tier')
    parser.add_argument('-s', '--check-speed-modules', action='store_true', help='Check beaconed speed modules.')
    parser.add_argument('-st', '--speed-module-tier', type=int, default=3, help='Speed module tier')
    parser.add_argument('-q', '--module-quality', type=str, default=DEFAULT_MODULE_QUALITY, help='Module quality')
    parser.add_argument('-pq', '--prod-module-quality', type=str, default=None, help='Production module quality, overrides --module-quality')
    parser.add_argument('-qq', '--quality-module-quality', type=str, default=None, help='Quality module quality, overrides --module-quality')
    parser.add_argument('-sq', '--speed-module-quality', type=str, default=None, help='Speed module quality, overrides --module-quality')
    parser.add_argument('-bq', '--building-quality', type=str, default=DEFAULT_BUILDING_QUALITY, help='Building quality. Affects both crafting speed and beacon efficiency.')
    parser.add_argument('-mq', '--max-quality-unlocked', type=str, default=DEFAULT_MAX_QUALITY_UNLOCKED, help='Max quality unlocked')
    parser.add_argument('-ii', '--input-items', metavar="", nargs='*', default=None, help='Custom input items to the solver. Should be phrased as item-1=cost-1 item-2=cost-2 ..., with no spaces around equals sign.')
    parser.add_argument('-iq', '--input-quality', default=DEFAULT_INPUT_QUALITY, help='Input quality to the solver. Only used if --input-items flag is set.')
    parser.add_argument('-ir', '--input-resources', metavar="", nargs='*', default=None, help='Custom input resources to the solver. Should be phrased as resource-1=cost-1 resource-2=cost-2 ..., with no spaces around equals sign. If not present, uses all resources on all planets. See data/space-age-2.0.11.json for resource keys.')
    parser.add_argument('-ab', '--allow-byproducts', action='store_true', help='Allows any item besides specified inputs or outputs to exist as a byproduct in the solution. Equivalent to adding void recipes. If not present, byproducts are recycled.')
    parser.add_argument('-rp', '--recipe-prod-modifiers', metavar="", nargs='*', default=None, help='Recipe productivity modifiers obtained from technology tree. Should be phrased as recipe-1=modifier-1 recipe-2=modifier-2 ..., with no spaces around equals sign.')
    parser.add_argument('-ar', '--allowed-recipes', nargs='+', default=None, help='Allowed recipes. Only one of {--allowed-recipes} or {--disallowed-recipes} can be used. See data/space-age-2.0.11.json for recipe keys.')
    parser.add_argument('-dr', '--disallowed-recipes', nargs='+', default=None, help='Disallowed recipes. Only one of {--allowed-recipes} or {--disallowed-recipes} can be used. See data/space-age-2.0.11.json for recipe keys.')
    parser.add_argument('-ac', '--allowed-crafting-machines', nargs='+', type=str, help='Allowed crafting machines. Only one of {--allowed-crafting-machines} or {--disallowed-crafting-machines} can be used. See data/space-age-2.0.11.json for crafting machine keys. (default: None)')
    parser.add_argument('-dc', '--disallowed-crafting-machines', nargs='+', type=str, help='Disallowed crafting machines. Only one of {--disallowed-crafting-machines} or {--disdisallowed-crafting-machines} can be used. See data/space-age-2.0.11.json for crafting machine keys. (default: None)')
    parser.add_argument('-rc', '--resource-cost', type=float, default=DEFAULT_RESOURCE_COST, help='Resource cost')
    parser.add_argument('-oc', '--offshore-cost', type=float, default=DEFAULT_OFFSHORE_COST, help='Offshore cost')
    parser.add_argument('-mc', '--module-cost', type=float, default=DEFAULT_MODULE_COST, help='Module cost')
    parser.add_argument('-bc', '--building-cost', type=float, default=DEFAULT_MODULE_COST, help='Module cost')
    parser.add_argument('-o', '--output', type=str, default=None, help='Output results to csv (if present)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose mode. Prints out item and recipe information during setup.')
    args = parser.parse_args()

    if (args.input_items == None) and (args.input_resources == None):
        inputs = setup_inputs(args.resource_cost, args.offshore_cost)
    else:
        inputs = []
        if args.input_items != None:
            input_items = parse_input_list(args.input_items, args.input_quality)
            inputs.extend(input_items)
        if args.input_resources != None:
            input_resources = parse_resources_list(args.input_resources)
            inputs.extend(input_resources)

    recipe_prod_modifiers = parse_recipe_prod_modifiers(args.recipe_prod_modifiers) if args.recipe_prod_modifiers else None

    config = {
        "data": FACTORIO_DATA_FILENAME,
        "quality_module_tier": args.quality_module_tier,
        "quality_module_quality": args.quality_module_quality or args.module_quality,
        "prod_module_tier": args.prod_module_tier,
        "prod_module_quality": args.prod_module_quality or args.module_quality,
        "check_speed_modules": args.check_speed_modules,
        "speed_module_tier": args.speed_module_tier,
        "speed_module_quality": args.speed_module_quality or args.module_quality,
        "building_quality": args.building_quality,
        "max_quality_unlocked": args.max_quality_unlocked,
        "allow_byproducts": args.allow_byproducts,
        "module_cost": args.module_cost,
        "building_cost": args.building_cost,
        "recipe_prod_modifiers": recipe_prod_modifiers,
        "allowed_recipes": args.allowed_recipes if args.allowed_recipes else None,
        "disallowed_recipes": args.disallowed_recipes if args.disallowed_recipes else None,
        "allowed_crafting_machines": args.allowed_crafting_machines if args.allowed_crafting_machines else None,
        "disallowed_crafting_machines": args.disallowed_crafting_machines if args.disallowed_crafting_machines else None,
        "inputs": inputs,
        "outputs": [
            {
                "key": args.output_item,
                "quality": args.output_quality,
                "amount": args.output_amount
            }
        ]
    }

    solver = LinearSolver(config=config, output_filename=args.output, verbose=args.verbose)
    solver.run()

if __name__=='__main__':
    main()
