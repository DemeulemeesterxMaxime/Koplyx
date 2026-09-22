"""Collage Wayland via une session clavier explicitement autorisée par le bureau."""

from uuid import uuid4

from gi.repository import Gio, GLib


BUS_NAME = "org.freedesktop.portal.Desktop"
DESKTOP_PATH = "/org/freedesktop/portal/desktop"
REMOTE = "org.freedesktop.portal.RemoteDesktop"
REQUEST = "org.freedesktop.portal.Request"
SESSION = "org.freedesktop.portal.Session"


class PortalKeyboard:
    def __init__(self, get_restore_token=None, save_restore_token=None):
        self.bus = None
        self.session = None
        self.ready = False
        self.pending = False
        self._request_path = None
        self._response_id = 0
        self._closed_id = 0
        self._timeout_id = 0
        self._done = None
        self._get_restore_token = get_restore_token or (lambda: "")
        self._save_restore_token = save_restore_token or (lambda _token: None)

    def prepare(self, done):
        if self.pending:
            return
        if self.ready:
            done(True, "Collage direct déjà autorisé. Sélectionnez votre champ, puis choisissez un élément.")
            return
        self.pending = True
        self._done = done
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            token = "koplyx_" + uuid4().hex
            self._request("CreateSession", (), {"session_handle_token": GLib.Variant("s", token)}, self._created)
        except GLib.Error:
            self._fail("Le bureau ne fournit pas le collage Wayland. Utilisez Ctrl+V après restauration.")

    def _request(self, method, args, options, callback):
        token = "koplyx_" + uuid4().hex
        options["handle_token"] = GLib.Variant("s", token)
        sender = self.bus.get_unique_name()[1:].replace(".", "_")
        self._request_path = f"{DESKTOP_PATH}/request/{sender}/{token}"

        def response(_bus, _sender, path, _interface, _signal, parameters):
            if path != self._request_path:
                return
            self._clear_request()
            code, results = parameters.unpack()
            if code != 0:
                self._fail("Autorisation de collage refusée ou annulée. Vous pouvez réessayer dans les paramètres.")
                return
            callback(results)

        self._response_id = self.bus.signal_subscribe(
            BUS_NAME, REQUEST, "Response", None, None, Gio.DBusSignalFlags.NONE, response
        )
        request_path = self._request_path

        def completed(bus, result):
            try:
                bus.call_finish(result)
            except GLib.Error:
                if self._request_path == request_path:
                    self._fail("Le portail du bureau a refusé la demande de collage.")

        signatures = {"CreateSession": "(a{sv})", "SelectDevices": "(oa{sv})", "Start": "(osa{sv})"}
        self._timeout_id = GLib.timeout_add_seconds(120, self._expired)
        self.bus.call(
            BUS_NAME, DESKTOP_PATH, REMOTE, method,
            GLib.Variant(signatures[method], (*args, options)), GLib.VariantType.new("(o)"),
            Gio.DBusCallFlags.NONE, 5000, None, completed,
        )

    def _created(self, results):
        self.session = results.get("session_handle")
        if not self.session:
            self._fail("Le bureau n'a pas créé de session de collage.")
            return
        self._closed_id = self.bus.signal_subscribe(
            BUS_NAME, SESSION, "Closed", self.session, None, Gio.DBusSignalFlags.NONE,
            self._closed,
        )
        # Uniquement le clavier : aucun partage d'écran ni contrôle de la souris.
        options = {
            "types": GLib.Variant("u", 1),
            "persist_mode": GLib.Variant("u", 2),
        }
        restore_token = self._get_restore_token()
        if restore_token:
            options["restore_token"] = GLib.Variant("s", restore_token)
        self._request("SelectDevices", (self.session,), options, self._selected)

    def _selected(self, _results):
        self._request("Start", (self.session, ""), {}, self._started)

    def _started(self, results):
        if not results.get("devices", 0) & 1:
            self._fail("Le bureau n'a pas autorisé le clavier pour le collage.")
            return
        restore_token = results.get("restore_token")
        if restore_token:
            # Le portail renouvelle le jeton à chaque démarrage réussi. Le
            # dernier jeton doit remplacer l'ancien pour le prochain lancement.
            self._save_restore_token(restore_token)
        self.ready = True
        self.pending = False
        done, self._done = self._done, None
        if done:
            if restore_token:
                message = "Collage direct autorisé de façon persistante. Sélectionnez votre champ, puis choisissez un élément."
            else:
                message = "Collage direct autorisé pour cette session. Le bureau n'a pas fourni de jeton persistant."
            done(True, message)

    def paste(self):
        if not self.ready:
            return False
        try:
            # Les keysyms évitent de dépendre de la disposition AZERTY/QWERTY.
            for key, state in ((0xffe3, 1), (0x76, 1), (0x76, 0), (0xffe3, 0)):
                self.bus.call_sync(
                    BUS_NAME, DESKTOP_PATH, REMOTE, "NotifyKeyboardKeysym",
                    GLib.Variant("(oa{sv}iu)", (self.session, {}, key, state)), None,
                    Gio.DBusCallFlags.NONE, 1000, None,
                )
            return True
        except GLib.Error:
            # Fermer la session libère également les touches en cas d'échec partiel.
            self.close()
            return False

    def has_restore_token(self):
        """Indique si le portail peut tenter une reconnexion silencieuse."""
        return bool(self._get_restore_token())

    def _clear_request(self):
        if self._response_id:
            self.bus.signal_unsubscribe(self._response_id)
            self._response_id = 0
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = 0
        self._request_path = None

    def _expired(self):
        self._timeout_id = 0
        self._fail("La demande de collage a expiré. Réessayez dans les paramètres.")
        return GLib.SOURCE_REMOVE

    def _closed(self, *_args):
        self.session = None
        self._fail("L'autorisation de collage a été fermée par le bureau.")

    def _fail(self, message):
        done, self._done = self._done, None
        self.close()
        if done:
            done(False, message)

    def close(self):
        if self.bus:
            for path, interface in ((self._request_path, REQUEST), (self.session, SESSION)):
                if path:
                    self.bus.call(BUS_NAME, path, interface, "Close", None, None,
                                  Gio.DBusCallFlags.NONE, 1000, None, None)
            if self._closed_id:
                self.bus.signal_unsubscribe(self._closed_id)
                self._closed_id = 0
        self._clear_request()
        self.session = None
        self.ready = False
        self.pending = False
        self._done = None
