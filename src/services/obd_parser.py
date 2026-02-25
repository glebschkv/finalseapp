"""
OBD-II Log Parser Service.
Implements BR2: New Chat Creation with Log Upload
"""

import pandas as pd
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from enum import Enum

from ..config.logging_config import get_logger

logger = get_logger(__name__)


class OBDParseError(Exception):
    """Custom exception for OBD-II parsing errors."""
    pass


class MetricStatus(Enum):
    """Status classification for metrics."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class OBDMetric:
    """Represents a parsed OBD-II metric."""
    name: str
    value: float
    unit: str
    status: str = "normal"  # 'normal', 'warning', 'critical'
    pid: Optional[str] = None
    description: Optional[str] = None
    normal_range: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class FaultCode:
    """Represents an OBD-II Diagnostic Trouble Code (DTC)."""
    code: str
    description: str
    severity: str  # 'critical', 'warning', 'info'
    category: str  # 'powertrain', 'chassis', 'body', 'network'
    is_generic: bool = True
    possible_causes: List[str] = field(default_factory=list)
    recommended_action: Optional[str] = None


class OBDParser:
    """
    Parser for OBD-II log files (CSV format).

    Supports:
    - BR2.1: User uploads a valid log file
    - BR2.2: User uploads an invalid file type
    - BR2.3: User uploads a valid file type with bad data
    """

    # Normal ranges for common OBD-II metrics
    METRIC_RANGES: Dict[str, Dict[str, float]] = {
        "engine_rpm": {
            "min": 600, "max": 7000,
            "warning_low": 400, "warning_high": 6500,
            "critical_low": 200, "critical_high": 7500
        },
        "coolant_temp": {
            "min": 70, "max": 105,
            "warning_low": 50, "warning_high": 110,
            "critical_low": 30, "critical_high": 120
        },
        "vehicle_speed": {
            "min": 0, "max": 200,
            "warning_low": 0, "warning_high": 180,
            "critical_low": 0, "critical_high": 220
        },
        "throttle_position": {
            "min": 0, "max": 100,
            "warning_low": 0, "warning_high": 95,
            "critical_low": 0, "critical_high": 100
        },
        "engine_load": {
            "min": 0, "max": 80,
            "warning_low": 0, "warning_high": 85,
            "critical_low": 0, "critical_high": 95
        },
        "fuel_level": {
            "min": 10, "max": 100,
            "warning_low": 5, "warning_high": 100,
            "critical_low": 0, "critical_high": 100
        },
        "intake_air_temp": {
            "min": -20, "max": 60,
            "warning_low": -30, "warning_high": 70,
            "critical_low": -40, "critical_high": 80
        },
        "maf_rate": {
            "min": 2, "max": 300,
            "warning_low": 1, "warning_high": 400,
            "critical_low": 0, "critical_high": 500
        },
        "fuel_pressure": {
            "min": 250, "max": 450,
            "warning_low": 200, "warning_high": 500,
            "critical_low": 100, "critical_high": 600
        },
        "battery_voltage": {
            "min": 12.4, "max": 14.7,
            "warning_low": 11.8, "warning_high": 15.0,
            "critical_low": 11.0, "critical_high": 16.0
        }
    }

    # Comprehensive OBD-II fault code definitions (185+ codes)
    FAULT_CODE_DATABASE: Dict[str, Tuple[str, str, List[str]]] = {
        # ===== FUEL AND AIR METERING (P0100-P0199) =====
        "P0100": ("Mass Air Flow Circuit Malfunction", "warning", ["Dirty MAF sensor", "Air leak", "Wiring issue"]),
        "P0101": ("Mass Air Flow Circuit Range/Performance", "warning", ["Dirty MAF sensor", "Vacuum leak"]),
        "P0102": ("Mass Air Flow Circuit Low Input", "warning", ["Sensor failure", "Wiring open circuit"]),
        "P0103": ("Mass Air Flow Circuit High Input", "warning", ["Sensor failure", "Short circuit"]),
        "P0104": ("Mass Air Flow Circuit Intermittent", "warning", ["Loose connection", "Damaged wiring"]),
        "P0105": ("Manifold Absolute Pressure Circuit Malfunction", "warning", ["MAP sensor failure", "Vacuum leak"]),
        "P0106": ("MAP/Barometric Pressure Circuit Range/Performance", "warning", ["MAP sensor", "Intake leak"]),
        "P0107": ("MAP/Barometric Pressure Circuit Low Input", "warning", ["Short to ground", "Wiring issue"]),
        "P0108": ("MAP/Barometric Pressure Circuit High Input", "warning", ["Open circuit", "Sensor failure"]),
        "P0110": ("Intake Air Temperature Circuit Malfunction", "warning", ["IAT sensor", "Wiring"]),
        "P0111": ("Intake Air Temperature Circuit Range/Performance", "warning", ["IAT sensor location", "Heat soak"]),
        "P0112": ("Intake Air Temperature Circuit Low Input", "warning", ["Short to ground", "Sensor"]),
        "P0113": ("Intake Air Temperature Circuit High Input", "warning", ["Open circuit", "Connector"]),

        # Coolant Temperature
        "P0115": ("Engine Coolant Temperature Circuit Malfunction", "critical", ["Sensor failure", "Wiring issue"]),
        "P0116": ("Engine Coolant Temperature Circuit Range/Performance", "warning", ["Thermostat stuck", "Sensor drift"]),
        "P0117": ("Engine Coolant Temperature Circuit Low Input", "warning", ["Short to ground", "Sensor failure"]),
        "P0118": ("Engine Coolant Temperature Circuit High Input", "critical", ["Open circuit", "Sensor failure"]),
        "P0119": ("Engine Coolant Temperature Circuit Intermittent", "warning", ["Loose connection"]),

        # Throttle Position
        "P0120": ("Throttle Position Sensor Circuit Malfunction", "critical", ["TPS failure", "Wiring damage"]),
        "P0121": ("Throttle Position Sensor Range/Performance", "warning", ["TPS wear", "Calibration needed"]),
        "P0122": ("Throttle Position Sensor Circuit Low Input", "critical", ["Short to ground"]),
        "P0123": ("Throttle Position Sensor Circuit High Input", "critical", ["Open circuit"]),
        "P0124": ("Throttle Position Sensor Circuit Intermittent", "warning", ["Loose connection", "Worn TPS"]),
        "P0125": ("Insufficient Coolant Temperature for Closed Loop", "warning", ["Thermostat", "ECT sensor"]),

        # Oxygen Sensors - Bank 1
        "P0130": ("O2 Sensor Circuit Malfunction (Bank 1 Sensor 1)", "warning", ["Sensor aging", "Exhaust leak"]),
        "P0131": ("O2 Sensor Circuit Low Voltage (Bank 1 Sensor 1)", "warning", ["Lean condition", "Sensor failure"]),
        "P0132": ("O2 Sensor Circuit High Voltage (Bank 1 Sensor 1)", "warning", ["Rich condition", "Sensor failure"]),
        "P0133": ("O2 Sensor Circuit Slow Response (Bank 1 Sensor 1)", "warning", ["Sensor aging"]),
        "P0134": ("O2 Sensor Circuit No Activity (Bank 1 Sensor 1)", "warning", ["Sensor failure", "Wiring issue"]),
        "P0135": ("O2 Sensor Heater Circuit Malfunction (Bank 1 Sensor 1)", "warning", ["Heater circuit", "Fuse"]),
        "P0136": ("O2 Sensor Circuit Malfunction (Bank 1 Sensor 2)", "warning", ["Downstream sensor"]),
        "P0137": ("O2 Sensor Circuit Low Voltage (Bank 1 Sensor 2)", "warning", ["Lean exhaust", "Sensor"]),
        "P0138": ("O2 Sensor Circuit High Voltage (Bank 1 Sensor 2)", "warning", ["Rich exhaust", "Sensor"]),
        "P0139": ("O2 Sensor Circuit Slow Response (Bank 1 Sensor 2)", "warning", ["Sensor aging"]),
        "P0140": ("O2 Sensor Circuit No Activity (Bank 1 Sensor 2)", "warning", ["Sensor failure"]),
        "P0141": ("O2 Sensor Heater Circuit Malfunction (Bank 1 Sensor 2)", "warning", ["Heater failure"]),

        # Oxygen Sensors - Bank 2
        "P0150": ("O2 Sensor Circuit Malfunction (Bank 2 Sensor 1)", "warning", ["Sensor aging", "Exhaust leak"]),
        "P0151": ("O2 Sensor Circuit Low Voltage (Bank 2 Sensor 1)", "warning", ["Lean condition"]),
        "P0152": ("O2 Sensor Circuit High Voltage (Bank 2 Sensor 1)", "warning", ["Rich condition"]),
        "P0153": ("O2 Sensor Circuit Slow Response (Bank 2 Sensor 1)", "warning", ["Sensor aging"]),
        "P0154": ("O2 Sensor Circuit No Activity (Bank 2 Sensor 1)", "warning", ["Sensor failure"]),
        "P0155": ("O2 Sensor Heater Circuit Malfunction (Bank 2 Sensor 1)", "warning", ["Heater circuit"]),
        "P0156": ("O2 Sensor Circuit Malfunction (Bank 2 Sensor 2)", "warning", ["Downstream sensor"]),
        "P0157": ("O2 Sensor Circuit Low Voltage (Bank 2 Sensor 2)", "warning", ["Sensor failure"]),
        "P0158": ("O2 Sensor Circuit High Voltage (Bank 2 Sensor 2)", "warning", ["Sensor failure"]),

        # Fuel System
        "P0169": ("Incorrect Fuel Composition", "warning", ["Wrong fuel type", "Contaminated fuel"]),
        "P0170": ("Fuel Trim Malfunction (Bank 1)", "warning", ["Vacuum leak", "Fuel pressure issue"]),
        "P0171": ("System Too Lean (Bank 1)", "warning", ["Vacuum leak", "Low fuel pressure", "MAF issue"]),
        "P0172": ("System Too Rich (Bank 1)", "warning", ["Leaking injector", "High fuel pressure"]),
        "P0173": ("Fuel Trim Malfunction (Bank 2)", "warning", ["Vacuum leak", "Fuel pressure"]),
        "P0174": ("System Too Lean (Bank 2)", "warning", ["Vacuum leak", "Low fuel pressure"]),
        "P0175": ("System Too Rich (Bank 2)", "warning", ["Leaking injector", "High pressure"]),
        "P0180": ("Fuel Temperature Sensor A Circuit", "warning", ["Sensor failure", "Wiring"]),
        "P0181": ("Fuel Temperature Sensor A Range/Performance", "warning", ["Sensor drift"]),
        "P0182": ("Fuel Temperature Sensor A Circuit Low", "warning", ["Short to ground"]),
        "P0183": ("Fuel Temperature Sensor A Circuit High", "warning", ["Open circuit"]),
        "P0190": ("Fuel Rail Pressure Sensor Circuit", "critical", ["Sensor failure", "Wiring"]),
        "P0191": ("Fuel Rail Pressure Sensor Range/Performance", "warning", ["Sensor drift", "Fuel pressure"]),
        "P0192": ("Fuel Rail Pressure Sensor Circuit Low", "warning", ["Short to ground"]),
        "P0193": ("Fuel Rail Pressure Sensor Circuit High", "warning", ["Open circuit"]),
        "P0194": ("Fuel Rail Pressure Sensor Circuit Intermittent", "warning", ["Loose connection"]),

        # ===== FUEL AND AIR METERING (P0200-P0299) =====
        "P0200": ("Injector Circuit Malfunction", "critical", ["Injector failure", "Wiring", "ECU"]),
        "P0201": ("Injector Circuit Malfunction - Cylinder 1", "critical", ["Injector 1", "Wiring"]),
        "P0202": ("Injector Circuit Malfunction - Cylinder 2", "critical", ["Injector 2", "Wiring"]),
        "P0203": ("Injector Circuit Malfunction - Cylinder 3", "critical", ["Injector 3", "Wiring"]),
        "P0204": ("Injector Circuit Malfunction - Cylinder 4", "critical", ["Injector 4", "Wiring"]),
        "P0205": ("Injector Circuit Malfunction - Cylinder 5", "critical", ["Injector 5", "Wiring"]),
        "P0206": ("Injector Circuit Malfunction - Cylinder 6", "critical", ["Injector 6", "Wiring"]),
        "P0207": ("Injector Circuit Malfunction - Cylinder 7", "critical", ["Injector 7", "Wiring"]),
        "P0208": ("Injector Circuit Malfunction - Cylinder 8", "critical", ["Injector 8", "Wiring"]),
        "P0218": ("Transmission Fluid Over Temperature", "critical", ["Low fluid", "Cooler blockage", "Heavy load"]),
        "P0219": ("Engine Overspeed Condition", "critical", ["Rev limiter issue", "Transmission slip"]),
        "P0220": ("Throttle/Pedal Position Sensor B Circuit", "warning", ["APP sensor B", "Wiring"]),
        "P0221": ("Throttle/Pedal Position Sensor B Range/Performance", "warning", ["Sensor drift"]),
        "P0222": ("Throttle/Pedal Position Sensor B Circuit Low", "critical", ["Short to ground"]),
        "P0223": ("Throttle/Pedal Position Sensor B Circuit High", "critical", ["Open circuit"]),
        "P0230": ("Fuel Pump Primary Circuit Malfunction", "critical", ["Fuel pump relay", "Wiring", "Pump"]),
        "P0231": ("Fuel Pump Secondary Circuit Low", "critical", ["Fuel pump", "Wiring"]),
        "P0232": ("Fuel Pump Secondary Circuit High", "critical", ["Short circuit", "Relay stuck"]),
        "P0261": ("Cylinder 1 Injector Circuit Low", "warning", ["Short to ground", "Injector"]),
        "P0262": ("Cylinder 1 Injector Circuit High", "warning", ["Open circuit", "Injector"]),
        "P0263": ("Cylinder 1 Contribution/Balance", "warning", ["Injector", "Compression"]),
        "P0264": ("Cylinder 2 Injector Circuit Low", "warning", ["Short to ground", "Injector"]),
        "P0265": ("Cylinder 2 Injector Circuit High", "warning", ["Open circuit", "Injector"]),

        # ===== IGNITION SYSTEM (P0300-P0399) =====
        "P0300": ("Random/Multiple Cylinder Misfire Detected", "critical", ["Spark plugs", "Ignition coils", "Fuel injectors"]),
        "P0301": ("Cylinder 1 Misfire Detected", "critical", ["Spark plug", "Ignition coil", "Injector"]),
        "P0302": ("Cylinder 2 Misfire Detected", "critical", ["Spark plug", "Ignition coil", "Injector"]),
        "P0303": ("Cylinder 3 Misfire Detected", "critical", ["Spark plug", "Ignition coil", "Injector"]),
        "P0304": ("Cylinder 4 Misfire Detected", "critical", ["Spark plug", "Ignition coil", "Injector"]),
        "P0305": ("Cylinder 5 Misfire Detected", "critical", ["Spark plug", "Ignition coil", "Injector"]),
        "P0306": ("Cylinder 6 Misfire Detected", "critical", ["Spark plug", "Ignition coil", "Injector"]),
        "P0307": ("Cylinder 7 Misfire Detected", "critical", ["Spark plug", "Ignition coil", "Injector"]),
        "P0308": ("Cylinder 8 Misfire Detected", "critical", ["Spark plug", "Ignition coil", "Injector"]),
        "P0320": ("Ignition/Distributor Engine Speed Input Circuit", "critical", ["CKP sensor", "Wiring"]),
        "P0321": ("Ignition/Distributor Engine Speed Input Range/Performance", "warning", ["CKP sensor"]),
        "P0322": ("Ignition/Distributor Engine Speed Input No Signal", "critical", ["CKP sensor", "Wiring"]),
        "P0325": ("Knock Sensor 1 Circuit (Bank 1 or Single Sensor)", "warning", ["Knock sensor", "Wiring"]),
        "P0326": ("Knock Sensor 1 Range/Performance (Bank 1)", "warning", ["Knock sensor"]),
        "P0327": ("Knock Sensor 1 Circuit Low (Bank 1)", "warning", ["Short to ground"]),
        "P0328": ("Knock Sensor 1 Circuit High (Bank 1)", "warning", ["Open circuit"]),
        "P0330": ("Knock Sensor 2 Circuit (Bank 2)", "warning", ["Knock sensor 2", "Wiring"]),
        "P0335": ("Crankshaft Position Sensor A Circuit", "critical", ["CKP sensor", "Reluctor wheel", "Wiring"]),
        "P0336": ("Crankshaft Position Sensor A Range/Performance", "warning", ["CKP sensor", "Air gap"]),
        "P0337": ("Crankshaft Position Sensor A Circuit Low", "critical", ["Short to ground"]),
        "P0338": ("Crankshaft Position Sensor A Circuit High", "critical", ["Open circuit"]),
        "P0340": ("Camshaft Position Sensor A Circuit (Bank 1 or Single)", "critical", ["CMP sensor", "Timing chain"]),
        "P0341": ("Camshaft Position Sensor A Range/Performance (Bank 1)", "warning", ["CMP sensor", "Timing"]),
        "P0342": ("Camshaft Position Sensor A Circuit Low (Bank 1)", "critical", ["Short to ground"]),
        "P0343": ("Camshaft Position Sensor A Circuit High (Bank 1)", "critical", ["Open circuit"]),
        "P0345": ("Camshaft Position Sensor A Circuit (Bank 2)", "critical", ["CMP sensor B2"]),
        "P0350": ("Ignition Coil Primary/Secondary Circuit", "critical", ["Coil pack", "Wiring", "ECU"]),
        "P0351": ("Ignition Coil A Primary/Secondary Circuit", "critical", ["Coil A", "Wiring"]),
        "P0352": ("Ignition Coil B Primary/Secondary Circuit", "critical", ["Coil B", "Wiring"]),
        "P0353": ("Ignition Coil C Primary/Secondary Circuit", "critical", ["Coil C", "Wiring"]),
        "P0354": ("Ignition Coil D Primary/Secondary Circuit", "critical", ["Coil D", "Wiring"]),

        # ===== AUXILIARY EMISSION CONTROLS (P0400-P0499) =====
        "P0400": ("EGR Flow Malfunction", "warning", ["EGR valve", "Carbon buildup", "Vacuum"]),
        "P0401": ("EGR Flow Insufficient Detected", "warning", ["EGR valve stuck closed", "Carbon buildup"]),
        "P0402": ("EGR Flow Excessive Detected", "warning", ["EGR valve stuck open", "Vacuum leak"]),
        "P0403": ("EGR Circuit Malfunction", "warning", ["EGR solenoid", "Wiring"]),
        "P0404": ("EGR Control Circuit Range/Performance", "warning", ["EGR position sensor"]),
        "P0405": ("EGR Sensor A Circuit Low", "warning", ["Short to ground"]),
        "P0406": ("EGR Sensor A Circuit High", "warning", ["Open circuit"]),
        "P0410": ("Secondary Air Injection System", "warning", ["AIR pump", "Check valve"]),
        "P0411": ("Secondary Air Injection System Incorrect Flow", "warning", ["AIR pump weak", "Blockage"]),
        "P0420": ("Catalyst System Efficiency Below Threshold (Bank 1)", "warning", ["Catalytic converter wear", "O2 sensor issue"]),
        "P0421": ("Warm Up Catalyst Efficiency Below Threshold (Bank 1)", "warning", ["Catalytic converter"]),
        "P0430": ("Catalyst System Efficiency Below Threshold (Bank 2)", "warning", ["Catalytic converter wear"]),
        "P0440": ("Evaporative Emission Control System Malfunction", "info", ["Gas cap loose", "EVAP leak"]),
        "P0441": ("Evaporative Emission Control System Incorrect Purge Flow", "info", ["Purge valve"]),
        "P0442": ("Evaporative Emission Control System Leak Detected (small leak)", "info", ["Small EVAP leak"]),
        "P0443": ("Evaporative Emission Control System Purge Control Valve Circuit", "info", ["Purge valve circuit"]),
        "P0444": ("Evaporative Emission Control System Purge Control Valve Circuit Open", "info", ["Open circuit"]),
        "P0445": ("Evaporative Emission Control System Purge Control Valve Circuit Shorted", "info", ["Short circuit"]),
        "P0446": ("Evaporative Emission Control System Vent Control Circuit", "info", ["Vent valve"]),
        "P0447": ("Evaporative Emission Control System Vent Control Circuit Open", "info", ["Open circuit"]),
        "P0448": ("Evaporative Emission Control System Vent Control Circuit Shorted", "info", ["Short circuit"]),
        "P0449": ("Evaporative Emission Control System Vent Valve/Solenoid Circuit", "info", ["Vent solenoid"]),
        "P0450": ("Evaporative Emission Control System Pressure Sensor", "info", ["FTP sensor"]),
        "P0451": ("Evaporative Emission Control System Pressure Sensor Range/Performance", "info", ["FTP sensor drift"]),
        "P0452": ("Evaporative Emission Control System Pressure Sensor Low", "info", ["Short to ground"]),
        "P0453": ("Evaporative Emission Control System Pressure Sensor High", "info", ["Open circuit"]),
        "P0455": ("Evaporative Emission Control System Leak Detected (large leak)", "warning", ["Large EVAP leak", "Gas cap missing"]),
        "P0456": ("Evaporative Emission Control System Leak Detected (very small leak)", "info", ["Very small EVAP leak"]),

        # ===== VEHICLE SPEED AND IDLE CONTROL (P0500-P0599) =====
        "P0500": ("Vehicle Speed Sensor Malfunction", "warning", ["VSS failure", "Wiring issue"]),
        "P0501": ("Vehicle Speed Sensor Range/Performance", "warning", ["VSS calibration"]),
        "P0502": ("Vehicle Speed Sensor Circuit Low Input", "warning", ["Short to ground"]),
        "P0503": ("Vehicle Speed Sensor Intermittent/Erratic/High", "warning", ["Loose connection"]),
        "P0505": ("Idle Control System Malfunction", "warning", ["Idle air control valve", "Vacuum leak"]),
        "P0506": ("Idle Control System RPM Lower Than Expected", "warning", ["IAC valve", "Vacuum leak"]),
        "P0507": ("Idle Control System RPM Higher Than Expected", "warning", ["Vacuum leak", "Throttle body dirty"]),
        "P0510": ("Closed Throttle Position Switch", "warning", ["TPS adjustment", "Switch"]),
        "P0520": ("Engine Oil Pressure Sensor/Switch Circuit", "critical", ["Oil pressure sensor", "Wiring"]),
        "P0521": ("Engine Oil Pressure Sensor/Switch Range/Performance", "critical", ["Oil pressure", "Sensor"]),
        "P0522": ("Engine Oil Pressure Sensor/Switch Low Voltage", "critical", ["Low oil pressure", "Sensor"]),
        "P0523": ("Engine Oil Pressure Sensor/Switch High Voltage", "critical", ["Sensor failure", "Wiring"]),
        "P0530": ("A/C Refrigerant Pressure Sensor Circuit", "warning", ["A/C sensor", "Wiring"]),
        "P0531": ("A/C Refrigerant Pressure Sensor Range/Performance", "warning", ["Low refrigerant"]),
        "P0532": ("A/C Refrigerant Pressure Sensor Circuit Low", "warning", ["Short to ground"]),
        "P0533": ("A/C Refrigerant Pressure Sensor Circuit High", "warning", ["Open circuit"]),
        "P0550": ("Power Steering Pressure Sensor Circuit", "warning", ["PSP sensor", "Wiring"]),
        "P0560": ("System Voltage Malfunction", "warning", ["Alternator", "Battery", "Wiring"]),
        "P0562": ("System Voltage Low", "warning", ["Alternator weak", "Battery drain"]),
        "P0563": ("System Voltage High", "warning", ["Alternator overcharging", "Regulator"]),

        # ===== COMPUTER OUTPUT CIRCUITS (P0600-P0699) =====
        "P0600": ("Serial Communication Link Malfunction", "critical", ["ECU communication", "Wiring"]),
        "P0601": ("Internal Control Module Memory Check Sum Error", "critical", ["ECU failure", "Reprogramming needed"]),
        "P0602": ("Control Module Programming Error", "critical", ["ECU programming", "Reflash needed"]),
        "P0603": ("Internal Control Module Keep Alive Memory (KAM) Error", "warning", ["Battery disconnect", "ECU"]),
        "P0604": ("Internal Control Module Random Access Memory (RAM) Error", "critical", ["ECU failure"]),
        "P0605": ("Internal Control Module Read Only Memory (ROM) Error", "critical", ["ECU failure"]),
        "P0606": ("ECM/PCM Processor", "critical", ["ECU internal failure"]),
        "P0607": ("Control Module Performance", "critical", ["ECU performance issue"]),
        "P0615": ("Starter Relay Circuit", "warning", ["Starter relay", "Wiring"]),
        "P0616": ("Starter Relay Circuit Low", "warning", ["Short to ground"]),
        "P0617": ("Starter Relay Circuit High", "warning", ["Open circuit", "Relay stuck"]),
        "P0620": ("Generator Control Circuit", "warning", ["Alternator control", "Wiring"]),
        "P0625": ("Generator Field Terminal Circuit Low", "warning", ["Alternator field"]),
        "P0626": ("Generator Field Terminal Circuit High", "warning", ["Alternator field"]),
        "P0627": ("Fuel Pump A Control Circuit/Open", "critical", ["Fuel pump relay", "Wiring"]),
        "P0628": ("Fuel Pump A Control Circuit Low", "critical", ["Short to ground"]),
        "P0629": ("Fuel Pump A Control Circuit High", "critical", ["Open circuit"]),
        "P0650": ("Malfunction Indicator Lamp (MIL) Control Circuit", "warning", ["MIL bulb", "Wiring"]),

        # ===== TRANSMISSION (P0700-P0899) =====
        "P0700": ("Transmission Control System Malfunction", "warning", ["TCM issue", "Wiring"]),
        "P0701": ("Transmission Control System Range/Performance", "warning", ["TCM performance"]),
        "P0702": ("Transmission Control System Electrical", "warning", ["TCM electrical"]),
        "P0703": ("Brake Switch B Circuit", "warning", ["Brake switch", "Wiring"]),
        "P0704": ("Clutch Switch Input Circuit", "warning", ["Clutch switch"]),
        "P0705": ("Transmission Range Sensor Circuit (PRNDL)", "warning", ["TR sensor", "Adjustment"]),
        "P0706": ("Transmission Range Sensor Range/Performance", "warning", ["TR sensor"]),
        "P0707": ("Transmission Range Sensor Circuit Low", "warning", ["Short to ground"]),
        "P0708": ("Transmission Range Sensor Circuit High", "warning", ["Open circuit"]),
        "P0710": ("Transmission Fluid Temperature Sensor Circuit", "warning", ["TFT sensor"]),
        "P0711": ("Transmission Fluid Temperature Sensor Range/Performance", "warning", ["TFT sensor"]),
        "P0712": ("Transmission Fluid Temperature Sensor Circuit Low", "warning", ["Short to ground"]),
        "P0713": ("Transmission Fluid Temperature Sensor Circuit High", "warning", ["Open circuit"]),
        "P0715": ("Input/Turbine Speed Sensor Circuit Malfunction", "warning", ["Speed sensor"]),
        "P0716": ("Input/Turbine Speed Sensor Range/Performance", "warning", ["Speed sensor"]),
        "P0717": ("Input/Turbine Speed Sensor Circuit No Signal", "critical", ["Speed sensor failure"]),
        "P0720": ("Output Speed Sensor Circuit Malfunction", "warning", ["Speed sensor"]),
        "P0721": ("Output Speed Sensor Range/Performance", "warning", ["Speed sensor"]),
        "P0722": ("Output Speed Sensor Circuit No Signal", "critical", ["Speed sensor failure"]),
        "P0725": ("Engine Speed Input Circuit", "warning", ["Engine speed input"]),
        "P0730": ("Incorrect Gear Ratio", "critical", ["Transmission wear", "Low fluid"]),
        "P0731": ("Gear 1 Incorrect Ratio", "critical", ["Transmission 1st gear"]),
        "P0732": ("Gear 2 Incorrect Ratio", "critical", ["Transmission 2nd gear"]),
        "P0733": ("Gear 3 Incorrect Ratio", "critical", ["Transmission 3rd gear"]),
        "P0734": ("Gear 4 Incorrect Ratio", "critical", ["Transmission 4th gear"]),
        "P0735": ("Gear 5 Incorrect Ratio", "critical", ["Transmission 5th gear"]),
        "P0740": ("Torque Converter Clutch Circuit Malfunction", "warning", ["TCC solenoid"]),
        "P0741": ("Torque Converter Clutch Circuit Performance/Stuck Off", "warning", ["TCC stuck off"]),
        "P0742": ("Torque Converter Clutch Circuit Stuck On", "warning", ["TCC stuck on"]),
        "P0743": ("Torque Converter Clutch Circuit Electrical", "warning", ["TCC electrical"]),
        "P0744": ("Torque Converter Clutch Circuit Intermittent", "warning", ["TCC intermittent"]),
        "P0750": ("Shift Solenoid A Malfunction", "warning", ["Shift solenoid A"]),
        "P0751": ("Shift Solenoid A Performance/Stuck Off", "warning", ["Solenoid A stuck"]),
        "P0752": ("Shift Solenoid A Stuck On", "warning", ["Solenoid A stuck on"]),
        "P0755": ("Shift Solenoid B Malfunction", "warning", ["Shift solenoid B"]),
        "P0756": ("Shift Solenoid B Performance/Stuck Off", "warning", ["Solenoid B stuck"]),
        "P0757": ("Shift Solenoid B Stuck On", "warning", ["Solenoid B stuck on"]),
        "P0760": ("Shift Solenoid C Malfunction", "warning", ["Shift solenoid C"]),
        "P0765": ("Shift Solenoid D Malfunction", "warning", ["Shift solenoid D"]),
        "P0770": ("Shift Solenoid E Malfunction", "warning", ["Shift solenoid E"]),
        "P0775": ("Pressure Control Solenoid B", "warning", ["PC solenoid B"]),
        "P0780": ("Shift Malfunction", "critical", ["Transmission shift issue"]),
        "P0781": ("1-2 Shift Malfunction", "critical", ["1-2 shift failure"]),
        "P0782": ("2-3 Shift Malfunction", "critical", ["2-3 shift failure"]),
        "P0783": ("3-4 Shift Malfunction", "critical", ["3-4 shift failure"]),
        "P0784": ("4-5 Shift Malfunction", "critical", ["4-5 shift failure"]),

        # ===== CHASSIS CODES (C-CODES) =====
        "C0035": ("Left Front Wheel Speed Sensor Circuit", "warning", ["Wheel speed sensor", "Wiring"]),
        "C0040": ("Right Front Wheel Speed Sensor Circuit", "warning", ["Wheel speed sensor", "Wiring"]),
        "C0045": ("Left Rear Wheel Speed Sensor Circuit", "warning", ["Wheel speed sensor", "Wiring"]),
        "C0050": ("Right Rear Wheel Speed Sensor Circuit", "warning", ["Wheel speed sensor", "Wiring"]),
        "C0550": ("ECU Malfunction", "critical", ["ABS/ESC module", "Internal failure"]),
        "C0561": ("ABS System Disabled", "critical", ["ABS system fault"]),
        "C1095": ("ABS Hydraulic Pump Motor Circuit", "critical", ["ABS pump", "Motor"]),
        "C1201": ("Engine Control System Malfunction", "warning", ["Engine fault affects ABS"]),
        "C1234": ("Wheel Speed Sensor LF Input Signal Missing", "warning", ["LF sensor", "Wiring"]),
        "C1235": ("Wheel Speed Sensor RF Input Signal Missing", "warning", ["RF sensor", "Wiring"]),
        "C1236": ("Wheel Speed Sensor LR Input Signal Missing", "warning", ["LR sensor", "Wiring"]),
        "C1237": ("Wheel Speed Sensor RR Input Signal Missing", "warning", ["RR sensor", "Wiring"]),

        # ===== BODY CODES (B-CODES) =====
        "B0001": ("Driver Frontal Stage 1 Deployment Control", "critical", ["Airbag driver side"]),
        "B0002": ("Driver Frontal Stage 2 Deployment Control", "critical", ["Airbag driver side"]),
        "B0003": ("Passenger Frontal Stage 1 Deployment Control", "critical", ["Airbag passenger side"]),
        "B0100": ("Driver Frontal Deployment Loop Resistance Low", "critical", ["Airbag circuit low"]),
        "B0101": ("Driver Frontal Deployment Loop Resistance High", "critical", ["Airbag circuit high"]),
        "B1000": ("ECU Malfunction", "warning", ["Body control module"]),
        "B1200": ("Climate Control Pushbutton Circuit Malfunction", "info", ["Climate control buttons"]),
        "B1318": ("Battery Voltage Low", "warning", ["Battery", "Charging system"]),
        "B1342": ("ECU Damaged/Replaced", "warning", ["BCM needs programming"]),
        "B1600": ("PATS Received Incorrect Key Code", "warning", ["Incorrect key", "Immobilizer"]),

        # ===== NETWORK CODES (U-CODES) =====
        "U0001": ("High Speed CAN Communication Bus", "critical", ["CAN bus failure"]),
        "U0100": ("Lost Communication With ECM/PCM A", "critical", ["ECM communication lost"]),
        "U0101": ("Lost Communication With TCM", "critical", ["TCM communication lost"]),
        "U0121": ("Lost Communication With ABS Module", "critical", ["ABS communication lost"]),
        "U0140": ("Lost Communication With BCM", "warning", ["BCM communication lost"]),
        "U0155": ("Lost Communication With Instrument Panel Cluster", "warning", ["IPC communication lost"]),
        "U0401": ("Invalid Data Received From ECM/PCM", "warning", ["Invalid ECM data"]),
        "U1000": ("Class 2 Communication Malfunction", "warning", ["Communication bus error"]),
        "U1041": ("Loss of Electronic Brake Control Module Communication", "critical", ["EBCM lost"]),
        "U1300": ("Low Fuel Level", "info", ["Low fuel indication"]),
    }

    # Column name mappings (various CSV formats)
    COLUMN_MAPPINGS: Dict[str, List[str]] = {
        "engine_rpm": ["engine_rpm", "rpm", "engine rpm", "eng_rpm", "ENGINE_RPM", "RPM"],
        "coolant_temp": ["coolant_temp", "coolant_temperature", "ect", "engine_coolant_temp", "COOLANT_TEMP"],
        "vehicle_speed": ["vehicle_speed", "speed", "vss", "VEHICLE_SPEED", "SPEED"],
        "throttle_position": ["throttle_position", "throttle", "tps", "THROTTLE_POSITION", "TPS"],
        "engine_load": ["engine_load", "load", "calculated_load", "ENGINE_LOAD", "LOAD"],
        "fuel_level": ["fuel_level", "fuel", "fuel_tank_level", "FUEL_LEVEL"],
        "intake_air_temp": ["intake_air_temp", "iat", "intake_temp", "INTAKE_AIR_TEMP", "IAT"],
        "maf_rate": ["maf_rate", "maf", "mass_air_flow", "MAF_RATE", "MAF"],
        "fuel_pressure": ["fuel_pressure", "fp", "FUEL_PRESSURE"],
        "battery_voltage": ["battery_voltage", "battery", "voltage", "BATTERY_VOLTAGE"],
        "fault_codes": ["fault_codes", "dtc", "trouble_codes", "FAULT_CODES", "DTC", "codes"],
        "timestamp": ["timestamp", "time", "datetime", "TIMESTAMP", "TIME"],
    }

    # Unit mappings
    METRIC_UNITS: Dict[str, str] = {
        "engine_rpm": "RPM",
        "coolant_temp": "°C",
        "vehicle_speed": "km/h",
        "throttle_position": "%",
        "engine_load": "%",
        "fuel_level": "%",
        "intake_air_temp": "°C",
        "maf_rate": "g/s",
        "fuel_pressure": "kPa",
        "battery_voltage": "V",
    }

    METRIC_DESCRIPTIONS: Dict[str, str] = {
        "engine_rpm": "Engine revolutions per minute",
        "coolant_temp": "Engine coolant temperature",
        "vehicle_speed": "Current vehicle speed",
        "throttle_position": "Throttle pedal position percentage",
        "engine_load": "Calculated engine load percentage",
        "fuel_level": "Fuel tank level percentage",
        "intake_air_temp": "Intake manifold air temperature",
        "maf_rate": "Mass air flow rate",
        "fuel_pressure": "Fuel rail pressure",
        "battery_voltage": "Battery/charging system voltage",
    }

    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate if a file is a valid OBD-II log (BR2.1, BR2.2, BR2.3).

        Args:
            file_path: Path to the file to validate

        Returns:
            Tuple of (is_valid, message)
        """
        path = Path(file_path)

        # Check file exists
        if not path.exists():
            return False, "File does not exist"

        # Check file extension (BR2.2)
        if path.suffix.lower() != ".csv":
            return False, "File must be a .csv file. Please upload a valid OBD-II log file."

        # Try to parse the file
        try:
            df = pd.read_csv(file_path)

            if df.empty:
                return False, "File is empty. Please upload a valid OBD-II log file."

            # Check for valid OBD-II columns (BR2.3)
            valid_columns = self._find_valid_columns(df)
            if not valid_columns:
                return False, "No valid OBD-II data found in file. Please ensure your CSV contains OBD-II metrics."

            return True, f"Valid OBD-II log file with {len(valid_columns)} metrics detected."

        except pd.errors.EmptyDataError:
            return False, "File is empty or corrupted."
        except pd.errors.ParserError:
            return False, "File is not a valid CSV format."
        except Exception as e:
            logger.error(f"Error validating file: {e}")
            return False, f"Error reading file: {str(e)}"

    def parse_csv(self, file_path: str) -> Dict[str, Any]:
        """
        Parse an OBD-II CSV log file.

        Args:
            file_path: Path to the CSV file

        Returns:
            Dictionary containing parsed metrics, fault codes, and statistics

        Raises:
            OBDParseError: If parsing fails
        """
        # Validate first
        is_valid, message = self.validate_file(file_path)
        if not is_valid:
            raise OBDParseError(message)

        try:
            df = pd.read_csv(file_path)
            logger.info(f"Parsing OBD-II log: {file_path} ({len(df)} rows)")

            # Extract metrics
            metrics = self._extract_metrics(df)

            # Extract fault codes
            fault_codes = self._extract_fault_codes(df)

            # Calculate statistics
            stats = self._calculate_statistics(df, metrics)

            result = {
                "file_path": file_path,
                "row_count": len(df),
                "metrics": [m.__dict__ for m in metrics],
                "fault_codes": [f.__dict__ for f in fault_codes],
                "statistics": stats,
                "has_issues": any(m.status != "normal" for m in metrics) or len(fault_codes) > 0,
                "critical_count": sum(1 for m in metrics if m.status == "critical") + sum(1 for f in fault_codes if f.severity == "critical"),
                "warning_count": sum(1 for m in metrics if m.status == "warning") + sum(1 for f in fault_codes if f.severity == "warning"),
            }

            logger.info(f"Parsed {len(metrics)} metrics and {len(fault_codes)} fault codes")
            return result

        except Exception as e:
            logger.error(f"Error parsing OBD-II file: {e}")
            raise OBDParseError(f"Failed to parse OBD-II log: {str(e)}")

    def _find_valid_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """Find valid OBD-II columns in the dataframe."""
        valid_columns = {}
        df_columns_lower = {col.lower(): col for col in df.columns}

        for metric_name, possible_names in self.COLUMN_MAPPINGS.items():
            for name in possible_names:
                if name.lower() in df_columns_lower:
                    valid_columns[metric_name] = df_columns_lower[name.lower()]
                    break

        return valid_columns

    def _extract_metrics(self, df: pd.DataFrame) -> List[OBDMetric]:
        """Extract and analyze metrics from the dataframe."""
        metrics = []
        column_map = self._find_valid_columns(df)

        for metric_name, column_name in column_map.items():
            if metric_name in ["fault_codes", "timestamp"]:
                continue

            try:
                values = pd.to_numeric(df[column_name], errors="coerce").dropna()
                if values.empty:
                    continue

                # Calculate average value
                avg_value = values.mean()
                latest_value = values.iloc[-1] if len(values) > 0 else avg_value

                # Classify status
                status = self._classify_metric_status(metric_name, latest_value)

                # Get normal range string
                ranges = self.METRIC_RANGES.get(metric_name, {})
                normal_range = f"{ranges.get('min', 'N/A')} - {ranges.get('max', 'N/A')}" if ranges else "N/A"

                metric = OBDMetric(
                    name=metric_name,
                    value=float(round(latest_value, 2)),
                    unit=self.METRIC_UNITS.get(metric_name, ""),
                    status=status,
                    description=self.METRIC_DESCRIPTIONS.get(metric_name, ""),
                    normal_range=normal_range
                )
                metrics.append(metric)

            except Exception as e:
                logger.warning(f"Error extracting metric {metric_name}: {e}")

        return metrics

    def _extract_fault_codes(self, df: pd.DataFrame) -> List[FaultCode]:
        """Extract fault codes from the dataframe."""
        fault_codes = []
        column_map = self._find_valid_columns(df)

        if "fault_codes" not in column_map:
            return fault_codes

        dtc_column = column_map["fault_codes"]

        # Collect all unique fault codes
        all_codes = set()
        for value in df[dtc_column].dropna():
            # Parse fault codes (may be comma-separated or space-separated)
            codes = re.findall(r"[PCBU][0-9]{4}", str(value).upper())
            all_codes.update(codes)

        # Create FaultCode objects
        for code in sorted(all_codes):
            fault_code = self._create_fault_code(code)
            if fault_code:
                fault_codes.append(fault_code)

        return fault_codes

    def _create_fault_code(self, code: str) -> Optional[FaultCode]:
        """Create a FaultCode object from a code string."""
        code = code.upper()

        # Determine category
        prefix = code[0]
        categories = {
            "P": "powertrain",
            "C": "chassis",
            "B": "body",
            "U": "network"
        }
        category = categories.get(prefix, "unknown")

        # Check if generic (second character is 0) or manufacturer-specific
        is_generic = code[1] == "0" or code[1] == "2" or code[1] == "3"

        # Look up in database
        if code in self.FAULT_CODE_DATABASE:
            description, severity, causes = self.FAULT_CODE_DATABASE[code]
            return FaultCode(
                code=code,
                description=description,
                severity=severity,
                category=category,
                is_generic=is_generic,
                possible_causes=causes,
                recommended_action=self._get_recommended_action(severity)
            )
        else:
            # Unknown code
            return FaultCode(
                code=code,
                description=f"{'Generic' if is_generic else 'Manufacturer-specific'} {category} code",
                severity="warning" if is_generic else "info",
                category=category,
                is_generic=is_generic,
                possible_causes=["Refer to vehicle service manual"],
                recommended_action="Have the code diagnosed by a professional mechanic"
            )

    def _classify_metric_status(self, metric_name: str, value: float) -> str:
        """Classify a metric value as normal, warning, or critical."""
        ranges = self.METRIC_RANGES.get(metric_name)
        if not ranges:
            return "normal"

        # Critical range check
        if value < ranges.get("critical_low", float("-inf")) or value > ranges.get("critical_high", float("inf")):
            return "critical"

        # Warning range check
        if value < ranges.get("warning_low", float("-inf")) or value > ranges.get("warning_high", float("inf")):
            return "warning"

        # Normal range check
        if value < ranges.get("min", float("-inf")) or value > ranges.get("max", float("inf")):
            return "warning"

        return "normal"

    def _get_recommended_action(self, severity: str) -> str:
        """Get recommended action based on severity."""
        actions = {
            "critical": "Stop driving immediately and have the vehicle inspected by a professional mechanic.",
            "warning": "Schedule a service appointment soon to diagnose and address this issue.",
            "info": "Monitor the situation. This may not require immediate attention."
        }
        return actions.get(severity, "Consult a professional mechanic for diagnosis.")

    def _calculate_statistics(self, df: pd.DataFrame, metrics: List[OBDMetric]) -> Dict[str, Any]:
        """Calculate summary statistics for the OBD data."""
        stats = {
            "total_rows": len(df),
            "metrics_count": len(metrics),
            "normal_count": sum(1 for m in metrics if m.status == "normal"),
            "warning_count": sum(1 for m in metrics if m.status == "warning"),
            "critical_count": sum(1 for m in metrics if m.status == "critical"),
        }

        # Add per-metric statistics
        column_map = self._find_valid_columns(df)
        metric_stats = {}

        for metric in metrics:
            if metric.name in column_map:
                col = column_map[metric.name]
                values = pd.to_numeric(df[col], errors="coerce").dropna()
                if not values.empty:
                    metric_stats[metric.name] = {
                        "min": float(round(values.min(), 2)),
                        "max": float(round(values.max(), 2)),
                        "mean": float(round(values.mean(), 2)),
                        "std": float(round(values.std(), 2)) if len(values) > 1 else 0.0
                    }

        stats["metric_statistics"] = metric_stats
        return stats

    def get_metric_explanation(self, metric_name: str) -> str:
        """Get a human-readable explanation of a metric."""
        return self.METRIC_DESCRIPTIONS.get(metric_name, f"OBD-II metric: {metric_name}")

    def get_fault_code_info(self, code: str) -> Optional[FaultCode]:
        """Get information about a specific fault code."""
        return self._create_fault_code(code)
