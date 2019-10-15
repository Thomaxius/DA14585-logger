import bluepy
from bluepy.btle import Peripheral, DefaultDelegate
import binascii
from datetime import datetime
from logger import setup_logger
from collections import OrderedDict
import numpy as np

MAC_ADDRESS = ""
GENERAL_SERVICE_UUID = "2ea78970-7d44-44bb-b097-26183f402400"
CONTROL_SERVICE_UUID = "2ea78970-7d44-44bb-b097-26183f402409"
READ_SERVICE_UUID = "2ea78970-7d44-44bb-b097-26183f402410"
LOG_HANDLE = "dialog-data"
LOGFILE_NAME = "dialog-data.log"


class Dialog(Peripheral):

    def __init__(self, addr):
        Peripheral.__init__(self, addr)
        self.service = self.getServiceByUUID(GENERAL_SERVICE_UUID)
        self.control_characteristic = self.service.getCharacteristics(CONTROL_SERVICE_UUID)[0]
        self.data_characteristic = self.service.getCharacteristics(READ_SERVICE_UUID)[0]

    def enable_notifications(self):
        self.data_characteristic_handle = self.data_characteristic.getHandle()
        self.writeCharacteristic(self.data_characteristic_handle + 1, b"\x01\00", True)

    def enable_sensors(self):
        self.control_characteristic_handle = self.control_characteristic.getHandle()
        self.control_characteristic.write(b"\x01", True)


