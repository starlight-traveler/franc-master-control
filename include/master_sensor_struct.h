#pragma once

struct MasterSensorData
{
    unsigned long timestamp;
    // BME688 fields:
    float bme_temperature;
    float bme_pressure;
    float bme_humidity;
    float bme_gas_resistance;
    float bme_altitude;
    // ENS160 fields:
    int ens_aqi;
    int ens_tvoc;
    int ens_eco2;
    float ens_hp0;
    float ens_hp1;
    float ens_hp2;
    float ens_hp3;
    // LSM6D032 fields:
    float lsm_accel_x;
    float lsm_accel_y;
    float lsm_accel_z;
    float lsm_gyro_x;
    float lsm_gyro_y;
    float lsm_gyro_z;
    // MPLAltimeter fields:
    float mpl_pressure;
    float mpl_altitude;
    // BNO055 fields:
    float bno_accel_x;
    float bno_accel_y;
    float bno_accel_z;
    float bno_mag_x;
    float bno_mag_y;
    float bno_mag_z;
    float bno_gyro_x;
    float bno_gyro_y;
    float bno_gyro_z;
    float bno_euler_heading;
    float bno_euler_roll;
    float bno_euler_pitch;
    float bno_linear_accel_x;
    float bno_linear_accel_y;
    float bno_linear_accel_z;
    float bno_gravity_x;
    float bno_gravity_y;
    float bno_gravity_z;
    uint8_t bno_calibration_system;
    uint8_t bno_calibration_gyro;
    uint8_t bno_calibration_accel;
    uint8_t bno_calibration_mag;
};
