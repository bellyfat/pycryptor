#!/usr/bin/python
# -*- coding: utf-8 -*-
# Locker v4.0 (follows new protocol)
# Implemented as class
#
# =============================================================================
# MIT License

# Copyright (c) 2019 Arunanshu Biswas

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# =============================================================================

import hashlib
import os
import stat
import string
from struct import pack, unpack
from functools import partial, lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DecryptionError(ValueError):
    pass


def _writer(file_path, new_file, method, flag, **kwargs):
    """Facilitates reading/writing to file.
    This function facilitates reading from *file_path* and writing to
    *new_file* with the provided method by looping through each line
    of the file_path of fixed length, specified by *block_size*.

      Usage
     -------

    file_path = File to be written on.

     new_file = Name of the encrypted/decrypted file to written upon.

      method = The way in which the file must be overwritten.
               (encrypt or decrypt)

        flag = This is to identify if the method being used is
               for encryption or decryption.
               If the *flag* is *True* then the *nonce* value
               is written to the end of the *new_file*.
               If the *flag* is *False*, then the *nonce* is written to
               *file_path*.
    """

    salt = kwargs['salt']
    nonce = kwargs['nonce']
    block_size = kwargs['block_size']

    os.chmod(file_path, stat.S_IRWXU)
    with open(file_path, 'rb') as fin:
        with open(new_file, 'wb+') as fout:
            if flag:
                # Append *nonce* and *salt* before encryption.
                nonce_salt = pack('12s32s', nonce, salt)
                fout.write(nonce_salt)

            else:
                # Moving ahead towards the encrypted data.
                # Setting new block_size for reading encrypted data
                fin.seek(12 + 32)
                block_size += 16

            # Loop through the *fin*, generate encrypted data
            # and write it to *fout*.
            while True:
                part = fin.read(block_size)
                if not part:
                    break
                fout.write(method(data=part))


def locker(file_path, password, remove=True, **kwargs):
    """Provides file locking/unlocking mechanism
    This function either encrypts or decrypts the file - *file_path*.
    Encryption or decryption depends upon the file's extension.
    The user's encryption or decryption task is almost automated since
    *encryption* or *decryption* is determined by the file's extension.

       Usage
     ---------

     file_path = File to be written on.

      password = Password to be used for encryption/decryption.

        remove = If set to True, the the file that is being
                 encrypted or decrypted will be removed.
                 (Default: True).
    """

    if kwargs:
        block_size = kwargs.get('block_size', 64 * 1024)
        ext = kwargs.get('ext', '.0DAY').strip(string.whitespace)
        iterations = kwargs.get('iterations', 50000)
        dklen = kwargs.get('dklen', 32)
    else:
        block_size = 64 * 1024
        ext = '.0DAY'
        iterations = 50000
        dklen = 32

    # The file is being decrypted.
    if file_path.endswith(ext):
        method = 'decrypt'
        flag = False
        new_file = os.path.splitext(file_path)[0]

        # Retrieve the *nonce* and *salt*.
        with open(file_path, 'rb') as f:
            nonce, salt = unpack('12s32s',
                                 f.read(12 + 32))

    # The file is being encrypted
    else:
        method = 'encrypt'
        flag = True
        new_file = file_path + ext
        nonce = os.urandom(12)
        salt = os.urandom(32)

    # Create a *password_hash* and *cipher* with
    # required method.
    password_hash = hashlib.pbkdf2_hmac('sha512', password,
                                        salt, iterations, dklen)
    cipher_obj = getattr(AESGCM(password_hash), method)
    crp = partial(cipher_obj, nonce=nonce, associated_data=None)

    try:
        _writer(file_path, new_file,
                crp, flag,
                nonce=nonce, salt=salt,
                block_size=block_size, )
    except InvalidTag:
        os.remove(new_file)
        raise DecryptionError('Invalid Password or tampered data.')

    if remove:
        os.remove(file_path)