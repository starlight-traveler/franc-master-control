import serial
import struct
import flatbuffers
import logging
from lib.sensor_log.SensorBatch import SensorBatch
from lib.sensor_log.SensorType import SensorType

# Optional: Import other sensor data classes if needed

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define serial port and baud rate
SERIAL_PORT = 'COM3'  # Replace with your serial port
BAUD_RATE = 115200    # Replace with your baud rate

# Initialize serial connection
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

def read_exactly(ser, num_bytes):
    """Read exactly num_bytes from the serial port."""
    data = bytearray()
    while len(data) < num_bytes:
        packet = ser.read(num_bytes - len(data))
        if not packet:
            break  # Timeout or no data
        data.extend(packet)
    return bytes(data)

def deserialize_sensor_batch(buf):
    """Deserialize a SensorBatch FlatBuffer and store data."""
    try:
        sensor_batch = SensorBatch.GetRootAsSensorBatch(buf, 0)

        # Access common timestamp
        batch_timestamp = sensor_batch.Timestamp()
        logger.info(f"Batch Timestamp: {batch_timestamp}")

        # Access SensorMessages
        messages = sensor_batch.MessagesLength()
        for i in range(messages):
            sensor_message = sensor_batch.Messages(i)

            sensor_type = sensor_message.SensorType()
            timestamp = sensor_message.Timestamp()

            logger.info(f"Sensor Type: {SensorType.Name(sensor_type)}")
            logger.info(f"Message Timestamp: {timestamp}")

            # Access the union data based on sensor_type
            if sensor_type == SensorType.BME688:
                data = sensor_message.DataAsBME688Data()
                if data:
                    temperature = data.Temperature()
                    pressure = data.Pressure()
                    humidity = data.Humidity()
                    gas_resistance = data.GasResistance()
                    altitude = data.Altitude()
                    logger.info(f"BME688 Data: Temp={temperature} °C, Pressure={pressure} hPa, Humidity={humidity} %, Gas Resistance={gas_resistance} KOhms, Altitude={altitude} m")
            elif sensor_type == SensorType.ENS160:
                data = sensor_message.DataAsENS160Data()
                if data:
                    aqi = data.Aqi()
                    tvoc = data.Tvoc()
                    eco2 = data.Eco2()
                    hp0 = data.Hp0()
                    hp1 = data.Hp1()
                    hp2 = data.Hp2()
                    hp3 = data.Hp3()
                    logger.info(f"ENS160 Data: AQI={aqi}, TVOC={tvoc}, eCO2={eco2}, HP0={hp0}, HP1={hp1}, HP2={hp2}, HP3={hp3}")
            elif sensor_type == SensorType.LSM6D032:
                data = sensor_message.DataAsLSM6D032Data()
                if data:
                    accel_x = data.AccelX()
                    accel_y = data.AccelY()
                    accel_z = data.AccelZ()
                    gyro_x = data.GyroX()
                    gyro_y = data.GyroY()
                    gyro_z = data.GyroZ()
                    logger.info(f"LSM6D032 Data: Accel=({accel_x}, {accel_y}, {accel_z}) m/s², Gyro=({gyro_x}, {gyro_y}, {gyro_z}) °/s")
            elif sensor_type == SensorType.MPLAltimeter:
                data = sensor_message.DataAsMPLAltimeterData()
                if data:
                    pressure = data.Pressure()
                    altitude = data.Altitude()
                    logger.info(f"MPLAltimeter Data: Pressure={pressure} Pa, Altitude={altitude} m")
            elif sensor_type == SensorType.BNO055:
                data = sensor_message.DataAsBNO055Data()
                if data:
                    accel_x = data.AccelX()
                    accel_y = data.AccelY()
                    accel_z = data.AccelZ()
                    mag_x = data.MagX()
                    mag_y = data.MagY()
                    mag_z = data.MagZ()
                    gyro_x = data.GyroX()
                    gyro_y = data.GyroY()
                    gyro_z = data.GyroZ()
                    euler_heading = data.EulerHeading()
                    euler_roll = data.EulerRoll()
                    euler_pitch = data.EulerPitch()
                    linear_accel_x = data.LinearAccelX()
                    linear_accel_y = data.LinearAccelY()
                    linear_accel_z = data.LinearAccelZ()
                    gravity_x = data.GravityX()
                    gravity_y = data.GravityY()
                    gravity_z = data.GravityZ()
                    calibration_status_system = data.CalibrationStatusSystem()
                    calibration_status_gyro = data.CalibrationStatusGyro()
                    calibration_status_accel = data.CalibrationStatusAccel()
                    calibration_status_mag = data.CalibrationStatusMag()
                    logger.info(f"BNO055 Data: Accel=({accel_x}, {accel_y}, {accel_z}) m/s², Mag=({mag_x}, {mag_y}, {mag_z}) uT, Gyro=({gyro_x}, {gyro_y}, {gyro_z}) °/s, Euler=({euler_heading}, {euler_roll}, {euler_pitch})°, Linear Accel=({linear_accel_x}, {linear_accel_y}, {linear_accel_z}) m/s², Gravity=({gravity_x}, {gravity_y}, {gravity_z}) m/s², Calibration Status: System={calibration_status_system}, Gyro={calibration_status_gyro}, Accel={calibration_status_accel}, Mag={calibration_status_mag}")
            else:
                logger.warning("Unknown Sensor Type. Cannot deserialize data.")

    except Exception as e:
        logger.error(f"Failed to deserialize SensorBatch: {e}")

def receive_and_deserialize(ser):
    """Continuously receive and deserialize FlatBuffer messages from serial."""
    while True:
        # Step 1: Read the first 4 bytes for the message length
        length_bytes = read_exactly(ser, 4)
        if len(length_bytes) < 4:
            logger.warning("Incomplete length header received.")
            continue  # Or handle timeout

        # Unpack the length (assuming little-endian)
        message_length = struct.unpack('<I', length_bytes)[0]

        # Step 2: Read the FlatBuffer message based on the length
        message_bytes = read_exactly(ser, message_length)
        if len(message_bytes) < message_length:
            logger.warning("Incomplete FlatBuffer message received.")
            continue  # Or handle timeout

        # Step 3: Deserialize the FlatBuffer
        deserialize_sensor_batch(message_bytes)

        # Optional: Perform further processing with the deserialized data

if __name__ == "__main__":
    try:
        receive_and_deserialize(ser)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting.")
    finally:
        ser.close()
