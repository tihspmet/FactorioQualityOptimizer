'''
This script was written to solve the following problem.
Suppose we have a recipe A->B, and we start with basic quality A and want only legendary B.
We can do this by recycling any non-legendary B back into A.
We also assume this recipe can accept prod modules.
What are the optimal ratios of prod/quality in the assemblers, and what is the ratio of basic A to legendary B?

At a high level, we can solve a specific configuration by setting up a system of equations,
    then loop over all possible configurations to find the optimal configuration.
The system of equations is loosely based on this: https://kirkmcdonald.github.io/posts/calculation.html

We start by labeling each item i1, ..., iN, eg iron plate=i1, iron gear wheel=i2, etc.
A given recipe might be something like 2 iron plate -> 1 iron gear wheel, which would be 2i1 -> i2.
In general these look like a1*i1 + ... + aN*iN -> bi*i1 + ... + bN*iN (for most recipes, most an/bn are zero).
We can then construct a system of equations that balances the recipes in such a way to turn a given input into a given output.

As a simple example, suppose we wanted to know how many iron plates were needed for 1 iron gear.
Let #g be the number of output gears, #p be the number of input plates,
    and #R be a variable that represents how many buildings are needed for the (plate -> gear) recipe (assuming crafting speed 1)
We then have:

#R = 1 (each recipe building produces 1 gear)
#p = 2*#R  (each recipe building consumes 2 plates)

We can re-write in a more explicit way that states every variable in every equation:
1*#R + 0*#p = 1
-2*#R + 1*#p = 0

This can be abstracted as a matrix equation:
   -------
p: |-2  1|   |#R|   |0|
g: | 1  0| x |#p| = |1|
   -------

More generally we can setup any matrix problem as follows:
   ---------
i1:|R11 ... RM1  1  |   |#R1       |   |0   |
...|... ... ... (0s)| x |(#R2..#RM)| = |(0s)|
iN:|RN1 ... RNM  0  |   |#i1       |   |1   |

This matrix equation will solve for M=N-1 recipe buildings and some unknown #input i1 to generate 1 output of iN.
Once in matrix form, it can be solved quickly by numpy.

The code below represents i1-i5 as the five quality inputs, i6-i10 as the five quality outputs,
    and R1-R5 as the five different quality production recipes, and R6-R9 as the four different recycling recipes (we don't recycle legendary outputs).
#i1 is the main variable being solved (unknown # basic inputs) to generate 1 legendary output.

We use itertools to loop over all permutations of 0/4, 1/3, 2/2, 3/1, 4/0 in the first four production recipes to find the best one.
The last (legendary) production recipe is always prodded.
'''
import itertools
import numpy as np

# EMP allows 5 modules and 50% prod bonus
NUM_RECYCLING_MODULES = 4
NUM_CRAFTING_MODULES = 5
ASSEMBLER_PROD_BONUS = 0.5
RECYCLING_RATIO = 0.25
PROD_BONUS = 0.25
QUALITY_PROBABILITY = 0.062
NUM_QUALITIES = 5

def initialize_recipe_matrix(frac_quality):
    frac_prod = 1-frac_quality
    q = NUM_CRAFTING_MODULES * QUALITY_PROBABILITY * frac_quality
    p = 1 + NUM_CRAFTING_MODULES * PROD_BONUS * frac_prod + ASSEMBLER_PROD_BONUS
    # setup recipe matrix
    X = np.zeros((NUM_QUALITIES, NUM_QUALITIES))

    for i in range(NUM_QUALITIES-1):
        X[i,i] = (1-q[i]) * p[i]

    for i in range(0, NUM_QUALITIES-2):
        for j in range(i+1, NUM_QUALITIES-1):
            X[i,j] = 0.9 * 10**(i-j+1) * q[i] * p[i]

    for i in range(NUM_QUALITIES-1):
        X[i, NUM_QUALITIES-1] = 10**(i-NUM_QUALITIES+2) * q[i] * p[i]

    X[NUM_QUALITIES-1, NUM_QUALITIES-1] = 1 + NUM_CRAFTING_MODULES * PROD_BONUS + ASSEMBLER_PROD_BONUS
    return X.T

def initialize_recycling_matrix():
    # setup recycling matrix
    r = NUM_RECYCLING_MODULES * QUALITY_PROBABILITY
    R = np.zeros((NUM_QUALITIES-1, NUM_QUALITIES))

    for i in range(NUM_QUALITIES-1):
        R[i, i] = (1-r)

    for i in range(0, NUM_QUALITIES-2):
        for j in range(i+1, NUM_QUALITIES-1):
            R[i,j] = 0.9 * 10**(i-j+1) * r

    for i in range(NUM_QUALITIES-1):
        R[i, NUM_QUALITIES-1] = 10**(i-NUM_QUALITIES+2) * r

    R *= RECYCLING_RATIO
    return R.T

def solve(frac_quality, input, goal):
    X = initialize_recipe_matrix(frac_quality)
    R = initialize_recycling_matrix()
    # convert to matrix for row reduction
    X_inputs = -np.identity(NUM_QUALITIES)
    R_inputs = np.block([[-np.identity(NUM_QUALITIES-1)], [np.zeros((1, NUM_QUALITIES-1))]])
    recipes = np.block([
            [X_inputs, R],
            [X, R_inputs]
    ])
    eqs = np.block([[recipes, input.reshape(NUM_QUALITIES*2, 1)]])

    result = np.linalg.solve(eqs, goal)
    num_input = result[-1]
    return num_input

def optimize_modules(input, goal):
    best_frac_quality = None
    best_num_input = 9999999
    possible_frac_qualities = np.array([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    for frac_quality in itertools.product(possible_frac_qualities, repeat=4):
        frac_quality = np.array(frac_quality)
        num_input = solve(frac_quality, input, goal)
        if num_input < best_num_input:
            best_num_input = num_input
            best_frac_quality = frac_quality
    return (best_frac_quality, best_num_input)

def loop_over_goals():
    for i in range(1, NUM_QUALITIES):
        input = np.zeros(NUM_QUALITIES*2)
        input[0] = 1
        goal = np.zeros(NUM_QUALITIES*2)
        goal[i] = 1
        best_frac_quality, best_num_input = optimize_modules(input, goal)
        print(f'Optimizing Q1 Input to Q{i+1} Input: {best_num_input}')
        print(f'num Q1: {best_num_input}')
        print(f'quality ratios: {best_frac_quality}')
        print('')

    for i in range(1, NUM_QUALITIES):
        input = np.zeros(NUM_QUALITIES*2)
        input[0] = 1
        goal = np.zeros(NUM_QUALITIES*2)
        goal[i+NUM_QUALITIES] = 1
        best_frac_quality, best_num_input = optimize_modules(input, goal)
        print(f'Optimizing Q1 Input to Q{i+1} Output: {best_num_input}')
        print(f'num Q1: {best_num_input}')
        print(f'quality ratios: {best_frac_quality}')
        print('')

np.set_printoptions(linewidth=10000, suppress=True, )

if __name__ == '__main__':
    #loop_over_goals()

    input = np.zeros(NUM_QUALITIES*2)
    input[0] = 1
    goal = np.zeros(NUM_QUALITIES*2)
    goal[-1] = 1
    best_frac_quality, best_num_input = optimize_modules(input, goal)
    print(f'Optimizing Q1 Input to Q5 Output')
    print(f'num Q1 input: {best_num_input}')
    print(f'quality ratios: {best_frac_quality}')
    print('')
