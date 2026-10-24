# -*- coding: utf-8 -*-
"""Local lobby nickname patch.

The bundled lobby pre-data hard-codes the player name ``BRING_BACK_ROE!!``
(16 ASCII bytes, prefixed with a 17 = 16 + NUL length byte inside the 2298-byte
DT blob).  This stream transform rewrites that length-prefixed field with the
local account name, re-encrypts the frame and fixes the frame body length.
"""
import struct

from roe_protocol_2022 import FrameBuffer, dt_plain, encrypt

DEFAULT_NAME = b'BRING_BACK_ROE!!'


class LobbyNicknameStream:
    def __init__(self, key, nickname):
        name = nickname.encode('utf-8')
        if not 1 <= len(name) <= 64:
            raise ValueError('昵称长度必须是 1..64 字节')
        if b'\x00' in name:
            raise ValueError('昵称不能包含 NUL')
        self.key = key
        self.name = name
        self.frames = FrameBuffer()

    @staticmethod
    def _patch(plain, name):
        """Return patched plaintext or None when this frame has no nickname."""
        marker = b'BRING_BACK_ROE!!'
        at = plain.find(marker)
        if at <= 0:
            return None
        if plain[at - 1] != len(marker) + 1:
            return None
        if plain[at + len(marker):at + len(marker) + 1] != b'\x00':
            return None
        start = at - 1
        end = at + len(marker) + 1
        return plain[:start] + bytes([len(name) + 1]) + name + b'\x00' + plain[end:]

    def feed(self, data):
        output, updates = [], []
        for frame in self.frames.feed(data):
            result = frame
            if frame[2:4] == bytes(2):
                plain = dt_plain(frame, self.key)
                if plain is not None:
                    patched = self._patch(plain, self.name)
                    if patched is not None:
                        head = struct.unpack_from('>I', frame, 4)[0]
                        cipher = encrypt(patched, self.key)
                        header = bytearray(frame[:head])
                        struct.pack_into('>I', header, 8, len(cipher))
                        result = bytes(header) + cipher
                        updates.append(dict(nickname=self.name.decode('utf-8'),
                                            previous=DEFAULT_NAME.decode('ascii'),
                                            plaintext=len(plain), patched=len(patched)))
            output.append(result)
        return b''.join(output), updates

    def finish(self):
        if self.frames.pending:
            raise ValueError('TCP-поток завершился внутри lobby-кадра')
