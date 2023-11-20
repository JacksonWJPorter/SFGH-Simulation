import simpy
import random

# Constants
WAITING_FOR_TREATMENT_DURATION = 5
WAITING_FOR_BED_ZONE_DURATION = 10
DISCHARGE_DELAYS_DURATION = 8
TRANSFER_DURATION = 15
SIMULATION_TIME = 100
TRIAGE_DURATION = 2  # Assumption: Placeholder value for triage duration
DIAGNOSIS_TREATMENT_DURATION = 10  # Assumption: Placeholder value for diagnosis/treatment duration

# Simulation environment
env = simpy.Environment()

# Define resources and queues
available_beds = simpy.Resource(env, capacity=10)
available_staff_for_triage = simpy.Resource(env, capacity=5)
waiting_for_triage_queue = simpy.Store(env)
waiting_for_bed_zone_queue = simpy.Store(env)
waiting_for_treatment_queue = simpy.Store(env)
discharge_delays_queue = simpy.Store(env)

# Patient class to track individual patient data
class Patient:
    def __init__(self, acuity_level, arrival_mode):
        self.acuity_level = acuity_level
        self.arrival_mode = arrival_mode
        self.status = "Waiting"
        self.destination = None
        self.is_diverted = False
        self.wait_time = 0
        self.assessment_process_time = 0
        self.treatment_process_time = 0
        self.discharge_process_time = 0

patients = []

# Schedule events
def schedule_event(event_type, entity, time):
    yield env.timeout(time)
    scheduled_events.put({'type': event_type, 'entity': entity})

# Arrival event
def incoming_patients():
    patient_list = [Patient(random.randint(1, 5), random.choice(["ambulance", "walk-in"])) for _ in range(5)]
    return patient_list

# Triage PLaceholder
def triage_patient(patient):
    patient.acuity_level = random.randint(1, 5)

# Diagnosis/treatment
def process_diagnosis_treatment(patient):
    patient.status = 3  # 3 for diagnosis/treatment completed
    patient.assessment_process_time = 0
    patient.treatment_process_time = 0

def admission_duration():
    return random.uniform(8, 12)

def discharge_process_ready():
    return random.choice([True, False])

def divert_ambulances_to_alternative_facility():
    pass

def resume_ambulance_arrivals():
    pass

def assign_patient_to_diagnosis_treatment(patient):
    patient.status = 2  # 2 for in treatment
    patient.assessment_process_time = random.uniform(5, 10)  # Placeholder value for assessment process time
    patient.treatment_process_time = random.uniform(15, 20)  # Placeholder value for treatment process time


def diagnosis_treatment_complete(patient):
    return random.choice([True, False])

def assign_patient_to_waiting_room(patient):
    patient.status = 1  # 1 for waiting

def move_patient_to_waiting_room(patient):
    waiting_for_treatment_queue.put(patient)

def move_patient_to_discharge(patient):
    patient.destination = 1  # 1 for discharged home

def admit_patient_to_unit(patient):
    patient.destination = 2  # 2 for transferred to ICU

def transfer_patient_to_next_care_level(patient):
    pass

def change_ambulance_diversion_status(patient):
    pass

def available_medical_staff():
    return available_staff_for_triage.count

def patients_in_diagnosis_treatment():
    return [patient for patient in waiting_for_treatment_queue.items]

def increment_queue(queue, patient):
    queue.put(patient)

def complete_discharge(patient):
    pass

def dequeue_patient(queue):
    return queue.get()

# Schedule events
def schedule_event(event_type, entity, time):
    yield env.timeout(time)
    scheduled_events.put({'type': event_type, 'entity': entity})

