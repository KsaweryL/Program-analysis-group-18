import jpamb
from jpamb import jvm
from dataclasses import dataclass

import sys
from loguru import logger

#my own
import os

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}")

methodid, input = jpamb.getcase()


@dataclass
class PC:
    method: jvm.AbsMethodID
    offset: int

    def __iadd__(self, delta):
        self.offset += delta
        return self

    def __add__(self, delta):
        return PC(self.method, self.offset + delta)

    def __str__(self):
        return f"{self.method}:{self.offset}"


@dataclass
class Bytecode:
    suite: jpamb.Suite
    methods: dict[jvm.AbsMethodID, list[jvm.Opcode]]

    def __getitem__(self, pc: PC) -> jvm.Opcode:
        try:
            opcodes = self.methods[pc.method]
        except KeyError:
            opcodes = list(self.suite.method_opcodes(pc.method))
            self.methods[pc.method] = opcodes

        return opcodes[pc.offset]


@dataclass
class Stack[T]:
    items: list[T]

    def __bool__(self) -> bool:
        return len(self.items) > 0

    @classmethod
    def empty(cls):
        return cls([])

    def peek(self) -> T:
        return self.items[-1]

    def pop(self) -> T:
        return self.items.pop(-1)

    def push(self, value):
        self.items.append(value)
        return self

    def __str__(self):
        if not self:
            return "ϵ"
        return "".join(f"{v}" for v in self.items)


suite = jpamb.Suite()
bc = Bytecode(suite, dict())


@dataclass
class Frame:
    locals: dict[int, jvm.Value]
    stack: Stack[jvm.Value]
    pc: PC

    def __str__(self):
        locals = ", ".join(f"{k}:{v}" for k, v in sorted(self.locals.items()))
        return f"<{{{locals}}}, {self.stack}, {self.pc}>"

    def from_method(method: jvm.AbsMethodID) -> "Frame":
        return Frame({}, Stack.empty(), PC(method, 0))


@dataclass
class State:
    heap: dict[int, jvm.Value]
    frames: Stack[Frame]

    def __str__(self):
        return f"{self.heap} {self.frames}"


