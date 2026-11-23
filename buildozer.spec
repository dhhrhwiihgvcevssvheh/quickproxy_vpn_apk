[app]
title = QuickProxy Device VPN
package.name = quickproxyvpn
package.domain = com.quickproxy.vpn
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,java
version = 0.1
requirements = python3,kivy,pyjnius
orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,FOREGROUND_SERVICE,WAKE_LOCK
android.add_src = java_src
android.services = ProxyVpnService:com.quickproxy.vpn.ProxyVpnService
android.archs = arm64-v8a
android.accept_sdk_license = True