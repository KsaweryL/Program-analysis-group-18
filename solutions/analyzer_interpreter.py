import subprocess
import sys
from loguru import logger
import re
import random

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
search_area_type = re.search(r'\b:\(([A-Z]+)?\)\b', method)

assert search_area_type, "No known combination of inputs was found."

occurences: dict[str, int] = {}
total_occurences = 0
has_2_inputs = False

#counters
def Return_counters(occurences_dict, command, args, method):
    
    global total_occurences

    occurences_dict["ok_occurence"] = 0
    occurences_dict["divide_by_zero_occurence"] = 0
    occurences_dict["assertion_error_occurence"] = 0
    occurences_dict["out_of_bounds_occurence"] = 0
    occurences_dict["null_pointer_occurence"] = 0
    occurences_dict["infinite_loop_occurence"] = 0

    #command = ["python", "solutions/interpreter.py", method, arg]

    for arg in args:
        new_command = command.copy()
        new_command.append(method)
        new_command.append(arg)

        # Run the script and capture output
        result = subprocess.run(
            new_command,
            text=True,
            capture_output=True
        )

        if re.search(r'\bok\b', result.stdout):
            occurences_dict["ok_occurence"] += 1
            total_occurences += 1
        elif re.search(r'\bdivide by zero\b', result.stdout):
            occurences_dict["divide_by_zero_occurence"] += 1
            total_occurences += 1       
        elif re.search(r'assertion error', result.stdout):
            occurences_dict["assertion_error_occurence"] += 1
            total_occurences += 1
        elif re.search(r'\bout of bounds\b', result.stdout):
            occurences_dict["out_of_bounds_occurence"] += 1 
            total_occurences += 1        
        elif re.search(r'\bnull pointer\b', result.stdout):
            occurences_dict["null_pointer_occurence"] += 1
            total_occurences += 1
        elif re.search(r'\b\*\b', result.stdout):
            occurences_dict["infinite_loop_occurence"] += 1
            total_occurences += 1

    return occurences_dict

#depending on the type of input variable, we need to change input variables
args_to_check = []
command = ["python", "solutions/interpreter.py"]

#logger.debug(search_area_type.group(0))

if re.search(r'\(Z\)', search_area_type.group(0)):
    #boolean

   #let's define the input we want to check
   args_to_check.append('(true)')
   args_to_check.append('(false)')
   
elif re.search(r'\(I\)', search_area_type.group(0)):
    #Integer

    #for now, generate 0 integer + 10 random numbers form uniform distribution 1 to 100
    args_to_check.append(f"(0)")
    for i in range(10):
        args_to_check.append(f"'({random.randint(0, 100)})'")

elif re.search(r'\(II\)', search_area_type.group(0)):
    #2 Integers

    args_to_check_int = []
        #for now, generate 0 integer + 10 random numbers form uniform distribution 1 to 100
    args_to_check_int.append(0)
    for i in range(2):
        args_to_check_int.append(f"'({random.randint(0, 100)})'")

    #now put it in proper format
    for arg1 in args_to_check_int:
        for arg2 in args_to_check_int:
            args_to_check.append(f"({arg1}, {arg2})")


elif re.search(r'\(B\)', search_area_type.group(0)):
    #byte

    raise ValueError("Byte type dynamic analysis is not yet implemented")
elif re.search(r'\(C\)', search_area_type.group(0)):
    raise ValueError("Char type dynamic analysis is not yet implemented")
elif re.search(r'\(\)', search_area_type.group(0)):
    #void

    #no args to pass
    pass
else:
    raise ValueError("Unknow type")


    

#logger.debug(result.stdout)
#print("Errors (if any):")
#print(result.stderr)

occurences = Return_counters(occurences,command, args_to_check, method)

#logger.debug(occurences)

lower_bound = 0.2
upper_bound = 0.98
additional_number = 0.49

if total_occurences == 0:
    total_occurences = 1

if occurences["ok_occurence"]/total_occurences >= lower_bound:
    if occurences["ok_occurence"]/total_occurences + 0.49 > upper_bound:
        print(f"ok;{upper_bound*100}%")
    else:
        print(f"ok;{round(occurences["ok_occurence"]/total_occurences*100)+49}%")
else:
    print(f"ok;{lower_bound*100}%")

if occurences["divide_by_zero_occurence"]>= lower_bound:
    if occurences["divide_by_zero_occurence"]/total_occurences + 0.49 > upper_bound:
        print(f"divide by zero;{upper_bound*100}%")
    else:
        print(f"divide by zero;{round(occurences["divide_by_zero_occurence"]/total_occurences*100)+49}%")
else:
    print(f"divide by zero;{lower_bound*100}%")

if occurences["assertion_error_occurence"]>= lower_bound:
    if occurences["assertion_error_occurence"]/total_occurences + 0.49 > upper_bound:
        print(f"assertion error;{upper_bound*100}%")
    else:
        print(f"assertion error;{round(occurences["assertion_error_occurence"]/total_occurences*100)+49}%")

else:
        print(f"assertion error;{lower_bound*100}%")

if occurences["out_of_bounds_occurence"]>= lower_bound:
    if occurences["out_of_bounds_occurence"]/total_occurences + 0.49 > upper_bound:
        print(f"out of bounds;{upper_bound*100}%")
    else:
        print(f"out of bounds;{round(occurences["out_of_bounds_occurence"]/total_occurences*100)+49}%")
else:
    print(f"out of bounds;{lower_bound*100}%")

if occurences["null_pointer_occurence"]>= lower_bound:
    if occurences["null_pointer_occurence"]/total_occurences + 0.49 > upper_bound:
        print(f"null pointer;{upper_bound*100}%")
    else:
        print(f"null pointer;{round(occurences["null_pointer_occurence"]/total_occurences*100)+49}%")
else:
    print(f"null pointer;{lower_bound*100}%")

