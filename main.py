import itertools
import numpy as np

NUM_MODULES = 4
RECYCLING_RATIO = 0.25
PROD_BONUS = 0.25
QUALITY_PROBABILITY = 0.06
NUM_QUALITIES = 5

def initialize_recipe_matrix(frac_quality):
    frac_prod = 1-frac_quality
    q = NUM_MODULES * QUALITY_PROBABILITY * frac_quality
    p = 1 + NUM_MODULES * PROD_BONUS * frac_prod
    # setup recipe matrix
    X = np.zeros((NUM_QUALITIES, NUM_QUALITIES))

    for i in range(NUM_QUALITIES-1):
        X[i,i] = (1-q[i]) * p[i]
    
    for i in range(0, NUM_QUALITIES-2):
        for j in range(i+1, NUM_QUALITIES-1):
            X[i,j] = 0.9 * 10**(i-j+1) * q[i] * p[i]
    
    for i in range(NUM_QUALITIES-1):
        X[i, NUM_QUALITIES-1] = 10**(i-NUM_QUALITIES+2) * q[i] * p[i]
    
    X[NUM_QUALITIES-1, NUM_QUALITIES-1] = p[-1]
    return X.T

def initialize_recycling_matrix():
    # setup recycling matrix
    r = NUM_MODULES * QUALITY_PROBABILITY
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

def solve(frac_quality):
    X = initialize_recipe_matrix(frac_quality)
    R = initialize_recycling_matrix()
    # convert to matrix for row reduction
    X_inputs = -np.identity(NUM_QUALITIES)
    R_inputs = np.block([[-np.identity(NUM_QUALITIES-1)], [np.zeros((1, NUM_QUALITIES-1))]])
    recipes = np.block([
            [X_inputs, R],
            [X, R_inputs]
    ])
    q1_input = np.zeros((NUM_QUALITIES*2, 1))
    q1_input[0] = 1
    eqs = np.block([[recipes, q1_input]])

    q5_output = np.zeros(NUM_QUALITIES*2)
    q5_output[-1] = 1

    result = np.linalg.solve(eqs, q5_output)
    num_input = result[-1]
    return num_input

if __name__ == '__main__':
    best_frac_quality = None
    best_num_input = 9999999
    possible_frac_qualities = np.array([0, 0.25, 0.5, 0.75, 1])
    for frac_quality in itertools.product(possible_frac_qualities, repeat=4):
        frac_quality = np.array(frac_quality)
        num_input = solve(frac_quality)
        if num_input < best_num_input:
            best_num_input = num_input
            best_frac_quality = frac_quality
    print(f'best quality ratios: {best_frac_quality}')
    print(f'best Q1 Input per Q% Output: {best_num_input}')
