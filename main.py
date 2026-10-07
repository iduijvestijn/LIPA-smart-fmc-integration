import time
import numpy as np
from src.instruments.thorlabs_kdc101 import KDC101

def main():
    serial_number = str("27266437")
    stage = KDC101(serial_no=serial_number)

    try:
        stage.connect()
        print("Connection succesful, starting sweep")

        sweep_type1 = np.arange(0, 6, 1)
        for pos in sweep_type1:
            stage.move_abs(pos)
            #TRIGGER LOGOC FOR AWG M2p.6576

            time.sleep(0.5)
        print("Returning to home")
        stage.home()

    except Exception as e:
        print(f"Error occured during sweep: {e}")

    finally:
        stage.disconnect()

if __name__ == "__main__":
    main()
