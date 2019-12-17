import logging
import os
import torch
import numpy as np
import gzip

from typing import Tuple, List, Generator
from itertools import chain

from flambe.dataset import Dataset
from flambe.compile import registrable_factory

logger = logging.getLogger(__name__)

# (input, move probs, game outcome)
DataPoint = Tuple[torch.Tensor, torch.Tensor, torch.Tensor]


def stone_plane(plane: str) -> torch.Tensor:
    bits = np.unpackbits(np.array(bytearray.fromhex('0' + plane)))[7:]
    return torch.tensor(bits).float().view(19, 19)


def move_plane(turn: str) -> List[torch.Tensor]:
    # 0 = black, 1 = white
    # 17) All 1 if black is to move, 0 otherwise
    # 18) All 1 if white is to move, 0 otherwise
    ones = torch.ones(19, 19)
    zeros = torch.zeros(19, 19)
    if turn == '0':
        # black's turn to move
        return [ones, zeros]
    return [zeros, ones]


def parse_file(filename: str) -> Generator[DataPoint, None, None]:
    input_planes: List[torch.Tensor] = []
    logger.info(f'Processing {filename}')
    with gzip.open(filename, 'rt') as f:  # type: ignore
        for i, line in enumerate(f):
            remainder = i % 19
            if remainder < 16:
                input_planes.append(stone_plane(line.strip()))
            elif remainder == 16:
                input_planes.extend(move_plane(line.strip()))
            elif remainder == 17:
                move_probs = torch.tensor([float(p) for p in line.split()])
            else:
                # remainder == 18
                yield torch.stack(input_planes), move_probs, torch.tensor(float(line))
                input_planes = []


def get_datapoints(filenames: List[str]) -> List[DataPoint]:
    return [i for i in chain(*[parse_file(f) for f in filenames])]


def get_file_paths(data_dir_path: str, prefix: str, low: int, high: int) -> List[str]:
    return [os.path.join(data_dir_path, f'{prefix}.{i}.gz') for i in range(low, high)]


class GoDataset(Dataset):

    def __init__(self, train_files: List[str], val_files: List[str], test_files: List[str]):
        self._train = get_datapoints(train_files)
        self._val = get_datapoints(val_files)
        self._test = get_datapoints(test_files)

    @property
    def train(self) -> List[DataPoint]:
        return self._train

    @property
    def val(self) -> List[DataPoint]:
        return self._val

    @property
    def test(self) -> List[DataPoint]:
        return self._test

    @registrable_factory
    @classmethod
    def from_data_dir(cls, data_dir_path: str, prefix: str,
                      train_high: int, val_high: int, test_high: int) -> 'GoDataset':
        train_paths = get_file_paths(data_dir_path, prefix, 0, train_high)
        val_paths = get_file_paths(data_dir_path, prefix, train_high, val_high)
        test_paths = get_file_paths(data_dir_path, prefix, val_high, test_high)
        return cls(train_paths, val_paths, test_paths)
