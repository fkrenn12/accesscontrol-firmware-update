# `hardware/neo.py`

Treiber fuer die zwei adressierbaren NeoPixel des Geraets. Das Modul kapselt den MicroPython-`neopixel`-Treiber und stellt eine gemeinsame, schichtbasierte LED-Steuerung mit asynchronem Blinken bereit.

## Voraussetzungen

- MicroPython auf einem unterstuetzten Board
- `machine.Pin`
- MicroPython-Modul `neopixel`
- `uasyncio`
- `config.constants.const.NEOPIXEL_PIN`

Der Pin wird nicht direkt in diesem Modul festgelegt. Er kommt aus `config/constants.py`:

| Board | NeoPixel-Pin |
| --- | ---: |
| ESP32-S3 | `1` |
| WROVER | `18` |
| Arduino Nano | `18` |

Das Modul initialisiert immer `2` physische Pixel. Beide Pixel erhalten jeweils dieselbe Farbe.

## Import

```python
from hardware.neo import (
    vpixel,
    RED,
    GREEN,
    BLUE,
    OFF,
    LAYER_BACKGROUND,
    LAYER_RELAY,
    LAYER_ALARM,
    LAYER_RFID,
)
```

Beim Import wird automatisch das globale Objekt `vpixel` erzeugt:

```python
vpixel = VirtualPixel(const.NEOPIXEL_PIN)
```

## Prioritaetsebenen

Mehrere Teile der Anwendung koennen gleichzeitig einen LED-Zustand setzen. Jede Ebene besitzt ihren eigenen Zustand. Die hoechste aktive Ebene gewinnt bei der Ausgabe:

| Konstante | Wert | Prioritaet | Zweck |
| --- | ---: | --- | --- |
| `LAYER_BACKGROUND` | `0` | niedrigste | Grundzustand, z. B. Bereitschaft |
| `LAYER_RELAY` | `1` | | Relaiszustand |
| `LAYER_ALARM` | `2` | | Alarmanzeige |
| `LAYER_RFID` | `3` | hoechste | RFID-Aktion oder Rueckmeldung |
| `LAYER_ALL` | `-1` | Sonderwert | Alle Blinkaufgaben stoppen |

Eine hoehere Ebene kann eine niedrigere Ebene temporaer verdecken. Wird sie auf `TRANSPARENT` gesetzt, wird wieder die darunterliegende Ebene sichtbar. `OFF` ist dagegen eine echte schwarze Farbe und bleibt als aktive Ebene erhalten.

## API

### `VirtualPixel(pin)`

Erzeugt einen Treiber fuer den angegebenen GPIO-Pin und initialisiert beide Pixel mit `OFF`.

### `on(color_on, index_layer)`

Setzt `color_on` auf der angegebenen Ebene und aktualisiert die Hardware sofort.

```python
vpixel.on(GREEN, LAYER_BACKGROUND)
vpixel.on(RED, LAYER_RFID)
```

Da `LAYER_RFID` hoeher priorisiert ist, wird in diesem Beispiel Rot angezeigt.

### `off(index_layer)`

Setzt die angegebene Ebene auf `OFF` und aktualisiert die Hardware.

```python
vpixel.off(LAYER_RFID)
```

### `blink(...)`

Startet ein asynchrones Blinkmuster auf einer Ebene. Die Methode wartet nicht auf das Ende des Blinkens, sondern legt eine `uasyncio`-Task an. Ein bereits laufendes Blinkmuster auf derselben Ebene wird vorher beendet.

```python
await vpixel.blink(
    repeats=3,
    ms_on=200,
    ms_off=200,
    color_on=BLUE,
    color_off=OFF,
    index_layer=LAYER_RFID,
)
```

Parameter:

- `repeats`: Anzahl der Blinkzyklen; ein negativer Wert blinkt dauerhaft.
- `ms_on`: Einschaltdauer pro Zyklus in Millisekunden.
- `ms_off`: Ausschaltdauer pro Zyklus in Millisekunden.
- `color_on`: Farbe waehrend der Einschaltphase.
- `color_off`: Farbe waehrend der Ausschaltphase.
- `index_layer`: Ebene, auf der geblinkt wird; Standard ist `LAYER_BACKGROUND`.

Standardwerte sind `2` Wiederholungen, `200 ms` an und `200 ms` aus.

### `blink_stop(index_layer)`

Beendet das Blinkmuster auf der angegebenen Ebene. Mit `LAYER_ALL` werden alle Ebenen gestoppt:

```python
await vpixel.blink_stop(LAYER_RFID)
await vpixel.blink_stop(LAYER_ALL)
```

Nach dem Ende eines Blinkmusters wird die betreffende Ebene automatisch bereinigt. Auf `LAYER_BACKGROUND` wird sie auf `OFF` gesetzt; auf hoeheren Ebenen wird sie auf `TRANSPARENT` gesetzt, damit eine darunterliegende Anzeige wieder sichtbar werden kann.

## Farbkonstanten

Das Modul stellt mehrere vorkonfigurierte RGB-Tupel bereit:

- Grundfarben: `RED_BASE`, `GREEN_BASE`, `BLUE_BASE`
- Volle Farben: `RED_FULL`, `GREEN_FULL`, `BLUE_FULL`
- Gedimmte Farben: `RED`, `GREEN`, `BLUE`
- Niedrige Helligkeit: `RED_LOW`, `GREEN_LOW`, `BLUE_LOW`
- Orange: `ORANGE_LOW`, `ORANGE`, `ORANGE_FULL`
- Weiss: `WHITE`, `WHITE_FULL`
- Sonderwerte: `OFF`, `TRANSPARENT`

Farben koennen auch als eigenes RGB-Tupel mit drei Ganzzahlen verwendet werden, zum Beispiel `(25, 0, 0)`.

## Beispiel: Grundzustand mit RFID-Ueberlagerung

```python
import uasyncio as asyncio
from hardware.neo import vpixel, BLUE, GREEN, OFF
from hardware.neo import LAYER_BACKGROUND, LAYER_RFID


async def show_status():
    vpixel.on(GREEN, LAYER_BACKGROUND)
    await vpixel.blink(
        repeats=-1,
        color_on=BLUE,
        color_off=OFF,
        index_layer=LAYER_RFID,
    )

    await asyncio.sleep_ms(3000)
    await vpixel.blink_stop(LAYER_RFID)


asyncio.run(show_status())
```

## Standalone-Test

Wird `hardware/neo.py` direkt ausgefuehrt, startet der eingebaute Endlostest. Dieser prueft nacheinander Hintergrund- und RFID-Layer sowie das Stoppen einzelner beziehungsweise aller Blinkaufgaben.

```text
mpremote run hardware/neo.py
```

Der Test setzt voraus, dass das Board verbunden ist, `config` importiert werden kann und am konfigurierten GPIO zwei NeoPixel angeschlossen sind.

## Hinweise

- `blink()` und `blink_stop()` sind asynchron und muessen innerhalb einer laufenden `uasyncio`-Event-Schleife aufgerufen werden.
- Die vier Layer teilen sich eine einzelne physische Ausgabe. Sie sind eine Prioritaetslogik, keine vier unabhaengigen LEDs.
- `TRANSPARENT` darf fuer hoehere Layer verwendet werden, um den darunterliegenden Zustand wieder freizugeben. Fuer den Hintergrund sollte `off()` beziehungsweise `OFF` verwendet werden.
- Das Modul verwaltet pro Layer hoechstens eine Blink-Task. Ein neuer Aufruf von `blink()` ersetzt das laufende Muster derselben Ebene.
