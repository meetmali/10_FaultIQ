"""Seed content for the rooftop-unit fault library (written for FaultIQ, based on common RTU fault rules)."""

FAULTS = [
    {
        "code": "econ-stuck-closed",
        "name": "Economizer not economizing",
        "component": "Outdoor-air damper",
        "symptoms": "Outdoor air is cool enough for free cooling but the outdoor-air damper stays at minimum position "
        "while the compressor runs. Mixed air temperature stays close to return air temperature. High energy use on mild days.",
        "causes": "Damper actuator failed or stuck closed, broken linkage, economizer controller disabled, "
        "faulty outdoor-air temperature sensor or wrong changeover setpoint.",
        "checks": "Command the damper open and watch the blades move. Check actuator power and linkage. "
        "Verify the outdoor-air sensor reading and the economizer changeover setpoint.",
    },
    {
        "code": "econ-stuck-open",
        "name": "Excess outdoor air",
        "component": "Outdoor-air damper",
        "symptoms": "Outdoor-air damper is wide open while outdoor air is hotter than return air. Mixed air is warm, "
        "the cooling coil runs at high load and the space may feel humid.",
        "causes": "Damper stuck open, actuator spring return failure, economizer high-limit setting wrong, "
        "outdoor-air temperature sensor reading low.",
        "checks": "Check the economizer high-limit setting and outdoor-air sensor. Command the damper to minimum "
        "and confirm it closes. Inspect the actuator and linkage.",
    },
    {
        "code": "low-refrigerant",
        "name": "Insufficient cooling capacity",
        "component": "Refrigerant circuit",
        "symptoms": "Cooling is commanded at or near 100% but the supply air temperature stays well above setpoint. "
        "Space temperature drifts up on hot afternoons. Compressor runs continuously.",
        "causes": "Low refrigerant charge from a leak, dirty or blocked condenser coil, failed compressor stage, "
        "dirty evaporator coil or restricted metering device.",
        "checks": "Measure suction and discharge pressure, superheat and subcooling. Inspect and clean the condenser coil. "
        "Leak-check the circuit and confirm every compressor stage starts.",
    },
    {
        "code": "mat-sensor",
        "name": "Mixed-air temperature sensor fault",
        "component": "Mixed-air sensor",
        "symptoms": "Mixed air temperature reads outside the range between outdoor and return air temperature, "
        "which is physically impossible. Economizer control behaves erratically.",
        "causes": "Sensor drift or bias, poorly placed sensor with stratified air, wiring fault, wrong sensor type configured.",
        "checks": "Compare the sensor against a calibrated thermometer. Check placement (use an averaging sensor), "
        "wiring and the configured sensor type and offset.",
    },
    {
        "code": "cooling-leak",
        "name": "Cooling while not commanded",
        "component": "Cooling coil / compressor control",
        "symptoms": "Cooling command is at zero but the supply air is several degrees colder than mixed air. "
        "Overcooling and wasted energy.",
        "causes": "Leaking chilled-water valve, stuck compressor contactor, control wiring fault, override left in hand.",
        "checks": "Check the compressor contactor and any hand-off-auto overrides. On chilled-water units, check the valve seats.",
    },
    {
        "code": "fan-off-occupied",
        "name": "Supply fan off during occupancy",
        "component": "Supply fan",
        "symptoms": "No airflow during occupied hours, rooms get stuffy and warm, supply air temperature follows "
        "mixed air because nothing moves.",
        "causes": "Broken fan belt, failed motor or VFD fault, schedule error, tripped safety such as a freeze stat or smoke detector.",
        "checks": "Check the belt and motor, VFD alarms, safety circuits and the occupancy schedule.",
    },
]
