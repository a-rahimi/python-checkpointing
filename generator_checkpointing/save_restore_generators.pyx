from typing import Generator, List, Tuple

from generator_checkpointing.jump cimport *


def save_generator_state(gen: Generator) -> Tuple[int, List]:
    cdef PyFrameObject *frame = <PyFrameObject *>gen.gi_frame

    stack_size = frame.f_stacktop - frame.f_localsplus
    stack_content = [
            <object>frame.f_localsplus[i] if frame.f_localsplus[i] else None
            for i in range(stack_size)
        ]
    return (frame.f_lasti, stack_content)


def restore_generator(gen: Generator, saved_frame: Tuple[int, List]) -> Generator:
    cdef PyFrameObject *frame = <PyFrameObject *>gen.gi_frame
    saved_f_lasti, saved_stack_content = saved_frame

    frame.f_lasti = saved_f_lasti

    cdef int i = 0
    for o in saved_stack_content:
        # TODO: Make sure this is necessary and that i'm not leaking a reference here.
        Py_INCREF(o)
        frame.f_localsplus[i] = <PyObject*> o
        i += 1

    frame.f_stacktop = frame.f_localsplus + i
    assert frame.f_stacktop - frame.f_localsplus == len(saved_stack_content)

    return gen
