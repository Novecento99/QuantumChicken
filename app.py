import os
import threading
import uuid
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

jobs = {}


def ts():
    return datetime.now().strftime("%H:%M:%S")


def log(job_id, msg, kind="info", step=None):
    entry = {"time": ts(), "msg": msg, "kind": kind}
    if step is not None:
        entry["step"] = step
    jobs[job_id]["logs"].append(entry)


def run_qubit(job_id):
    try:
        from qiskit import QuantumCircuit
        from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
        from qiskit_ibm_runtime import SamplerV2 as Sampler, QiskitRuntimeService

        # Step 1 — connect
        log(job_id, "Logging into IBM Quantum…", step=1)
        QiskitRuntimeService.save_account(
            channel="ibm_quantum_platform",
            token=os.environ["IBM_QUANTUM_TOKEN"],
            overwrite=True,
            set_as_default=True,
        )
        service = QiskitRuntimeService()
        log(job_id, "Connected to IBM Quantum.", "success", step=1)

        # Step 2 — find a chip
        log(job_id, "Looking for the least busy real quantum processor…", step=2)
        backend = service.least_busy(operational=True, simulator=False, min_num_qubits=1)
        pending = backend.status().pending_jobs
        log(job_id, f"Found '{backend.name}' — {pending} jobs currently in queue.", "success", step=2)

        # Step 3 — build the circuit
        log(job_id, "Applying a Hadamard gate to place the qubit in superposition: |ψ⟩ = 1/√2 (|0⟩ + |1⟩)", step=3)
        circuit = QuantumCircuit(1)
        circuit.h(0)
        circuit.measure_all()
        log(job_id, "The qubit is now both 0 and 1 at the same time.", step=3)
        log(job_id, "Transpiling circuit to the chip's native gate set…", step=3)
        pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
        isa_circuit = pm.run(circuit)
        log(job_id, "Circuit ready.", "success", step=3)

        # Step 4 — run on hardware
        log(job_id, f"Sending job to '{backend.name}'…", step=4)
        sampler = Sampler(mode=backend)
        job = sampler.run([isa_circuit], shots=1)
        log(job_id, f"Queued. Job ID: {job.job_id()} — waiting for our turn on the chip…", step=4)

        # Step 5 — read result
        result = job.result()
        counts = dict(result[0].data.meas.get_counts())
        value = list(counts.keys())[0]

        log(job_id, f"Measurement result: {value}. Superposition collapsed. The universe has branched.", "success", step=5)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["result"] = value

    except Exception as e:
        log(job_id, str(e), "error")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["result"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    data = request.get_json(silent=True) or {}
    option_a = (data.get("a") or "A").strip() or "A"
    option_b = (data.get("b") or "B").strip() or "B"
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "running",
        "logs": [],
        "result": None,
        "option_a": option_a,
        "option_b": option_b,
    }
    thread = threading.Thread(target=run_qubit, args=(job_id,), daemon=True)
    thread.start()
    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "not_found"}), 404
    return jsonify(job)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
