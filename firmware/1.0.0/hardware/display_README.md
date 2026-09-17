# Display Wrapper (`display.py`)

This Python file implements a wrapper class for managing a 7-segment display using the `TM1637` hardware module. It provides dynamic control for displaying information such as text, time, and status updates, suitable for microcontroller environments like ESP32 or Raspberry Pi Pico.

---

## Features

- **Dynamic 7-Segment Control**:
  - Display time, status messages, or custom numbers on a 4-segment display.
- **Brightness Control**:
  - Adjustable brightness levels (0-7).
- **Scrolling Text**:
  - Handles text longer than 4 segments with smooth scrolling.
- **Animation System**:
  - Automatically transitions between sequences such as time display and background animations.
- **Device Config Integration**:
  - Reads settings such as display brightness, scrolling speed, and sequences from a configuration.
- **Multi-Layer Display**:
  - Supports layers (background, status, pin, etc.) with defined priorities for rendering content.

---

## How It Works

1. **Initialization**:
   - The `Display` class initializes the `TM1637` hardware module using pin definitions from the configuration.
   - It sets brightness, resets the display, and optionally starts an animation task.

2. **Display Updates**:
   - The content is displayed in prioritized layers:
     1. **Forced Text** (`force_off`)
     2. **Pin Code** (`pin`)
     3. **Countdown Timer** (`seconds_until_off`)
     4. **Status Text** (`status`)
     5. **Background Content** (`background`)

3. **Animation System**:
   - The display can scroll animations like text or time.
   - Background sequences (e.g., system messages) cycle periodically based on configuration.

4. **Custom Text/Numbers**:
   - Update display content using the `background`, `status`, or `pin` methods.

5. **Error Handling**:
   - Handles exceptions during animations and resets gracefully.

---

## Class Overview

### **`Display` Class**
A wrapper around the `TM1637` library for managing the 7-segment display.

#### Methods:
- **`__init__()`**:
  - Initializes the display, sets brightness, and starts animation if enabled.

- **`clear()`**:
  - Clears all segments of the display.
  
- **`brightness(brightness)`**:
  - Sets the display brightness (0-7).

- **`background(text: str, colon: bool)`**:
  - Shows text in the background layer. Optionally shows/hides the colon.

- **`status(text: str, colon: bool)`**:
  - Updates the status layer with higher priority than the background.

- **`force_off(text: str, colon: bool)`**:
  - Forces text on the display with the highest priority.

- **`pin(pin: int, colon: bool)`**:
  - Displays a PIN number with priority over background and status.

- **`seconds_until_off(seconds: int)`**:
  - Displays a countdown timer (MM:SS format) layer.

- **`__animation()`**:
  - A background coroutine for running animations based on a sequence of texts.

---

## Key Features and Configurations

### **Configurations**
The `Display` class reads configurations from `defaults.DEVICE_CONFIG`. Below are the key values:
- **`display/enabled`**: Turns the display on/off (`1` or `0`).
- **`display/brightness`**: Sets the brightness level of the display.
- **`display/scroll-speed`**: Speed for scrolling text (seconds).
- **`display/background-show-time-seconds`**: Duration to show background animations (seconds).
- **`display/background-sequence/*`**: Defines animation sequences for different modes (e.g., `control` mode or `on/off` states).

### **Animation System**
- Supports displaying text sequences with a scrolling effect for longer text.
- Each sequence consists of a `duration` (in seconds) and a `message`.
- Example animation: `"System Ready"` -> `"Machine 1"`.

---

## How to Use

### **Basic Initialization**
```python
from display import Display

# Create an instance of the Display class
display = Display()

# Clear the display
display.clear()
```

### **Set Brightness**
```python
# Set brightness (0-7)
display.brightness(5)
```

### **Show Background Text**
```python
# Show text on the background layer
display.background("INFO", colon=True)
```

### **Show Status**
```python
# Display status text with higher priority
display.status("ERR", colon=False)
```

### **Show PIN**
```python
# Display a PIN (higher priority than background/status)
display.pin(1234)
```

### **Show a Countdown Timer**
```python
# Show countdown in MM:SS format
display.seconds_until_off(120)  # Example: 120 seconds
```

---

## Requirements

- **MicroPython or CircuitPython** for microcontroller environments.
- `tm1637` library for hardware control of TM1637 display modules.
- `defaults.DEVICE_CONFIG` for configuration management.
  
Example `tm1637` hardware module: A 7-segment 4-digit display.

---

## Future Improvements

- Extend functionality for dynamic layer prioritization.
- Add more granular error handling for hardware failures.
- Support customizable segment patterns for advanced graphics.
- Add unit tests for verification in various configurations.

---

## License

This project is free to use under the MIT license. For more details, check the `LICENSE` file.