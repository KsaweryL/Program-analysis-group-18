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
        return f"S.heap: {self.heap} S.frames: {self.frames}"


def step(state: State) -> State | str:
    assert isinstance(state, State), f"expected frame (or state?) but got {state}"
    frame = state.frames.peek()
    # bc stands for bytecode
    opr = bc[frame.pc]
    logger.debug(f"STEP {opr}\n{state}")
    match opr:
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
        case jvm.Return(type=jvm.Int()):
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.stack.push(v1)
                frame.pc += 1
                return state
            else:
                return "ok -- Function returned successfully with an empty frame"
        case jvm.Return(type=None):
            v1 = frame.stack.pop()
            return "ok -- Function returned successfully with an empty frame"
        case jvm.New(classname=opr):
            """- Creates a new instance of the specified class
            - Pushes a reference to the new instance onto the operand stack
            - The instance is uninitialized
            - Must be followed by an invokespecial to call <init> before use
            - May trigger class initialization if the class is not yet initialized
            """
            frame.pc += 1
            # raise NotImplementedError("New is not implemented")
            return state

        case jvm.Get(static=True, field=field):
            """
            According to the JVM spec:

            - For static fields (getstatic):
            * Pushes the value of the specified static field onto the stack
            * May trigger class initialization if not yet initialized

             + * opr : "get"
                * static : <bool>
                * field : object
                    * class : <ClassName>
                    * name : <string>
                    * type : <SimpleType>
                -- get value from $field (might be $static)
                -- {getfield} ["objectref"] -> ["value"]
                -- if static {getstatic} [] -> ["value"]
            """
            if field.fieldid.name == "$assertionsDisabled":
                # for this special instruction, skipping the actual checks (this is just a hardcoded check)
                frame.pc += 1
                frame.stack.push(field)
                return state

            # return "went into the getStatic"
            # return "assertion error"
            else:
                raise NotImplementedError("Get is not implemented")
        # the number of words here means how many 32bit values does the element contain (int is a single word)
        case jvm.Dup(words=1):
            # the .peek() returns the last element of the stack
            last_stack_element = state.frames.peek()
            state.frames.push(last_stack_element)
            frame.pc += 1
            return state

        case jvm.Dup(words=2):
            # the .peek() returns the last element of the stack
            raise NotImplementedError(f"Don't know how to handle Dup with 2 words")
        case jvm.Ifz(condition=condition_value, target=target_pc_value):
            # DUMMY: not implemented
            # print(f"condition_value: {condition_value}")
            # print(f"target_pc_value: {target_pc_value}")
            most_recent_frame: Frame = state.frames.peek()
            # print(f"before popping: most_recent_frame: {most_recent_frame}")
            most_recent_stack_element: jvm.Value = most_recent_frame.stack.pop()
            # print(f"most_recent_frame: {most_recent_frame}")
            # print(f"most_recent_stack_element: {most_recent_stack_element}")
            if condition_value == "ne":
                # the ifz looks at the current value in the operand stack. if condition is "ne", then the jump is made if opr[0] !=0
                if most_recent_stack_element != 0:
                    # keeping the method value the same since we are staying within a single functions active frame
                    frame.pc.method = frame.pc.method
                    # since the condition was true, the program counter moves to the new location
                    frame.pc.offset = target_pc_value
                else:
                    # if the condition was not filled, the execution just moves to the next instruction
                    frame.pc.offset += 1
            elif condition_value == "eq":
                if most_recent_stack_element == 0:
                    frame.pc.offset = target_pc_value
                else:
                    frame.pc.offset += 1
            else:
                raise NotImplementedError("this if operation is not implemented")
            return state

        case jvm.InvokeSpecial():
            # DUMMY: not implemented
            frame.pc += 1
            return state
        case jvm.Throw():
            # DUMMY: not implemented
            frame.pc += 1
            return state
        case a:
            logger.debug(f"type(a): {type(a)}")
            logger.debug(f"opr: {opr}")
            raise NotImplementedError(f"Don't know how to handle: {a!r}")


"""
this is the part of the file that runs when 
.venv/bin/python3 solutions/interpreter.py 'jpamb.cases.Simple.assertBoolean:(Z)V' '(false)' 
is ran
"""
frame = Frame.from_method(methodid)
for i, v in enumerate(input.values):
    frame.locals[i] = v

    logger.debug(f"v: {v}")

state = State({}, Stack.empty().push(frame))

for x in range(1000):
    state = step(state)
    if isinstance(state, str):
        print(state)
        break
else:
    print("The interpreter ran more than 1000 steps. You probably have infinite loop")
