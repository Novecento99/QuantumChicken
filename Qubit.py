# Core Qiskit imports
import os
import sys

from dotenv import load_dotenv
from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

# IBM Runtime specific imports
from qiskit_ibm_runtime import SamplerV2 as Sampler, QiskitRuntimeService
import qiskit

load_dotenv()

print("Python:", sys.version.split()[0])
print("qiskit:", qiskit.__version__)


def run_circuit_and_get_counts(circuit, backend, shots=1):
    """
    Runs a quantum circuit on a specified backend and returns the measurement counts.

    Args:
        circuit (QuantumCircuit): The quantum circuit to run.
        backend: The Qiskit backend (real device or simulator).
        shots (int): The number of shots to run the circuit.

    Returns:
        dict: A dictionary of measurement counts.
    """
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
    isa_circuit = pm.run(circuit)

    sampler = Sampler(mode=backend)

    job = sampler.run([isa_circuit], shots=shots)
    result = job.result()

    return result[0].data.meas.get_counts()


def main():
    # --- Build the Bell circuit (phi-plus) ---
    bell = QuantumCircuit(1)
    bell.h(0)
    bell.measure_all()  # creates a classical register named "meas"

    # Initialize IBM Runtime service (use saved credentials or save an account first)
    # If a specific channel fails, prefer the default initialization below.
    QiskitRuntimeService.save_account(
        channel="ibm_quantum_platform",
        token=os.environ["IBM_QUANTUM_TOKEN"],
        overwrite=True,
        set_as_default=True,
    )

    service = QiskitRuntimeService()

    # Use the least busy backend, or uncomment the loading of a specific backend like "ibm_fez".
    backend = service.least_busy(operational=True, simulator=False, min_num_qubits=127)
    # backend = service.backend("ibm_fez")
    print(backend.name)

    # Run the circuit and get counts
    counts = run_circuit_and_get_counts(bell, backend, shots=1)

    # declare counts as a dict (ex:{'1': 1} )

    counts = dict(counts)

    # print the value of the first key in the counts dict
    print(list(counts.keys())[0])

    return list(counts.keys())[0]
