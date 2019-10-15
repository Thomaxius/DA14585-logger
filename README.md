# DA14585-logger
Log sensor readings from Dialog DA14585 Multi Sensor IoT-kit

## How does it work?
- It connects to the sensor, parses incoming sensor reports as listed in table 8 of the [DA14585 documentation](https://www.dialog-semiconductor.com/sites/default/files/um-b-101_da14585_iot_multi_sensor_development_kit_developer_guide_rev1.1.pdf)

## What is supported and what isn't?
Currently, it supports reading from the following sensors:
- Accelerometer (accelerometer, gyroscope and magnetometer)
- Environment (pressure, humidity, temperature and gas)
- Fusion
- Ambient light and proximity

I'm not planning on supporting any more sensors right now.

Configuring or disabling\enabling sensors is not supported. Please use the "Dialog IoT Sensors" -Android\IOS app for this purpose.



## Unit readings
| Reading        | unit           |
| ------------- |:-------------:|
| Pressure      | hectopascal (hPa)      |
| Humidity | Relative Humidity (RH) %      |
| Temperature | Celcius (C)      |
| Gas | Ohms (?)      |
| Ambient light | Lux      |
| Proximity | On/Off |

I haven't confirmed what the gas sensor reading is supposed to be, but I'm guessing It's ohms which should be turned into ppm. [Here](https://jayconsystems.com/blog/understanding-a-gas-sensor) is further reading for those who are interested.

## Problems
There can be many disconnects from the device. Having too many sensors on or too high power modes can be a culprit. Please use the "Dialog IoT Sensors" -Android\IOS app to configure which sensors are on and at what power.

## Further reading
- Similar project: [Thanospan/EESTech-Challenge-2018-2019](https://github.com/thanospan/EESTech-Challenge-2018-2019)
- Dialog's own Python sample can be found in [their sensors official page's](https://www.dialog-semiconductor.com/products/da14585-iot-multi-sensor-development-kit) "Raspberry Pi Gateway Script Package"
