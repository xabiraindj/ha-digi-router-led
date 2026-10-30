
"""Control de los LED del router DIGI PE5301-01."""

import aiohttp
import base64
import json
import logging
import secrets

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad
from yarl import URL

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)


class DigiRouter:
    """Cliente del router DIGI."""

    def __init__(self, hass, entry):
        self.hass = hass
        self.host = entry.data[CONF_HOST].strip().rstrip("/")
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]

        # Sesión HTTP propia que permite cookies de direcciones IP.
        self.session = aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        )

        self.aes_key = None
        self.session_key = None
        self.is_on = None

    def url(self, path):
        """Construir URL."""
        return f"http://{self.host}{path}"

    @staticmethod
    def encrypt_payload(obj, key_text, iv_text):
        """Cifrar JSON mediante AES-CBC."""
        key = base64.b64decode(key_text)
        iv = base64.b64decode(iv_text)[:16]

        plaintext = json.dumps(
            obj,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(plaintext, AES.block_size))

        return {
            "content": base64.b64encode(encrypted).decode("ascii"),
            "key": "",
            "iv": iv_text,
        }

    def decrypt_payload(self, data):
        """Descifrar respuesta del router."""
        if not self.aes_key:
            raise HomeAssistantError(
                "No hay una clave AES disponible."
            )

        try:
            key = base64.b64decode(self.aes_key)
            iv = base64.b64decode(data["iv"])[:16]
            encrypted = base64.b64decode(data["content"])

            cipher = AES.new(key, AES.MODE_CBC, iv)
            plaintext = unpad(
                cipher.decrypt(encrypted),
                AES.block_size,
            ).decode("utf-8")

            result = json.loads(plaintext)

            if isinstance(result, dict):
                _LOGGER.debug(
                    "DIGI: respuesta descifrada. Campos=%s, resultado=%s",
                    list(result.keys()),
                    result.get("result", "sin campo result"),
                )

            return result

        except (
            ValueError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
        ) as err:
            _LOGGER.warning(
                "DIGI: no se pudo descifrar la respuesta."
            )
            raise HomeAssistantError(
                "No se pudo descifrar la respuesta del router."
            ) from err

    async def request_json(self, path, method="GET", payload=None):
        """Enviar petición al router."""
        headers = {
            "Content-Type": (
                "application/x-www-form-urlencoded; charset=UTF-8"
            )
        }

        data = None

        if method in ("POST", "PUT", "DELETE") and "/cgi-bin/" in path:
            if not self.aes_key or not self.session_key:
                raise HomeAssistantError(
                    "Falta la sesión o el token CSRF."
                )

            iv_text = base64.b64encode(
                secrets.token_bytes(32)
            ).decode("ascii")

            encrypted = self.encrypt_payload(
                payload or {},
                self.aes_key,
                iv_text,
            )

            data = json.dumps(
                encrypted,
                separators=(",", ":"),
            )

            headers["CSRFToken"] = self.session_key

            _LOGGER.debug(
                "DIGI: enviando %s %s. Token CSRF disponible: %s",
                method,
                path,
                bool(self.session_key),
            )

        # Comprobar si la cookie está almacenada y disponible.
        try:
            cookies = self.session.cookie_jar.filter_cookies(
                URL(self.url(path))
            )

            session_cookie_available = "Session" in cookies

            _LOGGER.debug(
                "DIGI: Cookie Session disponible para %s %s: %s. "
                "Tipo de cookie jar: %s",
                method,
                path,
                session_cookie_available,
                type(self.session.cookie_jar).__name__,
            )

        except Exception:
            _LOGGER.exception(
                "DIGI: no se pudo comprobar la cookie Session."
            )

        try:
            async with self.session.request(
                method,
                self.url(path),
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:

                response_text = await response.text()

                _LOGGER.debug(
                    "DIGI: respuesta HTTP %s en %s %s. "
                    "Cookie Session recibida: %s",
                    response.status,
                    method,
                    path,
                    "Session" in response.cookies,
                )

                try:
                    result = json.loads(response_text)
                except (json.JSONDecodeError, TypeError):
                    result = {}

                if response.status >= 400:
                    detail = ""

                    if isinstance(result, dict):
                        detail = str(
                            result.get("result", "")
                        )

                    _LOGGER.warning(
                        "DIGI: HTTP %s en %s %s; detalle=%s",
                        response.status,
                        method,
                        path,
                        detail or "sin detalle",
                    )

                    raise HomeAssistantError(
                        f"El router respondió HTTP {response.status}. "
                        f"Detalle: {detail or 'sin detalle'}"
                    )

        except HomeAssistantError:
            raise

        except Exception as err:
            _LOGGER.exception(
                "DIGI: error de comunicación con el router."
            )

            raise HomeAssistantError(
                "No se pudo comunicar con el router DIGI."
            ) from err

        if (
            isinstance(result, dict)
            and "content" in result
            and "iv" in result
        ):
            result = self.decrypt_payload(result)

        if isinstance(result, dict) and result.get("sessionkey"):
            self.session_key = result["sessionkey"]

        return result

    async def login(self):
        """Iniciar sesión y obtener claves nuevas."""

        _LOGGER.debug("DIGI: iniciando sesión en el router.")

        self.aes_key = None
        self.session_key = None

        # Obtener clave pública RSA.
        public_data = await self.request_json(
            "/getRSAPublickKey"
        )

        public_key = (
            public_data.get("RSAPublicKey")
            if isinstance(public_data, dict)
            else None
        )

        if not public_key:
            raise HomeAssistantError(
                "El router no ha proporcionado su clave pública RSA."
            )

        # Generar clave AES de 256 bits.
        self.aes_key = base64.b64encode(
            secrets.token_bytes(32)
        ).decode("ascii")

        iv_text = base64.b64encode(
            secrets.token_bytes(32)
        ).decode("ascii")

        try:
            rsa_key = RSA.import_key(public_key)
            rsa_cipher = PKCS1_v1_5.new(rsa_key)

            encrypted_key = rsa_cipher.encrypt(
                self.aes_key.encode("ascii")
            )

        except (ValueError, TypeError, IndexError) as err:
            self.aes_key = None

            raise HomeAssistantError(
                "No se pudo interpretar la clave RSA del router."
            ) from err

        # Preparar credenciales.
        login_payload = {
            "Input_Account": self.username,
            "Input_Passwd": base64.b64encode(
                self.password.encode("utf-8")
            ).decode("ascii"),
            "currLang": "en",
            "RememberPassword": 2,
            "SHA512_password": False,
        }

        encrypted = self.encrypt_payload(
            login_payload,
            self.aes_key,
            iv_text,
        )

        encrypted["key"] = base64.b64encode(
            encrypted_key
        ).decode("ascii")

        # Enviar inicio de sesión.
        try:
            async with self.session.post(
                self.url("/UserLogin"),
                headers={
                    "Content-Type": (
                        "application/x-www-form-urlencoded; charset=UTF-8"
                    )
                },
                data=json.dumps(
                    encrypted,
                    separators=(",", ":"),
                ),
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:

                response_text = await response.text()

                _LOGGER.debug(
                    "DIGI: UserLogin HTTP %s. "
                    "Cookie Session recibida: %s",
                    response.status,
                    "Session" in response.cookies,
                )

                try:
                    result = json.loads(response_text)
                except (json.JSONDecodeError, TypeError):
                    result = {}

                if response.status >= 400:
                    self.aes_key = None

                    detail = (
                        result.get("result", "")
                        if isinstance(result, dict)
                        else ""
                    )

                    raise HomeAssistantError(
                        f"El inicio de sesión devolvió HTTP "
                        f"{response.status}: {detail or 'sin detalle'}"
                    )

        except HomeAssistantError:
            raise

        except Exception as err:
            self.aes_key = None

            _LOGGER.exception(
                "DIGI: error durante el inicio de sesión."
            )

            raise HomeAssistantError(
                "No se pudo iniciar sesión en el router."
            ) from err

        # Descifrar respuesta de inicio de sesión.
        if (
            isinstance(result, dict)
            and "content" in result
            and "iv" in result
        ):
            result = self.decrypt_payload(result)

        if not isinstance(result, dict):
            self.aes_key = None

            raise HomeAssistantError(
                "Respuesta de inicio de sesión inesperada."
            )

        detail = result.get(
            "result",
            "sin campo result",
        )

        self.session_key = result.get("sessionkey")

        _LOGGER.debug(
            "DIGI: Resultado del inicio de sesión: %s. "
            "Token CSRF recibido: %s",
            detail,
            bool(self.session_key),
        )

        if not self.session_key:
            self.aes_key = None

            _LOGGER.error(
                "DIGI: el inicio de sesión no devolvió "
                "un token CSRF válido."
            )

            raise HomeAssistantError(
                "El inicio de sesión no devolvió un token CSRF. "
                f"Resultado: {detail}"
            )

        _LOGGER.debug(
            "DIGI: inicio de sesión completado correctamente."
        )

    async def set_led(self, state):
        """Autenticar y cambiar el estado de los LED."""

        _LOGGER.debug(
            "DIGI: solicitud para cambiar LED a %s.",
            "ENCENDIDOS" if state else "APAGADOS",
        )

        # Nueva autenticación en cada pulsación.
        self.aes_key = None
        self.session_key = None

        await self.login()

        try:
            result = await self.request_json(
                "/cgi-bin/LEDStatus",
                method="PUT",
                payload={"status": state},
            )

        except HomeAssistantError as err:

            if "HTTP 401" not in str(err):
                raise

            _LOGGER.warning(
                "DIGI: HTTP 401. Se intentará iniciar sesión "
                "otra vez."
            )

            self.aes_key = None
            self.session_key = None

            await self.login()

            result = await self.request_json(
                "/cgi-bin/LEDStatus",
                method="PUT",
                payload={"status": state},
            )

        if not isinstance(result, dict):
            raise HomeAssistantError(
                "Respuesta inesperada al cambiar los LED."
            )

        self.is_on = result.get(
            "isactive",
            state,
        )

        _LOGGER.info(
            "DIGI: orden enviada. Estado solicitado: %s.",
            "ENCENDIDO" if state else "APAGADO",
        )

        return self.is_on

    async def close(self):
        """Cerrar la sesión HTTP."""
        if not self.session.closed:
            await self.session.close()


async def async_setup_entry(hass, entry, async_add_entities):
    """Crear el interruptor."""
    router = DigiRouter(hass, entry)

    async_add_entities([
        DigiLedSwitch(router, entry)
    ])

    entry.async_on_unload(router.close)


class DigiLedSwitch(SwitchEntity):
    """Interruptor de los LED del router."""

    _attr_has_entity_name = True
    _attr_name = "LED del router"
    _attr_icon = "mdi:router-wireless-settings"

    def __init__(self, router, entry):
        self.router = router
        self._attr_unique_id = f"{entry.entry_id}_led"

    @property
    def is_on(self):
        """Devolver último estado conocido."""
        return self.router.is_on

    async def async_turn_on(self, **kwargs):
        """Encender LED."""
        self._attr_is_on = await self.router.set_led(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Apagar LED."""
        self._attr_is_on = await self.router.set_led(False)
        self.async_write_ha_state()
