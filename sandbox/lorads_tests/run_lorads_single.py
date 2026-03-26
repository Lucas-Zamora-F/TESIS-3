import subprocess
from pathlib import Path


def windows_path_to_wsl(path: Path) -> str:
    path = path.resolve()
    drive = path.drive[0].lower()
    tail = str(path).replace("\\", "/")[2:]
    return f"/mnt/{drive}{tail}"


def main():
    # ===============================
    # PATHS
    # ===============================
    instance_win = Path("data/instances/sdplib/arch0.dat-s")
    instance_wsl = windows_path_to_wsl(instance_win)

    lorads_exec = "/home/lucas_zamora/lorads_build/lorads_src/build/LoRADS_v_2_0_1-alpha"

    # ===============================
    # CONFIGURACIÓN
    # ===============================
    config = {
        "timesLogRank": 1.5,
        "initRho": 1e-3,
        "rhoFreq": 10,
        "rhoFactor": 1.05,
        "ALMRhoFactor": 1.05,
        "maxALMIter": 2000,
        "maxADMMIter": 0,
        "timeSecLimit": 180,
        "endALMSubTol": 1e-3,
        "highAccMode": 1,
        # opcionales si quieres:
        #"phase1Tol": 1e-2,
        #"phase2Tol": 1e-5,
        #"l2Rescaling": 1,
        #"reoptLevel": 1,
        #"dyrankLevel": 2,
    }

    # ===============================
    # COMANDO
    # ===============================
    cmd = ["wsl", lorads_exec, instance_wsl]

    for key, value in config.items():
        cmd.append(f"--{key}")
        cmd.append(str(value))

    print("Running command:")
    print(" ".join(cmd))
    print("=" * 60)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")

    process.wait()

    print("\n" + "=" * 60)
    print("Finished with code:", process.returncode)


if __name__ == "__main__":
    main()