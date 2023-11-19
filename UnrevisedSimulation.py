import simpy
import random

# Constants
NUM_BEDS = 20
NUM_STAFF = 10
SIMULATION_TIME = 1000  # Adjust as needed

# Simulation environment
env = simpy.Environment()

# Resources
beds = simpy.Resource(env, capacity=NUM_BEDS)
staff = simpy.Resource(env, capacity=NUM_STAFF)

# Queues
triage_queue = simpy.Store(env)
waiting_for_bed_queue = simpy.Store(env)
waiting_for_treatment_queue = simpy.Store(env)
discharge_delays_queue = simpy.Store(env)

# Assumptions
# - Patients arrive following a Poisson process
# - Triage and treatment times are exponentially distributed
# - Bed turnover times are exponentially distributed
# - Staff availability is constant

def patient_arrival(env):
    patient_id = 1
    while True:
        yield env.timeout(random.expovariate(1.0))  # Poisson process
        env.process(triage_patient(env, f'Patient-{patient_id}'))
        patient_id += 1

def triage_patient(env, patient):
    acuity_level = random.randint(1, 5)
    triage_duration = random.expovariate(0.5)
    
    yield env.timeout(triage_duration)
    
    # Assign patient to a treatment queue based on acuity level
    if acuity_level == 1:
        triage_queue.put(patient)
    elif acuity_level == 2:
        waiting_for_bed_queue.put(patient)
    elif acuity_level == 3:
        waiting_for_treatment_queue.put(patient)
    elif acuity_level == 4:
        waiting_for_treatment_queue.put(patient)
    elif acuity_level == 5:
        discharge_delays_queue.put(patient)

def treatment_process(env, patient):
    treatment_duration = random.expovariate(0.3)
    
    with staff.request() as req:
        yield req
        yield env.timeout(treatment_duration)

def bed_admission_process(env, patient):
    bed_admission_duration = random.expovariate(0.2)
    
    with beds.request() as req:
        yield req
        yield env.timeout(bed_admission_duration)

def discharge_process(env, patient):
    discharge_duration = random.expovariate(0.1)
    
    with beds.request() as req:
        yield req
        yield env.timeout(discharge_duration)

# Process for handling triage queue
def process_triage_queue(env):
    while True:
        patient = yield triage_queue.get()
        env.process(treatment_process(env, patient))

# Process for handling waiting for bed queue
def process_waiting_for_bed_queue(env):
    while True:
        patient = yield waiting_for_bed_queue.get()
        env.process(bed_admission_process(env, patient))

# Process for handling waiting for treatment queue
def process_waiting_for_treatment_queue(env):
    while True:
        patient = yield waiting_for_treatment_queue.get()
        env.process(treatment_process(env, patient))

# Process for handling discharge delays queue
def process_discharge_delays_queue(env):
    while True:
        patient = yield discharge_delays_queue.get()
        env.process(discharge_process(env, patient))

# Start simulation
env.process(patient_arrival(env))
env.process(process_triage_queue(env))
env.process(process_waiting_for_bed_queue(env))
env.process(process_waiting_for_treatment_queue(env))
env.process(process_discharge_delays_queue(env))

env.run(until=SIMULATION_TIME)
