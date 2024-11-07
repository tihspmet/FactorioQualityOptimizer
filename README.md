# Factorio Quality Optimizer

## Background

The latest expansion to Factorio introduced [Quality](https://factorio.com/blog/post/fff-375), a new mechanic in which quality modules can be used to increase the quality of every item in the game.
However, producing higher tiers of quality is exponentially difficult, as the probability of increasing quality by even one tier is quite small, let alone trying to make Legendary.
One way to automate the crafting of higher-tier quality items is to recycle lower-quality items that are below the desired tier, as demonstrated in the original quality FFF that only retains rare and above:

![alt text](fff-375-quality-recycling.jpg)

However, optimal recycling loops are not as simple as shoving quality modules everywhere, and often require a mix of prod and quality modules.
The optimal mix depends significantly on factors such as the module tiers (1-3), the module qualities (1-5), the starting and ending qualities being crafted, and any additional prod bonuses.
Sometimes the optimal mix is skewed more towards quality modules and sometimes towards prod modules, and it's usually not obvious what the exact ratio will be ahead of time.

## Overview of the Scripts

There are currently two scripts in the `scripts` folder, `generic_linear_solver.py` and `one_step_matrix_solver.py`.
The script `generic_linear_solver.py` is the main script that should be used.
The other script, `one_step_matrix_solver.py`, was the first script written and is kept for legacy purposes.

### Generic Linear Solver

This script optimizes prod/qual modules in order to minimize the number of low-quality inputs needed per high-quality output.
The linear solver script uses a technique called [Linear Programming](https://en.wikipedia.org/wiki/Linear_programming), or LP for short.
With LP, every possible recipe is added during setup, and the algorithm automatically picks out recipes that contribute to the optimal solution, while ignoring any recipes that don't.

The script only has two command line arguments: a json config file, and an optional verbose flag.
We can run `python ./scripts/generic_linear_solver.py --help` to print a help message:

```
usage: Generic Linear Solver [-h] [-c CONFIG] [-v]

This program optimizes prod/qual ratios in factories in order to minimize inputs needed for a given output

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Config file. Defaults to 'examples/one_step_example.json'.
  -v, --verbose         Verbose mode. Prints out item and recipe information during setup.
```

To understand how to customize the script, you should first read through the examples below, then copy and modify one of the example config files for your own custom configuration.

#### Example 1: One Step Example

This example only has two recipes: crafting item-1 into item-2, and recycling item-2 into item-1.
For this script, we assume we're late-game and have access to all tier-3 legendary modules.
We craft using a tier-3 assembler that has four module slots and no extra productivity.

The script is run with the command `python ./scripts/generic_linear_solver.py --config ./examples/generic_linear_solver/one_step_example.json`:

```
Solving...

Solution:
Objective value = 79.9

Recipes used:
normal__craft-1-to-2__2-qual__2-prod: 106.1
uncommon__craft-1-to-2__2-qual__2-prod: 14.8
rare__craft-1-to-2__2-qual__2-prod: 4.8
epic__craft-1-to-2__2-qual__2-prod: 1.5
legendary__craft-1-to-2__0-qual__4-prod: 0.3
normal__recycle-2-to-1__4-qual__0-prod: 139.4
uncommon__recycle-2-to-1__4-qual__0-prod: 37.2
rare__recycle-2-to-1__4-qual__0-prod: 10.6
epic__recycle-2-to-1__4-qual__0-prod: 3.2
```

In this case we get 79.9 normal inputs per legendary output, using 2 prod/2 qual wherever possible, except for legendary crafting which uses 4 prod modules.
This result matches the default settings for `scripts/one_step_matrix_solver.py`, so seems to be working correctly!

#### Example 2: Two Step Example

This is the same example as above, except we have one intermediate item between our normal input and legendary output.
Basically we're going from normal item-1 to legendary item-3, with an intermediate step of item-2.
Let's see the result by running `python ./scripts/generic_linear_solver.py --config ./examples/generic_linear_solver/two_step_example.json`:

```Solving...

Solution:
Objective value = 37.2

Recipes used:
normal__craft-1-to-2__2-qual__2-prod: 37.2
normal__craft-2-to-3__2-qual__2-prod: 64.9
uncommon__craft-2-to-3__2-qual__2-prod: 17.3
rare__craft-2-to-3__2-qual__2-prod: 4.9
epic__craft-2-to-3__2-qual__2-prod: 1.5
legendary__craft-2-to-3__0-qual__4-prod: 0.3
normal__recycle-3-to-2__4-qual__0-prod: 85.3
uncommon__recycle-3-to-2__4-qual__0-prod: 33.6
rare__recycle-3-to-2__4-qual__0-prod: 10.5
epic__recycle-3-to-2__4-qual__0-prod: 3.2
```

In this case we only need 37.2 normal inputs per legendary output, and again we use 2 qual / 2 prod everywhere possible.
Something interesting to note is that we don't do any recycling loops from item-2 to item-1, and instead only recycle item-3 into item-2.

#### Making a custom config file

The contents of `one_step_example.json` are shown below:

```
{
    "quality_module_tier": 2,
    "quality_module_quality_level": 4,
    "prod_module_tier": 2,
    "prod_module_quality_level": 4,
    "max_quality_unlocked": 4,
    "items": ["item-1", "item-2"],
    "inputs": [
        "normal__item-1"
    ],
    "output": {
        "item_id": "legendary__item-2",
        "amount": 1.0
    },
    "minimize": "normal__item-1",
    "recipes": [
        {
            "key": "craft-1-to-2",
            "allow_productivity": true,
            "module_slots": 4,
            "additional_prod": 0,
            "ingredients": [
                {
                    "name": "item-1",
                    "amount": 1.0
                }
            ],
            "results": [
                {
                    "name": "item-2",
                    "amount": 1.0
                }
            ]
        },
        {
            "key": "recycle-2-to-1",
            "allow_productivity": false,
            "module_slots": 4,
            "additional_prod": 0,
            "ingredients": [
                {
                    "name": "item-2",
                    "amount": 1.0
                }
            ],
            "results": [
                {
                    "name": "item-1",
                    "amount": 0.25
                }
            ]
        }
    ]
}
```

First, note that the module tiers and quality levels use zero-based indexing, so the module tiers run from 0-2 and the quality levels run from 0-4, with 0 representing normal and 4 representing legendary.

Second, note that the linear solver itself doesn't know anything about recycling.
Instead, recycling recipes need to be added to the recipe list, just like any other recipe.

The `additional_prod` flag is useful in cases where the building gives a productivity bonus or when there's some amount of unlocked infinite research.
This flag has units between 0 and 1, so for instance a foundry or EM plant should set this to `0.5`.

The `allow_productivity` flag should be set to `False` for recycling recipes or for crafting recipes that don't allow prod modules.

#### To-Dos

- I'd like to make a third script that can run the linear solver on actual Factorio recipes that use Factorio data and wouldn't require setting up an enormous config file. This would make it easy to run something like "make legendary module 3s as efficiently as possible" and it could solve an entire factory starting from ore mining.
- I think optimizing high-quality outputs per low-quality input might not be the right cost function in all cases. I'm wondering if "number of modules used" could be a better cost function. For instance, a player might only have 100 modules, and making new modules is really expensive, whereas adding more mining drills is really cheap. The player might rather just make more legendary outputs/sec with existing modules, even if it means wasting more normal inputs/sec.
- Speed modules? In the second point above, in theory there *could* be some use for speed modules in certain rare cases if it meant consuming more inputs/ouput but made final quality outputs/sec higher (note I find this unlikely but I'm not 100% sure without solving). However the combinatorics would make things tricky if we wanted every possible combination of speed/qual/prod.

### One Step Matrix Solver

This script optimizes the prod/qual modules at each quality stage in a recycling loop, and prints the number of low-quality inputs to high-quality outputs.
It also prints out any extra by-products, such as how many higher-quality items will be produced than the one being requested.
Note the recycler always has four quality modules.
All of the allowed parameters are shown below, and are also shown with the command `$ python ./main.py --help`:

```
This program optimizes prod/qual ratios in factories, and calculates outputs for a given input

options:
  -h, --help            show this help message and exit
  -st STARTING_TYPE, --starting-type STARTING_TYPE
                        Starting item type. String that is either 'ingredient' or 'product'. Ignored if --no-recycling flag is set, as starting type must be ingredient. (default: ingredient)
  -et ENDING_TYPE, --ending-type ENDING_TYPE
                        Ending item type. String that is either 'ingredient' or 'product'. Ignored if --no-recycling flag is set, as ending type must be product. (default: product)
  -pt PRODUCTIVITY_TIER, --productivity-tier PRODUCTIVITY_TIER
                        Productivity module tier. Number from 1 to 3. (default: 3)
  -qt QUALITY_TIER, --quality-tier QUALITY_TIER
                        Quality module tier. Number from 1 to 3. (default: 3)
  -q MODULE_QUALITY, --module-quality MODULE_QUALITY
                        Quality of the modules in the assembler and recycler (if present). Number from 1 to 5. (default: 5)
  -sq STARTING_QUALITY, --starting-quality STARTING_QUALITY
                        Starting quality ingredient. Number from 1 to 4. (default: 1)
  -eq ENDING_QUALITY, --ending-quality ENDING_QUALITY
                        Ending quality to optimize. Number from 2 to 5. Must be greater than starting quality. (default: 5)
  -mq MAX_QUALITY, --max-quality MAX_QUALITY
                        Max quality unlocked. Number from 3 to 5. Must be greater than or equal to ending quality. (default: 5)
  --enable-recycling, --no-enable-recycling
                        Enables recycling loops. Set this flag if you have unlocked the recycler. (default: True)
  -ms MODULE_SLOTS, --module-slots MODULE_SLOTS
                        number of module slots in the crafting building. (default: 4)
  -p ADDITIONAL_PROD, --additional-prod ADDITIONAL_PROD
                        any extra prod bonus, either from the building or recipe research. Units are percent out of 100. For example if using the foundry, enter 50. (default: 0)
```

The script is written in python and depends on the libraries in `requirements.txt`.
Detailed instructions on how to setup the required python environment is beyond the scope of this README, but if you're new to Python and want to run it, I would recommend the following steps:
1. search "how to install python {windows/mac/linux}" in google and get python available in the terminal or powershell.
2. use `git clone` to get a copy of this repository
3. use `virtualenv` to setup a virtual environment
4. run `pip install -r requirements.txt`
5. run `python ./main.py {--args}` to run the script

Some exmaples of the One Step Matrix Solver are shown below.

#### Example 1

Suppose you're really late-game and have access to legendary tier 3 modules, while using an assembler with four modules slots, and want a recycling loop that turns normal ingredients into legendary products (note this is script with all defaults).

Command:
```
python ./main.py
```

Output:

```
optimizing recycling loop that turns ingredient quality 1 into product quality 5

q1 input per q5 output: 79.87855759632312
recipe q1 uses 2 quality modules and 2 prod modules
recipe q2 uses 2 quality modules and 2 prod modules
recipe q3 uses 2 quality modules and 2 prod modules
recipe q4 uses 2 quality modules and 2 prod modules
recipe q5 uses 0 quality modules and 4 prod modules
```

#### Example 2

Suppose instead you're mid-game and have all tier 3 modules, but they are only level 2 quality (uncommon). Also suppose you haven't unlocked epic yet, and want to do a recycling loop that turns normal ingredients into uncommon products, and you're using the electromagnetics plant with 5 modules slots and built-in productivity of 50%.

Command:
```
$ python ./main.py --productivity-tier 3 --quality-tier 3 --module-quality 2 --starting-quality 1 --ending-quality 2 --max-quality 3 --module-slots 5 --additional-prod 50
```

Output:
```
optimizing recycling loop that turns ingredient quality 1 into product quality 2

q1 input per q2 output: 2.466913725362153
recipe q1 uses 5 quality modules and 0 prod modules
recipe q2 uses 0 quality modules and 5 prod modules

as an additional bonus you get the following for each q2 output:
q3 ingredient: 0.013713390145949652
q3 output: 0.08162732229731934

```

Now let's try the same as above but optimizing for rare outputs. We change `--ending-quality 2` to `--ending-quality 3`:
```
$ python ./main.py --productivity-tier 3 --quality-tier 3 --module-quality 2 --starting-quality 1 --ending-quality 3 --max-quality 3 --module-slots 5 --additional-prod 50

optimizing recycling loop that turns ingredient quality 1 into product quality 3

q1 input per q3 output: 8.524892733141074
recipe q1 uses 5 quality modules and 0 prod modules
recipe q2 uses 5 quality modules and 0 prod modules
recipe q3 uses 0 quality modules and 5 prod modules
```

So in this mid-game case the modules are more biased towards quality than prod.

#### Example 3

Suppose we're late-game (all modules are tier 3 legendary), and we want to turn an item into itself. Is it better to go up the production chain and down (craft then recycle), or down the production chain and back up (recycle then craft)? We'll just use normal assemblers (four module slots, no additional prod). This is where the `--starting-type` and `--ending-type` come in handy.

Going up-then-down the production chain gives 185.3 inputs/output:

```
python ./main.py --starting-type ingredient --ending-type ingredient

optimizing recycling loop that turns ingredient quality 1 into ingredient quality 5

q1 input per q5 output: 185.2831782227558
recipe q1 uses 2 quality modules and 2 prod modules
recipe q2 uses 2 quality modules and 2 prod modules
recipe q3 uses 1 quality modules and 3 prod modules
recipe q4 uses 0 quality modules and 4 prod modules
recipe q5 uses 0 quality modules and 4 prod modules
```

Going down-then-up the production chain gives around 171.5 inputs/output:

```
python ./main.py --starting-type product --ending-type product

optimizing recycling loop that turns product quality 1 into product quality 5

q1 input per q5 output: 171.5214553581744
recipe q1 uses 2 quality modules and 2 prod modules
recipe q2 uses 2 quality modules and 2 prod modules
recipe q3 uses 2 quality modules and 2 prod modules
recipe q4 uses 2 quality modules and 2 prod modules
recipe q5 uses 0 quality modules and 4 prod modules
```

So it's slightly better to go down-then-up, but not by much (171.5 vs 185.3).
