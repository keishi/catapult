# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import os

from telemetry.core import util

import py_utils


_BackendSettingsTuple = collections.namedtuple('_BackendSettingsTuple', [
    'browser_type', 'package', 'activity', 'command_line_name',
    'devtools_port', 'apk_name', 'supports_tab_control', 'supports_spki_list'])


class AndroidBrowserBackendSettings(_BackendSettingsTuple):
  """Base class for backend settings of Android browsers.

  These abstract away the differences that may exist between different
  browsers that may be installed or controlled on Android.

  Args:
    browser_type: The short browser name used by Telemetry to identify
      this from, e.g., the --browser command line argument.
    package: The package name used to identify the browser on Android.
      Each browser_type must match to a single package name and viceversa.
    activity: The activity name used to launch this browser via an intent.
    command_line_name: File name where the browser reads command line flags.
    devtools_port: Default remote port used to set up a DevTools conneciton.
      Subclasses may override how this value is interpreted.
    apk_name: Default apk name as built on a chromium checkout, used to
      find local apks on the host platform. Subclasses may override
      how this value is interpreted.
    supports_tab_control: Whether this browser variant supports the concept
      of tabs.
    supports_spki_list: Whether this browser supports spki-list for ignoring
      certificate errors. See: crbug.com/753948
  """
  __slots__ = ()

  def __str__(self):
    return '%s (%s)' % (self.browser_type, self.package)

  @property
  def profile_ignore_list(self):
    # Don't delete lib, since it is created by the installer.
    return ('lib', )

  def GetDevtoolsRemotePort(self, device):
    del device
    # By default return the devtools_port defined in the constructor.
    return self.devtools_port

  def FindLocalApk(self, device, chrome_root):
    # Subclasses may override this method to pick the correct apk based on
    # specific device features.
    del device  # Unused.
    if self.apk_name is None:
      return None
    else:
      return _FindLocalApk(chrome_root, self.apk_name)


class GenericChromeBackendSettings(AndroidBrowserBackendSettings):
  def __new__(cls, **kwargs):
    # Provide some defaults common to Chrome based backends.
    kwargs.setdefault('activity', 'com.google.android.apps.chrome.Main')
    kwargs.setdefault('command_line_name', 'chrome-command-line')
    kwargs.setdefault('devtools_port', 'localabstract:chrome_devtools_remote')
    kwargs.setdefault('apk_name', None)
    kwargs.setdefault('supports_tab_control', True)
    kwargs.setdefault('supports_spki_list', True)
    return super(GenericChromeBackendSettings, cls).__new__(cls, **kwargs)


class WebviewBasedBackendSettings(AndroidBrowserBackendSettings):
  def __new__(cls, **kwargs):
    # Provide some defaults common to WebView based backends.
    kwargs.setdefault('devtools_port',
                      'localabstract:webview_devtools_remote_{pid}')
    kwargs.setdefault('supports_tab_control', False)
    # TODO(crbug.com/753948): Switch to True when spki-list support is
    # implemented on WebView.
    kwargs.setdefault('supports_spki_list', False)
    return super(WebviewBasedBackendSettings, cls).__new__(cls, **kwargs)

  def GetDevtoolsRemotePort(self, device):
    # The DevTools port for WebView based backends depends on the browser PID.
    def get_activity_pid():
      return device.GetApplicationPids(self.package, at_most_one=True)

    pid = py_utils.WaitFor(get_activity_pid, timeout=30)
    return self.devtools_port.format(pid=pid)


ANDROID_CONTENT_SHELL = AndroidBrowserBackendSettings(
    browser_type='android-content-shell',
    package='org.chromium.content_shell_apk',
    activity='org.chromium.content_shell_apk.ContentShellActivity',
    command_line_name='content-shell-command-line',
    devtools_port='localabstract:content_shell_devtools_remote',
    apk_name='ContentShell.apk',
    supports_tab_control=False,
    supports_spki_list=True)

ANDROID_WEBVIEW = WebviewBasedBackendSettings(
    browser_type='android-webview',
    package='org.chromium.webview_shell',
    activity='org.chromium.webview_shell.TelemetryActivity',
    command_line_name='webview-command-line',
    # TODO(crbug.com/813047): Should override FindLocalApk instead.
    apk_name='SystemWebView.apk')

ANDROID_WEBVIEW_INSTRUMENTATION = WebviewBasedBackendSettings(
    browser_type='android-webview-instrumentation',
    package='org.chromium.android_webview.shell',
    activity='org.chromium.android_webview.shell.AwShellActivity',
    command_line_name='android-webview-command-line',
    apk_name='WebViewInstrumentation.apk')

ANDROID_CHROMIUM = GenericChromeBackendSettings(
    browser_type='android-chromium',
    package='org.chromium.chrome',
    apk_name='ChromePublic.apk')

ANDROID_CHROME = GenericChromeBackendSettings(
    browser_type='android-chrome',
    package='com.google.android.apps.chrome',
    # TODO(crbug.com/813047): Should override FindLocalApk instead.
    apk_name='Chrome.apk')

ANDROID_CHROME_BETA = GenericChromeBackendSettings(
    browser_type='android-chrome-beta',
    package='com.chrome.beta')

ANDROID_CHROME_DEV = GenericChromeBackendSettings(
    browser_type='android-chrome-dev',
    package='com.chrome.dev')

ANDROID_CHROME_CANARY = GenericChromeBackendSettings(
    browser_type='android-chrome-canary',
    package='com.chrome.canary')

ANDROID_SYSTEM_CHROME = GenericChromeBackendSettings(
    browser_type='android-system-chrome',
    package='com.android.chrome')


ANDROID_BACKEND_SETTINGS = (
    ANDROID_CONTENT_SHELL,
    ANDROID_WEBVIEW,
    ANDROID_WEBVIEW_INSTRUMENTATION,
    ANDROID_CHROMIUM,
    ANDROID_CHROME,
    ANDROID_CHROME_BETA,
    ANDROID_CHROME_DEV,
    ANDROID_CHROME_CANARY,
    ANDROID_SYSTEM_CHROME
)


def _FindLocalApk(chrome_root, apk_name):
  found_apk_path = None
  found_last_changed = None
  for build_path in util.GetBuildDirectories(chrome_root):
    apk_path = os.path.join(build_path, 'apks', apk_name)
    if os.path.exists(apk_path):
      last_changed = os.path.getmtime(apk_path)
      # Keep the most recently updated apk only.
      if last_changed is None or last_changed > found_last_changed:
        found_apk_path = apk_path
        found_last_changed = last_changed

  return found_apk_path
