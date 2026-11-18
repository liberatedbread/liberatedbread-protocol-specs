# BlueMaestro Tempo Disc Environmental Sensors

> **Status**: Identify only (untested; no measurement handler yet)
> **Protocol**: Passive BLE manufacturer advertisements
> **Manufacturer**: Blue Maestro
> **Manufacturer Status**: Active

## Overview

Tempo Disc and related BlueMaestro environmental sensors broadcast live readings
under company ID `0x0133`. A phone can monitor them without pairing, an account,
a GATT connection or a cloud service. The version byte selects the decoder. This
spec preserves the formats but is not a supported mobile integration until a real
measurement handler exists.

Only v13 and v23 have redacted physical-advertisement evidence in the public
parser fixtures. Other versions below are reported from synthetic app
comparisons, not physical verification. `scripts/test_bluemaestro_tempo_disc_spec.py`
checks an independent decoder against those public and synthetic vectors.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No — install the battery and scan |
| Method | `ble_direct`, passive only |
| Passphrase protection | `not_applicable` |
| Confidence | Medium overall; public-capture evidence only for v13/v23 |

**Factory reset**: Unknown. No reset procedure was established, and there is no
passive host binding to clear. Do not probe configuration writes looking for one.

**Rebinding**: A new controller only needs to scan. No old phone, factory reset
or credentials are required.

## Pairing

No pairing or bonding is needed for live advertisements. Connected logger history,
calibration, configuration and firmware behavior are outside this spec.

## Advertisement Formats

Offsets below include the version byte and exclude the two company-ID bytes.
Truncated measurement layouts are discarded whole; trailing statistics are allowed.

| Version | Family / evidence | Fields after version and battery |
|---------|-------------------|----------------------------------|
| 8, 13 | Legacy temperature; v13 has public captures | Four reserved bytes, signed big-endian temperature / 10 °C |
| 22, 23 | Legacy THD; v23 has public captures | Temperature / 10 °C, humidity / 10 %, **transmitted** signed dew point / 10 °C, all big-endian |
| 27 | THPD; reported | Big-endian temperature / 10 °C, humidity / 10 %, unsigned pressure / 10 mbar |
| 41 | Maxi temperature; reported | Thirteen reserved bytes, signed little-endian temperature / 100 °C |
| 42 | Maxi 3-in-1; reported | Little-endian temperature / 100 °C, humidity / 100 %; dew point calculated locally |
| 43 | Maxi 4-in-1; reported | Little-endian temperature / 100 °C, humidity / 100 %, signed 32-bit pressure / 100 mbar; dew point calculated locally |

Version 23's transmitted dew point can differ from the app-calculated result and
must be preserved. Versions 42/43 instead calculate dew point using the formula
in the YAML; zero humidity produces unknown. Versions 10, 100 and 101 are gateway
status, not sensor readings.

The complete offsets, minimum lengths, Maxi dew-point equation and test vectors
are in `device-specs/devices/bluemaestro-tempo-disc.yaml`.

## Out of Scope

Connected logger download, history, calibration, settings, reset commands,
cloud export, firmware updates and BlueMaestro Pacif-i. No manual was verified,
so no manual link is claimed.

## References

- [Bluetooth-Devices/bluemaestro-ble](https://github.com/Bluetooth-Devices/bluemaestro-ble)
- [Home Assistant BlueMaestro integration](https://www.home-assistant.io/integrations/bluemaestro/)
- [Blue Maestro](https://bluemaestro.com)
