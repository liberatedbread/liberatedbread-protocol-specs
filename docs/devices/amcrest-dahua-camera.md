# Amcrest / Dahua IP Camera / NVR

> **Status**: Spec Available (unverified) — active; documented CGI API
> **Protocol**: WiFi
> **Manufacturer**: Dahua Technology (Amcrest is a US brand on Dahua firmware)
> **Manufacturer Status**: Active

## Overview

Amcrest is a US brand OEM'd on Dahua firmware; both share a documented CGI/HTTP API and RTSP, controllable locally with no cloud. ONVIF Profile S devices.

## Protocol Summary

RTSP `rtsp://user:pass@{ip}:554/cam/realmonitor?channel=1&subtype=0`. CGI base
`/cgi-bin/...` (magicBox.cgi identity, snapshot.cgi, eventManager.cgi event
stream) over HTTP Digest. See the ONVIF reference for discovery.

The Amcrest Android app also uses Dahua's private **NetSDK/DVRIP service on TCP
37777** for device login and control. This is an additional app-observed surface,
not a correction to the documented CGI/RTSP API. Static analysis of app
`com.mm.android.AMCREST2` 1.10.000 establishes the port and SDK boundary; it does
not establish the private protocol's native framing, so this spec does not offer
a NetSDK/DVRIP client or packet catalogue.

See `device-specs/devices/amcrest-dahua-camera.yaml` for the full machine-readable spec.

## References

- <https://s3.amazonaws.com/amcrest-files/AMCREST_CGI_SDK_API.pdf>
- <https://github.com/rroller/dahua>
- <https://github.com/tchellomello/python-amcrest>