class MyDelegate(DefaultDelegate):

    logger = setup_logger(LOG_HANDLE, LOGFILE_NAME)

    def handleNotification(self, cHandle, raw_data):
        hexified_data = raw_data.hex()
        self.process_data(hexified_data)

    def process_data(self, data):
        sensor_report = self.extract_from_raw_sensor_data(data)
        sensor_report_dict = self.sensor_report(sensor_report)
        logline = self.get_logline(sensor_report_dict)
        self.log_data(logline)

    def get_logline(self, sensor_report_dict):
        logline = ""
        report = sensor_report_dict.get("REPORT")
        for reading, values_item in report.items():
            for key, value in values_item.items():
                logline += " {0}={1}".format(key, value)
        return logline

    def log_data(self, logline):
        self.logger.info(logline)

    def extract_from_raw_sensor_data(self, raw_data):
        """https://www.dialog-semiconductor.com/sites/default/files/um-b-101_da14585_iot_multi_sensor_development_kit_developer_guide_rev1.1.pdf Table 7"""
        preamble, timestamp, sensor_report = raw_data[0:2], raw_data[2:4], raw_data[4:]
        return sensor_report

    def sensor_report(self, sensor_report):
        timestamp = datetime.now().timestamp()
        sensor_report_json = OrderedDict({"TIMESTAMP": timestamp, "REPORT": OrderedDict({})})
        sensor_report_item = sensor_report_json.get("REPORT")
        if self.is_unsupported_sensor(self.to_int16(sensor_report[:2])):
            sensor_report_item.update({"UNKNOWN": sensor_report})
            return sensor_report_json
        reports = self.per_report_type_reports(sensor_report)
        for report in reports:
            report_id, report = self.to_int16(report[:2]), report[2:]
            sensor_item = self.SENSORS.get(report_id, None)
            if sensor_item is None:
                print("Unknown reading: ", sensor_report)
                continue
            report_type, report_parser = sensor_item.get("report_type"), sensor_item.get("report_parser")
            if not report_parser:
                print("Unsupported as of yet %s, data %s" % (report_type, report))
                return
            report_value = report_parser(self, report_id, report)
            sensor_report_item[report_type] = report_value
        return sensor_report_json

    def is_unsupported_sensor(self, sensor_id):
        return self.SENSORS.get(sensor_id, None) is None

    def per_report_type_reports(self, sensor_report):
        """Divides multi sensor report to a list with single reports: 040203669001000502033f720000 -> ['04020366900100', '0502033f720000']"""
        report_id = self.to_int16(sensor_report[:2])
        sensor = self.SENSORS.get(report_id).get("sensor")
        split_index = None
        if sensor == 'ACCELEROMETER':
            split_index = 18
        elif sensor == 'ENVIRONMENT':
            split_index = 14
        elif sensor == 'AMBIENT_LIGHT_AND_PROXIMITY':
            split_index = 14
        elif sensor == 'SENSOR_FUSION':
            split_index = None
        return self.divide_report_by_n(split_index, sensor_report)

    def divide_report_by_n(self, n, sensor_report):
        return [(sensor_report[i:i + n]) for i in range(0, len(sensor_report), n)] if n is not None else [sensor_report]

    def parse_accelerometer_report(self, report_id, sensor_report):
        report_type = self.SENSORS.get(report_id).get("report_type")
        xyz_hex_values = [sensor_report[4:8], sensor_report[8:12], sensor_report[12:16]]
        xyz_values = [self.parse_accelerometer_and_fusion_hex_value(x) for x in xyz_hex_values]
        return self.sort_dict({report_type+"_X": xyz_values[0], report_type+"_Y": xyz_values[1], report_type+"_Z": xyz_values[2]})

    def parse_accelerometer_and_fusion_hex_value(self, hex_value):
        # Turns hex value of accelerometer\fusion hexstring to human-readable values
        data = binascii.unhexlify(hex_value)
        data = int.from_bytes(data, byteorder="little")
        data = np.int16(data) / 32768.0
        return data

    def sort_dict(self, d):
        return OrderedDict(sorted(d.items()))

    def parse_environment_report(self, report_id, sensor_report):
        sensor_value = sensor_report[4:]
        report_type = self.SENSORS.get(report_id).get("report_type")
        value = None
        if report_type in ["TEMPERATURE", "PRESSURE"]:
            value = self.parse_environment_hex_value(sensor_value)
        if report_type == 'GAS':
            value = self.parse_gas_hex_value(sensor_value)
        elif report_type == 'HUMIDITY':
            value = self.parse_humidity_hex_value(sensor_value)
        return {report_type: value}

    def parse_environment_hex_value(self, hex_value):
        """Turns hex value of temperature, pressure and humidity into their respected human-readable values"""
        value = binascii.unhexlify(hex_value)
        value = int.from_bytes(value, byteorder="little") * 0.01
        return value

    def parse_gas_hex_value(self, hex_value):
        """Returns raw gas data"""
        data = binascii.unhexlify(hex_value)
        value = int.from_bytes(data, byteorder="little")
        return value

    def parse_humidity_hex_value(self, hex_value):
        data = binascii.unhexlify(hex_value)
        value = int.from_bytes(data, byteorder="little")
        humidity = round(value * 0.9765 * 0.001, 2)
        return humidity

    def parse_ambient_light_and_proximity_report(self, report_id, sensor_report):
        report_type = self.SENSORS.get(report_id).get("report_type")
        sensor_value = sensor_report[4:]
        value = None
        if report_type == 'AMBIENT_LIGHT':
            value = self.parse_ambient_light_hex_value(sensor_value)
        elif report_type == 'PROXIMITY':
            sensor_value = self.to_int16(sensor_value)
            if sensor_value == 0:
                value = "OFF"
            else:
                value = "ON"
        return {report_type: value}

    def parse_ambient_light_hex_value(self, hex_value):
        value = binascii.unhexlify(hex_value)
        value = int.from_bytes(value, byteorder="little") / 4
        return value

    def parse_fusion_report(self, report_id, sensor_report):
        wxyz_hex_values = [sensor_report[4:8], sensor_report[8:12], sensor_report[12:16], sensor_report[16:20]]
        wxyz_values = [self.parse_accelerometer_and_fusion_hex_value(x) for x in wxyz_hex_values]
        return self.sort_dict({"FUSION_W": wxyz_values[0], "FUSION_X": wxyz_values[1], "FUSION_Y": wxyz_values[2], "FUSION_Z": wxyz_values[3]})

    def to_int16(self, hex):
        data = binascii.unhexlify(hex)
        data = int.from_bytes(data, byteorder="little")
        data = np.int16(data)
        return data

    SENSORS = {
        1: {"report_type": "ACCELEROMETER", "sensor": "ACCELEROMETER", "report_parser": parse_accelerometer_report},
        2: {"report_type": "GYROSCOPE", "sensor": "ACCELEROMETER", "report_parser": parse_accelerometer_report},
        3: {"report_type": "MAGNETOMETER", "sensor": "ACCELEROMETER", "report_parser": parse_accelerometer_report},
        4: {"report_type": "PRESSURE", "sensor": "ENVIRONMENT", "report_parser": parse_environment_report},
        5: {"report_type": "HUMIDITY", "sensor": "ENVIRONMENT", "report_parser": parse_environment_report},
        6: {"report_type": "TEMPERATURE", "sensor": "ENVIRONMENT", "report_parser": parse_environment_report},
        7: {"report_type": "SENSOR_FUSION", "sensor": "SENSOR_FUSION", "report_parser": parse_fusion_report},
        8: {"report_type": "COMMAND_REPLY", "sensor": "COMMAND_REPLY"},
        9: {"report_type": "AMBIENT_LIGHT", "sensor": "AMBIENT_LIGHT_AND_PROXIMITY", "report_parser": parse_ambient_light_and_proximity_report},
        10: {"report_type": "PROXIMITY", "sensor": "AMBIENT_LIGHT_AND_PROXIMITY", "report_parser": parse_ambient_light_and_proximity_report},
        11: {"report_type": "GAS", "sensor": "ENVIRONMENT", "report_parser": parse_environment_report},
        12: {"report_type": "IAQ", "sensor": "INDOOR_AIR_QUALITY"},
        13: {"report_type": "BUTTON", "sensor": "BUTTON"},
        14: {"report_type": "VELOCITY_DELTA", "sensor": "VELOCITY_DELTA"},
        15: {"report_type": "EULER_ANGLE_DELTA", "sensor": "EULER_ANGLE_DELTA"},
        16: {"report_type": "QUATERNION_DELTA", "sensor": "QUATERNION_DELTA"},
    }


def main(MAC_ADDRESS):
    if not MAC_ADDRESS:
        print("Error: Mac Address not set.")
        return

    while True:
        print("Connecting to sensor...")
        try:

            d = Dialog(MAC_ADDRESS)
            print("Connection Succesful")

            print("Setting delegate")
            d.setDelegate(MyDelegate())
            print("Enabling notifications")
            d.enable_notifications()
            print("Enabling sensors")
            d.enable_sensors()

            print("Done setting up, listening to notifications..")
            while True:
                d.waitForNotifications(0)


        except bluepy.btle.BTLEDisconnectError:
            print("Disconnected from sensor, retrying..")
            pass


if __name__ == '__main__':
    main(MAC_ADDRESS)

