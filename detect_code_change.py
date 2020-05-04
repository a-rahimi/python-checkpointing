from typing import Generator, Set, Tuple
import collections
import glob
import importlib
import os
import pickle
import re

import calltrace
import save_restore_generators as jump

Checkpoint = collections.namedtuple("Checkpoint", ["name", "count", "generator_state"])


def change_point() -> str:
    module_cache = {}

    # Inspect each checkpoint in sequence to see if the code invoked has changed
    last_intact_trace_fname: str = ""
    for trace_fname in sorted(glob.glob("__checkpoints__/functions*.pkl")):
        with open(trace_fname, "rb") as f:
            functions = pickle.load(f)

        # Check each function the was called between this checkpoint and the previous
        # checkpoint. Determine whether the function's code has changed by comparing
        # the hash of its current bytecode against its old bytecode hash.
        for (filename, function_name), expected_hash in functions.items():
            # Load the file as a module. Use our own module cache to avoid polluting
            # the module cache.
            try:
                module = module_cache[filename]
            except KeyError:
                spec = importlib.util.spec_from_file_location("temporary", filename)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module_cache[filename] = module

            # The hash for the current implementation of the function
            current_hash = calltrace.hash_code(getattr(module, function_name).__code__)

            if current_hash != expected_hash:
                print(trace_fname, "has change", filename, function_name)
                return last_intact_trace_fname

        last_intact_trace_fname = trace_fname

    return last_intact_trace_fname


def checkpoint_to_resume() -> Tuple[int, str]:
    trace_fname = change_point()
    if not trace_fname:
        return -1, ""

    m = re.match(r"(.*/)(functions)(\d*)(\.pkl)", trace_fname)
    if not m:
        raise RuntimeError(f"Bad calltrace file path {trace_fname}")

    return int(m[3]), m[1] + "checkpoint" + m[3] + m[4]


def resume_and_save_checkpoints(gen: Generator, module_names: Set[str]):
    os.makedirs("__checkpoints__", exist_ok=True)

    checkpoint_i, checkpoint_fname = checkpoint_to_resume()
    if checkpoint_fname:
        with open(checkpoint_fname, "rb") as f:
            ckpt = pickle.load(f)
        jump.restore_generator(gen, ckpt.generator_state)
        resume_point = True
    else:
        resume_point = None

    print("Starting from checkpoint", checkpoint_i, checkpoint_fname)

    calltrace.trace_funcalls(module_names)
    while True:
        try:
            checkpoint_name = gen.send(resume_point)
        except StopIteration:
            break
        resume_point = False
        checkpoint_i += 1

        # Turn off tracing while we're processing this checkpoint. This isn't
        # strictly necessary but as the code changes, this makes it easier to reason
        # about infinite loops.
        calltrace.stop_trace_funcalls()

        # Save the checkpoint
        ckpt = Checkpoint(checkpoint_name, checkpoint_i, jump.save_generator_state(gen))
        with open("__checkpoints__/checkpoint%02d.pkl" % ckpt.count, "wb") as f:
            pickle.dump(ckpt, f)

        # Save the call log in a separae file
        with open("__checkpoints__/functions%02d.pkl" % ckpt.count, "wb") as f:
            pickle.dump(calltrace.funcall_log, f)

        # Clear the call log so that the next checkpoint only records the function
        # calls that happen after this checkpoint.
        calltrace.funcall_log.clear()

        # Resume tracing just for the next call to the generator
        calltrace.trace_funcalls(module_names)


def step0():
    print(">step 1")


def step1():
    print(">step 2")


def step2():
    print(">step 3")


def processing():
    print('starting')

    if (yield "step0"):
        print("Resuming before step0")

    step0()

    if (yield "step1"):
        print("Resuming before step1")

    step1()

    if (yield "step2"):
        print("Resuming before step2")

    step2()

    print("done")


def main():
    resume_and_save_checkpoints(processing(), [__file__])


if __name__ == "__main__":
    main()
