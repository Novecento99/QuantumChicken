import os
import threading
import uuid
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

load_dotenv()

app = Flask(__name__)

jobs = {}


def ts():
    return datetime.now().strftime("%H:%M:%S")


def log(job_id, msg, kind="info"):
    jobs[job_id]["logs"].append({"time": ts(), "msg": msg, "kind": kind})


def run_qubit(job_id):
    try:
        from qiskit import QuantumCircuit
        from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
        from qiskit_ibm_runtime import SamplerV2 as Sampler, QiskitRuntimeService

        log(job_id, "Saving IBM Quantum account credentials…")
        QiskitRuntimeService.save_account(
            channel="ibm_quantum_platform",
            token=os.environ["IBM_QUANTUM_TOKEN"],
            overwrite=True,
            set_as_default=True,
        )

        log(job_id, "Connecting to IBM Runtime Service…")
        service = QiskitRuntimeService()
        log(job_id, "Connected.", "success")

        log(job_id, "Searching for the least-busy real backend (≥127 qubits)…")
        backend = service.least_busy(
            operational=True, simulator=False, min_num_qubits=127
        )
        log(job_id, f"Backend selected: {backend.name}", "success")

        log(job_id, "Building single-qubit Hadamard circuit…")
        circuit = QuantumCircuit(1)
        circuit.h(0)
        circuit.measure_all()
        log(job_id, "Circuit ready.")

        log(job_id, "Transpiling circuit for the target backend…")
        pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
        isa_circuit = pm.run(circuit)
        log(job_id, "Transpilation complete.", "success")

        log(job_id, "Submitting job to the quantum device…")
        sampler = Sampler(mode=backend)
        job = sampler.run([isa_circuit], shots=1)
        log(job_id, f"Job submitted (ID: {job.job_id()}). Waiting in queue…")

        result = job.result()
        counts = dict(result[0].data.meas.get_counts())
        value = list(counts.keys())[0]

        log(job_id, f"Result received: {value}", "success")
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
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "logs": [], "result": None}
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
