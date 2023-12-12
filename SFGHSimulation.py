import simpy
import random
import numpy as np

# Constants and Parameters
SIMULATION_TIME = 1000
BED_COUNT = 40
NURSE_COUNT = 15
DOCTOR_COUNT = 7
ARRIVAL_RATES = {
    (23, 7): (6, 14),
    (7, 11): (9, 10),
    (11, 17): (15, 10),
    (17, 23): (18, 12)
}

# Define the performance metrics
total_patient_wait_time = 0
ambulance_diversion_count = 0
bed_turnover_times = []

# Define the simulation environment
env = simpy.Environment()

# Resources
beds = simpy.Resource(env, capacity=BED_COUNT)
nurses = simpy.Resource(env, capacity=NURSE_COUNT)
doctors = simpy.Resource(env, capacity=DOCTOR_COUNT)
ambulances = simpy.Resource(env, capacity=10)

# Patient class
class Patient:
    def __init__(self, acuity_level, arrival_mode, arrival_time):
        self.acuity_level = acuity_level
        self.arrival_mode = arrival_mode
        self.arrival_time = arrival_time
        self.bed_time = 0  # Time when the patient gets a bed
        self.discharge_time = 0  # Time when the patient gets discharged
        self.primary_doctor = None
        self.chief_complaint = None

def TRIA(a, b, c):
    return np.random.triangular(a, b, c)

def UNIF(a, b):
    return np.random.uniform(a, b)

# Function to get the current arrival rate
def get_current_arrival_rate(current_time):
    hour = current_time // 60 % 24  # Convert minutes to hour of the day
    for (start, end), rates in ARRIVAL_RATES.items():
        if start <= hour < end or (start > end and (hour < end or hour >= start)):
            return rates
    return (0, 0)  # Default rates if not within any specified intervals

# Patient arrival process
def patient_arrival(env):
    patient_id = 0
    while env.now < SIMULATION_TIME:
        patient_id += 1
        
        # Determine arrival mode based on the time of day
        walk_in_rate, ambulance_rate = get_current_arrival_rate(env.now)
        arrival_mode = 'ambulance' if random.random() < ambulance_rate / (walk_in_rate + ambulance_rate) else 'walk-in'
        
        # Determine acuity level based on arrival mode
        if arrival_mode == 'ambulance':
            acuity_level = random.choices([1, 2, 3, 4, 5], weights=[0.2, 0.35, 0.3, 0.15, 0], k=1)[0]
        else:  # walk-in
            acuity_level = random.choices([1, 2, 3, 4, 5], weights=[0, 0.1, 0.3, 0.4, 0.2], k=1)[0]
        
        arrival_time = env.now
        patient = Patient(acuity_level, arrival_mode, arrival_time)

        if arrival_mode == 'ambulance':
            env.process(ambulance_process(env, patient))
        else:
            env.process(patient_triage(env, patient))

        yield env.timeout(random.expovariate(1.0 / (walk_in_rate + ambulance_rate)))  # Average inter-arrival time

def ambulance_process(env, patient):
    with ambulances.request() as request:
        yield request

        # Simulate travel to the patient
        travel_to_patient_time = TRIA(5, 10, 20)
        yield env.timeout(travel_to_patient_time)

        # Simulate processing the patient
        process_time = UNIF(4, 10)
        yield env.timeout(process_time)

        # Check bed utilization and patient acuity for diversion
        bed_utilization = beds.count / beds.capacity
        if bed_utilization < 0.8 or patient.acuity_level in [1, 2]:
            # Simulate travel back to the hospital
            travel_back_time = 1.2 * travel_to_patient_time
            yield env.timeout(travel_back_time)
            env.process(patient_triage(env, patient))
        else:
            # Ambulance is diverted
            global ambulance_diversion_count
            ambulance_diversion_count += 1
            diversion_travel_time = TRIA(10, 15, 25) + travel_to_patient_time
            yield env.timeout(diversion_travel_time)
            # End process for the diverted patient


# Triage process
def patient_triage(env, patient):
    # Assigning a primary doctor (random selection)
    patient.primary_doctor = random.randint(1, DOCTOR_COUNT)
    # Determine chief complaint based on acuity level
    complaints = CHIEF_COMPLAINTS.get(patient.acuity_level, [])
    if complaints:
        patient.chief_complaint, _ = random.choices(complaints, weights=[prob for _, prob in complaints], k=1)[0]
        
    if patient.acuity_level != 1:  # Skip triage for acuity level 1
        with nurses.request() as request:
            yield request
            if patient.acuity_level in [2, 3]:
                triage_time = UNIF(0.75, 2.25)
            else:  # Acuity levels 4 and 5
                triage_time = UNIF(7.5, 11.25)
            yield env.timeout(triage_time)
    env.process(patient_treatment(env, patient))

# Chief complaints and probabilities based on acuity level
CHIEF_COMPLAINTS = {
    1: [('Trauma', 0.5), ('Cardiac Arrest', 0.5)],  # 50% chance for each, sum to 100%
    2: [('Stroke', 0.5), ('Severe Asthma', 0.5)],  # 50% chance for each, sum to 100%
    3: [('Broken Limb', 1.0)],  # 100% chance
    4: [('Laceration', 0.5), ('Mild Asthma', 0.5)],  # 50% chance for each, sum to 100%
    5: [('Common Cold', 1.0)]  # 100% chance
}

# Treatment process
def patient_treatment(env, patient):
    global total_patient_wait_time, ambulance_diversion_count, bed_turnover_times

    # Check bed availability for ambulance patients
    if patient.arrival_mode == 'ambulance':
        if len(beds.queue) / beds.capacity >= 0.8:  # 80% bed utilization
            ambulance_diversion_count += 1
            # Ambulance diversion logic here
            return

    with beds.request() as request:
        yield request
        patient.bed_time = env.now
        # Simulate treatment time
        yield env.timeout(random.uniform(5, 20))  # Placeholder for treatment time
        patient.discharge_time = env.now
        bed_turnover_times.append(patient.discharge_time - patient.bed_time)
        total_patient_wait_time += patient.bed_time - patient.arrival_time
        env.process(patient_discharge(env, patient))

# Discharge process
def patient_discharge(env, patient):
    # Simulate cleaning time
    cleaning_time = random.uniform(3, 6)
    yield env.timeout(cleaning_time)

# Run the simulation
env.process(patient_arrival(env))
env.run(until=SIMULATION_TIME)

# Calculate bed turnover rate
bed_turnover_rate = sum(bed_turnover_times) / (BED_COUNT * SIMULATION_TIME)

# Output performance metrics
print("\nPerformance Measures:")
print(f"Total Patient Wait Time: {total_patient_wait_time}")
print(f"Ambulance Diversion Count: {ambulance_diversion_count}")
print(f"Bed Turnover Rate: {bed_turnover_rate} per bed-hour")
