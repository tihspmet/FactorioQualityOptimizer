from collections import defaultdict
from ortools.linear_solver import pywraplp

NUM_RECYCLING_MODULE_SLOTS = 4
RECYCLING_RATIO = 0.25
JUMP_QUALITY_PROBABILITY = 0.1

#def calculate_craft_amount(self, frac_quality):
#    frac_prod = 1-frac_quality
#    q = self.module_slots * self.quality_module_probability * frac_quality
#    p = 1 + self.module_slots * self.prod_module_bonus * frac_prod + self.additional_prod
#    # setup recipe matrix
#    X = np.zeros(self.num_quality_items_in_solver)
#
#    X[0] = (1-q) * p
#
#    for i in range(self.num_quality_items_in_solver-1):
#        X[i] = 0.9 * 10**(-i+1) * q * p
#
#    X[self.num_quality_items_in_solver-1] = 10**(-self.num_quality_items_in_solver+2) * q * p
#
#    return X.reshape((self.num_quality_items_in_solver, 1))

QUALITY_NAMES = ['normal', 'uncommon', 'rare', 'epic', 'legendary']

def crafting_recipe_key(quality):
    return f'craft-{QUALITY_NAMES[quality]}'

def recycling_recipe_key(quality):
    return f'recycle-{QUALITY_NAMES[quality]}'

def ingredient_item_key(quality):
    return f'ingredient-{QUALITY_NAMES[quality]}'

def product_item_key(quality):
    return f'product-{QUALITY_NAMES[quality]}'

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

def calculate_recycle_amount(product_quality, ingredient_quality, max_quality_unlocked, quality_percent):
    return calculate_quality_probability_factor(product_quality, ingredient_quality, max_quality_unlocked, quality_percent) * RECYCLING_RATIO

class Item:

    def __init__(self, name, quality_level):
        self.name = name
        self.quality_level = quality_level
        self.quality_name = QUALITY_NAMES[quality_level]
        self.key = f'{self.name}-{self.quality_name}'
        self.recipe_vars = []
        self.constants = []

    def add_recipe_var(self, recipe, amount):
        self.recipe_vars.append(recipe * amount)
    
    def add_constant(self, num):
        self.constants.append(num)
    
    def get_constraint(self):
        return sum(self.recipe_vars)+sum(self.constants) == 0
    
class OneStepSolver:

    def __init__(self, quality_module_probability, prod_module_bonus, num_module_slots, max_quality_unlocked):
        self.quality_module_probability = quality_module_probability
        self.prod_module_bonus = prod_module_bonus
        self.num_module_slots = num_module_slots
        self.max_quality_unlocked = max_quality_unlocked
    
    def run(self):
        solver = pywraplp.Solver.CreateSolver("GLOP")

        ingredients = []
        products = []
        for quality in range(self.max_quality_unlocked+1):
            ingredient = Item(name='ingredient', quality_level=quality)
            ingredients.append(ingredient)
            product = Item(name='product', quality_level=quality)
            products.append(product)

        # Create one variable for each recipe and and one variable for free production of normal ingredient
        i1 = solver.NumVar(0, solver.infinity(), "supply-ingredient-normal")
        ingredients[0].add_recipe_var(i1, 1)

        crafting_recipes = []
        for ingredient in ingredients:
            for num_qual_modules in range(0, self.num_module_slots+1):
                num_prod_modules = self.num_module_slots - num_qual_modules
                name = f'craft {ingredient.key} with {num_qual_modules} qual / {num_prod_modules} prod'
                recipe = solver.NumVar(0, solver.infinity(), name=name)
                crafting_recipes.append(recipe)

                ingredient.add_recipe_var(recipe, -1)

                quality_percent = num_qual_modules * self.quality_module_probability
                prod_bonus = num_prod_modules * self.prod_module_bonus
                for product in products:
                    if product.quality_level >= ingredient.quality_level:
                        output = calculate_craft_amount(ingredient.quality_level, product.quality_level, self.max_quality_unlocked, quality_percent, prod_bonus)
                        print(f'craft {ingredient.key} -> {product.key} with {num_qual_modules} qual and {num_prod_modules} prod = {output}')
                        product.add_recipe_var(recipe, output)

        recycling_recipes = []
        for product in products:
            name = f'recycle {product.key}'
            recipe = solver.NumVar(0, solver.infinity(), name=name)
            recycling_recipes.append(recipe)

            product.add_recipe_var(recipe, -1)

            quality_percent = self.num_module_slots * self.quality_module_probability
            for ingredient in ingredients:
                if ingredient.quality_level >= product.quality_level:
                    output = calculate_recycle_amount(product.quality_level, ingredient.quality_level, self.max_quality_unlocked, quality_percent)
                    print(f'recycle {product.key} -> {ingredient.key} = {output}')
                    ingredient.add_recipe_var(recipe, output)


        products[self.max_quality_unlocked].add_constant(-1)

        for ingredient in ingredients:
            solver.Add(ingredient.get_constraint())

        for product in products:
            solver.Add(product.get_constraint())

        solver.Minimize(i1)

        # Solve the system.
        print(f"Solving...")
        status = solver.Solve()

        if status == pywraplp.Solver.OPTIMAL:
            print("Solution:")
            print(f"Objective value = {solver.Objective().Value():0.1f}")
            for crafting_recipe in crafting_recipes:
                if crafting_recipe.solution_value()>0:
                    print(f'{crafting_recipe.name()}: {crafting_recipe.solution_value():0.1f}')
            for recycling_recipe in recycling_recipes:
                if recycling_recipe.solution_value()>0:
                    print(f'{recycling_recipe.name()}: {recycling_recipe.solution_value():0.1f}')
        else:
            print("The problem does not have an optimal solution.")

        print("\nAdvanced usage:")
        print(f"Problem solved in {solver.wall_time():d} milliseconds")
        print(f"Problem solved in {solver.iterations():d} iterations")

def main():
    solver = OneStepSolver(quality_module_probability=0.062, prod_module_bonus=0.25, num_module_slots=4, max_quality_unlocked=4)
    solver.run()

if __name__=='__main__':
    main()
