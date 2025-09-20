#!/usr/bin/env python3
"""A very stupid syntatic analysis, that only checks for assertion errors."""

import logging
import tree_sitter
import tree_sitter_java
import jpamb
import sys


methodid = jpamb.getmethodid(
    "syntaxer",
    "1.0",
    "The Rice Theorem Cookers",
    ["syntatic", "python"],
    for_science=True,
)


JAVA_LANGUAGE = tree_sitter.Language(tree_sitter_java.language())
parser = tree_sitter.Parser(JAVA_LANGUAGE)

log = logging
log.basicConfig(level=logging.DEBUG)


srcfile = jpamb.sourcefile(methodid)

with open(srcfile, "rb") as f:
    log.debug("parse sourcefile %s", srcfile)
    tree = parser.parse(f.read())

simple_classname = str(methodid.classname.name)

log.debug(f"{simple_classname}")

#class query ##################################

# To figure out how to write these you can consult the
# https://tree-sitter.github.io/tree-sitter/playground
class_q = JAVA_LANGUAGE.query(
    f"""
    (class_declaration 
        name: ((identifier) @class-name 
               (#eq? @class-name "{simple_classname}"))) @class
"""
)

for node in tree_sitter.QueryCursor(class_q).captures(tree.root_node)["class"]:
    break
else:
    log.error(f"could not find a class of name {simple_classname} in {srcfile}")

    sys.exit(-1)

# log.debug("Found class %s", node.range)

#node is now a CLASS node

########################################
#method query
method_name = methodid.extension.name

method_q = JAVA_LANGUAGE.query(
    f"""
    (method_declaration name: 
      ((identifier) @method-name (#eq? @method-name "{method_name}"))
    ) @method
"""
)

for node in tree_sitter.QueryCursor(method_q).captures(node)["method"]:

    if not (p := node.child_by_field_name("parameters")):
        log.debug(f"Could not find parameteres of {method_name}")
        continue

    params = [c for c in p.children if c.type == "formal_parameter"]

    if len(params) != len(methodid.extension.params):
        continue

    # log.debug(methodid.extension.params)
    # log.debug(params)

    for tn, t in zip(methodid.extension.params, params):
        if (tp := t.child_by_field_name("type")) is None:
            break

        if tp.text is None:
            break

        # todo check for type.
    else:
        break
else:
    log.warning(f"could not find a method of name {method_name} in {simple_classname}")
    sys.exit(-1)

# log.debug("Found method %s %s", method_name, node.range)

#node is now a METHOD node
#body is definded from a METHOD node !!!!!!!!!!!!
body = node.child_by_field_name("body")
assert body and body.text
for t in body.text.splitlines():
    log.debug("line: %s", t.decode())

#############################################################################
#assert query
assert_q = JAVA_LANGUAGE.query(f"""(assert_statement) @assert""")

for node, t in tree_sitter.QueryCursor(assert_q).captures(body).items():
    if node == "assert":
        log.debug("Found assertion")
        print("assertion error;80%")
        break
    #sys.exit(0)
else:       #executes only if the loop completes without hitting break
    log.debug("Did not find any assertions")
    print("assertion error;10%")
    #sys.exit(0)

###########################################################################
# activity 7 - div query
# - update it so that it would also detect 0
div_expr = JAVA_LANGUAGE.query(
    f"""
    (binary_expression
    operator: "/"
    right: (decimal_integer_literal) @zero
    ) @expr
"""
)

# captured_expr is a dictionary!!
caputred_expr =  tree_sitter.QueryCursor(div_expr).captures(body)

dv_prob = 5
expr_node = None
zero_node = None
zero_node_val = None

# Node is a name, value holds a list with 1 clas sobject Node (which has various parameters)
#like type, start_point, end_point
for node, value in caputred_expr.items():
    if node == "expr":
        expr_node = node
    elif node == "zero":
        zero_node = node
        zero_node_val = value

if expr_node is not None and zero_node is not None:
    
    #0 in binary value
    #log.debug(f"value: {zero_node_val[0].text}")    
    
    if zero_node_val[0].text == b'0':
        dv_prob += 80
    else:
        dv_prob -= 5
else:
    dv_prob -= 5
 
print(f"divide by zero;{dv_prob}%")
sys.exit(0)