def step(state: State) -> State | str:
    assert isinstance(state, State), f"expected frame but got {state}"
    frame = state.frames.peek()
    opr = bc[frame.pc]
    logger.debug(f"STEP {opr}\n{state}")
    match opr:
        # activity 5
        case jvm.Dup():
            v = frame.stack.peek()
            frame.stack.push(v)
            frame.pc += 1
            return state
        case jvm.Throw():
            #since InvokeSpecial return a string - throw is almost never executed

            #TODO - throw usually doesn't work, because invoke specials doesn't work
            #plsu also we don't have an exception handler

            #i'm not sure if that's how we shoudl get our objref exactly
            exc_obj = frame.stack.pop()
            if exc_obj is None:
                return RuntimeError("NullPointerException")
            
            #delete current frame - return to the caller
            state.frames.pop()

            #if no more frames
            if not state.frames:
                return RuntimeError("uncaught exception")
            # Optionally, pushing the exception object to the previous frame's stack
            prev_frame = state.frames.peek()
            prev_frame.stack.push(exc_obj)
            return state
        case jvm.InvokeSpecial(method=method, is_interface=is_interface):
            
            return "assertion error"

            #while there may not be a decompiled version of the method - we can just check the stakc
            #For now, we will assume that we will load all parameters unti the variable of type jvm.Reference() is found

            params = {}
            checked_param = frame.stack.pop()
            dict_iterator = 0
            while checked_param.type != jvm.Reference():
                params[dict_iterator] = checked_param
                checked_param = frame.stack.pop()

            # Create and push new frame
            #but we effectively don't have the method_id for assetion error, so we shouldn't really enter it
            new_frame = Frame(params, Stack.empty(), PC(method, 0))
            state.frames.push(new_frame)

            # Advance caller's pc
            frame.pc += 1

            return state

            #unreachable code for now - becasue we don't have the decompiled methods in this project - tho
            #TODO - no decompiled version of AssertionError!!!
            # it's possible to decompile them on our own from jvm 
            #checking if the decompiled description of the method exists in json file
            decompiled_path = suite.decompiledfile(method.classname)
            if not os.path.exists(decompiled_path):
                logger.warning(f"Missing decompiled file for {method.classname}, skipping InvokeSpecial")
                frame.pc += 1
                return state
            # Getting method info from Suite
            method_info = suite.findmethod(method)
            param_types = method_info["params"]
            num_args = len(param_types)
            args = [frame.stack.pop() for _ in range(num_args)][::-1]  # reverse to preserve order

            # Check if method is static
            is_static = method_info.get("static", False)
            locals = {}

            if not is_static:
                # Pop 'this' reference for non-static methods
                this_ref = frame.stack.pop()
                locals[0] = this_ref
                for i, arg in enumerate(args, 1):
                    locals[i] = arg
            else:
                for i, arg in enumerate(args):
                    locals[i] = arg

            # Create and push new frame
            new_frame = Frame(locals, Stack.empty(), PC(method, 0))
            state.frames.push(new_frame)

            # Advance caller's pc
            frame.pc += 1
            return state
            
        case jvm.New(classname=classname):
            objref = jvm.Value(jvm.Reference(), classname)

            state.heap[objref] = jvm.Value(jvm.Object, {"classname": classname, "fields": {}}) 
            frame.stack.push(objref)
            frame.pc +=1
            return state
        case jvm.If(condition=cond, target=target):
            v2 = frame.stack.pop()
            v1 = frame.stack.pop()
            jump = False

            logger.debug(f"To compare {repr(v1)} and {repr(v2)}")
            if cond in ("eq", "ne", "lt", "le", "gt", "ge"):
                # Integer or boolean comparisons
                assert (v1.type == jvm.Int()), f"Expected int for Ifz but got {v1}"
                assert (v2.type == jvm.Int()), f"Expected int for Ifz but got {v2}"

                if cond == "eq":
                    #if v == 0, jump = True
                    jump = v1 == v2
                elif cond == "ne":
                    jump = v1 != v2
                elif cond == "lt":
                    jump = v1 < v2
                elif cond == "le":
                    jump = v1 <= v2
                elif cond == "gt":
                    jump = v1 > v2
                elif cond == "ge":
                    jump = v1 >= v2
            elif cond in ("is", "isnot"):
                # Reference comparisons
                jump = (v1 is v2) if cond == "is" else (v1 is not v2)
            else:
                raise RuntimeError(f"Unknown If condition: {cond}")
            
            if jump:
                frame.pc.offset = target
            else:
                frame.pc += 1
            

            return state
        case jvm.Binary(type=type,operant=opr):
            v2 = frame.stack.pop()
            v1 = frame.stack.pop()

            assert (v1.type == jvm.Int()) , f"Expected int for binary but got {v1}"
            assert (v2.type == jvm.Int()), f"Expected int for binary but got {v2}"

            result = jvm.Value.int(0)
            match(opr):
                case(jvm.BinaryOpr.Add):
                    result = jvm.Value.int(v1.value + v2.value)
                case(jvm.BinaryOpr.Rem):
                    if (v2 == jvm.Value.int(0)):
                        return "divide by zero"
                    result = jvm.Value.int(v1.value % v2.value)
                case(jvm.BinaryOpr.Div):
                    if (v2 == jvm.Value.int(0)):
                        return "divide by zero"
                    result = jvm.Value.int(v1.value // v2.value)
                case(jvm.BinaryOpr.Mul):
                    result = jvm.Value.int(v1.value * v2.value)
                case(jvm.BinaryOpr.Sub):
                    result = jvm.Value.int(v1.value - v2.value)
                case _:
                    raise NotImplementedError(f"Unhandled operation {opr}")

            frame.stack.push(result)

            frame.pc += 1
            return state
        # --------
        #lecturer said that for now I don't need to check every condition
        # I can't compare it againts python types - but ratehr against types defined
        # in the virtual machines - we use different ones
        case jvm.Ifz(condition=cond, target=target):
            v = frame.stack.pop()
            jump = False

            logger.debug(f"To compare {repr(v)}")
            if cond in ("eq", "ne", "lt", "le", "gt", "ge"):
                # Integer or boolean comparisons
                assert (v.type == jvm.Int()), f"Expected int for Ifz but got {v}"

                if cond == "eq":
                    #if v == 0, jump = True
                    jump = v == jvm.Value.int(0)
                elif cond == "ne":
                    jump = v != jvm.Value.int(0)
                elif cond == "lt":
                    jump = v < jvm.Value.int(0)
                elif cond == "le":
                    jump = v <= jvm.Value.int(0)
                elif cond == "gt":
                    jump = v > jvm.Value.int(0)
                elif cond == "ge":
                    jump = v >= jvm.Value.int(0)
            elif cond in ("is", "isnot"):
                # Reference comparisons
                jump = (v is None) if cond == "is" else (v is not None)
            else:
                raise RuntimeError(f"Unknown Ifz condition: {cond}")
            
            if jump:
                frame.pc.offset = target
            else:
                frame.pc += 1
            
            return state 
        # more things for this activity
        case jvm.Get(static=static, field=field):
            if static:
                t = field.fieldid.type
                logger.debug(f"Type: {field.fieldid.type}")
                #updating getstatic case to default static fields when missing
                if field not in state.heap:
                    #if isinstance(t, jvm.Boolean):
                    #    state.heap[field] = jvm.Value.boolean(False)
                    if isinstance(t, jvm.Int) or isinstance(t, jvm.Boolean):
                        state.heap[field] = jvm.Value.int(0)
                    elif isinstance(t, jvm.Float):
                        state.heap[field] = jvm.Value.float(0.0)
                    else:
                        state.heap[field] = jvm.Value.int(0)
                v = state.heap.get(field, None)
                if v is None:
                    raise NotImplementedError(f"Uninitialized static field {field}")
                #old - frame.stack.push(jvm.Value.int(0))
                #new
                frame.stack.push(v)
            else:
                objref = frame.stack.pop()
                if objref.vale is None:
                    return "NullPointerException"
                obj = state.heap.get(objref.value)
                if obj is None:
                    raise RuntimeError(f"Invalid object reference {objref}")
                v = obj.get(field.extension)
                if v is None:
                    raise RuntimeError(f"Field {field} not found in object {objref}")
                frame.stack.push(v)
            
            frame.pc += 1
            return state
        case jvm.Push(value=v):
            frame.stack.push(v)
            frame.pc += 1
            return state
        case jvm.Load(type=jvm.Int(), index=i):
            #input to this instruction is an index (ex STEP load:I 0 - 0 is an index)

            #convert binary to integers
            v = jvm.Value.int(0)
            #convert bool to int if neccessary
            if frame.locals[i].type == jvm.Boolean():
                if frame.locals[i]== jvm.Value.boolean(True):
                    v = jvm.Value.int(1)
                else:
                    v = jvm.Value.int(0) 
            else:
                v = frame.locals[i]
            frame.stack.push(v)
            frame.pc += 1
            return state
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Div):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value.int(v1.value // v2.value))
            frame.pc += 1
            return state
#        case jvm.Return(type=jvm.Int()):
#            v1 = frame.stack.pop()
#            state.frames.pop()
#            if state.frames:
#                frame = state.frames.peek()
#                frame.stack.push(v1)
#                frame.pc += 1
#                return state
#            else:
#                return "ok"
        case jvm.Return(type=type):

            #logger.debug(f"Return type: {type}")
            if type != None: 
                v1 = frame.stack.pop()
                state.frames.pop()
                if state.frames:
                    frame = state.frames.peek()
                    frame.stack.push(v1)
                    frame.pc += 1
                    return state
                else:
                    return "ok"
            else:
                return "ok"
        case a:
            a.help()
            raise NotImplementedError(f"Don't know how to handle: {a!r}")


frame = Frame.from_method(methodid)
for i, v in enumerate(input.values):
    frame.locals[i] = v

state = State({}, Stack.empty().push(frame))

for x in range(1000):
    state = step(state)
    if isinstance(state, str):
        print(state)
        break
else:
    print("*")


#additional comments
# - we can use logger.debug() for debugging
