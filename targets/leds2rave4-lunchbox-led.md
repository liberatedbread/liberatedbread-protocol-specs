# LEDs2RAVE4 / Lunchbox Dream LED family — target spec starter

## Target metadata
- target_id: leds2rave4-lunchbox-led
- app package_id(s):
  - com.spled.pzse (LED Chord)
  - com.led.spotled (SPOTLED)
  - com.led.iledcolor (iledcolor)
- device class: programmable LED skin / panel / backpack-style LED screens
- transport(s): Bluetooth (BLE expected)
- local-only viability: high for core control; cloud libraries optional (verify)

## Known facts (public)
- Dream LED Skin tutorial explicitly connects to an "SP107e" controller and uses the "LED CHORD" app.
- Dream LED Skin 2.0 tutorial uses SpotLED and indicates device names begin with "LBXDRMSKIN_LED_".
- Vendor partner: LEDs2RAVE4 is cited as a community partner for Dream LED skins.

## Device discovery signals
- BLE advertised name patterns:
  - "SP107e"
  - "LBXDRMSKIN_LED_" prefix
- Hardware hints:
  - WS2811/WS28xx-style pixel LEDs and RGB order configuration are referenced.
  - Segment/pixel totals are configured inside the app (device is a generic LED controller class).

## First experiments
1) Run ./scripts/detect_devices.sh near an active Dream LED Skin / controller and save logs.
2) HCI snoop:
   - connect in LED Chord and change brightness + switch effect
   - connect in SpotLED and upload a single small animation
3) Compare protocols:
   - Are LED Chord and SpotLED talking to the same GATT services?
   - Does SpotLED use higher-throughput transport (larger writes / chunking)?
4) Determine whether the device accepts control without bonding/pairing ("just works" GATT).

## Replacement app MVP
- scan + connect to the LED device
- set brightness / speed
- select effect index
- upload a simple bitmap/animation to device local storage if supported

## References
- Dream LED Skin tutorial (LED CHORD, SP107e): https://www.lunchboxpacks.com/pages/dream-led-tutorial
- Dream LED Skin 2.0 (SpotLED, LBXDRMSKIN_LED_): https://www.lunchboxpacks.com/blogs/resources/how-to-set-up-your-dream-led-skin-2-0
