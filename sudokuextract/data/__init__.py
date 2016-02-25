#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
import gzip
from pkg_resources import resource_filename, resource_exists

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

try:
    _range = xrange
except NameError:
    _range = range
import itertools

import numpy as np
from PIL import Image

from sudokuextract.extract import _extraction_iterator
from sudokuextract.ml.features import extract_efd_features
from sudokuextract.imgproc.blob import blobify

_url_to_mnist_train_data = "http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz"
_url_to_mnist_train_labels = "http://yann.lecun.com/exdb/mnist/train-labels-idx1-ubyte.gz"


def _toS32(bits):
    return struct.unpack_from(">i", bits)[0]


def _load_images_file(data, correct_magic_number=2051, flat_images=False):
    magic_number = _toS32(data[:4])
    if magic_number != correct_magic_number:
        raise ValueError("Error parsing images file. Read magic number {0} != {1}!".format(
            magic_number, correct_magic_number))
    n_images = _toS32(data[4:8])
    n_rows = _toS32(data[8:12])
    n_cols = _toS32(data[12:16])
    images = np.fromstring(data[16:], 'uint8').reshape(n_images, n_rows*n_cols)

    if not flat_images:
        images = [imrow.reshape(28, 28) for imrow in images]

    return images


def _load_labels_file(data, correct_magic_number=2049):
    magic_number = _toS32(data[:4])
    if magic_number != correct_magic_number:
        raise ValueError("Error parsing labels file. Read magic number {0} != {1}!".format(
            magic_number, correct_magic_number))
    n_labels = _toS32(data[4:8])
    return np.fromstring(data[8:], 'uint8')


def get_mnist_data(flat_images=False):
    X, y = _mnist_data(flat_images), _mnist_labels()
    if isinstance(X, list):
        for k in _range(len(X)):
            X[k] = 255 - X[k]
    else:
        X = 255 - X

    return X, y


def _mnist_data(flat_images=False):
    fname = resource_filename('sudokuextract.data', "train-images-idx3-ubyte.gz")
    if resource_exists('sudokuextract.data', "train-images-idx3-ubyte.gz"):
        f = gzip.open(fname, mode='rb')
        data = f.read()
        f.close()
    else:
        sio = StringIO(urlopen(_url_to_mnist_train_data).read())
        sio.seek(0)
        f = gzip.GzipFile(fileobj=sio, mode='rb')
        data = f.read()
        f.close()
        try:
            sio.seek(0)
            with open(fname, 'wb') as f:
                f.write(sio.read())
        except:
            pass

    return _load_images_file(data, 2051, flat_images)


def _mnist_labels():
    fname = resource_filename('sudokuextract.data', "train-labels-idx3-ubyte.gz")
    if resource_exists('sudokuextract.data', "train-labels-idx3-ubyte.gz"):
        f = gzip.open(fname, mode='rb')
        data = f.read()
        f.close()
    else:
        sio = StringIO(urlopen(_url_to_mnist_train_labels).read())
        sio.seek(0)
        f = gzip.GzipFile(fileobj=sio, mode='rb')
        data = f.read()
        f.close()
        try:
            sio.seek(0)
            with open(fname, 'wb') as f:
                f.write(sio.read())
        except:
            pass

    return _load_labels_file(data, 2049)


def get_sudokuextract_data(flat_images=False):
    return _sudokuextract_data(flat_images), _sudokuextract_labels()


def _sudokuextract_data(flat_images=False):
    fname = resource_filename('sudokuextract.data', "se-train-data.gz")
    if resource_exists('sudokuextract.data', "se-train-data.gz"):
        f = gzip.open(fname, mode='rb')
        data = np.load(f)
        f.close()
    else:
        raise IOError("SudokuExtract Training data file was not present!")

    return data#_load_images_file(data, 2051, flat_images)


def _sudokuextract_labels():
    fname = resource_filename('sudokuextract.data', "se-train-labels.gz")
    if resource_exists('sudokuextract.data', "se-train-labels.gz"):
        f = gzip.open(fname, mode='rb')
        data = np.load(f)
        f.close()
    else:
        raise IOError("SudokuExtract Training labels file was not present!")

    return data #_load_labels_file(data, 2049)


def create_data_set_from_images(path_to_data_dir):

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("This method requires matplotlib installed...")
        return

    images = []
    labels = []
    path_to_data_dir = os.path.abspath(os.path.expanduser(path_to_data_dir))
    _, _, files = os.walk(path_to_data_dir).next()
    for f in files:
        file_name, file_ext = os.path.splitext(f)
        if file_ext in ('.jpg', '.png', '.bmp') and "{0}.txt".format(file_name) in files:
            # The current file is an image and it has a corresponding text file as reference.
            # Use it as data.
            print("Handling {0}...".format(f))
            image = Image.open(os.path.join(path_to_data_dir, f))
            with open(os.path.join(path_to_data_dir, "{0}.txt".format(file_name)), 'rt') as f:
                parsed_img = f.read().strip().split('\n')
            for sudoku, subimage in _extraction_iterator(image):
                for k in range(len(sudoku)):
                    for kk in range(len(sudoku[k])):
                        ax = plt.subplot2grid((9, 9), (k, kk))
                        ax.imshow(sudoku[k][kk], plt.cm.gray)
                        ax.set_title(str(parsed_img[k][kk]))
                        ax.axis('off')
                plt.show()
                ok = raw_input("Is this OK (y/N)? ")
                if ok == 'y':
                    for k in range(len(sudoku)):
                        for kk in range(len(sudoku[k])):
                            images.append(sudoku[k][kk].copy())
                            labels.append(int(parsed_img[k][kk]))
                    break

    try:
        os.makedirs(os.path.expanduser('~/sudokuextract'))
    except:
        pass

    try:
        for i, (img, lbl) in enumerate(zip(images, labels)):
            img = Image.fromarray(img, 'L')
            with open(os.path.expanduser('~/sudokuextract/{1}_{0:04d}.jpg'.format(i+1, lbl)), 'w') as f:
                img.save(f)
    except Exception as e:
        print(e)

    print("Pre-blobify:  Label / N : {0}".format([(v, c) for v, c in zip(_range(10), np.bincount(labels))]))
    y = np.array(labels, 'int8')
    images, mask = blobify(images)
    y = y[mask]
    print("Post-blobify:  Label / N : {0}".format([(v, c) for v, c in zip(_range(10), np.bincount(y))]))

    print("Extract features...")
    X = np.array([extract_efd_features(img) for img in images])

    return images, labels, X, y


def save_training_data(X, y):
    _save_data('train', X, y)


def save_test_data(X, y):
    _save_data('test', X, y)


def _save_data(which, X, y)    :
    if X.shape[0] != len(y):
        raise TypeError("Length of data samples ({0}) was not identical "
                        "to length of labels ({1})".format(X.shape[0], len(y)))

    # Convert to numpy array.
    if not isinstance(X, np.ndarray):
        X = np.array(X)
    if not isinstance(y, np.ndarray):
        y = np.array(y)

    # Write feature_data
    fname = resource_filename('sudokuextract.data', "se-{0}-data.gz".format(which))
    with gzip.GzipFile(fname, mode='wb') as f:
        np.save(f, X)

    # Write labels
    fname = resource_filename('sudokuextract.data', "se-{0}-labels.gz".format(which))
    with gzip.GzipFile(fname, mode='wb') as f:
        np.save(f, y)



