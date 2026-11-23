import re
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex


def parse_proxy(raw: str) -> tuple[str, int, str, str]:
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("Proxy string is empty")

    cleaned = re.sub(r"^(socks5h?|https?)://", "", cleaned, flags=re.IGNORECASE)
    parts = cleaned.split(":")

    if len(parts) == 2:
        host, port_s, user, pwd = parts[0].strip(), parts[1].strip(), "", ""
    elif len(parts) == 4:
        host, port_s, user, pwd = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
    else:
        raise ValueError("Use host:port or host:port:user:pass")

    if not host:
        raise ValueError("Host is missing")
    if not port_s.isdigit():
        raise ValueError("Port must be numeric")

    port = int(port_s)
    if not (1 <= port <= 65535):
        raise ValueError("Port out of range (1-65535)")

    return host, port, user, pwd


class AndroidVpnBridge:
    """
    Android VpnService কন্ট্রোলার।
    """

    VPN_REQUEST_CODE = 1001

    def __init__(self):
        self.is_android = False
        self._activity = None
        self._intent_cls = None
        self._vpn_service_cls = None
        self._build_version = 0
        self._init_android()

    def _init_android(self):
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            BuildVersion = autoclass("android.os.Build$VERSION")
            self._activity = PythonActivity.mActivity
            self._intent_cls = autoclass("android.content.Intent")
            self._vpn_service_cls = autoclass("android.net.VpnService")
            self._build_version = int(BuildVersion.SDK_INT)
            self.is_android = self._activity is not None
        except Exception:
            self.is_android = False

    def start_vpn(self, protocol: str, host: str, port: int, username: str, password: str) -> tuple[str, str]:
        """
        Returns: (state, message)
        state: "connected" | "permission_needed" | "simulated"
        """
        if not self.is_android:
            return "simulated", f"Simulated VPN ({protocol}): {host}:{port}"

        prepare_intent = self._vpn_service_cls.prepare(self._activity)
        if prepare_intent is not None:
            self._activity.startActivityForResult(prepare_intent, self.VPN_REQUEST_CODE)
            return "permission_needed", "Allow VPN prompt, then tap Connect"

        ServiceClass = autoclass("com.quickproxy.vpn.ProxyVpnService")
        intent = self._intent_cls(self._activity, ServiceClass)
        intent.setAction("START")
        intent.putExtra("protocol", protocol)
        intent.putExtra("host", host)
        intent.putExtra("port", int(port))
        intent.putExtra("username", username)
        intent.putExtra("password", password)

        if self._build_version >= 26:
            self._activity.startForegroundService(intent)
        else:
            self._activity.startService(intent)

        return "connected", f"VPN Active ({protocol}): {host}:{port}"

    def stop_vpn(self) -> tuple[str, str]:
        if not self.is_android:
            return "disconnected", "Simulated VPN Disconnected"

        ServiceClass = autoclass("com.quickproxy.vpn.ProxyVpnService")
        intent = self._intent_cls(self._activity, ServiceClass)
        intent.setAction("STOP")

        if self._build_version >= 26:
            self._activity.startForegroundService(intent)
        else:
            self._activity.startService(intent)

        return "disconnected", "VPN Disconnected"


class VpnProxyUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=24, spacing=14, **kwargs)
        self.vpn_bridge = AndroidVpnBridge()
        self.protocol = "SOCKS5"
        self.connected = False

        self.add_widget(Label(
            text="QuickProxy Device VPN",
            font_size="24sp",
            bold=True,
            size_hint_y=None,
            height=44,
        ))

        self.add_widget(Label(
            text="Format: host:port:username:password",
            font_size="14sp",
            color=get_color_from_hex("#9CA3AF"),
            size_hint_y=None,
            height=24,
        ))

        self.proxy_input = TextInput(
            hint_text="192.168.1.10:1080:user:pass",
            multiline=False,
            font_size="16sp",
            size_hint_y=None,
            height=48,
        )
        self.add_widget(self.proxy_input)

        proto_box = BoxLayout(orientation="horizontal", spacing=10, size_hint_y=None, height=46)
        self.socks_btn = Button(
            text="SOCKS5",
            background_normal="",
            background_color=get_color_from_hex("#2563EB"),
        )
        self.http_btn = Button(
            text="HTTP",
            background_normal="",
            background_color=get_color_from_hex("#374151"),
        )
        self.socks_btn.bind(on_press=lambda _: self.set_protocol("SOCKS5"))
        self.http_btn.bind(on_press=lambda _: self.set_protocol("HTTP"))
        proto_box.add_widget(self.socks_btn)
        proto_box.add_widget(self.http_btn)
        self.add_widget(proto_box)

        btn_box = BoxLayout(orientation="horizontal", spacing=12, size_hint_y=None, height=54)
        self.connect_btn = Button(
            text="Connect",
            bold=True,
            background_normal="",
            background_color=get_color_from_hex("#16A34A"),
        )
        self.disconnect_btn = Button(
            text="Disconnect",
            bold=True,
            disabled=True,
            background_normal="",
            background_color=get_color_from_hex("#DC2626"),
        )
        self.connect_btn.bind(on_press=lambda _: self.on_connect())
        self.disconnect_btn.bind(on_press=lambda _: self.on_disconnect())
        btn_box.add_widget(self.connect_btn)
        btn_box.add_widget(self.disconnect_btn)
        self.add_widget(btn_box)

        self.status_label = Label(
            text="Status: Disconnected",
            font_size="16sp",
            bold=True,
            color=get_color_from_hex("#F87171"),
            size_hint_y=None,
            height=34,
        )
        self.detail_label = Label(
            text="Mode: Device-wide VpnService",
            font_size="13sp",
            color=get_color_from_hex("#D1D5DB"),
            size_hint_y=None,
            height=30,
        )
        self.add_widget(self.status_label)
        self.add_widget(self.detail_label)
        self.add_widget(Label())

    def set_protocol(self, proto: str):
        self.protocol = proto
        if proto == "SOCKS5":
            self.socks_btn.background_color = get_color_from_hex("#2563EB")
            self.http_btn.background_color = get_color_from_hex("#374151")
        else:
            self.http_btn.background_color = get_color_from_hex("#2563EB")
            self.socks_btn.background_color = get_color_from_hex("#374151")

    def on_connect(self):
        try:
            host, port, user, pwd = parse_proxy(self.proxy_input.text)
            state, msg = self.vpn_bridge.start_vpn(self.protocol, host, port, user, pwd)

            if state == "permission_needed":
                self.connected = False
                self.connect_btn.disabled = False
                self.disconnect_btn.disabled = True
                self.status_label.text = "Status: Permission Required"
                self.status_label.color = get_color_from_hex("#FBBF24")
                self.detail_label.text = msg
                return

            self.connected = True
            self.connect_btn.disabled = True
            self.disconnect_btn.disabled = False
            self.status_label.text = "Status: Connected"
            self.status_label.color = get_color_from_hex("#4ADE80")
            self.detail_label.text = msg
        except Exception as exc:
            self.status_label.text = f"Status: Error - {exc}"
            self.status_label.color = get_color_from_hex("#FBBF24")

    def on_disconnect(self):
        _, msg = self.vpn_bridge.stop_vpn()
        self.connected = False
        self.connect_btn.disabled = False
        self.disconnect_btn.disabled = True
        self.status_label.text = "Status: Disconnected"
        self.status_label.color = get_color_from_hex("#F87171")
        self.detail_label.text = msg


class QuickProxyVpnApp(App):
    def build(self):
        self.title = "QuickProxy Device VPN"
        return VpnProxyUI()

    def on_resume(self):
        # পারমিশন ডায়ালগ থেকে ফিরে এলে ইনপুট থাকলে অটো-কানেক্ট চেষ্টা
        if hasattr(self, "root") and isinstance(self.root, VpnProxyUI):
            if not self.root.connected and self.root.proxy_input.text.strip():
                Clock.schedule_once(lambda _: self.root.on_connect(), 0.3)


if __name__ == "__main__":
    QuickProxyVpnApp().run()