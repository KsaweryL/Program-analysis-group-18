import subprocess
import sys
from loguru import logger
import re

# examples of full commands
assertInteger = ["python", "solutions/interpreter.py","jpamb.cases.Simple.assertInteger:(I)V","(1)"]
multiError = ["python", "solutions/interpreter.py","jpamb.cases.Simple.multiError:(Z)I" ,"(true)"]

# ---
if len(sys.argv) <= 1:
    raise ValueError("No arguments were passed to the analyzer")
elif len(sys.argv) >2:
    raise ValueError("Too many arguments were given")



#now, we need to determine the second input, based on dynamic analysis for example
#First, we need to determine the type of input
method = sys.argv[1]
search_area_type = re.search(r'\b:\([A-Z]?\)\b', method)


#counters
def Return_counters(command, args, method):
    occurences: dict[str, int] = {}
    occurences["ok_occurence"] = 0
    occurences["divide_by_zero_occurence"] = 0
    occurences["assertion_error_occurence"] = 0
    occurences["out_of_bounds_occurence"] = 0
    occurences["null_pointer_occurence"] = 0
    occurences["infinite_loop_occurence"] = 0

    for arg in args:
        new_command = command.copy()
        new_command.append(method)
        new_command.append(arg)
        
        #command = ["python", "solutions/interpreter.py", method, arg]

        # Run the script and capture output
        result = subprocess.run(
            new_command,
            text=True,
            capture_output=True
        )

        if re.search(r'\bok\b', result.stdout):
            occurences["ok_occurence"] += 1

        if re.search(r'\bdivide by zero\b', result.stdout):
            occurences["divide_by_zero_occurence"] += 1
            
        if re.search(r'\bassertion error\b', result.stdout):
            occurences["assertion_error_occurence"] += 1

        if re.search(r'\bout of bounds\b', result.stdout):
            occurences["out_of_bounds_occurence"] += 1        
        
        if re.search(r'\bnull pointer\b', result.stdout):
            occurences["null_pointer_occurence"] += 1

        if re.search(r'\b\*\b', result.stdout):
            occurences["infinite_loop_occurence"] += 1

    return occurences

command = ["python", "solutions/interpreter.py"]
if re.search(r'\bZ\b', search_area_type.group(0)):
    #boolean

   #let's define the input we want to check
   args_to_check = ['(true)', '(false)']

   occurences = Return_counters(command, args_to_check, method)

   print(occurences)
   sys.exit(-1)
   
elif re.search(r'\bI\b', search_area_type):
    #Integer
    pass
elif re.search(r'\bB\b', search_area_type):
    #byte
    pass
elif re.search(r'\bC\b', search_area_type):
    pass
elif re.search(r'\b\b', search_area_type):
    #void
    pass
else:
    raise ValueError("Unknow type")
    

command = ["python", "solutions/interpreter.py", arg1, arg2]

# Run the script and capture output
result = subprocess.run(
    command,
    text=True,
    capture_output=True
)

#logger.debug(result.stdout)
#print("Errors (if any):")
#print(result.stderr)

if re.search(r'\bok\b', result.stdout):
    print("ok;80%")
else:
    print("ok;2%")

if re.search(r'\bdivide by zero\b', result.stdout):
    print("divide by zero;80%")
else:
    print("divide by zero;2%")

if re.search(r'\bassertion error\b', result.stdout):
    print("assertion error;80%")
else:
    print("assertion error;2%")

if re.search(r'\bout of bounds\b', result.stdout):
    print("out of bounds;80%")
else:
    print("out of bounds;2%")

if re.search(r'\bnull pointer\b', result.stdout):
    print("null pointer;80%")
else:
    print("null pointer;2%")
