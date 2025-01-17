from __future__ import annotations

from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from typing import Callable, Tuple, Sequence, List

import pydicom
from torch import Tensor
from torchvision.transforms.functional import to_tensor
from PIL import ImageFile, Image
from PIL.Image import Image as ImageType
from torch.utils.data import Dataset

from sparsam.utils import min_max_normalize_tensor

ImageFile.LOAD_TRUNCATED_IMAGES = True


class BaseSet(ABC, Dataset):
    def __init__(self, data_augmentation: Callable = None,
                 normalize: Callable | bool = True
                 ):
        self.data_augmentation = data_augmentation
        if normalize is True:
            normalize = partial(min_max_normalize_tensor, min_value=0, max_value=1)
        self.normalize = normalize

    def set_data_augmentation(self, data_augmentation: Callable):
        self.data_augmentation = data_augmentation

    def __getitem__(self, index: int) -> Tuple[Tensor, Tensor]:
        img, label = self._get_image_label_pair(index)
        if self.data_augmentation:
            img = self.data_augmentation(img)
        if isinstance(img, list):
            img = [self._normalize(view) for view in img]
        else:
            img = self._normalize(img)
        return img, label

    def _normalize(self, img: Tensor | ImageType):
        if not isinstance(img, Tensor):
            img = to_tensor(img)
        if self.normalize:
            img = self.normalize(img)
        return img


    @abstractmethod
    def _get_image_label_pair(self, index: int) -> Tuple[Tensor | ImageType | List[Tensor | ImageType], Tensor | int | None]:
        """
        :param index: which datapoint from the dataset to get
        return:
        img: the loaded and preprocessed, but UNNORMALIZED image
        label: if dataset is labeled returns the corresponding image label or dummy label/ None
        """
        pass


class ImageSet(BaseSet):
    def __init__(
            self,
            img_paths: Sequence[Path],
            labels: Sequence = None,
            img_size: int | Sequence[int] = None,
            data_augmentation: Callable = None,
            class_names: Sequence[str] = None,
            normalize: Callable | bool = True,
    ):
        super().__init__(data_augmentation=data_augmentation,
                         normalize=normalize)
        self.img_paths = img_paths
        self.labels = labels
        if class_names:
            self.class_names = class_names
        elif labels:
            self.class_names = sorted(list(set(labels)))
        else:
            self.class_names = None
        if img_size and not isinstance(img_size, tuple):
            img_size = (img_size, img_size)
        self.img_size = img_size

    def __len__(self):
        return len(self.img_paths)

    def _get_image_label_pair(self, index: int) -> Tuple[ImageType, int]:
        path = self.img_paths[index]
        if path.suffix == '.dcm':
            ds = pydicom.dcmread(path)
            img = Image.fromarray(ds.pixel_array, 'RGB')
        else:
            img = Image.open(path).convert('RGB')
        if self.img_size:
            img = img.resize(self.img_size, Image.NEAREST)
        if self.labels is not None:
            label = self.labels[index]
            if self.class_names is not None:
                label = self.class_names.index(label)
        else:
            label = 0
        return img, label
