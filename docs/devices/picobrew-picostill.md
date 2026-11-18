# PicoBrew PicoStill direct telemetry

> **Status**: Spec Available, untested
> **Protocol**: Wi-Fi, read-only HTTP
> **Manufacturer**: PicoBrew Inc.
> **Manufacturer Status**: Shutdown / receivership

## Overview

The PicoStill exposes a direct plain-HTTP telemetry route on its own LAN
address. This guide covers **only read-only `GET /data`**. It does not cover
heating, pumping, distillation control, recipe execution, firmware operations,
or emergency stop.

The replacement-server analysis comes from
[`chiefwigms/picobrew_pico`](https://github.com/chiefwigms/picobrew_pico/tree/36acae3003845b72568ef5f7d6cf168acb6f9b69).
No appliance was contacted for this spec, and no firmware-version compatibility
claim is made. The machine-readable version is
[`picobrew-picostill.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/picobrew-picostill.yaml).

!!! danger "Heat, pressure, and no network emergency stop"

    Telemetry cannot show that a fault is safe or prove that a heater or pump
    stopped. `picoChangeState`, closing a session log, and receiving any HTTP
    response are not emergency-stop mechanisms. Keep physical power isolation
    and the appliance's own safety controls available and use them for a fault.

## Setup, discovery, and rebinding

No client onboarding is needed for the recovered direct poller. Obtain the
PicoStill's address from the router or its trusted replacement-server
registration and request:

```text
GET http://<still-address>/data
```

The poller sends no HTTP credential or pairing token, so the trusted LAN is the
only gate shown by the source. There is no documented mDNS/SSDP discovery
protocol. Do not scan or actuate other PicoBrew models to find a still.

Initial Wi-Fi provisioning, in-place network rejoin, original server
authorization, and factory reset are not established. Changing a replacement
server's DNS or registration does not prove a Wi-Fi rejoin. Do not reset an
appliance merely to obtain telemetry or end a session.

## Nine-field response

The response is one `#...#` record with exactly nine comma-separated fields:

```text
#t1,t2,t3,t4,pres,ok,d1,d2,errmsg#
```

| Index | Field | What can safely be said |
|---:|---|---|
| 0 | `t1` | Reported coil-inlet-related raw value |
| 1 | `t2` | Reported coil-outlet-related raw value |
| 2 | `t3` | Reported pot-related raw value |
| 3 | `t4` | Reported ambient-related raw value |
| 4 | `pres` | Pressure-related raw value |
| 5 | `ok` | Opaque status string, not a proven boolean |
| 6 | `d1` | Unassigned raw string |
| 7 | `d2` | Unassigned raw string |
| 8 | `errmsg` | Opaque message string; may be empty |

**Units, scaling, precision, ranges, sentinels, and conversions are unknown.**
Do not label t1-t4 as Celsius or Fahrenheit, assign a pressure unit, convert
values, or create unit-bearing entities. The labels above describe the polling
code's mapping, not a verified measurement specification.

Parser procedure:

1. Strip surrounding HTTP whitespace and require both outer `#` delimiters.
2. Remove exactly those two characters and split the interior on commas.
3. Require exactly nine fields. Missing or additional fields are invalid.
4. Preserve every value as a string, including leading zeros and an empty
   `errmsg`. Do not round, coerce, or make a safety decision from it.
5. No escaping for a comma inside `errmsg` is documented. Such a record has
   more than nine fields and must be rejected rather than silently repaired.

An invented example that demonstrates string preservation, not real telemetry:

```text
#01.20,02.30,03.40,04.50,05.60,1,07.80,08.90,OK#
```

## Appliance-to-replacement-server role

Community replacement servers implement additional PicoStill and PicoBrew
routes, but those routes run **on the trusted replacement server**, and the
appliance calls them. They are not routes on the PicoStill and are not direct
appliance-local control:

| Case-sensitive route | Actual role |
|---|---|
| `/API/PicoStill/getFirmwareAddress` | Appliance asks the replacement server for a firmware address |
| `/firmware/picostill/<file>` | Appliance downloads a file from the replacement server; deliberately not invoked here |
| `/API/pico/picoChangeState` | Pico S/C/Pro route on the replacement server; current handler only returns blank CRLF and performs no action |

Do not bind these paths to the still's IP. Do not add firmware, heater, pump,
recipe, or session start/stop commands to this read-only spec. Ending a
Pico/Zymatic session or closing a ZSeries session finalizes a server log, not
proof of a safe hardware stop.

A local recovery setup normally maps `picobrew.com` and, where needed,
`www.picobrew.com` to the trusted server. Scope that DNS override to the
appliance/LAN and do not expose the replacement server's unauthenticated
admin/restart/shutdown routes. UIDs, registration tokens, and recipe IDs are
identifiers, not proof of cryptographic authentication.

## Verification and unknowns

`scripts/test_picobrew_picostill_spec.py` checks the delimiter parser against
valid, malformed, and string-preservation cases, verifies route direction and
case sensitivity, and asserts that no command, firmware, actuation, or
unit-bearing entity binding exists. No hardware calls are made.

Open questions include every unit and scale, `ok`/`errmsg` vocabulary,
`d1`/`d2`, comma escaping, firmware/version coverage, discovery and lifecycle
procedures, and actual fault behavior.

## References

- [Community replacement server](https://github.com/chiefwigms/picobrew_pico)
- [Direct still poller](https://github.com/chiefwigms/picobrew_pico/blob/36acae3003845b72568ef5f7d6cf168acb6f9b69/app/main/still_polling.py)
- [PicoStill replacement-server routes](https://github.com/chiefwigms/picobrew_pico/blob/36acae3003845b72568ef5f7d6cf168acb6f9b69/app/main/routes_picostill_api.py)
