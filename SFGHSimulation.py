import simpy
import random
import numpy as np

NUM_SIMULATIONS = 100
results = []

# Constants and Parameters
SIMULATION_TIME = 10000
BED_COUNT = 40
NURSE_COUNT = 15
DOCTOR_COUNT = 7
ARRIVAL_RATES = {
    (23, 7): (6, 14),
    (7, 11): (9, 10),
    (11, 17): (15, 10),
    (17, 23): (18, 12)
    }
# Additional
X_RAY_CAPACITY = 1  # Fixed capacity for X-ray
CT_SCAN_CAPACITY = 1  # Fixed capacity for CT Scan
OXYGEN_THERAPY_CAPACITY = 10  # Fixed capacity for Oxygen Therapy


def run_simulation():

    # Initialize resource usage tracking
    ambulance_diversion_count = 0
    bed_turnover_times = []
    bed_usage_time = 0
    doctor_usage_time = 0
    nurse_usage_time = 0
    ambulance_usage_time = 0
    all_patients = []
    time_in_system = []

    # Define the simulation environment
    env = simpy.Environment()

    # Resources
    beds = simpy.Resource(env, capacity=BED_COUNT)
    nurses = simpy.Resource(env, capacity=NURSE_COUNT)
    doctors = simpy.Resource(env, capacity=DOCTOR_COUNT)
    ambulances = simpy.Resource(env, capacity=10)
    # Additional
    x_ray_units = simpy.Resource(env, capacity=X_RAY_CAPACITY)
    ct_scan_units = simpy.Resource(env, capacity=CT_SCAN_CAPACITY)
    oxygen_therapy_units = simpy.Resource(env, capacity=OXYGEN_THERAPY_CAPACITY)


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
            self.wait_time_triage = 0
            self.wait_time_treatment = 0

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
            all_patients.append(patient)

            if arrival_mode == 'ambulance':
                env.process(ambulance_process(env, patient))
            else:
                env.process(patient_triage(env, patient))

            yield env.timeout(random.expovariate(1.0 / (walk_in_rate + ambulance_rate)) / 4.5)  # inter-arrival time

    def ambulance_process(env, patient):
        global ambulance_usage_time
        start_time = env.now
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
        ambulance_usage_time += env.now - start_time

    # Chief complaints and probabilities based on acuity level
    CHIEF_COMPLAINTS = {
        1: [('Trauma', 0.5), ('Cardiac Arrest', 0.5)],  # 50% chance for each
        2: [('Stroke', 0.5), ('Severe Asthma', 0.5)],  # 50% chance for each
        3: [('Broken Limb', 1.0)],  # 100% chance
        4: [('Laceration', 0.5), ('Mild Asthma', 0.5)],  # 50% chance for each
        5: [('Common Cold', 1.0)]  # 100% chance
    }

    # Triage process
    def patient_triage(env, patient):
        global nurse_usage_time
        start_time = env.now
        with nurses.request() as request:
            yield request

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
        nurse_usage_time += env.now - start_time
        patient.wait_time_triage = env.now - patient.arrival_time

    # Treatment Process
    def perform_procedure(env, procedure, patient):
        global doctor_usage_time
        global nurse_usage_time

        procedure_times = {
            'X-ray': UNIF(3, 5),
            'Surgery Type A': TRIA(10, 25, 50),
            'ECG': UNIF(7, 10),
            'Surgery Type B': TRIA(30, 45, 90),
            'CT Scan': UNIF(10, 25),
            'Medication': UNIF(2, 5),
            'Oxygen Therapy': UNIF(30, 60),
            'Nebulizer': UNIF(2, 3),
            'Cast/Splint': UNIF(5, 15),
            'Stitches': TRIA(10, 15, 25),
            'Tetanus Shot': UNIF(2, 5)
        }

        additional_staff_needed = {
            'Surgery Type A': {'nurse_prob': 0.1, 'death_rate': 0.025},
            'Surgery Type B': {'nurse_prob': 0.3, 'additional_doctor_prob': 0.25, 'death_rate': 0.05}
        }

        if procedure in additional_staff_needed:
            details = additional_staff_needed[procedure]
            # Check for additional nurse and/or doctor
            if 'nurse_prob' in details and random.random() < details['nurse_prob']:
                start_time = env.now
                with nurses.request() as nurse_req:
                    yield nurse_req
                    # Perform the procedure
                    yield env.timeout(procedure_times[procedure])
                nurse_usage_time += env.now - start_time

            if 'additional_doctor_prob' in details and random.random() < details['additional_doctor_prob']:
                start_time = env.now
                with doctors.request() as additional_doctor_req:
                    yield additional_doctor_req
                    # Perform the procedure
                    yield env.timeout(procedure_times[procedure])
                doctor_usage_time += env.now - start_time

        else:
            # For procedures that explicitly require doctors or nurses
            if procedure in ['Surgery Type A', 'Surgery Type B', 'Stitches']:
                start_time = env.now
                with doctors.request() as doctor_req:
                    yield doctor_req
                    yield env.timeout(procedure_times[procedure])
                doctor_usage_time += env.now - start_time
            elif procedure in ['ECG', 'Medication', 'Nebulizer', 'Tetanus Shot']:
                start_time = env.now
                with nurses.request() as nurse_req:
                    yield nurse_req
                    yield env.timeout(procedure_times[procedure])
                nurse_usage_time += env.now - start_time

            # Resource-specific procedures
            elif procedure == 'X-ray':
                with x_ray_units.request() as req:
                    yield req
                    yield env.timeout(procedure_times[procedure])

            elif procedure == 'CT Scan':
                with ct_scan_units.request() as req:
                    yield req
                    yield env.timeout(procedure_times[procedure])

            elif procedure == 'Oxygen Therapy':
                with oxygen_therapy_units.request() as req:
                    yield req
                    yield env.timeout(procedure_times[procedure])

            else:
                # For procedures that do not require specific resources
                yield env.timeout(procedure_times.get(procedure, 5))

            # Check for death rate in surgeries
            if procedure in ['Surgery Type A', 'Surgery Type B']:
                if random.random() < details.get('death_rate', 0):
                    yield env.timeout(UNIF(30, 60))  # Time for reports and notifications
                    return  # End procedure due to patient death

    def patient_treatment(env, patient):
        with beds.request() as request:
            start_time = env.now
            yield request
            # Simulate evaluation time by the primary doctor
            eval_time_dict = {
                'Trauma': UNIF(5, 12),
                'Cardiac Arrest': UNIF(2, 5),
                'Stroke': UNIF(5, 15),
                'Severe Asthma': 2,  # Fixed time
                'Broken Limb': UNIF(5, 10),
                'Laceration': 2,  # Fixed time
                'Mild Asthma': 2,  # Fixed time
                'Common Cold': UNIF(5, 10)
            }
            eval_time = eval_time_dict.get(patient.chief_complaint, 5)  # Default time if not listed
            yield env.timeout(eval_time)

            # Treatment details based on chief complaint
            treatment_details = {
                'Trauma': {'count': 4, 'procedures': [('X-ray', 0.9), ('Surgery Type A', 0.8)], 'rest': UNIF(2, 10)},
                'Cardiac Arrest': {'count': 3, 'procedures': [('ECG', 0.95), ('Surgery Type B', 0.6)], 'rest': UNIF(2, 15)},
                'Stroke': {'count': 3, 'procedures': [('CT Scan', 0.9), ('Medication', 0.8)], 'rest': UNIF(5, 15) if random.random() < 0.25 else UNIF(45, 50)},
                'Severe Asthma': {'count': 2, 'procedures': [('Oxygen Therapy', 0.9), ('Nebulizer', 0.7)], 'rest': UNIF(15, 25)},
                'Broken Limb': {'count': 2, 'procedures': [('X-ray', 0.8), ('Cast/Splint', 0.7)], 'rest': UNIF(5, 10)},
                'Laceration': {'count': 2, 'procedures': [('Stitches', 0.75), ('Tetanus Shot', 0.3)], 'rest': UNIF(10, 15)},
                'Mild Asthma': {'count': 1, 'procedures': [('Nebulizer', 0.6), ('Oxygen Therapy', 0.3)], 'rest': UNIF(5, 10)},
                'Common Cold': {'count': 1, 'procedures': [('Medication', 0.9)], 'rest': 5}  # Fixed rest time
            }

            treatment_info = treatment_details.get(patient.chief_complaint, {'count': 1, 'procedures': [('Medication', 1.0)], 'rest': 5})
            # Perform treatments
            for _ in range(treatment_info['count']):
                for procedure, probability in treatment_info['procedures']:
                    # Perform the procedure based on probability
                    if random.random() < probability:
                        yield env.process(perform_procedure(env, procedure, patient))
                # Simulate rest time
                rest_time = treatment_info['rest']
                yield env.timeout(rest_time)
            # Proceed to discharge process
            env.process(patient_discharge(env, patient))
        patient.bed_time = env.now
        patient.wait_time_treatment = patient.bed_time - start_time



    # Discharge process
    def patient_discharge(env, patient):
        global bed_turnover_times
        # Simulate cleaning time
        cleaning_time = random.uniform(3, 6)
        yield env.timeout(cleaning_time)
        
        # Calculate the time patient spent in the bed and add it to bed_turnover_times
        patient.discharge_time = env.now
        time_in_system.append(patient.discharge_time - patient.arrival_time)
        bed_occupied_time = patient.discharge_time - patient.bed_time
        bed_turnover_times.append(bed_occupied_time)


    # Queue Length Tracking
    triage_queue_lengths = []
    treatment_queue_lengths = []

    def track_queue_lengths(env):
        while True:
            triage_queue_lengths.append(len(nurses.queue))  # For triage queue
            treatment_queue_lengths.append(len(beds.queue))  # For bed queue
            yield env.timeout(1)  # Check every minute

    env.process(track_queue_lengths(env))

    # Run the simulation
    env.process(patient_arrival(env))
    env.run(until=SIMULATION_TIME)

    # Calculate bed turnover rate
    bed_usage_time = sum(bed_turnover_times)

    # Calculate averages
    avg_triage_queue_length = sum(triage_queue_lengths) / len(triage_queue_lengths)
    avg_treatment_queue_length = sum(treatment_queue_lengths) / len(treatment_queue_lengths)
    avg_triage_wait_time = sum([p.wait_time_triage for p in all_patients]) / len(all_patients)
    avg_treatment_wait_time = sum([p.wait_time_treatment for p in all_patients]) / len(all_patients)
    avg_patient_wait_time = sum([p.wait_time_triage + p.wait_time_treatment for p in all_patients]) / len(all_patients)
    bed_utilization_rate = bed_usage_time / (SIMULATION_TIME * BED_COUNT)
    doctor_utlization_rate = doctor_usage_time / (SIMULATION_TIME * DOCTOR_COUNT)
    nurse_utlization_rate = nurse_usage_time / (SIMULATION_TIME * NURSE_COUNT)
    ambulance_utilization_rate = ambulance_usage_time / (SIMULATION_TIME * 10)
    avg_time_in_system = sum(time_in_system)/len(all_patients)

    # # Output performance metrics for one run
    # print("\nPerformance Measures:")
    # print(f"Ambulance Diversion Count: {ambulance_diversion_count}")
    # print(f"Average Triage Queue Length: {avg_triage_queue_length}")
    # print(f"Average Treatment Queue Length: {avg_treatment_queue_length}")
    # print(f"Average Triage Patient Wait Time: {avg_triage_wait_time}")
    # print(f"Average Treatment Patient Wait Time: {avg_treatment_wait_time}")
    # print(f"Average Patient Wait Time: {avg_patient_wait_time}")
    # print(f"Bed Utilization Rate: {bed_utilization_rate}")
    # print(f"Doctor Utilization Rate: {doctor_utlization_rate}")
    # print(f"Nurse Utilization Rate: {nurse_utlization_rate}")
    # print(f"Ambulance Utilization Rate: {ambulance_utilization_rate}")  # Assuming 10 ambulances
    # print(f"Average Time in System: {avg_time_in_system}")

    return {
        "Ambulance Diversion Count": ambulance_diversion_count,
        "Average Triage Queue Length": avg_triage_queue_length,
        "Average Treatment Queue Length": avg_treatment_queue_length,
        "Average Triage Patient Wait Time": avg_triage_wait_time,
        "Average Treatment Patient Wait Time": avg_treatment_wait_time,
        "Average Patient Wait Time": avg_patient_wait_time,
        "Bed Utilization Rate": bed_utilization_rate,
        "Doctor Utilization Rate": doctor_utlization_rate,
        "Nurse Utilization Rate": nurse_utlization_rate,
        "Ambulance Utilization Rate": ambulance_utilization_rate,
        "Average Time in System": avg_time_in_system
    }

# Run the simulation multiple times
for _ in range(NUM_SIMULATIONS):
    # Reset variables for each run
    results.append(run_simulation())

# Calculate means of the average metrics
mean_metrics = {}
for metric in results[0].keys():
    mean_metrics[metric] = sum(result[metric] for result in results) / NUM_SIMULATIONS

# Print the mean metrics
for metric, value in mean_metrics.items():
    print(f"Mean {metric}: {value}")