# Process scheduled events
def process_scheduled_events(env):
    while True:
        event = yield scheduled_events.get()
        
        if event['type'] == 'Triage Completion':
            move_patient_to_waiting_room(event['entity'])
            yield env.process(schedule_event('Waiting for Treatment', event['entity'], time=WAITING_FOR_TREATMENT_DURATION))
            
        elif event['type'] == 'Diagnosis/Treatment Completion':
            if event['entity'].requires_admission():
                if available_beds.count > 0:
                    move_patient_to_waiting_room(event['entity'])
                    yield env.process(schedule_event('Waiting for Bed/Zone Admission', event['entity'], time=WAITING_FOR_BED_ZONE_DURATION))
                else:
                    increment_queue(waiting_for_bed_zone_queue, event['entity'])
            else:
                move_patient_to_discharge(event['entity'])
                yield env.process(schedule_event('Discharge Delays', event['entity'], time=DISCHARGE_DELAYS_DURATION))
            
        elif event['type'] == 'Discharge/Admission to Zone':
            if event['entity'].is_discharged():
                complete_discharge(event['entity'])
            else:
                if available_beds.count > 0:
                    admit_patient_to_unit(event['entity'])
                    yield env.process(schedule_event('Arrival at Next Care Level', event['entity'], time=TRANSFER_DURATION))
                else:
                    increment_queue(waiting_for_bed_zone_queue, event['entity'])

        elif event['type'] == 'Arrival at Next Care Level':
            transfer_patient_to_next_care_level(event['entity'])

        elif event['type'] == 'Ambulance Diversion Change':
            change_ambulance_diversion_status(event['entity'])
            if event['entity'].is_diverted():
                divert_ambulances_to_alternative_facility()
            else:
                resume_ambulance_arrivals()

        # For queue related events:
        
        elif event['type'] == 'Waiting for Triage':
            if available_staff_for_triage.count > 0:
                dequeued_patient = dequeue_patient(waiting_for_triage_queue)
                yield env.process(schedule_event('Triage Completion', dequeued_patient, time=TRIAGE_DURATION))
            # Always reschedule the event, even if no staff is available
            yield env.process(schedule_event('Waiting for Triage', event['entity'], time=TRIAGE_DURATION))


        elif event['type'] == 'Waiting for Bed/Zone Admission':
            if available_beds.count > 0:
                dequeued_patient = dequeue_patient(waiting_for_bed_zone_queue)
                yield env.process(schedule_event('Diagnosis/Treatment Completion', dequeued_patient, time=DIAGNOSIS_TREATMENT_DURATION))
            else:
                increment_queue(waiting_for_bed_zone_queue, event['entity'])

        elif event['type'] == 'Waiting for Treatment':
            if available_medical_staff() > 0:
                dequeued_patient = dequeue_patient(waiting_for_treatment_queue)
                yield env.process(schedule_event('Diagnosis/Treatment Completion', dequeued_patient, time=DIAGNOSIS_TREATMENT_DURATION))
            else:
                increment_queue(waiting_for_treatment_queue, event['entity'])

        elif event['type'] == 'Discharge Delays':
            if discharge_process_ready():
                dequeued_patient = dequeue_patient(discharge_delays_queue)
                yield env.process(schedule_event('Arrival at Next Care Level', dequeued_patient, time=TRANSFER_DURATION))
            else:
                increment_queue(discharge_delays_queue, event['entity'])

# Performance measure vars
total_wait_time = 0
diversion_count = 0
assessment_process_time = 0
treatment_process_time = 0
discharge_process_time = 0
bed_turnover_rate = 0

# Count of patients for bed turnover rate calculation vars
total_admitted_patients = 0
total_discharged_patients = 0


def run_simulation(env):
    global total_wait_time, diversion_count, assessment_process_time, treatment_process_time, discharge_process_time
    global total_admitted_patients, total_discharged_patients

    env.process(process_scheduled_events(env))
    env.run(until=SIMULATION_TIME)

# Calculate performance measures
incoming_patient_list = list(incoming_patients())  # Convert generator to list
for patient in incoming_patient_list:
    total_wait_time += patient.wait_time

    if patient.is_diverted:
        diversion_count += 1

    if patient.destination == 1:  # Discharged home
        total_discharged_patients += 1
        discharge_process_time += patient.discharge_process_time
    elif patient.destination == 2:  # Transferred to ICU
        total_admitted_patients += 1
        assessment_process_time += patient.assessment_process_time
        treatment_process_time += patient.treatment_process_time


    bed_turnover_rate = total_discharged_patients / SIMULATION_TIME 

print("\nPerformance Measures:")
print(f"Total Patient Wait Time: {total_wait_time}")
print(f"Ambulance Diversion Count: {diversion_count}")

# Check if there are admitted patients before calculating averages
if total_admitted_patients > 0:
    print(f"Average Assessment Process Time: {assessment_process_time / total_admitted_patients}")
    print(f"Average Treatment Process Time: {treatment_process_time / total_admitted_patients}")


# Check if there are discharged patients before calculating the average discharge process time
if total_discharged_patients > 0:
    print(f"Average Discharge Process Time: {discharge_process_time / total_discharged_patients}")

print(f"Bed Turnover Rate: {bed_turnover_rate}")

scheduled_events = simpy.Store(env)
run_simulation(env)
