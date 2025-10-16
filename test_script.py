import importlib.util, sys, pathlib, re
import json, pathlib
#import signals as sig
import matplotlib.pyplot as plt
from math import sqrt, pi

from explicit_model import build_model
from openseespy.opensees import *
build_model()

path = pathlib.Path("explicit_model.py")   # adjust if needed
text = path.read_text(encoding="utf-8")

wipeAnalysis()
tolerance = 1.0e-3
constraints('Transformation')    
numberer('RCM')                                    # Reverse Cuthill-McKee DOF numbering
system('SparseGeneral')                            # Solver for large systems
test('EnergyIncr', tolerance, 20 , 1)              # Convergence test: energy norm, tolerance, max iterations
algorithm('ModifiedNewton', '-initial')            # Modified Newton-Raphson algorithm
integrator('Newmark', 0.5, 0.25)                   # Newmark method (β=0.25, γ=0.5 for constant average)
analysis('Transient')                              # Type of analysis: transient (time history)

numEigen = 5
eigenValues = eigen(numEigen)
print("eigen values at start of transient:",eigenValues)
for i, lam in enumerate(eigenValues):
    if lam > 0:
        freq = sqrt(lam) / (2 * pi)
        period = 1 / freq
        print(f"Mode {i+1}: Frequency = {freq:.3f} Hz, Period = {period:.3f} s")
    else:
        print(f"Mode {i+1}: Invalid eigenvalue (λ = {lam})")