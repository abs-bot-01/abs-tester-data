# Native X11 interaction

This repository supports native X11 input without `computer_use` through
`bin/pi-tester-x11`.

## Prerequisites

The helper requires `xdpyinfo`, `xdotool`, ImageMagick `import`, and the
validated Xvfb display. Start the disposable display first:

```bash
bin/pi-tester-display
bin/pi-tester-x11 verify
```

The display defaults to `PI_TESTER_DISPLAY` or `:1042`. Every command verifies
that display before sending input. Override it explicitly when needed:

```bash
bin/pi-tester-x11 --display :1042 verify
```

## Input commands

Use coordinates from a fresh screenshot on the validated display:

```bash
bin/pi-tester-x11 click X Y [BUTTON]
bin/pi-tester-x11 type 'text'
bin/pi-tester-x11 key Return
bin/pi-tester-x11 drag SX SY W1X W1Y W2X W2Y TX TY
```

Drag requires two intermediate waypoints. Pointer motion is synchronous and
bounded by `PI_TESTER_X11_TIMEOUT` seconds (default `3`). If a drag command
fails while the button is held, the helper releases button 1 before exiting.
The command reports mechanical delivery only; accept the application result
only after a fresh screenshot confirms it.

## Evidence and provenance

Capture a raw root screenshot with:

```bash
bin/pi-tester-x11 capture tester-data/projects/<project>/runs/<run-id>/artifacts/<label>.png
```

For the normal cursor-marked run artifact, prefer:

```bash
bin/pi-tester-capture <project> <run-id> <label>
```

Record these fields in run notes when native X11 is used:

```text
input_backend=xdotool
screenshot_backend=ImageMagick import
computer_use_invoked=false
```

Do not replay stale coordinates. Remap source and destination after every
meaningful state change, and use only the application's visible interface.
