[app]

# Informacion de la app
title = appdron
package.name = appdron
package.domain = org.appdrontest1
version = 0.1

# Codigo fuente
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt

# Librerias (agrega aqui las que use tu app, ej: pillow,requests)
requirements = python3,kivy==2.3.0

# Pantalla
orientation = landscape
fullscreen = 0

# Permisos
android.permissions = android.permission.INTERNET

# Android
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

# python-for-android (version compatible con NDK 25b)
p4a.branch = v2024.01.21


[buildozer]

log_level = 2
warn_on_root = 0
