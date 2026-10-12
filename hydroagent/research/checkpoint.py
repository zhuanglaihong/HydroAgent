"""Complete optimizer state, including both random streams. No pickle loading."""
import random

import numpy as np


def random_snapshot():
    state = np.random.get_state()
    return {'numpy': [state[0], state[1].tolist(), state[2], state[3], state[4]],
            'python': random.getstate()}


def restore_random(value):
    state = value['numpy']
    np.random.set_state((state[0], np.asarray(state[1], dtype=np.uint32), state[2], state[3], state[4]))
    def tuples(item):
        return tuple(tuples(x) for x in item) if isinstance(item, list) else item
    random.setstate(tuples(value['python']))
