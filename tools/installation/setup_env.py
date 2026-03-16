import subprocess
import sys
import importlib.util


def check_and_install_python_packages():
    """
    Checks for required Python packages and installs them if missing.
    Follows PEP 8 conventions.
    """
    dependencies = {
        "pandas": "pandas",
        "matlabengine": "matlab.engine"
    }

    print("--- Checking Python Dependencies ---")

    for package, module_name in dependencies.items():
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            print(f"Package '{package}' not found. Installing...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", package]
                )
                print(f"Successfully installed '{package}'.")
            except subprocess.CalledProcessError as e:
                print(f"Error occurred while installing '{package}': {e}")
        else:
            print(f"{package} is already installed.")


def check_and_install_matlab_addons():
    """
    Connects to MATLAB to verify and install toolboxes and support packages.
    Handles MinGW-w64 as a special Support Package case.
    """
    required_toolboxes = [
        "Statistics and Machine Learning Toolbox",
        "Optimization Toolbox",
        "Signal Processing Toolbox",
        "Communications Toolbox"
    ]

    print("\n--- Checking MATLAB Add-ons ---")
    
    try:
        import matlab.engine
        print("Starting MATLAB engine...")
        eng = matlab.engine.start_matlab()

        # Fetch names using a cell array to avoid scalar struct errors
        print("Fetching installed products...")
        installed_names = eng.eval("{ver().Name}", nargout=1)

        # 1. Handle Standard Toolboxes
        for addon in required_toolboxes:
            if any(addon in name for name in installed_names):
                print(f"Add-on '{addon}' is already installed.")
            else:
                print(f"Add-on '{addon}' is missing. Attempting installation...")
                try:
                    eng.eval(f"matlab.addons.install('{addon}')", nargout=0)
                    print(f"Successfully installed '{addon}'.")
                except Exception as e:
                    print(f"Could not install '{addon}' automatically: {e}")

        # 2. Special Case: MinGW-w64 (Support Package)
        # Check if a C++ compiler is already configured
        print("Checking for MinGW-w64 compiler configuration...")
        try:
            compiler_info = eng.mex.getCompilerConfigurations('C++', 'Selected')
            if compiler_info:
                print("MinGW-w64 is already installed and configured.")
            else:
                raise ValueError("No compiler configured")
        except:
            print("MinGW-w64 is missing or not configured. Attempting to open explorer...")
            print("Note: Automated installation for Support Packages may require manual UI steps.")
            # Opening the support package installer specifically for MinGW
            eng.eval("supportPackageInstaller", nargout=0)
            print("Please follow the prompts in the MATLAB window to complete MinGW installation.")

        # Final setup for MEX
        try:
            eng.eval("mex -setup C++", nargout=0)
        except:
            pass

        eng.quit()
        print("MATLAB engine closed.")

    except ImportError:
        print("Error: 'matlabengine' module not detected.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    check_and_install_python_packages()
    check_and_install_matlab_addons()