import jpamb
from jpamb import jvm
from dataclasses import dataclass

import sys
from loguru import logger

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
        case jvm.InvokeSpecial(method=method, is_interface=is_interface):

            pass
        case jvm.New(classname=classname):
            #as a reference, we will use current number of objects on the heap
            objref = len(state.heap)

            state.heap[objref] = jvm.Value(jvm.Reference(), {"classname": classname, "fields": {}}) 
            frame.stack.push(objref)
            frame.pc +=1
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
                assert (v.type == jvm.Int()) or ( v.type == jvm.Boolean()), f"Expected int or bool for Ifz but got {v}"

                v2 = jvm.Value.int(0)
                #convert bool to int if neccessary
                if v.type == jvm.Boolean():
                    if v == True:
                        v2 = jvm.Value.int(1)
                    else:
                        v2 = jvm.Value.int(0) 
                else:
                    v2 = v

                if cond == "eq":
                    #if v == 0, jump = True
                    jump = v2 == jvm.Value.int(0)
                elif cond == "ne":
                    jump = v2 != jvm.Value.int(0)
                elif cond == "lt":
                    jump = v2 < jvm.Value.int(0)
                elif cond == "le":
                    jump = v2 <= jvm.Value.int(0)
                elif cond == "gt":
                    jump = v2 > jvm.Value.int(0)
                elif cond == "ge":
                    jump = v2 >= jvm.Value.int(0)
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
                    if isinstance(t, jvm.Boolean):
                        state.heap[field] = jvm.Value.boolean(False)
                    elif isinstance(t, jvm.Int):
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
            frame.stack.push(frame.locals[i])
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
