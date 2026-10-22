"""
Test the VJoyController class in joy.py
Verifies that the vJoy device is recognized and driven correctly by QGroundControl
"""

import time
import sys
import os

# Add this script's directory to sys.path so joy.py next to it can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from joy import VJoyController

def test_basic_movement():
    """Test basic stick movement and button presses"""
    print("=== vJoy Controller test ===")
    try:
        # 1. Initialize the controller
        print("1. Initializing vJoy device...")
        controller = VJoyController(device_id=1)
        print("   vJoy device initialized.")
        time.sleep(1) # short wait to make sure initialization is done

        # 2. Test left stick (X, Y) - move right
        print("2. Testing left stick, move right...")
        controller.set_axis('x', 1.0) # X axis max (right)
        controller.set_axis('y', 0.0) # Y axis centered
        controller.update()
        print("   Left stick X axis set to 1.0 (right), Y axis centered.")
        time.sleep(2) # hold for 2 seconds

        # 3. Test left stick (X, Y) - move left
        print("3. Testing left stick, move left...")
        controller.set_axis('x', -1.0) # X axis min (left)
        controller.set_axis('y', 0.0)  # Y axis centered
        controller.update()
        print("   Left stick X axis set to -1.0 (left), Y axis centered.")
        time.sleep(2) # hold for 2 seconds

        # 4. Test left stick (X, Y) - centered
        print("4. Testing left stick, centered...")
        controller.set_axis('x', 0.0) # X axis centered
        controller.set_axis('y', 0.0) # Y axis centered
        controller.update()
        print("   Left stick X, Y axes set to 0.0 (centered).")
        time.sleep(1)

        # 5. Test right stick (RX, RY) - move up
        print("5. Testing right stick, move up...")
        controller.set_axis('rx', 0.0)  # RX axis centered
        controller.set_axis('ry', -1.0) # RY axis min (up)
        controller.update()
        print("   Right stick RX axis centered, RY axis set to -1.0 (up).")
        time.sleep(2) # hold for 2 seconds

        # 6. Test right stick (RX, RY) - centered
        print("6. Testing right stick, centered...")
        controller.set_axis('rx', 0.0) # RX axis centered
        controller.set_axis('ry', 0.0) # RY axis centered
        controller.update()
        print("   Right stick RX, RY axes set to 0.0 (centered).")
        time.sleep(1)

        # 7. Test button press
        print("7. Testing press and release of button 1...")
        controller.press_button(1, True) # press button 1
        controller.update()
        print("   Button 1 pressed.")
        time.sleep(1) # hold for 1 second

        controller.press_button(1, False) # release button 1
        controller.update()
        print("   Button 1 released.")
        time.sleep(1)

        # 8. Test button press (button 2)
        print("8. Testing press and release of button 2...")
        controller.press_button(2, True) # press button 2
        controller.update()
        print("   Button 2 pressed.")
        time.sleep(1) # hold for 1 second

        controller.press_button(2, False) # release button 2
        controller.update()
        print("   Button 2 released.")
        time.sleep(1)

        # 9. Reset and close
        print("9. Resetting and closing the device...")
        controller.reset()
        controller.close()
        print("   Device reset and closed.")

        print("\n=== Test complete ===")
        print("Check in QGroundControl that the joystick input is recognized and responds correctly.")

    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_basic_movement()