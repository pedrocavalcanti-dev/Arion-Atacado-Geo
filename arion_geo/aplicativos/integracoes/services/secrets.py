"""Credential protection backends. Production secrets use current-user Windows DPAPI."""
import base64
import ctypes
import os
from ctypes import wintypes

from .errors import SecretStorageUnavailable


class SecretProtector:
    def protect(self, plaintext: str) -> str:
        raise NotImplementedError

    def unprotect(self, ciphertext: str) -> str:
        raise NotImplementedError


class WindowsDPAPISecretProtector(SecretProtector):
    """Use DPAPI's current-user scope; the app must run as the same Windows account."""

    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    @classmethod
    def _api(cls):
        if os.name != "nt":
            raise SecretStorageUnavailable()
        try:
            crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            crypt32.CryptProtectData.argtypes = [ctypes.POINTER(cls.DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(cls.DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(cls.DATA_BLOB)]
            crypt32.CryptProtectData.restype = wintypes.BOOL
            crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(cls.DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(cls.DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(cls.DATA_BLOB)]
            crypt32.CryptUnprotectData.restype = wintypes.BOOL
            kernel32.LocalFree.argtypes = [ctypes.c_void_p]
            kernel32.LocalFree.restype = ctypes.c_void_p
            return crypt32, kernel32
        except Exception:
            raise SecretStorageUnavailable() from None

    @classmethod
    def _blob(cls, payload: bytes):
        buffer = ctypes.create_string_buffer(payload)
        blob = cls.DATA_BLOB(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        return blob, buffer

    def protect(self, plaintext: str) -> str:
        crypt32, kernel32 = self._api()
        raw = b""
        source_buffer = None
        destination = self.DATA_BLOB()
        try:
            raw = plaintext.encode("utf-8")
            source, source_buffer = self._blob(raw)
            ok = crypt32.CryptProtectData(ctypes.byref(source), "ARION integration credential", None, None, None, self.CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(destination))
            if not ok:
                raise SecretStorageUnavailable()
            encrypted = ctypes.string_at(destination.pbData, destination.cbData)
            return base64.b64encode(encrypted).decode("ascii")
        except SecretStorageUnavailable:
            raise
        except Exception:
            raise SecretStorageUnavailable() from None
        finally:
            if destination.pbData:
                kernel32.LocalFree(destination.pbData)
            del source_buffer, raw

    def unprotect(self, ciphertext: str) -> str:
        crypt32, kernel32 = self._api()
        try:
            raw = base64.b64decode(ciphertext.encode("ascii"), validate=True)
        except (ValueError, UnicodeError):
            raise SecretStorageUnavailable() from None
        source, source_buffer = self._blob(raw)
        destination = self.DATA_BLOB()
        try:
            ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, self.CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(destination))
            if not ok:
                raise SecretStorageUnavailable()
            try:
                return ctypes.string_at(destination.pbData, destination.cbData).decode("utf-8")
            except UnicodeError:
                raise SecretStorageUnavailable() from None
        except SecretStorageUnavailable:
            raise
        except Exception:
            raise SecretStorageUnavailable() from None
        finally:
            if destination.pbData:
                kernel32.LocalFree(destination.pbData)
            del source_buffer, raw


class TestSecretProtector(SecretProtector):
    """Test-only reversible backend. Never use for deployments."""

    def protect(self, plaintext: str) -> str:
        return "test:" + base64.b64encode(plaintext.encode("utf-8")).decode("ascii")

    def unprotect(self, ciphertext: str) -> str:
        if not ciphertext.startswith("test:"):
            raise SecretStorageUnavailable()
        try:
            return base64.b64decode(ciphertext[5:], validate=True).decode("utf-8")
        except (ValueError, UnicodeError):
            raise SecretStorageUnavailable() from None


def get_secret_protector() -> SecretProtector:
    return WindowsDPAPISecretProtector()
